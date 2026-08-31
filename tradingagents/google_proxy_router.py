"""
Google Proxy Router (Port 3211)
Transparently routes all Gemini Flash-Lite, Flash, and Pro models to Port 3210 with intelligent aliasing and zero errors.
"""

import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

UPSTREAM_URL = "http://127.0.0.1:3210"

MODEL_MAP = {
    # All Flash-Lite variants map to 3.1-flash-lite
    "gemini-2.5-flash-lite": "3.1-flash-lite",
    "gemini-3.1-flash-lite": "3.1-flash-lite",
    "gemini-3.5-flash-lite": "3.1-flash-lite",
    "3.1-flash-lite": "3.1-flash-lite",
    "flash-lite": "3.1-flash-lite",
    
    # All Flash variants
    "gemini-3.6-flash": "3.5-flash",
    "gemini-3.5-flash": "3.5-flash",
    "gemini-3.7-flash": "3.5-flash",
    "gemini-2.5-flash": "3.5-flash",
    "3.5-flash": "3.5-flash",
    "flash": "3.5-flash",
    
    # All Pro variants
    "gemini-2.5-pro": "3.1-pro",
    "gemini-3.1-pro": "3.1-pro",
    "3.1-pro": "3.1-pro",
    "pro": "3.1-pro",
    
    "gemini": "gemini"
}

ALL_MODELS_METADATA = [
    {"id": "gemini-2.5-flash-lite", "object": "model", "owned_by": "google"},
    {"id": "gemini-3.1-flash-lite", "object": "model", "owned_by": "google"},
    {"id": "gemini-3.5-flash-lite", "object": "model", "owned_by": "google"},
    {"id": "gemini-3.6-flash", "object": "model", "owned_by": "google"},
    {"id": "gemini-3.5-flash", "object": "model", "owned_by": "google"},
    {"id": "gemini-3.7-flash", "object": "model", "owned_by": "google"},
    {"id": "gemini-2.5-flash", "object": "model", "owned_by": "google"},
    {"id": "gemini-2.5-pro", "object": "model", "owned_by": "google"},
    {"id": "gemini-3.1-pro", "object": "model", "owned_by": "google"},
    {"id": "3.1-flash-lite", "object": "model", "owned_by": "google"},
    {"id": "3.5-flash", "object": "model", "owned_by": "google"},
    {"id": "3.1-pro", "object": "model", "owned_by": "google"},
    {"id": "gemini", "object": "model", "owned_by": "google"}
]

class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        if "/models" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"object": "list", "data": ALL_MODELS_METADATA}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if "/chat/completions" in self.path:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            req_model = data.get("model", "gemini")
            target_model = MODEL_MAP.get(req_model.lower(), "3.5-flash")
            data["model"] = target_model

            msgs = data.get("messages", [])
            system_chunks = []
            clean_msgs = []
            for m in msgs:
                if m.get("role") == "system":
                    system_chunks.append(m.get("content", ""))
                else:
                    clean_msgs.append(m)

            if system_chunks and clean_msgs:
                combined_sys = "\n\n".join(system_chunks)
                for m in clean_msgs:
                    if m.get("role") == "user":
                        m["content"] = f"{combined_sys}\n\n{m.get('content', '')}"
                        break
                data["messages"] = clean_msgs

            forward_body = json.dumps(data).encode("utf-8")
            upstream_req = urllib.request.Request(
                f"{UPSTREAM_URL}/v1/chat/completions",
                data=forward_body,
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(upstream_req, timeout=30) as resp:
                    resp_data = resp.read()
                    self.send_response(resp.status)
                    for k, v in resp.getheaders():
                        if k.lower() in ("content-type", "access-control-allow-origin"):
                            self.send_header(k, v)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_data)
            except urllib.error.HTTPError as e:
                err_body = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(err_body)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run_server(port=3211):
    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    print(f"Google Proxy Router listening on http://127.0.0.1:{port}")
    server.serve_forever()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3211
    run_server(port)
