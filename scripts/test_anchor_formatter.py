import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import sqlite3
import re

conn = sqlite3.connect(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
cur = conn.cursor()

def clean_short_citation(cit: str) -> str:
    y_m = re.search(r'\b(19\d\d|20\d\d)\b', cit)
    year = y_m.group(1) if y_m else ""
    first_part = cit.split(';')[0].split(',')[0].strip()
    first_part = re.sub(r'[\'\"\(].*?[\'\"]', '', first_part).strip(' ()')
    if year and year not in first_part:
        return f"{first_part} {year}"
    return first_part

def format_anchor(title: str, citation: str, law: str, trigger: str, max_chars: int = 340) -> str:
    short_cit = clean_short_citation(citation)
    header = f"[{title}] ({short_cit}): "
    trig_str = f" Trigger: {trigger}" if trigger else ""
    
    full_text = f"{header}{law}{trig_str}"
    full_text = " ".join(full_text.strip().split())
    if len(full_text) <= max_chars:
        return full_text
        
    room_for_law = max_chars - len(header) - len(trig_str) - 3
    if room_for_law >= 60:
        law_cut = law[:room_for_law]
        sb = [m.end() for m in re.finditer(r'(?<!\d)\.\s+', law_cut)]
        if sb and sb[-1] > 40:
            law_cut = law_cut[:sb[-1]].rstrip()
        else:
            sp = law_cut.rfind(' ')
            if sp > 40:
                law_cut = law_cut[:sp].rstrip() + "..."
            else:
                law_cut = law_cut.rstrip() + "..."
        res = f"{header}{law_cut}{trig_str}"
        return " ".join(res.strip().split())
    else:
        res = full_text[:max_chars-3]
        sp = res.rfind(' ')
        if sp > 100:
            res = res[:sp] + "..."
        return " ".join(res.strip().split())

rows = cur.execute("SELECT title, author_citation, core_law, physical_trigger FROM institutional_playbook").fetchall()
print(f"Testing all {len(rows)} concepts:")
for r in rows:
    fmt = format_anchor(r[0], r[1], r[2], r[3])
    print(f"[{len(fmt)} chars] {fmt}\n")
conn.close()
