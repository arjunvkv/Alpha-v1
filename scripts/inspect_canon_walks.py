import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import sqlite3

conn = sqlite3.connect(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
cur = conn.cursor()

cur.execute("SELECT walk_id, canonical_key, lesson FROM pattern_walks WHERE source = 'INSTITUTIONAL_CANON'")
rows = cur.fetchall()
print(f"Total institutional anchor walks: {len(rows)}")
for r in rows:
    print(f"\nID: {r[0]} | Key: {r[1]}")
    print(f"Lesson: {r[2]}")
conn.close()
