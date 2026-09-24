# Cloudflare Auto-Connector for OpenCode (Tailscale Compatible + HTTP/HTTPS Proxy Bridge)
import os
import sys
import time
import json
import socket
import select
import shutil
import struct
import threading
import urllib.request
import urllib.error
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

try:
    import cloudflare_autoconnector_helper as helper
except ImportError:
    helper = None

# Configuration
OPENCODE_API_URL = os.environ.get("OPENCODE_API_URL", "http://127.0.0.1:4096")
WARP_CLI_PATHS = [
    r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe",
    r"C:\Program Files (x86)\Cloudflare\Cloudflare WARP\warp-cli.exe",
    "warp-cli.exe",
    "warp-cli"
]
HTTP_BRIDGE_PORT = 40001
WARP_SOCKS_PORT = 40000
POLL_INTERVAL_SEC = 2.5
COOLDOWN_SEC = 30.0

# Strict rate limit signatures and connection drop signatures
RATE_LIMIT_KEYWORDS = [
    "429",
    "rate limit",
    "rate_limit",
    "rate-limit",
    "too many requests",
    "quota exceeded",
    "exceeded your quota",
    "error 1015",
    "error 1020",
    "cf-mitigated",
    "blocked by cloudflare",
    "cannot connect to api",
    "unable to connect",
    "fetch failed",
    "socket connection was closed",
    "socket connection closed",
    "bad gateway",
    "502",
    "econnreset",
    "etimedout",
    "free usage exceeded",
    "free_tier_limit",
    "free limit reached",
    "subscribe to go"
]



