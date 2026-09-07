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
COOLDOWN_SEC = 60.0

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
    "econnreset",
    "etimedout"
]



class ThreadedHttpToSocks5Bridge:
    """Ultra-reliable threaded HTTP CONNECT and forward proxy bridge forwarding to Cloudflare WARP SOCKS5 proxy."""
    def __init__(self, http_port=HTTP_BRIDGE_PORT, socks_host="127.0.0.1", socks_port=WARP_SOCKS_PORT):
        self.http_port = http_port
        self.socks_host = socks_host
        self.socks_port = socks_port
        self._server_sock = None
        self._running = False
        self.proxied_requests = 0
        self.last_target = "None"
        self.recent_logs: List[str] = []

    def log(self, msg: str):
        t = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 10:
            self.recent_logs.pop(0)
        print(entry, flush=True)

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
        # SOCKS5 connect request: DOMAINNAME (0x03)
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
                    remote_sock = self.connect_socks5(host, port)
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
                self.log(f"[PROXY OK] CONNECT {host}:{port} (client: {client_addr}) -> WARP SOCKS5")

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
                    remote_sock = self.connect_socks5(host, port)
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
                self.log(f"[PROXY OK] {method} {host}:{port} (client: {client_addr}) -> WARP SOCKS5")

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

            subprocess.run([self.warp_exe, "mode", "proxy"], capture_output=True, timeout=5)
            try:
                subprocess.run([self.warp_exe, "tunnel", "rotate-keys"], capture_output=True, timeout=5)
            except Exception:
                pass

            subprocess.run([self.warp_exe, "connect"], capture_output=True, timeout=5)

            # Verify SOCKS5 port is active and accepting connections
            for _ in range(8):
                time.sleep(1.0)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1.0)
                    if s.connect_ex(("127.0.0.1", WARP_SOCKS_PORT)) == 0:
                        s.close()
                        self.warp_state = self.get_warp_status()
                        self.intercept_count += 1
                        self.last_rotation_time = time.time()
                        self.last_event = f"WARP reconnected & verified at {datetime.now().strftime('%H:%M:%S')} (Tailscale active)"
                        return True
                    s.close()
                except Exception:
                    pass

            self.last_event = "WARP reconnect completed"
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

    def check_session_rate_limit(self) -> bool:
        """Inspect latest messages for rate limit / Cloudflare errors."""
        if not self.session_id:
            return False

        url = f"{OPENCODE_API_URL}/session/{self.session_id}/message"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CloudflareAutoConnector/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                msgs = json.loads(resp.read().decode("utf-8"))
                self.total_messages = len(msgs)
                if not msgs:
                    self.last_msg_status = "No messages"
                    return False

                last_msg = msgs[-1]
                msg_id = last_msg.get("id") or str(len(msgs))
                info = last_msg.get("info", {})
                role = info.get("role", "unknown")
                finish_reason = str(info.get("finishReason", "")).lower()
                error_obj = info.get("error")

                # Only evaluate assistant messages with actual errors
                if role != "assistant" and not error_obj:
                    self.last_msg_status = f"OK ({role})"
                    return False

                parts = last_msg.get("parts", [])
                text_content = ""
                for p in parts:
                    if isinstance(p, dict):
                        if p.get("type") == "text":
                            text_content += " " + p.get("text", "")
                        elif p.get("type") == "error":
                            text_content += " " + str(p.get("error", ""))

                combined_text = (text_content + " " + finish_reason + " " + str(error_obj or "")).lower()

                is_rate_limited = False
                detected_keyword = None
                for kw in RATE_LIMIT_KEYWORDS:
                    if kw in combined_text:
                        is_rate_limited = True
                        detected_keyword = kw
                        break

                if is_rate_limited:
                    self.last_msg_status = f"RATE LIMIT ({detected_keyword})"
                    now = time.time()
                    if msg_id != self.last_handled_msg_id and (now - self.last_rotation_time) > COOLDOWN_SEC:
                        self.last_handled_msg_id = msg_id
                        self.last_event = f"Rate limit intercepted: '{detected_keyword}'"
                        return True
                else:
                    self.last_msg_status = f"OK ({role})"

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
        print(f"  WARP SOCKS5 Proxy : 127.0.0.1:{WARP_SOCKS_PORT}")
        print(f"  Proxied Requests  : {getattr(self, 'bridge', None) and self.bridge.proxied_requests or 0} routed via Cloudflare")
        print(f"  Last Proxy Target : {getattr(self, 'bridge', None) and self.bridge.last_target or 'None'}")
        print(f"  Auto-Rotations    : {self.intercept_count} intercepts")
        print("-" * 68)
        print(f"  Last Activity     : {self.last_event}")
        print("=" * 68)

    def run(self):
        print("Starting Cloudflare Auto-Connector (Tailscale Compatible)...")
        while True:
            try:
                self.warp_state = self.get_warp_status()
                self.attach_opencode_session()

                if self.opencode_online and self.session_id:
                    triggered = self.check_session_rate_limit()
                    if triggered:
                        self.render_dashboard()
                        success = self.rotate_warp()
                        if success:
                            time.sleep(1.0)
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
