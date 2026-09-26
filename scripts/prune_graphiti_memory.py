"""
Database Pruning and Consolidation Script for Graphiti Temporal Pattern Memory.
Safely removes orphaned ephemeral one-off study walks while preserving:
- All WIN walks (historic + canonical)
- All TRAP walks (documented pitfalls)
- All INSTITUTIONAL_CANON literature walks
- All reinforced walks (occurrence_count > 1)
"""

import sqlite3
import re
import json
from pathlib import Path

DB_PATH = Path(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")

NOISE_PATTERNS = [
    r"TURN_[AB]", r"\d{1,2}_\d{2}_UTC", r"MONDAY", r"TUESDAY", r"WEDNESDAY", r"THURSDAY", r"FRIDAY",
    r"VENDOR_ARTEFACT", r"TAG_CLASSIFIER", r"POST_WINDOW", r"GATE_CLOSED", r"SCHEDULED_REASSESSMENT",
    r"SUBPOINT_DISPLACEMENT", r"POST_CLOSE_GRIND"
]

def prune_database():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Pre-stats
    total_before = cur.execute("SELECT count(*) FROM pattern_walks").fetchone()[0]
    print(f"Total pattern_walks before pruning: {total_before}")

    # Identify noise one-off study walks
    rows = cur.execute("""
        SELECT walk_id, canonical_key, outcome, occurrence_count, lesson, source 
        FROM pattern_walks 
        WHERE outcome = 'STUDY' AND occurrence_count = 1 AND (source IS NULL OR source != 'INSTITUTIONAL_CANON')
    """).fetchall()

    delete_ids = []
    for r in rows:
        walk_id, key, outcome, count, lesson, source = r
        is_noise = False
        # Check if key contains noise patterns or has > 5 tags
        for np in NOISE_PATTERNS:
            if re.search(np, key, re.IGNORECASE):
                is_noise = True
                break
        if key.count(" + ") >= 5:
            is_noise = True
        if "Turn " in (lesson or "") or "UTC" in (lesson or ""):
            is_noise = True
            
        if is_noise:
            delete_ids.append(walk_id)

    print(f"Identified {len(delete_ids)} noise one-off study walks to prune.")

    # Execute deletion in batches
    batch_size = 500
    for i in range(0, len(delete_ids), batch_size):
        batch = delete_ids[i:i+batch_size]
        q_marks = ",".join("?" for _ in batch)
        cur.execute(f"DELETE FROM pattern_walks WHERE walk_id IN ({q_marks})", batch)
        cur.execute(f"DELETE FROM episode_events WHERE walk_id IN ({q_marks})", batch)
        cur.execute(f"DELETE FROM observation_usage_audit WHERE walk_id IN ({q_marks})", batch)

    conn.commit()

    # Prune unreferenced pattern_nodes
    cur.execute("""
        DELETE FROM pattern_nodes 
        WHERE pattern_id NOT IN (
            SELECT DISTINCT canonical_name FROM (
                SELECT canonical_key FROM pattern_walks
            )
        ) AND occurrence_count <= 1
    """)
    conn.commit()

    # Post-stats
    total_after = cur.execute("SELECT count(*) FROM pattern_walks").fetchone()[0]
    nodes_after = cur.execute("SELECT count(*) FROM pattern_nodes").fetchone()[0]
    print(f"Total pattern_walks after pruning: {total_after} (Pruned {total_before - total_after} walks)")
    print(f"Total pattern_nodes after pruning: {nodes_after}")

    # Vacuum database to reclaim space
    conn.execute("VACUUM")
    conn.close()
    print("Database vacuumed and optimized cleanly.")

if __name__ == "__main__":
    prune_database()
