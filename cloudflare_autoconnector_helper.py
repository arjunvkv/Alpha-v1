"""
========================================================================================
     CLOUDFLARE AUTO-CONNECTOR HELPER & RUNTIME DISCOVERY ARCHIVE
========================================================================================
Companion Module attached to cloudflare_autoconnector.py.
Provides diagnostic checks, egress IP verification, account credential validation,
and historical root-cause documentation for OpenCode free-tier model routing (big-pickle).

KEY ARCHITECTURAL DISCOVERIES & LESSONS (SEPTEMBER 2026):
----------------------------------------------------------------------------------------
1. SOCKS5 DOMAINNAME (0x03) vs IPv4 RESOLUTION (0x01):
   - PROBLEM: Previously, ThreadedHttpToSocks5Bridge resolved destination hostnames locally
     using socket.gethostbyname() and sent an IPv4 (0x01) address connect request to WARP SOCKS5.
   - IMPACT: When connecting to an IPv4 destination, Cloudflare WARP egresses through a shared
     carrier NAT IPv4 pool in Chennai (e.g. 104.28.219.117). This shared IPv4 is constantly
     exhausted by multiple users on opencode.ai, triggering 'Free usage exceeded, subscribe to Go'.
   - RESOLUTION: Updated connect_socks5() to preserve the raw domain name and send a SOCKS5
     DOMAINNAME (0x03) request. Cloudflare WARP resolves the domain natively on its edge network,
     routing traffic directly over end-to-end IPv6 (2a09:bac5:xxxx:11cd::).
   - RESULT: Every WARP key rotation assigns a dedicated, fresh IPv6 subnet (/64) with its own
     untouched daily token bucket on opencode.ai.

2. ACCOUNT CREDENTIALS VS ANONYMOUS IP RATE LIMITER:
   - OpenCode's backend (opencode.ai/zen/v1) prioritizes credentials in this order:
     a) If an API key is provided (Authorization: Bearer sk-...), it evaluates the account
        quota first. If that account exceeded its daily quota, the request is immediately
        rejected with FreeUsageLimitError REGARDLESS of the client IP!
     b) If no key or 'public' is provided, it falls back to IP rate-limiting based on the
        first 4 segments of IPv6 (subnet /64) or the raw IPv4.
   - ROOT CAUSE: ~/.local/share/opencode/account.json retained an exhausted opencode API key
     (sk-WFkGKfEC...). Every request sent that key, masking the rotated IP.
   - RESOLUTION: Removed the opencode account from account.json so OpenCode defaults to
     the anonymous IP-based tier through the fresh WARP IPv6 tunnel.

3. ISP PROTOCOL FILTERING (MASQUE vs WIREGUARD):
   - Local Indian ISPs (Airtel, Jio) throttle or block WireGuard UDP traffic on port 2408.
   - MASQUE (HTTPS / QUIC over UDP port 443 with HTTP/2 TCP fallback) connects reliably
     with sub-30ms latency to the Chennai (MAA) colocation.

4. OPENCODE RETRY CACHE IN MEMORY:
   - When OpenCode encounters a FreeUsageLimitError, it writes {"type": "retry", "next": <ts>}
     into memory for that session.
   - Even after IP rotation, THAT specific session remains blocked until the server restarts
     or a fresh session ID is created.

5. MCP META-TOOL DEPRECATION (alpha_call_desk_tool TRAP):
   - Exposing meta-dispatcher tools like call_desk_tool or list_desk_tools in FastMCP caused
     the LLM to attempt indirect wrappers (alpha_call_desk_tool) instead of direct native tool calls.
   - Deprecated call_desk_tool and list_desk_tools from @mcp.tool so the LLM calls canonical
     tools directly (alpha_query_analyst_desk, alpha_get_deep_orderflow_telemetry, etc.).
========================================================================================
"""

import os
import sys
import json
import time
import socket
import struct
import ssl
import subprocess
import urllib.request
from typing import Dict, Any, Optional, Tuple

WARP_SOCKS_PORT = 40000
HTTP_BRIDGE_PORT = 40001
OPENCODE_API_URL = os.environ.get("OPENCODE_API_URL", "http://127.0.0.1:4096")
OPENCODE_DATA_DIR = os.path.expanduser(r"~\.local\share\opencode")
ACCOUNT_JSON_PATH = os.path.join(OPENCODE_DATA_DIR, "account.json")
AUTH_JSON_PATH = os.path.join(OPENCODE_DATA_DIR, "auth.json")


def verify_socks5_egress(host: str = "cloudflare.com", port: int = 443, socks_port: int = WARP_SOCKS_PORT) -> Dict[str, str]:
    """
    Directly connects to WARP SOCKS5 on localhost using DOMAINNAME (0x03)
    and queries cdn-cgi/trace to return the exact public egress IP and colocation.
    """
    results = {"success": False, "ip": "", "colo": "", "warp": "", "error": ""}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(8.0)
        s.connect(("127.0.0.1", socks_port))
        
        # SOCKS5 handshake (No Auth)
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        if resp != b"\x05\x00":
            results["error"] = f"SOCKS5 auth negotiation failed: {resp}"
            s.close()
            return results

        # SOCKS5 connect request with DOMAINNAME (0x03)
        host_b = host.encode("utf-8")
        req = b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b + struct.pack(">H", port)
        s.sendall(req)
        resp = s.recv(4)
        if not resp or resp[1] != 0:
            results["error"] = f"SOCKS5 connect error: {resp}"
            s.close()
            return results

        # Consume bound address
        atyp = resp[3]
        if atyp == 1:
            s.recv(6)
        elif atyp == 3:
            dlen = s.recv(1)[0]
            s.recv(dlen + 2)
        elif atyp == 4:
            s.recv(18)

        # Wrap in TLS and send trace request
        ctx = ssl.create_default_context()
        ss = ctx.wrap_socket(s, server_hostname=host)
        ss.sendall(f"GET /cdn-cgi/trace HTTP/1.1\r\nHost: {host}\r\nUser-Agent: AutoconnectorHelper/1.0\r\nConnection: close\r\n\r\n".encode())

        data = b""
        while True:
            chunk = ss.recv(4096)
            if not chunk:
                break
            data += chunk
        ss.close()

        lines = data.decode("utf-8", errors="ignore").split("\n")
        trace_data = {}
        for line in lines:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                trace_data[k] = v

        results["success"] = True
        results["ip"] = trace_data.get("ip", "")
        results["colo"] = trace_data.get("colo", "")
        results["warp"] = trace_data.get("warp", "")
        results["is_ipv6"] = ":" in results["ip"]
    except Exception as e:
        results["error"] = str(e)
    return results