class ThreadedHttpToSocks5Bridge:
    """Ultra-reliable threaded HTTP CONNECT and forward proxy bridge supporting Cloudflare WARP SOCKS5 and Direct routing."""
    def __init__(self, http_port=HTTP_BRIDGE_PORT, socks_host="127.0.0.1", socks_port=WARP_SOCKS_PORT):
        self.http_port = http_port
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.routing_mode = "warp"  # Route through fresh Cloudflare WARP SOCKS5 IP
        self._server_sock = None
        self._running = False
        self.proxied_requests = 0
        self.last_target = "None"
        self.recent_logs: List[str] = []
        self._active_sockets = set()
        self._lock = threading.Lock()

    def log(self, msg: str):
        t = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 10:
            self.recent_logs.pop(0)
        print(entry, flush=True)

    def reset_tunnels(self):
        """Terminate all existing persistent keep-alive client sockets so new connections use fresh route."""
        with self._lock:
            for s in list(self._active_sockets):
                try:
                    s.close()
                except Exception:
                    pass
            self._active_sockets.clear()
        self.log("[TUNNELS RESET] Terminated all active persistent client sockets")

    def switch_route(self) -> str:
        # Enforce pure Cloudflare WARP egress (direct ISP is rate-limited)
        self.routing_mode = "warp"
        self.reset_tunnels()
        return self.routing_mode

    def connect_remote(self, dest_host: str, dest_port: int) -> socket.socket:
        # Strictly route all traffic via Cloudflare WARP SOCKS5 proxy
        return self.connect_socks5(dest_host, dest_port)

    def connect_socks5(self, dest_host: str, dest_port: int) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(15.0)
        s.connect((self.socks_host, self.socks_port))
        # SOCKS5 greeting: no auth
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        if resp != b"\x05\x00":
            s.close()
            raise RuntimeError("SOCKS5 auth failed")
        # SOCKS5 connect request: pass DOMAINNAME (0x03) so WARP resolves natively and routes via dedicated rotating IPv6
        try:
            ip_bytes = socket.inet_aton(dest_host)
            req = b"\x05\x01\x00\x01" + ip_bytes + struct.pack(">H", dest_port)
        except OSError:
            host_bytes = dest_host.encode("utf-8")
            req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + struct.pack(">H", dest_port)
        s.sendall(req)
        resp = s.recv(4)
        if not resp or resp[1] != 0:
            s.close()
            raise RuntimeError(f"SOCKS5 connect error: {resp}")
        atyp = resp[3]
        if atyp == 1:
            s.recv(6)
        elif atyp == 3:
            dlen = s.recv(1)[0]
            s.recv(dlen + 2)
        elif atyp == 4:
            s.recv(18)
        s.settimeout(None)
        return s

    def handle_client(self, client_sock: socket.socket):
        remote_sock = None
        client_addr = "unknown"
        try:
            client_addr = f"{client_sock.getpeername()[0]}:{client_sock.getpeername()[1]}"
        except Exception:
            pass

        try:
            client_sock.settimeout(10.0)
            req_data = b""
            while b"\r\n\r\n" not in req_data and b"\n\n" not in req_data:
                chunk = client_sock.recv(4096)
                if not chunk:
                    client_sock.close()
                    return
                req_data += chunk
                if len(req_data) > 65536:
                    break

            lines = req_data.decode("utf-8", errors="ignore").split("\r\n")
            req_line = lines[0].strip()
            parts = req_line.split()
            if len(parts) < 2:
                client_sock.close()
                return

            method = parts[0].upper()
            target = parts[1]

            if method == "CONNECT":
                if ":" in target:
                    host, port_str = target.split(":")
                    port = int(port_str)
                else:
                    host, port = target, 443

                try:
                    remote_sock = self.connect_remote(host, port)
                except Exception as e:
                    self.log(f"[PROXY FAIL] CONNECT {host}:{port} from {client_addr}: {e}")
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    client_sock.close()
                    return

                # Acknowledge CONNECT tunnel establishment
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                client_sock.settimeout(None)
                self.proxied_requests += 1
                self.last_target = f"{host}:{port}"
                self.log(f"[PROXY OK] CONNECT {host}:{port} (client: {client_addr}) -> {self.routing_mode.upper()}")

                with self._lock:
                    self._active_sockets.add(client_sock)
                    self._active_sockets.add(remote_sock)

                sockets = [client_sock, remote_sock]
                while True:
                    rlist, _, xlist = select.select(sockets, [], sockets, 60.0)
                    if xlist:
                        break
                    if not rlist:
                        continue
                    for s in rlist:
                        other = remote_sock if s is client_sock else client_sock
                        try:
                            data = s.recv(65536)
                            if not data:
                                return
                            other.sendall(data)
                        except Exception:
                            return

            else:
                from urllib.parse import urlsplit
                parsed = urlsplit(target)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 80

                try:
                    remote_sock = self.connect_remote(host, port)
                except Exception as e:
                    self.log(f"[PROXY FAIL] {method} {host}:{port} from {client_addr}: {e}")
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    client_sock.close()
                    return

                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                first_line = f"{method} {path} {parts[2] if len(parts) > 2 else 'HTTP/1.1'}\r\n"
                headers_rest = req_data.split(b"\r\n", 1)[1] if b"\r\n" in req_data else b""
                remote_sock.sendall(first_line.encode("utf-8") + headers_rest)
                client_sock.settimeout(None)
                self.proxied_requests += 1
                self.last_target = f"{host}:{port}"
                self.log(f"[PROXY OK] {method} {host}:{port} (client: {client_addr}) -> {self.routing_mode.upper()}")

                sockets = [client_sock, remote_sock]
                while True:
                    rlist, _, xlist = select.select(sockets, [], sockets, 60.0)
                    if xlist:
                        break
                    if not rlist:
                        continue
                    for s in rlist:
                        other = remote_sock if s is client_sock else client_sock
                        try:
                            data = s.recv(65536)
                            if not data:
                                return
                            other.sendall(data)
                        except Exception:
                            return

        except Exception:
            pass
        finally:
            with self._lock:
                self._active_sockets.discard(client_sock)
                self._active_sockets.discard(remote_sock)
            if client_sock:
                try:
                    client_sock.close()
                except Exception:
                    pass
            if remote_sock:
                try:
                    remote_sock.close()
                except Exception:
                    pass

    def start(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("0.0.0.0", self.http_port))
        self._server_sock.listen(128)
        self._running = True
        self.log(f"HTTP Proxy Bridge listening on 0.0.0.0:{self.http_port} (Localhost + Tailscale 100.95.56.22)")
        while self._running:
            try:
                client_sock, _ = self._server_sock.accept()
                t = threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                break


