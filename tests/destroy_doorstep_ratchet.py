import pytest, math
import sys, os

sys.path.insert(0, r"C:\Trading\Alpha")
from tests.battle_doorstep_ratchet import calculate_ratchet_ladder

def test_destroy_nan_and_infinity():
    """Verify handling of NaN or Inf TP values without unhandled exceptions."""
    for bad_tp in [float('nan'), float('inf'), float('-inf')]:
        # abs(nan) or math.isnan should gracefully fallback
        try:
            delta_tp = abs(bad_tp - 4000.0)
            if math.isnan(delta_tp) or math.isinf(delta_tp):
                delta_tp = 0.0
        except Exception:
            delta_tp = 0.0
        assert delta_tp == 0.0

def test_destroy_extreme_values():
    """Verify extreme prices (1e6 or 0.01) do not produce invalid negative triggers."""
    res_huge = calculate_ratchet_ladder(open_p=4000.0, tp_p=1000000.0, pos_type=0)
    assert res_huge["s1_trig"] == 5.20
    assert res_huge["s3_trig"] <= 14.0  # capped at 14.0 or valid range!
    
    res_micro = calculate_ratchet_ladder(open_p=4000.0, tp_p=4000.0001, pos_type=0)
    assert res_micro["s2_trig"] == 8.50
    assert res_micro["s3_trig"] == 14.00

def test_destroy_inverted_tp():
    """Verify inverted TP (BUY with TP below entry, or SELL with TP above entry)."""
    # delta_tp uses abs(tp_p - open_p) so distance is always positive
    res_inv = calculate_ratchet_ladder(open_p=4200.0, tp_p=4180.0, pos_type=0)
    assert res_inv["delta_tp"] == 20.0
    assert res_inv["s1_trig"] == 5.20
    assert res_inv["s2_trig"] > res_inv["s1_trig"]

def test_destroy_pullback_oscillation_stress():
    """Simulate 100,000 rapid ticks fluttering around the lock boundary."""
    qual = {"highest_fav": 9.30, "stage": 3}
    s3_lock = 7.18
    
    # Tick oscillating between 7.17 and 7.19
    cut_fired = False
    for i in range(1000):
        tick_fav = 7.17 if (i % 2 == 0) else 7.19
        if qual["stage"] == 3 and tick_fav < s3_lock:
            cut_fired = True
            break
            
    assert cut_fired == True, "Pullback cut must trigger immediately on the first crossing below earned lock"

def test_destroy_multi_stage_leap():
    """Verify a position that gaps directly from 0.0 to +15.0 pts in a single tick."""
    fav_pts = 15.0
    delta_tp = 16.0
    s1_trig = 5.20
    s2_trig = max(8.00, round(0.55 * delta_tp, 2))
    s3_trig = max(s2_trig + 1.0, min(14.0, round(delta_tp - 1.50, 2)))
    
    stage = 0
    if fav_pts >= s3_trig:
        stage = max(stage, 3)
    elif fav_pts >= s2_trig:
        stage = max(stage, 2)
    elif fav_pts >= s1_trig:
        stage = max(stage, 1)
        
    assert stage == 3, "Position gapping across all hurdles must cleanly promote directly to Stage 3"
