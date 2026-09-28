import pytest
import sys, os

sys.path.insert(0, r"C:\Trading\Alpha")

def calculate_ratchet_ladder(open_p: float, tp_p: float, pos_type: int):
    """Replicates the production ratchet ladder logic from alpha_trading_desk.py."""
    delta_tp = abs(tp_p - open_p) if tp_p > 0.0 else 0.0
    s1_trig = 5.20
    s1_lock = 0.50

    if delta_tp >= 6.0:
        s2_trig = min(11.00, max(8.00, round(0.55 * delta_tp, 2)))
        s2_lock = min(4.00, max(3.50, round(0.25 * delta_tp, 2)))
        s3_trig = max(s2_trig + 0.75, min(14.00, round(delta_tp - 1.50, 2)))
        s3_lock = max(7.00, round(0.70 * delta_tp, 2))
    else:
        s2_trig = 8.50
        s2_lock = 3.50
        s3_trig = 14.00
        s3_lock = 8.00
        
    # Calculate SL levels
    if pos_type == 0:  # BUY
        s1_sl = round(open_p + s1_lock, 2)
        s2_sl = round(open_p + s2_lock, 2)
        s3_sl = round(open_p + s3_lock, 2)
    else:  # SELL
        s1_sl = round(open_p - s1_lock, 2)
        s2_sl = round(open_p - s2_lock, 2)
        s3_sl = round(open_p - s3_lock, 2)

    return {
        "delta_tp": delta_tp,
        "s1_trig": s1_trig, "s1_lock": s1_lock, "s1_sl": s1_sl,
        "s2_trig": s2_trig, "s2_lock": s2_lock, "s2_sl": s2_sl,
        "s3_trig": s3_trig, "s3_lock": s3_lock, "s3_sl": s3_sl,
    }

def test_today_trade_exact_coordinates():
    """Verify today's trade (Ticket #551474745) triggers Doorstep Harvest properly."""
    res = calculate_ratchet_ladder(open_p=4160.25, tp_p=4150.00, pos_type=1)
    
    assert res["delta_tp"] == 10.25
    assert res["s1_trig"] == 5.20
    assert res["s1_lock"] == 0.50
    assert res["s1_sl"] == 4159.75
    
    # Stage 2
    assert res["s2_trig"] == 8.00  # max(8.0, 0.55 * 10.25 = 5.64) -> 8.00
    assert res["s2_lock"] == 3.50  # min(4.0, max(3.5, 0.25 * 10.25 = 2.56)) -> 3.50
    assert res["s2_sl"] == 4156.75
    
    # Stage 3 (Doorstep Harvest)
    assert res["s3_trig"] == 8.75  # max(8.00 + 0.75, min(14.0, 10.25 - 1.5 = 8.75)) -> 8.75
    assert res["s3_lock"] == 7.17  # max(7.0, round(0.70 * 10.25, 2) = 7.17)
    assert res["s3_sl"] == 4153.08
    
    # Today's peak was 9.30 pts -> must qualify Stage 3!
    peak_fav = 9.30
    assert peak_fav >= res["s3_trig"]

def test_ladder_strict_monotonicity():
    """Verify s1 < s2 < s3 triggers and locks across wide spectrum of targets."""
    for dtp in [6.0, 7.5, 9.0, 10.0, 12.5, 15.0, 18.0, 20.0, 25.0, 30.0, 40.0]:
        res_buy = calculate_ratchet_ladder(open_p=4000.0, tp_p=4000.0 + dtp, pos_type=0)
        assert res_buy["s1_trig"] < res_buy["s2_trig"] < res_buy["s3_trig"], f"Trigger order violated for dTP={dtp}"
        assert res_buy["s1_lock"] < res_buy["s2_lock"] < res_buy["s3_lock"], f"Lock order violated for dTP={dtp}"
        assert res_buy["s1_sl"] < res_buy["s2_sl"] < res_buy["s3_sl"], f"SL order BUY violated for dTP={dtp}"

        res_sell = calculate_ratchet_ladder(open_p=4000.0, tp_p=4000.0 - dtp, pos_type=1)
        assert res_sell["s1_sl"] > res_sell["s2_sl"] > res_sell["s3_sl"], f"SL order SELL violated for dTP={dtp}"

def test_stage1_capital_armor_invariance():
    """Verify Stage 1 is STRICTLY fixed at 5.2 pts and 0.50 lock regardless of TP distance."""
    for dtp in [6.0, 10.0, 20.0, 50.0, 100.0]:
        res = calculate_ratchet_ladder(open_p=4200.0, tp_p=4200.0 + dtp, pos_type=0)
        assert res["s1_trig"] == 5.20
        assert res["s1_lock"] == 0.50

def test_fallback_on_zero_or_tiny_tp():
    """Verify clean fixed fallback when TP is unset (0.0) or tiny (<6.0)."""
    res_zero = calculate_ratchet_ladder(open_p=4200.0, tp_p=0.0, pos_type=0)
    assert res_zero["s1_trig"] == 5.20
    assert res_zero["s2_trig"] == 8.50
    assert res_zero["s3_trig"] == 14.00
    assert res_zero["s3_lock"] == 8.00

    res_tiny = calculate_ratchet_ladder(open_p=4200.0, tp_p=4204.0, pos_type=0)
    assert res_tiny["s2_trig"] == 8.50
    assert res_tiny["s3_trig"] == 14.00
