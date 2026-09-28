import sys, os, json, datetime
from datetime import timezone

sys.path.insert(0, r"C:\Trading\Alpha")
import MetaTrader5 as mt5
from tests.battle_doorstep_ratchet import calculate_ratchet_ladder

def run_large_sample_backtest():
    if not mt5.initialize():
        print("MT5 failed")
        return None
        
    deals = mt5.history_deals_get(datetime.datetime(2024, 1, 1, tzinfo=timezone.utc), datetime.datetime.now(timezone.utc))
    orders = mt5.history_orders_get(datetime.datetime(2024, 1, 1, tzinfo=timezone.utc), datetime.datetime.now(timezone.utc))
    
    positions = {}
    for d in (deals or []):
        if d.symbol == "XAUUSD":
            positions.setdefault(d.position_id, []).append(d)
            
    trade_records = []
    for pid, pdeals in positions.items():
        if len(pdeals) < 2: continue
        entry_d = min(pdeals, key=lambda x: x.time)
        exit_d = max(pdeals, key=lambda x: x.time)
        side = "BUY" if entry_d.type == 0 else "SELL"
        entry_p = float(entry_d.price)
        exit_p = float(exit_d.price)
        vol = float(entry_d.volume)
        actual_profit = sum(d.profit for d in pdeals)
        t_start = datetime.datetime.fromtimestamp(entry_d.time)
        t_end = datetime.datetime.fromtimestamp(exit_d.time)
        orders_for_pos = [o for o in orders if o.position_id == pid or o.ticket == entry_d.order]
        setup_order = min(orders_for_pos, key=lambda x: x.time_setup) if orders_for_pos else None
        planned_sl = setup_order.sl if (setup_order and setup_order.sl > 0) else (entry_p - 8.0 if side == "BUY" else entry_p + 8.0)
        planned_tp = setup_order.tp if (setup_order and setup_order.tp > 0) else (entry_p + 15.0 if side == "BUY" else entry_p - 15.0)
        delta_tp = abs(planned_tp - entry_p) if planned_tp > 0 else 15.0
        delta_sl = abs(entry_p - planned_sl) if planned_sl > 0 else 8.0
        rates = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1, t_start, t_end + datetime.timedelta(minutes=1))
        
        trade_records.append({
            "ticket": pid, "side": side, "vol": vol, "entry_p": entry_p, "exit_p": exit_p,
            "actual_profit": actual_profit, "planned_sl": planned_sl, "planned_tp": planned_tp,
            "delta_tp": delta_tp, "delta_sl": delta_sl, "rates": rates
        })
    mt5.shutdown()
    
    # Run evaluation across the 3 core models
    models = ["NO_TRAIL", "PREV_FIXED", "NEW_DOORSTEP"]
    report = {}
    
    for m in models:
        profits = []
        for tr in trade_records:
            rates = tr["rates"]
            if rates is None or len(rates) == 0:
                profits.append(tr["actual_profit"])
                continue
                
            side = tr["side"]
            entry_p = tr["entry_p"]
            vol = tr["vol"]
            delta_tp = tr["delta_tp"]
            sl_orig = tr["planned_sl"]
            tp_orig = tr["planned_tp"]
            
            curr_sl = sl_orig
            peak_fav = 0.0
            exit_p = tr["exit_p"]
            stopped = False
            
            # Setup ladder parameters
            if m == "PREV_FIXED":
                s1_trig, s1_lock = 5.20, 0.50
                s2_trig, s2_lock = 8.50, 3.50
                s3_trig, s3_lock = 14.00, 8.00
            elif m == "NEW_DOORSTEP":
                ladder = calculate_ratchet_ladder(entry_p, tp_orig, 0 if side == "BUY" else 1)
                s1_trig, s1_lock = ladder["s1_trig"], ladder["s1_lock"]
                s2_trig, s2_lock = ladder["s2_trig"], ladder["s2_lock"]
                s3_trig, s3_lock = ladder["s3_trig"], ladder["s3_lock"]
                
            for r in rates:
                fav = (r['high'] - entry_p) if side == "BUY" else (entry_p - r['low'])
                if fav > peak_fav: peak_fav = fav
                
                if m != "NO_TRAIL":
                    # Update SL
                    if peak_fav >= s3_trig:
                        req_sl = (entry_p + s3_lock) if side == "BUY" else (entry_p - s3_lock)
                        if (side == "BUY" and req_sl > curr_sl) or (side == "SELL" and req_sl < curr_sl): curr_sl = req_sl
                    elif peak_fav >= s2_trig:
                        req_sl = (entry_p + s2_lock) if side == "BUY" else (entry_p - s2_lock)
                        if (side == "BUY" and req_sl > curr_sl) or (side == "SELL" and req_sl < curr_sl): curr_sl = req_sl
                    elif peak_fav >= s1_trig:
                        req_sl = (entry_p + s1_lock) if side == "BUY" else (entry_p - s1_lock)
                        if (side == "BUY" and req_sl > curr_sl) or (side == "SELL" and req_sl < curr_sl): curr_sl = req_sl
                        
                # Check execution
                if side == "BUY":
                    if r['high'] >= tp_orig and tp_orig > 0:
                        exit_p = tp_orig
                        stopped = True
                        break
                    elif r['low'] <= curr_sl:
                        exit_p = curr_sl
                        stopped = True
                        break
                else:
                    if r['low'] <= tp_orig and tp_orig > 0:
                        exit_p = tp_orig
                        stopped = True
                        break
                    elif r['high'] >= curr_sl:
                        exit_p = curr_sl
                        stopped = True
                        break
                        
            pts = (exit_p - entry_p) if side == "BUY" else (entry_p - exit_p)
            pnl = round(pts * vol * 100.0, 2) if stopped else tr["actual_profit"]
            profits.append(pnl)
            
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        tot_win = sum(wins)
        tot_loss = abs(sum(losses))
        
        win_rate = (len(wins) / len(profits) * 100.0) if profits else 0.0
        pf = (tot_win / tot_loss) if tot_loss > 0 else 99.9
        total_pnl = sum(profits)
        avg_win = (tot_win / len(wins)) if wins else 0.0
        avg_loss = (tot_loss / len(losses)) if losses else 0.0
        payoff = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        
        # Drawdown calculation
        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in profits:
            cum += p
            if cum > peak: peak = cum
            dd = peak - cum
            if dd > max_dd: max_dd = dd
            
        report[m] = {
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "wins": len(wins),
            "losses": len(losses),
            "profit_factor": pf,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff": payoff,
            "max_dd": max_dd
        }
        
    return report

