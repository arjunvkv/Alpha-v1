import sys, json, subprocess, time
from datetime import datetime, timezone

def list_daemons():
    """Return daemon.py python processes via Get-CimInstance, with tasklist fallback."""
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
             "| Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            text=True, timeout=30)
        procs = json.loads(out)
        if isinstance(procs, dict):
            procs = [procs]
        return [{"pid": p.get("ProcessId"),
                 "cmd": (p.get("CommandLine") or "")} for p in procs
                if p.get("CommandLine") and "daemon.py" in p["CommandLine"]]
    except Exception as e:
        # Fallback to tasklist if Get-CimInstance fails (e.g. 0x80041006)
        try:
            out = subprocess.check_output(
                ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/V', '/FO', 'CSV'],
                text=True, timeout=30)
            daemons = []
            for line in out.splitlines()[1:]:
                parts = line.split('","')
                if len(parts) >= 9 and "daemon.py" in line:
                    daemons.append({"pid": parts[1], "cmd": line})
            return daemons
        except Exception as e2:
            return [{"error": f"both methods failed: {e} | {e2}"}]

daemons = list_daemons()

result = {"daemons": daemons, "ts": datetime.now(timezone.utc).isoformat()}
print(json.dumps(result, indent=2, default=str))
