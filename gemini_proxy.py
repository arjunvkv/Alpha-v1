import urllib.request, json, os, sys, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

SIGNATURE_CACHE = {}
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", ""))
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

class GeminiProxyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        res = {
            "object": "list",
            "data": [
                {"id": "gemini-3.5-flash-lite", "object": "model", "owned_by": "google"},
                {"id": "gemini-3.1-flash-lite", "object": "model", "owned_by": "google"},
                {"id": "qwen/qwen3.8-27b", "object": "model", "owned_by": "groq"}
            ]
        }
        self.wfile.write(json.dumps(res).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
            
            # Step 1: Re-inject cached thought_signatures into assistant messages
            messages = payload.get('messages', [])
            for m in messages:
                if m.get('role') == 'assistant' and m.get('tool_calls'):
                    for tc in m['tool_calls']:
                        cid = tc.get('id')
                        if cid and cid in SIGNATURE_CACHE:
                            tc['extra_content'] = {'google': {'thought_signature': SIGNATURE_CACHE[cid]}}

            # Step 2: Determine Auth
            auth_header = self.headers.get('Authorization')
            if not auth_header or auth_header.strip() in ['Bearer', 'Bearer null', 'Bearer undefined']:
                auth_header = f"Bearer {GOOGLE_API_KEY}"

            is_stream = payload.get('stream', False)
            response = None
            used_groq = False

            # Step 3: Attempt Google with fast retry
            for attempt in range(2):
                req = urllib.request.Request(
                    GOOGLE_URL,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json', 'Authorization': auth_header, 'User-Agent': 'Mozilla/5.0'}
                )
                try:
                    response = urllib.request.urlopen(req, timeout=15)
                    if response:
                        break
                except urllib.error.HTTPError as e:
                    if e.code in [429, 503, 500]:
                        print(f"[Gemini Proxy] Google returned {e.code} on attempt {attempt+1}. Backoff 1.0s...", file=sys.stderr)
                        time.sleep(1.0)
                    else:
                        break
                except Exception:
                    time.sleep(1.0)

            # Step 4: If Google is quota exhausted (429/503), Instant Failover to Groq Cloud
            if not response:
                print(f"[Gemini Proxy Failover] Google quota reached -> Instantly routing to Groq Cloud (Qwen 3.8 27B / 800 t/s)...", file=sys.stderr)
                groq_payload = dict(payload)
                groq_payload['model'] = 'qwen/qwen3.8-27b'
                groq_req = urllib.request.Request(
                    GROQ_URL,
                    data=json.dumps(groq_payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}', 'User-Agent': 'Mozilla/5.0'}
                )
                response = urllib.request.urlopen(groq_req, timeout=20)
                used_groq = True

            self.send_response(response.status)
            for k, v in response.getheaders():
                if k.lower() not in ['transfer-encoding', 'content-length']:
                    self.send_header(k, v)
            self.send_header('Access-Control-Allow-Origin', '*')

            if is_stream:
                self.end_headers()
                for line in response:
                    line_str = line.decode('utf-8', errors='ignore')
                    if not used_groq and line_str.startswith('data: ') and not line_str.startswith('data: [DONE]'):
                        try:
                            chunk_data = json.loads(line_str[6:].strip())
                            choices = chunk_data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                tcs = delta.get('tool_calls', [])
                                for tc in tcs:
                                    cid = tc.get('id')
                                    sig = tc.get('extra_content', {}).get('google', {}).get('thought_signature')
                                    if cid and sig:
                                        SIGNATURE_CACHE[cid] = sig
                        except Exception:
                            pass
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        break
            else:
                res_data = response.read()
                if not used_groq:
                    try:
                        res_json = json.loads(res_data.decode('utf-8'))
                        choices = res_json.get('choices', [])
                        if choices:
                            msg = choices[0].get('message', {})
                            tcs = msg.get('tool_calls', [])
                            for tc in tcs:
                                cid = tc.get('id')
                                sig = tc.get('extra_content', {}).get('google', {}).get('thought_signature')
                                if cid and sig:
                                    SIGNATURE_CACHE[cid] = sig
                    except Exception:
                        pass
                self.send_header('Content-Length', str(len(res_data)))
                self.end_headers()
                try:
                    self.wfile.write(res_data)
                except (ConnectionResetError, BrokenPipeError):
                    pass

        except urllib.error.HTTPError as e:
            err_data = e.read()
            print(f"[Gemini Proxy Error] HTTP {e.code}: {err_data[:200]}", file=sys.stderr)
            try:
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(err_data)))
                self.end_headers()
                self.wfile.write(err_data)
            except Exception:
                pass
        except Exception as e:
            print(f"[Gemini Proxy Error] Exception: {e}", file=sys.stderr)
            err_msg = json.dumps({'error': {'message': str(e), 'type': 'proxy_error'}}).encode('utf-8')
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(err_msg)))
                self.end_headers()
                self.wfile.write(err_msg)
            except Exception:
                pass

    def log_message(self, format, *args):
        pass

def run_proxy(port=4095):
    server = ThreadingHTTPServer(('127.0.0.1', port), GeminiProxyHandler)
    print(f"[Gemini Proxy] High-Availability Dual-Cloud (Google + Groq Failover) Proxy running on http://127.0.0.1:{port}/v1")
    server.serve_forever()

if __name__ == '__main__':
    run_proxy()
