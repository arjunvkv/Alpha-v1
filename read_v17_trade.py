import urllib.request, json, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sid = 'ses_f6ec54dc8ffecoS0hYWUM97Flx'
url = f'http://127.0.0.1:4096/session/{sid}/message'
msgs = json.loads(urllib.request.urlopen(url).read().decode('utf-8'))

print(f"Total msgs: {len(msgs)}")
for i in range(25, len(msgs)):
    m = msgs[i]
    role = m.get('info', {}).get('role') or m.get('role')
    for p in m.get('parts', []):
        ptype = p.get('type')
        if ptype == 'text':
            txt = p.get('text', '')
            if any(k in txt for k in ["540706170", "Supply_Retrace", "DECISION", "EXECUTE", "SELL_LIMIT", "Exit", "EXIT"]):
                print(f"\n[1==== SWIFT MSG #{i [{role}] ====]")
                print(txt[:1200])
        elif ptype == 'tool':
            tname = p.get('tool')
            args = p.get('call', {}).get('arguments')
            if any(k in str(tname) for k in ['place', 'execute', 'update', 'close']):
                print(f"\n--- MSG #{i} TOOL [{tname}] ---")
                print(args)