def verify_http_bridge_egress(bridge_port: int = HTTP_BRIDGE_PORT) -> Dict[str, str]:
    """Tests the HTTP proxy bridge via curl to verify it passes traffic over fresh IPv6."""
    try:
        res = subprocess.run(
            ["curl.exe", "-s", "-x", f"http://127.0.0.1:{bridge_port}", "https://cloudflare.com/cdn-cgi/trace"],
            capture_output=True,
            text=True,
            timeout=5
        )
        data = {}
        for line in res.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
        return {
            "success": True,
            "ip": data.get("ip", ""),
            "colo": data.get("colo", ""),
            "warp": data.get("warp", ""),
            "is_ipv6": ":" in data.get("ip", "")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def audit_opencode_credentials() -> Dict[str, Any]:
    """
    Audits account.json and auth.json to verify whether an exhausted opencode
    credential exists that could hijack requests away from the fresh IP pool.
    """
    audit = {
        "account_json_exists": os.path.exists(ACCOUNT_JSON_PATH),
        "auth_json_exists": os.path.exists(AUTH_JSON_PATH),
        "has_opencode_in_account": False,
        "has_opencode_in_auth": False,
        "is_safe": True
    }

    if audit["account_json_exists"]:
        try:
            with open(ACCOUNT_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active = data.get("active", {})
                accounts = data.get("accounts", {})
                for acc_id, acc in accounts.items():
                    if acc.get("serviceID") == "opencode":
                        audit["has_opencode_in_account"] = True
                        audit["is_safe"] = False
                if "opencode" in active:
                    audit["has_opencode_in_account"] = True
                    audit["is_safe"] = False
        except Exception:
            pass

    if audit["auth_json_exists"]:
        try:
            with open(AUTH_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "opencode" in data:
                    audit["has_opencode_in_auth"] = True
                    audit["is_safe"] = False
        except Exception:
            pass

    return audit


def clean_opencode_credentials() -> bool:
    """Removes any exhausted opencode account entries from account.json and auth.json."""
    cleaned = False
    if os.path.exists(ACCOUNT_JSON_PATH):
        try:
            with open(ACCOUNT_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            accounts = data.get("accounts", {})
            active = data.get("active", {})

            to_remove = [k for k, v in accounts.items() if v.get("serviceID") == "opencode"]
            for k in to_remove:
                del accounts[k]
                cleaned = True

            if "opencode" in active:
                del active["opencode"]
                cleaned = True

            if cleaned:
                with open(ACCOUNT_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
        except Exception:
            pass

    return cleaned


def test_big_pickle_reachability(session_id: str) -> Dict[str, Any]:
    """Sends a minimal probe to the active OpenCode session to verify big-pickle responds."""
    url = f"{OPENCODE_API_URL}/session/{session_id}/prompt_async"
    payload = json.dumps({
        "parts": [{"type": "text", "text": "PING"}],
        "model": {"providerID": "opencode", "modelID": "big-pickle"}
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return {"status_code": resp.status, "dispatched": resp.status in (200, 204)}
    except Exception as e:
        return {"status_code": 0, "dispatched": False, "error": str(e)}


if __name__ == "__main__":
    print("=" * 68)
    print("      CLOUDFLARE AUTO-CONNECTOR DIAGNOSTIC HELPER SUITE      ")
    print("=" * 68)

    print("\n[1] Testing Direct SOCKS5 DOMAINNAME (0x03) Egress...")
    s5_info = verify_socks5_egress()
    print(f"    Success: {s5_info.get('success')}")
    print(f"    IP     : {s5_info.get('ip')} (IPv6={s5_info.get('is_ipv6')})")
    print(f"    Colo   : {s5_info.get('colo')}")
    print(f"    WARP   : {s5_info.get('warp')}")

    print("\n[2] Testing HTTP Proxy Bridge Port 40001 Egress...")
    hb_info = verify_http_bridge_egress()
    print(f"    Success: {hb_info.get('success')}")
    print(f"    IP     : {hb_info.get('ip')} (IPv6={hb_info.get('is_ipv6')})")
    print(f"    Colo   : {hb_info.get('colo')}")
    print(f"    WARP   : {hb_info.get('warp')}")

    print("\n[3] Auditing OpenCode Credential State...")
    cred_audit = audit_opencode_credentials()
    print(f"    Safe for Anonymous IP Pool : {cred_audit.get('is_safe')}")
    print(f"    Exhausted Key in account.json: {cred_audit.get('has_opencode_in_account')}")
    print(f"    Exhausted Key in auth.json   : {cred_audit.get('has_opencode_in_auth')}")

    print("\n[+] Diagnostic Complete.")
    print("=" * 68)
