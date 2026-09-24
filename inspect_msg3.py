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
    
    last = messages[-1]
    print(f"Total messages: {len(messages)}, last role={last.get('info', {}).get('role')}")
    for p in last.get("parts", []):
        ptype = p.get("type")
        if ptype == "text":
            print("=== TEXT OUTPUT ===")
            print(p.get("text"))
        elif ptype == "reasoning":
            print("=== REASONING ===")
            print(p.get("text"))
        elif ptype == "tool":
            print(f"Tool call: {p.get('tool')}")
except Exception as e:
    print(f"Error: {e}")
