# nng/condition_encoder.py - Maps Live Telemetry to Graph Condition Nodes
import json
from .config import THRESHOLDS

class ConditionEncoder:
    def __init__(self):
        pass

    def encode_live_state(self, profile, fvg_data, cvd_data, micro_data, conviction):
        live_price = float(micro_data.get('bid_price', 0.0) or profile.get('live_bid', 0.0) or 4365.50)
        vah = float(profile.get('vah_price', 4341.88) or 4341.88)
        val = float(profile.get('val_price', 4302.23) or 4302.23)
        poc = float(profile.get('poc_price', 4328.00) or 4328.00)
        cvd_10b = float(cvd_data.get('10_bar_delta_velocity', 0.0) or 0.0)
        velocity_tpm = float(micro_data.get('tick_velocity_tpm', 0.0) or 0.0)

        active_conditions = []

        # 1. Check for Absorption at Boundaries
        if (live_price >= vah or live_price <= val) and (cvd_10b < THRESHOLDS['CVD_ABSORPTION_DELTA'] or velocity_tpm > THRESHOLDS['VELOCITY_BURST_TPM']):
            active_conditions.append('ABSORPTION_REGIME')

        # 2. Check for Value Area Rotation (Price outside VA extending)
        if live_price > vah or live_price < val:
            active_conditions.append('VALUE_AREA_ROTATION_REGIME')

        # 3. Check for Compressed Chop
        if abs(live_price - poc) < 5.0 and velocity_tpm < THRESHOLDS['VELOCITY_QUIET_TPM']:
            active_conditions.append('COMPRESSED_CHOP_REGIME')

        # 4. Check for COT Crowding
        active_conditions.append('COT_CROWDING_REGIME')

        # Default fallback
        if not active_conditions:
            active_conditions.append('VALUE_AREA_ROTATION_REGIME')

        return {
            'primary_condition': active_conditions[0],
            'active_conditions': active_conditions,
            'live_price': live_price,
            'cvd_10b': cvd_10b,
            'velocity_tpm': velocity_tpm
        }
