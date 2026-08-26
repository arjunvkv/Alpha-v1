"""Process Cleanup Script for Intelligent Trading Desk.
Terminates ALL background intelligent daemon processes using psutil.
"""

import os
import psutil

def kill_all_daemons():
    my_pid = os.getpid()
    killed = 0
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.pid == my_pid:
                continue
            cmd = p.info.get('cmdline') or []
            cmd_str = " ".join(cmd)
            if 'intelligent_daemon' in cmd_str or 'alpha_mcp_server' in cmd_str:
                p.kill()
                print(f"[KILLED] Process PID {p.pid}: {cmd_str[:60]}")
                killed += 1
        except Exception:
            pass
    print(f"[CLEANUP COMPLETE] Terminated {killed} stale background daemon processes.")

if __name__ == "__main__":
    kill_all_daemons()
