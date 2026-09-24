import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import sqlite3
import json
from pathlib import Path

conn = sqlite3.connect(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
cur = conn.cursor()

print("=== CHECKING PATTERN_NODES INTEGRITY ===")
cur.execute("SELECT COUNT(*) FROM pattern_nodes WHERE pattern_id IS NULL OR pattern_id = ''")
print("Null/empty pattern_ids:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM pattern_nodes WHERE occurrence_count < 0")
print("Negative occurrence_count:", cur.fetchone()[0])

print("\n=== CHECKING PATTERN_WALKS INTEGRITY ===")
cur.execute("SELECT COUNT(*) FROM pattern_walks WHERE canonical_key IS NULL OR canonical_key = ''")
print("Null/empty canonical_key:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM pattern_walks WHERE outcome NOT IN ('WIN', 'TRAP', 'STUDY')")
print("Invalid outcomes:", cur.fetchone()[0])
cur.execute("SELECT outcome, COUNT(*) FROM pattern_walks GROUP BY outcome")
print("Outcomes distribution:", cur.fetchall())
cur.execute("SELECT COUNT(*) FROM pattern_walks WHERE synaptic_weight <= 0")
print("Zero or negative synaptic weight:", cur.fetchone()[0])

# Check for JSON syntax errors in patterns_json
cur.execute("SELECT walk_id, patterns_json FROM pattern_walks")
bad_json = 0
for r in cur.fetchall():
    try:
        p = json.loads(r[1])
        if not isinstance(p, list):
            bad_json += 1
    except:
        bad_json += 1
print("Bad patterns_json count in pattern_walks:", bad_json)

print("\n=== CHECKING EPISODE_EVENTS INTEGRITY ===")
cur.execute("SELECT COUNT(*) FROM episode_events WHERE walk_id IS NULL")
print("Null walk_id in episode_events:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM episode_events WHERE outcome NOT IN ('WIN', 'TRAP', 'STUDY')")
print("Invalid outcomes in episode_events:", cur.fetchone()[0])

print("\n=== CHECKING OBSERVATION_USAGE_AUDIT INTEGRITY ===")
cur.execute("SELECT COUNT(*) FROM observation_usage_audit WHERE walk_id IS NULL")
print("Null walk_id in observation_usage_audit:", cur.fetchone()[0])
cur.execute("SELECT retrieval_type, COUNT(*) FROM observation_usage_audit GROUP BY retrieval_type")
print("Retrieval types in audit:", cur.fetchall())

print("\n=== CHECKING INSTITUTIONAL_PLAYBOOK TABLE ===")
cur.execute("SELECT COUNT(*) FROM institutional_playbook")
print("Institutional concepts count:", cur.fetchone()[0])
cur.execute("SELECT concept_id, category, title, substr(core_law, 1, 60) FROM institutional_playbook LIMIT 5")
for r in cur.fetchall():
    print(r)

print("\n=== CHECKING RECALL COUNTS & LAST RECALLED ===")
cur.execute("SELECT COUNT(*) FROM pattern_walks WHERE recall_count > 0")
print("Walks with recall_count > 0:", cur.fetchone()[0])
cur.execute("SELECT canonical_key, outcome, occurrence_count, recall_count, last_recalled_at FROM pattern_walks WHERE recall_count > 0 ORDER BY recall_count DESC LIMIT 5")
for r in cur.fetchall():
    print(r)

conn.close()
