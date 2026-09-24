import sys
import sqlite3
import json

conn = sqlite3.connect(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
cur = conn.cursor()

cur.execute("SELECT canonical_key, outcome, occurrence_count, lesson FROM pattern_walks WHERE outcome IN ('WIN', 'TRAP') AND (canonical_key LIKE '%ORDER_BLOCK%' OR canonical_key LIKE '%FVG%')")
rows = cur.fetchall()
print(f"Total walks with either ORDER_BLOCK or FVG: {len(rows)}")

both = [r for r in rows if 'ORDER_BLOCK' in r[0] and 'FVG' in r[0]]
print(f"Total walks with BOTH ORDER_BLOCK and FVG: {len(both)}")
for b in both:
    print(f"[{b[1]}] {b[0]} (count={b[2]}): {b[3][:80]}")

print("\n--- Breakdown of the 82 stumbles matched for ['ORDER_BLOCK', 'FVG'] ---")
cur.execute("SELECT canonical_key, outcome, occurrence_count, lesson FROM pattern_walks WHERE outcome = 'TRAP' AND (canonical_key LIKE '%ORDER_BLOCK%' OR canonical_key LIKE '%FVG%')")
traps = cur.fetchall()
print(f"Trap rows count: {len(traps)} | Sum of occurrences: {sum(t[2] for t in traps)}")
for t in traps[:10]:
    print(f"Count={t[2]}: {t[0]}")
