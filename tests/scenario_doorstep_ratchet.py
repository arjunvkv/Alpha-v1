import pytest
import sys, os

sys.path.insert(0, r"C:\Trading\Alpha")
from tests.battle_doorstep_ratchet import calculate_ratchet_ladder

def simulate_trade_progression(entry_p, tp_p, sl_p, pos_type, ticks, duration_s=60.0):
    """Simulates the 500ms loop logic over a series of price ticks."""
    res = calculate_ratchet_ladder(open_p=entry_p, tp_p=tp_p, pos_type=pos_type)
    
    qual = {"highest_fav": 0.0, "stage": 0}
    current_sl = sl_p
    exit_p = None
    exit_reason = None
    
    s1_trig, s1_lock, s1_sl = res["s1_trig"], res["s1_lock"], res["s1_sl"]
    s2_trig, s2_lock, s2_sl = res["s2_trig"], res["s2_lock"], res["s2_sl"]
    s3_trig, s3_lock, s3_sl = res["s3_trig"], res["s3_lock"], res["s3_sl"]
    
    for tick_price in ticks:
        fav_pts = (tick_price - entry_p) if pos_type == 0 else (entry_p - tick_price)
        if fav_pts > qual["highest_fav"]:
            qual["highest_fav"] = fav_pts
            
        if qual["highest_fav"] >= s3_trig:
            qual["stage"] = max(qual["stage"], 3)
        elif qual["highest_fav"] >= s2_trig:
            qual["stage"] = max(qual["stage"], 2)
        elif qual["highest_fav"] >= s1_trig:
            qual["stage"] = max(qual["stage"], 1)
            
        q_stage = qual["stage"]
        
        # FundedNext 32s rule check
        if duration_s < 32.0:
            continue
            
        # Pullback cut check
        if q_stage == 3 and fav_pts < s3_lock:
            exit_p = tick_price
            exit_reason = "Stage 3 Pullback Cut"
            break
        elif q_stage == 2 and fav_pts < s2_lock:
            exit_p = tick_price
            exit_reason = "Stage 2 Pullback Cut"
            break
        elif q_stage == 1 and fav_pts < s1_lock:
            exit_p = tick_price
            exit_reason = "BE Pullback Cut"
            break
            
        # SL update
        if q_stage == 3:
            current_sl = s3_sl
        elif q_stage == 2:
            current_sl = s2_sl
        elif q_stage == 1:
            current_sl = s1_sl
            
        # Check standard SL or TP hit
        if pos_type == 0:  # BUY
            if tick_price <= current_sl:
                exit_p = current_sl
                exit_reason = f"SL Hit ({current_sl})"
                break
            elif tick_price >= tp_p and tp_p > 0:
                exit_p = tp_p
                exit_reason = "TP Hit"
                break
        else:  # SELL
            if tick_price >= current_sl:
                exit_p = current_sl
                exit_reason = f"SL Hit ({current_sl})"
                break
            elif tick_price <= tp_p and tp_p > 0:
                exit_p = tp_p
                exit_reason = "TP Hit"
                break
                
    return {
        "final_stage": qual["stage"],
        "highest_fav": qual["highest_fav"],
        "current_sl": current_sl,
        "exit_p": exit_p,
        "exit_reason": exit_reason,
        "pts": ((exit_p - entry_p) if pos_type == 0 else (entry_p - exit_p)) if exit_p else 0.0
    }

def test_scenario_1_today_trade_doorstep_bounce():
    """Scenario 1: Ticket #551474745 replay.
    Sell @ 4160.25, SL 4166.50, TP 4150.00.
    Drops to 4150.95 (+9.3 pts), bounces to 4156.85.
    Under new logic, Stage 3 locks +7.18 pts (SL 4153.07).
    """
    ticks = [
        4160.25, 4158.00, 4155.00, 4153.00, 4150.95,  # flush
        4152.00, 4153.00, 4153.08                     # bounce back to Stage 3 SL
    ]
    sim = simulate_trade_progression(entry_p=4160.25, tp_p=4150.00, sl_p=4166.50, pos_type=1, ticks=ticks, duration_s=120.0)
    
    assert sim["final_stage"] == 3
    assert round(sim["highest_fav"], 2) == 9.30
    # Must exit on pullback cut or SL hit at ~4153 (locking 7+ pts) instead of collapsing to 4156.75!
    assert sim["pts"] >= 7.00
    assert "Stage 3" in sim["exit_reason"] or "SL Hit" in sim["exit_reason"]

def test_scenario_2_highway_runner_with_healthy_retest():
    """Scenario 2: Wide 25-pt TP runner.
    Long @ 4280.00, SL 4272.00, TP 4305.00.
    Advances to 4292.00 (+12 pts), pulls back to 4287.00 (+7 pts), then reaches 4305.00.
    Must NOT be choked on the +7 pt retest!
    """
    ticks = [
        4280.00, 4283.00, 4286.00, 4290.00, 4292.00,  # +12 pts advance
        4290.00, 4288.00, 4287.00,                    # retest to +7 pts (above BE +0.5!)
        4293.00, 4298.00, 4302.00, 4305.00            # continuation to TP
    ]
    sim = simulate_trade_progression(entry_p=4280.00, tp_p=4305.00, sl_p=4272.00, pos_type=0, ticks=ticks, duration_s=300.0)
    
    # Position survives the retest and reaches full TP!
    assert sim["exit_reason"] == "TP Hit"
    assert sim["pts"] == 25.00

def test_scenario_3_trapped_retest_expansion():
    """Scenario 3: 18-pt TP trade.
    Short @ 4265.00, SL 4273.00, TP 4247.00.
    Advances to 4258.80 (+6.2 pts), then completely V-reverses to 4274.00.
    Must be saved at BE (+0.50 pts) and NOT take full loss!
    """
    ticks = [
        4265.00, 4262.00, 4260.00, 4258.80,  # +6.2 pts peak
        4261.00, 4264.00, 4265.00, 4268.00, 4273.00  # V-reversal
    ]
    sim = simulate_trade_progression(entry_p=4265.00, tp_p=4247.00, sl_p=4273.00, pos_type=1, ticks=ticks, duration_s=180.0)
    
    assert sim["final_stage"] == 1
    assert sim["pts"] >= 0.0  # Saved at Breakeven!
    assert "BE Pullback Cut" in sim["exit_reason"] or "SL Hit" in sim["exit_reason"]

def test_scenario_4_fundednext_32s_shield():
    """Scenario 4: Fast expansion to +9.0 pts in 10 seconds.
    Under 32s, SL modification into profit is delayed to prevent Quick Strike breach.
    """
    ticks = [4160.00, 4155.00, 4151.00]
    # Under 32s duration
    sim_early = simulate_trade_progression(entry_p=4160.00, tp_p=4150.00, sl_p=4166.50, pos_type=1, ticks=ticks, duration_s=15.0)
    assert sim_early["current_sl"] == 4166.50  # Original SL preserved until 32s!

    # At 35s duration
    sim_post = simulate_trade_progression(entry_p=4160.00, tp_p=4150.00, sl_p=4166.50, pos_type=1, ticks=ticks, duration_s=35.0)
    assert sim_post["current_sl"] < 4160.00  # SL ratcheted into profit!
