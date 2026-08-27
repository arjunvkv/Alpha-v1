import urllib.request, json, os
from http.server import HTTPServer, BaseHTTPRequestHandler

SIGNATURE_CACHE = {}
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", ""))
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

class GeminiProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            payload = json.loads(body.decode('utf-8'))
            
            # Step 1: Re-inject cached thought_signatures into assistant messages
            messages = payload.get('messages', [])
            for m in messages:
                if m.get('role') == 'assistant' and m.get('tool_calls'):
                    for tc in m['tool_calls']:
                        cid = tc.get('id')
                        if cid and cid in SIGNATURE_CACHE:
                            tc['extra_content'] = {'google': {'thought_signature': SIGNATURE_CACHE[cid]}}

            # Step 2: Forward to Google AI Studio
            fwd_headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {GOOGLE_API_KEY}',
                'User-Agent': 'Mozilla/5.0'
            }
            req = urllib.request.Request(GOOGLE_URL, data=json.dumps(payload).encode('utf-8'), headers=fwd_headers)
            
            with urllib.request.urlopen(req, timeout=30) as res:
                res_data = res.read()
                res_json = json.loads(res_data.decode('utf-8'))
                
                # Step 3: Cache any new thought_signatures returned by Google
                choices = res_json.get('choices', [])
                if choices:
                    msg = choices[0].get('message', {})
                    tcs = msg.get('tool_calls', [])
                    for tc in tcs:
                        cid = tc.get('id')
                        sig = tc.get('extra_content', {}).get('google', {}).get('thought_signature')
                        if cid and sig:
                            SIGNATURE_CACHE[cid] = sig

                self.send_response(res.status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(res_data)))
                self.end_headers()
                self.wfile.write(res_data)

        except urllib.error.HTTPError as e:
            err_data = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(err_data)))
            self.end_headers()
            self.wfile.write(err_data)
        except Exception as e:
            err_msg = json.dumps({'error': str(e)}).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

    def log_message(self, format, *args):
        pass

def run_proxy(port=4095):
    server = HTTPServer(('127.0.0.1', port), GeminiProxyHandler)
    print(f"[Gemini Proxy] Transparent Thought-Signature Proxy running on http://127.0.0.1:{port}/v1")
    server.serve_forever()

if __name__ == '__main__':
    run_proxy()
