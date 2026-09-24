import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sqlite3
import json
from pathlib import Path
sys.path.insert(0, r"C:\Trading\Alpha")
from tradingagents.pattern_memory_engine import PatternMemoryEngine

engine = PatternMemoryEngine()

print("=== TESTING SEARCH_FACTS WITH COMMON CIO QUERIES ===")

test_queries = [
    ["BSL_SWEEP", "4TF_BEARISH"],
    ["POC_ABSORPTION"],
    ["PRE_NEWS_DRIFT"],
    ["ASIAN_RANGE_SWEEP", "CVD_DIVERGENCE"],
    ["ORDER_BLOCK", "FVG"],
    ["TURTLE_SOUP"],
    ["DEAD_TAPE", "LOW_VELOCITY"],
    ["NON_EXISTENT_TAG_XYZ_123"],
    [],
    None
]

for q in test_queries:
    print(f"\n--- QUERY: {q} ---")
    try:
        res = engine.search_facts(patterns=q, symbol="XAUUSD")
        print(f"Length: {len(res)} chars | Token approx: {len(res.split())} words")
        print(res)
    except Exception as e:
        print(f"ERROR: {e}")