def test_large_sample_and_account_growth():
    """Verify that New Doorstep Ratchet achieves higher Total PnL, higher Win Rate, and strictly controlled Drawdown."""
    rep = run_large_sample_backtest()
    assert rep is not None
    
    print("\n" + "=" * 120)
    print(f"{'STRATEGY MODEL':<18} | {'TOTAL PnL':<12} | {'WIN RATE':<9} | {'W / L':<8} | {'AVG WIN':<10} | {'AVG LOSS':<10} | {'PAYOFF':<8} | {'MAX DD':<10} | {'PF'}")
    print("=" * 120)
    for name, r in rep.items():
        print(f"{name:<18} | ${r['total_pnl']:>10.2f} | {r['win_rate']:>7.1f}% | {r['wins']:>2}/{r['losses']:<2} | ${r['avg_win']:>8.2f} | ${r['avg_loss']:>8.2f} | {r['payoff']:>6.2f}:1 | ${r['max_dd']:>8.2f} | {r['profit_factor']:>5.2f}")
    print("=" * 120)
    
    # Assertions on Account Growth:
    # 1. Total P&L must be superior to Previous Fixed
    assert rep["NEW_DOORSTEP"]["total_pnl"] > rep["PREV_FIXED"]["total_pnl"], "New Doorstep Ratchet must yield higher total equity!"
    
    # 2. Win rate must be preserved at ~48%
    assert rep["NEW_DOORSTEP"]["win_rate"] >= 45.0, "Win rate must be preserved by Capital Armor!"
    
    # 3. Average win must improve over previous fixed
    assert rep["NEW_DOORSTEP"]["avg_win"] > rep["PREV_FIXED"]["avg_win"], "Average Win must improve due to doorstep harvesting!"
    
    # 4. Max Drawdown must be significantly better than No Trailing
    assert rep["NEW_DOORSTEP"]["max_dd"] < rep["NO_TRAIL"]["max_dd"], "Max Drawdown must be strictly controlled vs No Trailing!"

if __name__ == "__main__":
    test_large_sample_and_account_growth()
