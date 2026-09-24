import sqlite3
import json
from pathlib import Path

db_path = Path(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in DB:", tables)

for t in tables:
    count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Table {t}: {count} rows")

print("\n--- OUTCOMES IN PATTERN_WALKS ---")
for r in cur.execute("SELECT outcome, COUNT(*), SUM(occurrence_count) FROM pattern_walks GROUP BY outcome").fetchall():
    print(r)

print("\n--- SOURCES IN PATTERN_WALKS ---")
for r in cur.execute("SELECT source, COUNT(*) FROM pattern_walks GROUP BY source").fetchall():
    print(r)

print("\n--- TOP 10 WALKS BY SYNAPTIC WEIGHT ---")
for r in cur.execute("SELECT walk_id, canonical_key, outcome, occurrence_count, synaptic_weight, source, substr(lesson, 1, 80) FROM pattern_walks ORDER BY synaptic_weight DESC LIMIT 10").fetchall():
    print(r)

print("\n--- RECENT LIVE OBSERVATIONS IN EPISODE_EVENTS (LAST 5) ---")
for r in cur.execute("SELECT event_id, symbol, outcome, source, created_at, substr(lesson, 1, 80) FROM episode_events ORDER BY event_id DESC LIMIT 5").fetchall():
    print(r)

print("\n--- RECENT AUDIT LOGS IN OBSERVATION_USAGE_AUDIT (LAST 5) ---")
for r in cur.execute("SELECT audit_id, walk_id, canonical_key, outcome, retrieval_type, recalled_at FROM observation_usage_audit ORDER BY audit_id DESC LIMIT 5").fetchall():
    print(r)

conn.close()
