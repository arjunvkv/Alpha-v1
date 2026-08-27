import urllib.request, json, os, sys, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

SIGNATURE_CACHE = {}
FUNCTION_NAME_CACHE = {}
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

def get_api_keys():
    google_k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or ""
    groq_k = os.environ.get("GROQ_API_KEY") or ""
    
    if not google_k or not groq_k:
        try:
            cfg_path = os.path.expanduser("~/.config/opencode/opencode.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    env_b = cfg.get("env", {})
                    google_k = google_k or env_b.get("GEMINI_API_KEY") or env_b.get("GOOGLE_GENERATIVE_AI_API_KEY") or ""
                    groq_k = groq_k or env_b.get("GROQ_API_KEY") or ""
        except Exception:
            pass
    return google_k.strip(), groq_k.strip()

def prune_messages(messages, max_recent=40):
    if len(messages) <= max_recent:
        return messages
    
    # Slice tail but ensure we don't start on an orphaned tool response
    start_idx = max(0, len(messages) - max_recent)
    while start_idx > 0 and messages[start_idx].get('role') == 'tool':
        start_idx -= 1
        
    tail = messages[start_idx:]
    first_msg = messages[0] if messages[0].get('role') in ['system', 'user'] else None
    if first_msg and first_msg not in tail:
        return [first_msg] + tail
    return tail

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
                {"id": "gemini-flash-lite-latest", "object": "model", "owned_by": "google"},
                {"id": "gemini-flash-latest", "object": "model", "owned_by": "google"},
                {"id": "gemini-3.1-flash-lite", "object": "model", "owned_by": "google"},
                {"id": "gemini-3.5-flash-lite", "object": "model", "owned_by": "google"},
                {"id": "gemini-3.6-flash", "object": "model", "owned_by": "google"}
            ]
        }
        self.wfile.write(json.dumps(res).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
            
            # Extract valid tool names from tools array
            declared_tool_names = []
            for t in payload.get('tools', []):
                fn = t.get('function', {})
                name = fn.get('name')
                if name:
                    declared_tool_names.append(name)
            default_tool_name = declared_tool_names[0] if declared_tool_names else "mcp_alpha_get_account_status"

            # Step 0: Optimize context window (prune stale historical turns)
            messages = payload.get('messages', [])
            if messages:
                messages = prune_messages(messages, max_recent=40)
                payload['messages'] = messages

            # Step 1: Re-inject thought_signatures and normalize function names/tool messages
            for m in messages:
                # Clean empty name on messages
                if 'name' in m and not m['name']:
                    del m['name']

                if m.get('role') == 'assistant' and m.get('tool_calls'):
                    for tc in m['tool_calls']:
                        cid = tc.get('id')
                        fn = tc.get('function', {})
                        fn_name = fn.get('name')
                        if cid and fn_name:
                            FUNCTION_NAME_CACHE[cid] = fn_name
                        if cid and cid in SIGNATURE_CACHE:
                            tc['extra_content'] = {'google': {'thought_signature': SIGNATURE_CACHE[cid]}}

                elif m.get('role') == 'tool':
                    cid = m.get('tool_call_id')
                    # Ensure name is ALWAYS valid and matching a declared tool
                    if not m.get('name') or m['name'].strip() == "":
                        m['name'] = FUNCTION_NAME_CACHE.get(cid, default_tool_name)
                    if m.get('content') is None or m.get('content') == '':
                        m['content'] = "{}"

            # Step 2: Determine Auth
            google_key, _ = get_api_keys()
            auth_header = self.headers.get('Authorization')
            if not auth_header or auth_header.strip() in ['Bearer', 'Bearer null', 'Bearer undefined']:
                auth_header = f"Bearer {google_key}"
            elif not auth_header.startswith("Bearer "):
                auth_header = f"Bearer {auth_header.strip()}"

            is_stream = payload.get('stream', False)
            response = None
            last_error = None
            max_retries = 5
            retry_delay = 1.5
            current_model = payload.get('model', 'gemini-3.1-flash-lite')

            # Step 3: Pure Retries with Adaptive Backoff & In-Family Fallback to Healthy Model
            for attempt in range(max_retries):
                req = urllib.request.Request(
                    GOOGLE_URL,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json', 'Authorization': auth_header, 'User-Agent': 'Mozilla/5.0'}
                )
                try:
                    response = urllib.request.urlopen(req, timeout=30)
                    if response:
                        break
                except urllib.error.HTTPError as e:
                    last_error = e
                    if e.code in [429, 503, 500]:
                        print(f"[Gemini Proxy Auto-Smoother] Model '{payload.get('model')}' rate-limited ({e.code}). (Attempt {attempt+1}/{max_retries})...", file=sys.stderr)
                        # If a specific model is quota exhausted, switch payload to healthy gemini-3.1-flash-lite
                        if attempt >= 2 and payload.get('model') != 'gemini-3.1-flash-lite':
                            print(f"[Gemini Proxy Auto-Smoother] Switching from '{payload.get('model')}' to active 'gemini-3.1-flash-lite'...", file=sys.stderr)
                            payload['model'] = 'gemini-3.1-flash-lite'
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.4, 6.0)
                    else:
                        raise e
                except Exception as e:
                    last_error = e
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.4, 6.0)

            if not response:
                if isinstance(last_error, urllib.error.HTTPError):
                    raise last_error
                else:
                    raise Exception(str(last_error))

            self.send_response(response.status)
            for k, v in response.getheaders():
                if k.lower() not in ['transfer-encoding', 'content-length']:
                    self.send_header(k, v)
            self.send_header('Access-Control-Allow-Origin', '*')

            if is_stream:
                self.end_headers()
                for line in response:
                    line_str = line.decode('utf-8', errors='ignore')
                    if line_str.startswith('data: ') and not line_str.startswith('data: [DONE]'):
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
    print(f"[Gemini Proxy] Multithreaded Streaming Thought-Signature Proxy running on http://127.0.0.1:{port}/v1")
    server.serve_forever()

if __name__ == '__main__':
    run_proxy()