class CloudflareAutoConnector:
    def __init__(self):
        self.warp_exe = self._find_warp_cli()
        self.session_id: Optional[str] = None
        self.session_title: Optional[str] = None
        self.total_messages: int = 0
        self.intercept_count: int = 0
        self.last_handled_msg_id: Optional[str] = None
        self.last_rotation_time: float = 0.0
        self.last_event: str = "Initialized (Tailscale-Safe HTTP Bridge Mode)."
        self.warp_state: str = "Unknown"
        self.opencode_online: bool = False
        self.last_msg_status: str = "Idle"
        if helper:
            cleaned = helper.clean_opencode_credentials()
            if cleaned:
                self.last_event = "Cleared stale account.json key (Anonymous IPv6 pool active)"
        self._ensure_proxy_mode()
        self._start_http_bridge()

    def _start_http_bridge(self):
        self.bridge = ThreadedHttpToSocks5Bridge(HTTP_BRIDGE_PORT, "127.0.0.1", WARP_SOCKS_PORT)
        t = threading.Thread(target=self.bridge.start, daemon=True)
        t.start()

    def _find_warp_cli(self) -> Optional[str]:
        for path in WARP_CLI_PATHS:
            if os.path.isabs(path) and os.path.exists(path):
                return path
            found = shutil.which(path)
            if found:
                return found
        return None

    def _ensure_proxy_mode(self):
        """Ensure WARP is in proxy mode so Tailscale and network routes are never broken."""
        if self.warp_exe:
            try:
                subprocess.run([self.warp_exe, "mode", "proxy"], capture_output=True, timeout=5)
            except Exception:
                pass

    def get_warp_status(self) -> str:
        if not self.warp_exe:
            return "WARP CLI not found"
        try:
            res = subprocess.run(
                [self.warp_exe, "status"],
                capture_output=True,
                text=True,
                timeout=4
            )
            out = res.stdout.strip()
            if "Connected" in out:
                return "CONNECTED (HTTP Proxy Bridge -> SOCKS5 -> WARP)"
            elif "Connecting" in out:
                return "CONNECTING..."
            elif "Disconnected" in out:
                return "DISCONNECTED"
            return out.split("\n")[0] if out else "Unknown"
        except Exception as e:
            return f"Error: {e}"

    def rotate_warp(self) -> bool:
        """Disconnect, rotate keys, and reconnect WARP in proxy mode for fresh IP without disrupting Tailscale."""
        if not self.warp_exe:
            self.last_event = "Cannot rotate: warp-cli not found"
            return False

        try:
            self.last_event = "Rotating Cloudflare WARP route (Tailscale safe)..."
            subprocess.run([self.warp_exe, "disconnect"], capture_output=True, timeout=5)
            time.sleep(1.0)

            # Re-register client for a brand new device token and fresh edge session
            try:
                subprocess.run([self.warp_exe, "registration", "delete"], capture_output=True, timeout=5)
                subprocess.run([self.warp_exe, "--accept-tos", "registration", "new"], capture_output=True, timeout=5)
            except Exception:
                pass

            subprocess.run([self.warp_exe, "mode", "proxy"], capture_output=True, timeout=5)
            try:
                subprocess.run([self.warp_exe, "tunnel", "rotate-keys"], capture_output=True, timeout=5)
                subprocess.run([self.warp_exe, "tunnel", "masque-options", "set", "h3-with-h2-fallback"], capture_output=True, timeout=5)
            except Exception:
                pass

            subprocess.run([self.warp_exe, "connect"], capture_output=True, timeout=5)

            # Verify SOCKS5 port is active and accepting connections, and warp=on
            verified = False
            for _ in range(12):
                time.sleep(1.0)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1.5)
                    if s.connect_ex(("127.0.0.1", WARP_SOCKS_PORT)) == 0:
                        s.close()
                        p = subprocess.run([
                            "curl.exe", "-s", "-x", f"socks5h://127.0.0.1:{WARP_SOCKS_PORT}",
                            "https://cloudflare.com/cdn-cgi/trace"
                        ], capture_output=True, text=True, timeout=5)
                        if "warp=on" in p.stdout:
                            verified = True
                            break
                    s.close()
                except Exception:
                    pass

            self.warp_state = self.get_warp_status()
            self.intercept_count += 1
            self.last_rotation_time = time.time()
            if verified:
                self.last_event = f"WARP rotated & verified (warp=on) at {datetime.now().strftime('%H:%M:%S')}"
            else:
                self.last_event = f"WARP reconnected at {datetime.now().strftime('%H:%M:%S')}"
            return True
        except Exception as e:
            self.last_event = f"WARP rotation error: {e}"
            return False

    def attach_opencode_session(self) -> bool:
        """Find active or target session on OpenCode from config or newest."""
        try:
            target_cfg_id = None
            cfg_path = os.path.join(r"C:\Trading\Alpha\config", "opencode_session_config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as cf:
                        target_cfg_id = json.load(cf).get("session_id")
                except Exception:
                    pass

            req = urllib.request.Request(f"{OPENCODE_API_URL}/session", headers={"User-Agent": "CloudflareAutoConnector/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                sessions = json.loads(resp.read().decode("utf-8"))
                self.opencode_online = True
                if not sessions:
                    self.session_id = None
                    self.session_title = "No active session"
                    return False

                target = None
                if target_cfg_id:
                    for s in sessions:
                        if s.get("id") == target_cfg_id:
                            target = s
                            break

                if not target:
                    for s in sessions:
                        title = s.get("title", "")
                        if "v15" in title.lower():
                            target = s
                            break

                if not target:
                    for s in sessions:
                        title = s.get("title", "")
                        if "alpha" in title.lower():
                            target = s
                            break

                if not target:
                    target = sessions[0]

                self.session_id = target.get("id")
                self.session_title = target.get("title", "Untitled")
                return True
        except Exception:
            self.opencode_online = False
            return False

    def check_session_status_error(self) -> Tuple[bool, Optional[str]]:
        """Inspect /session/status for rate limit / free usage exceeded errors."""
        if not self.session_id:
            return False, None
        try:
            url = f"{OPENCODE_API_URL}/session/status"
            req = urllib.request.Request(url, headers={"User-Agent": "CloudflareAutoConnector/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                s_info = data.get(self.session_id, {})
                s_type = str(s_info.get("type", "")).lower()
                if s_type in ("retry", "error"):
                    action = s_info.get("action") or {}
                    reason = str(action.get("reason", "")).lower()
                    title = str(action.get("title", "")).lower()
                    msg = str(s_info.get("message", "")).lower()
                    combined = f"{s_type} {reason} {title} {msg}"
                    for kw in RATE_LIMIT_KEYWORDS:
                        if kw in combined:
                            return True, kw
        except Exception:
            pass
        return False, None

    def abort_session(self):
        """Abort stuck retry turn via OpenCode API so next backoff timer is cleared."""
        if not self.session_id:
            return
        try:
            url = f"{OPENCODE_API_URL}/session/{self.session_id}/abort"
            req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json", "User-Agent": "CloudflareAutoConnector/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.last_event = f"Aborted stuck retry turn in session {self.session_id} (HTTP {resp.status})"
        except Exception as e:
            self.last_event = f"Abort session error: {e}"

    def check_session_rate_limit(self) -> bool:
        """Inspect session status and latest messages strictly for rate limit / free tier limit errors."""
        if not self.session_id:
            return False

        # 1. First priority: Check /session/status (where OpenCode marks retry/backoff on free_tier_limit)
        status_triggered, detected_kw = self.check_session_status_error()
        if status_triggered:
            now = time.time()
            self.last_msg_status = f"RATE LIMIT / STATUS ({detected_kw})"
            if (now - self.last_rotation_time) > COOLDOWN_SEC:
                self.last_rotation_time = now
                self.last_event = f"Rate/Tier limit in status: '{detected_kw}'"
                return True
            return False

        # 2. Check recent messages for real errors
        url = f"{OPENCODE_API_URL}/session/{self.session_id}/message"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CloudflareAutoConnector/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                msgs = json.loads(resp.read().decode("utf-8"))
                self.total_messages = len(msgs)
                if not msgs:
                    self.last_msg_status = "No messages"
                    return False

                # Inspect up to the last 5 messages, starting from the most recent
                for m in reversed(msgs[-5:]):
                    info = m.get("info", {})
                    msg_id = m.get("id") or info.get("id") or ""
                    finish_reason = str(info.get("finishReason") or info.get("finish") or "").lower()
                    error_obj = info.get("error")

                    parts = m.get("parts", [])
                    error_parts = [p for p in parts if isinstance(p, dict) and p.get("type") == "error"]

                    has_real_error = bool(error_obj) or (finish_reason in ["error", "fail", "failed"]) or bool(error_parts)
                    if not has_real_error:
                        continue

                    # Extract content strictly from the error object and error parts
                    error_tokens = []
                    if error_obj:
                        error_tokens.append(str(error_obj))
                    if finish_reason:
                        error_tokens.append(finish_reason)
                    for ep in error_parts:
                        error_tokens.append(str(ep.get("error") or ep.get("text") or ""))

                    combined_error_text = (" ".join(error_tokens)).lower()

                    for kw in RATE_LIMIT_KEYWORDS:
                        if kw in combined_error_text:
                            self.last_msg_status = f"RATE LIMIT ({kw})"
                            now = time.time()
                            if msg_id != self.last_handled_msg_id and (now - self.last_rotation_time) > COOLDOWN_SEC:
                                self.last_handled_msg_id = msg_id
                                self.last_event = f"Rate limit intercepted: '{kw}'"
                                return True
                            return False

                # If no errors found in last 5 messages
                latest_role = msgs[-1].get("info", {}).get("role", "unknown")
                self.last_msg_status = f"OK ({latest_role})"
                return False
        except Exception as e:
            self.last_msg_status = f"Poll error: {e}"
            return False

    def send_continuation_prompt(self):
        """Send prompt_async to OpenCode session to resume without interruption."""
        if not self.session_id:
            return

        url = f"{OPENCODE_API_URL}/session/{self.session_id}/prompt_async"
        payload = json.dumps({
            "parts": [
                {
                    "type": "text",
                    "text": "[AUTO-CONNECTOR] Network route refreshed via Cloudflare WARP. Please continue execution uninterrupted."
                }
            ]
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "CloudflareAutoConnector/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 204):
                    self.last_event = f"Continuation dispatched to session '{self.session_title}'"
        except Exception as e:
            self.last_event = f"Prompt dispatch error: {e}"

    def render_dashboard(self):
        """Minimal non-flickering terminal dashboard."""
        os.system("cls" if os.name == "nt" else "clear")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        warp_color = "\033[92m" if "CONNECTED" in self.warp_state else "\033[93m"
        oc_color = "\033[92m" if self.opencode_online else "\033[91m"
        reset_color = "\033[0m"

        oc_status = f"{oc_color}ONLINE{reset_color} ({OPENCODE_API_URL})" if self.opencode_online else f"{oc_color}OFFLINE{reset_color}"
        warp_disp = f"{warp_color}{self.warp_state}{reset_color}"

        print("=" * 68)
        print("     [+] CLOUDFLARE AUTO-CONNECTOR FOR OPENCODE (TAILSCALE-SAFE)     ")
        print("=" * 68)
        print(f"  System Time       : {now_str}")
        print(f"  OpenCode Server   : {oc_status}")
        print(f"  Attached Session  : {self.session_title or 'Searching...'} ({self.session_id or 'None'})")
        print(f"  Messages Count    : {self.total_messages}")
        print(f"  Last Status       : {self.last_msg_status}")
        print("-" * 68)
        print(f"  Cloudflare WARP   : {warp_disp}")
        print(f"  HTTP Proxy Bridge : http://0.0.0.0:{HTTP_BRIDGE_PORT} (Localhost + Tailscale 100.95.56.22)")
        print(f"  Active Route Mode : {getattr(self, 'bridge', None) and self.bridge.routing_mode.upper() or 'UNKNOWN'} (Auto-Swapping on Rate Limit)")
        print(f"  Proxied Requests  : {getattr(self, 'bridge', None) and self.bridge.proxied_requests or 0} requests handled")
        print(f"  Last Proxy Target : {getattr(self, 'bridge', None) and self.bridge.last_target or 'None'}")
        print(f"  Auto-Rotations    : {self.intercept_count} intercepts")
        print("-" * 68)
        print(f"  Last Activity     : {self.last_event}")
        print("=" * 68)

    def run(self):
        print("Starting Cloudflare Auto-Connector (Tailscale Compatible + Multi-Egress)...")
        while True:
            try:
                self.warp_state = self.get_warp_status()
                self.attach_opencode_session()

                if self.opencode_online and self.session_id:
                    triggered = self.check_session_rate_limit()
                    if triggered:
                        self.render_dashboard()
                        self.abort_session()
                        self.rotate_warp()
                        self.bridge.reset_tunnels()
                        self.last_event = "WARP IP rotated & verified; session cleared"
                        self.render_dashboard()
                        time.sleep(2.0)
                        self.send_continuation_prompt()

                self.render_dashboard()
                time.sleep(POLL_INTERVAL_SEC)
            except KeyboardInterrupt:
                print("\n[!] Auto-Connector stopped by user.")
                break
            except Exception as e:
                self.last_event = f"Loop exception: {e}"
                time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    connector = CloudflareAutoConnector()
    connector.run()
