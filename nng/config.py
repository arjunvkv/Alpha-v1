# nng/config.py - Configuration for Node Network Globe (NNG 2.0)
import os

NNG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(NNG_DIR), 'logs')
GRAPH_PERSISTENCE_PATH = os.path.join(DATA_DIR, 'nng_knowledge_globe.json')

# Thresholds for Condition Classification
THRESHOLDS = {
    'VELOCITY_BURST_TPM': 120.0,
    'VELOCITY_QUIET_TPM': 40.0,
    'CVD_ABSORPTION_DELTA': -300.0,
    'RSI_OVERSOLD': 30.0,
    'RSI_OVERBOUGHT': 70.0,
    'FVG_FRESH_MAX_FILL': 30.0,
    'FVG_EXHAUSTED_FILL': 60.0,
    'COT_EXTREME_PERCENTILE': 90.0,
    'REAL_YIELD_HAWKISH': 2.0,
    'MIN_ASYMMETRIC_RR': 2.5
}
