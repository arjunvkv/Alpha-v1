import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sid = "ses_f37b19167ffeKlQQE5p2pM0Vns"
url = f"http://127.0.0.1:4096/session/{sid}/message"

try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        messages = json.loads(resp.read().decode("utf-8"))
    
    for i, m in enumerate(messages):
        info = m.get("info", {})
        print(f"\n--- MESSAGE {i} [{info.get('role')}] ---")
        for p in m.get("parts", []):
            ptype = p.get("type")
            if ptype == "text":
                print(f"[TEXT]:\n{p.get('text')}\n")
            elif ptype == "reasoning":
                print(f"[REASONING]: {p.get('text')[:300]}...\n")
            elif ptype == "tool":
                print(f"[TOOL]: {p.get('tool')}")
except Exception as e:
    print(f"Error: {e}")
