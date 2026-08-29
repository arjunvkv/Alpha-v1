import urllib.request, json, os, sys, time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PROXY_LOG_PATH = r"C:\Trading\Alpha\logs\gemini_proxy_stream.log"
os.makedirs(os.path.dirname(PROXY_LOG_PATH), exist_ok=True)

def record_proxy_event(event_type: str, details: dict):
    try:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": now_ts,
            "event": event_type,
            **details
        }
        with open(PROXY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{now_ts}] === [{event_type.upper()}] ===\n{json.dumps(entry, indent=2)}\n\n")
    except Exception as e:
        print(f"[Proxy Log Error] {e}", file=sys.stderr)

SIGNATURE_CACHE = {}
FUNCTION_NAME_CACHE = {}
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# Configured Gemini Keys Pool with Zero-Restart Hot-Reloading
KEYS_CONFIG_PATH = os.path.expanduser("~/.config/opencode/gemini_keys.json")
_LAST_CFG_MTIME = 0
GEMINI_KEYS = []
ACTIVE_KEY_INDEX = 0

def reload_gemini_keys_if_changed():
    global GEMINI_KEYS, ACTIVE_KEY_INDEX, _LAST_CFG_MTIME
    if os.path.exists(KEYS_CONFIG_PATH):
        try:
            mtime = os.path.getmtime(KEYS_CONFIG_PATH)
            if mtime != _LAST_CFG_MTIME or not GEMINI_KEYS:
                with open(KEYS_CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                    d = json.load(f)
                    GEMINI_KEYS = d.get("keys", [])
                    ACTIVE_KEY_INDEX = d.get("active_index", 0)
                    _LAST_CFG_MTIME = mtime
                    if ACTIVE_KEY_INDEX >= len(GEMINI_KEYS):
                        ACTIVE_KEY_INDEX = 0
        except Exception:
            pass
    if not GEMINI_KEYS:
        env_k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or ""
        if env_k:
            GEMINI_KEYS = [env_k.strip()]
            ACTIVE_KEY_INDEX = 0

def save_gemini_keys_state():
    global GEMINI_KEYS, ACTIVE_KEY_INDEX, _LAST_CFG_MTIME
    try:
        data = {"keys": GEMINI_KEYS, "active_index": ACTIVE_KEY_INDEX}
        with open(KEYS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        _LAST_CFG_MTIME = os.path.getmtime(KEYS_CONFIG_PATH)
    except Exception:
        pass

def get_active_gemini_key():
    reload_gemini_keys_if_changed()
    return GEMINI_KEYS[ACTIVE_KEY_INDEX] if GEMINI_KEYS else ""

def rotate_default_gemini_key():
    global ACTIVE_KEY_INDEX, GEMINI_KEYS
    reload_gemini_keys_if_changed()
    if not GEMINI_KEYS:
        return ""
    old_idx = ACTIVE_KEY_INDEX
    ACTIVE_KEY_INDEX = (ACTIVE_KEY_INDEX + 1) % len(GEMINI_KEYS)
    save_gemini_keys_state()
    new_key = GEMINI_KEYS[ACTIVE_KEY_INDEX]
    print(f"\n⚡ [Gemini Proxy Zero-Restart Rotator] Key #{old_idx} hit rate-limits. Seamlessly swapped to Key #{ACTIVE_KEY_INDEX} ({new_key[:14]}...) without restarting OpenCode!\n", file=sys.stderr)
    return new_key

def get_api_keys():
    google_k = get_active_gemini_key()
    groq_k = os.environ.get("GROQ_API_KEY") or ""
    return google_k.strip(), groq_k.strip()

def compress_and_optimize_context(messages, min_turns_to_compress=12, max_chars_safe=80000):
    """
    Intelligent Auto-Compress Mechanism for OpenCode Trading Sessions.
    - NEVER compresses fresh or short sessions (len(messages) < min_turns_to_compress).
    - Caps individual massive dossier messages (>8000 chars) to prevent 413 Payload errors.
    - Only summarizes historical middle turns when conversation history is truly long (>= 12 turns).
    """
    if not messages or len(messages) < min_turns_to_compress:
        # For fresh or short sessions, keep messages completely intact (only trim massive raw blobs)
        cleaned = []
        for m in messages:
            cm = dict(m)
            c = cm.get('content')
            if isinstance(c, str) and len(c) > 12000 and cm.get('role') != 'system':
                cm['content'] = c[:4000] + "\n\n...[RAW DATA BLOB TRUNCATED]...\n\n" + c[-2000:]
            cleaned.append(cm)
        return cleaned

    # Clean individual oversized messages in the payload
    cleaned_messages = []
    for m in messages:
        cm = dict(m)
        c = cm.get('content')
        if isinstance(c, str) and len(c) > 8000 and cm.get('role') != 'system':
            cm['content'] = c[:3500] + "\n\n...[HISTORICAL DOSSIER TABLES COMPRESSED]...\n\n" + c[-1500:]
        cleaned_messages.append(cm)
    messages = cleaned_messages

    total_chars = sum(len(str(m.get('content', ''))) for m in messages)
    if total_chars < max_chars_safe:
        return messages

    # Keep root message and tail messages
    tail_count = 6
    start_tail_idx = max(1, len(messages) - tail_count)
    
    # Ensure start_tail_idx does NOT slice inside an active tool_call -> tool result pair
    while start_tail_idx > 1 and messages[start_tail_idx].get('role') == 'tool':
        start_tail_idx -= 1

    middle_messages = messages[1:start_tail_idx]
    tail_messages = messages[start_tail_idx:]
    first_msg = messages[0]

    if not middle_messages or len(middle_messages) < 4:
        return messages

    # Extract high-density structured facts from middle_messages
    positions_info = []
    market_levels = []
    patterns_recorded = []
    decisions_made = []

    for m in middle_messages:
        role = m.get('role', '')
        content = str(m.get('content', ''))
        
        if role == 'tool':
            name = m.get('name', '')
            if 'account_status' in name or 'equity' in content.lower():
                try:
                    d = json.loads(content)
                    eq = d.get('equity') or d.get('balance')
                    pos = d.get('positions', [])
                    if eq:
                        positions_info.append(f"FTMO Account Equity: ${eq} | Active Positions: {len(pos)}")
                except Exception:
                    pass
            elif 'record_pattern' in name:
                patterns_recorded.append(content[:150])
            elif 'execute_trade' in name:
                decisions_made.append(f"Trade Execution: {content[:150]}")
        elif role == 'assistant':
            if any(kw in content for kw in ['ORDER', 'BUY', 'SELL', 'WAIT', 'HOLD', 'REJECT']):
                for line in content.splitlines():
                    l_str = line.strip()
                    if any(kw in l_str for kw in ['**EXECUTIVE', 'Consensus:', 'Conviction:', 'DECISION:', 'TRADE:']):
                        decisions_made.append(l_str[:120])
            if any(kw in content for kw in ['Demand:', 'Supply:', 'Pivots:', 'VWAP:']):
                for line in content.splitlines():
                    if any(kw in line for kw in ['Demand:', 'Supply:', 'Pivots:', 'VWAP:']):
                        market_levels.append(line.strip()[:120])

    def _dedup(lst, max_items=5):
        seen = set()
        res = []
        for x in lst:
            if x and x not in seen:
                seen.add(x)
                res.append(x)
                if len(res) >= max_items:
                    break
        return res

    parts = []
    if positions_info:
        parts.append(f"**1. Account & Position State:**\n  • " + "\n  • ".join(_dedup(positions_info, 3)))
    if market_levels:
        parts.append(f"**2. Key Market Structure & Levels:**\n  • " + "\n  • ".join(_dedup(market_levels, 4)))
    if patterns_recorded:
        parts.append(f"**3. Pattern Book & Research Memory:**\n  • " + "\n  • ".join(_dedup(patterns_recorded, 3)))
    if decisions_made:
        parts.append(f"**4. Audited Desk Decisions & Flow:**\n  • " + "\n  • ".join(_dedup(decisions_made, 4)))

    if not parts:
        return messages

    compressed_text = (
        f"### 🗜️ [SYSTEM CONTEXT COMPRESSION SUMMARY: CUMULATIVE DESK MEMORY]\n"
        f"*(Auto-compressed {len(middle_messages)} historical turns to eliminate context bloat)*\n\n" +
        "\n\n".join(parts) + "\n---"
    )

    compressed_msg = {
        "role": "user",
        "content": compressed_text
    }

    print(f"[Gemini Proxy Context Auto-Compressor] Compressed {len(middle_messages)} bloated turns into structured memory bridge. Total active turns: {1 + 1 + len(tail_messages)}.", file=sys.stderr)
    return [first_msg, compressed_msg] + tail_messages

def normalize_tool_name(model_name: str, declared_names: list) -> str:
    if not model_name or not declared_names:
        return model_name
    if model_name in declared_names:
        return model_name
    for d in declared_names:
        if d.endswith(f"_{model_name}") or d.endswith(model_name):
            return d
    return model_name


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

            # Step 0: Intelligent Auto-Compress Mechanism
            messages = payload.get('messages', [])
            if messages:
                messages = compress_and_optimize_context(messages, min_turns_to_compress=12, max_chars_safe=80000)
                payload['messages'] = messages

            start_t = time.time()
            record_proxy_event("inbound_request", {
                "model": payload.get('model', 'gemini-3.5-flash-lite'),
                "turn_count": len(messages),
                "last_message_preview": (messages[-1].get("content")[:300] if messages else ""),
                "tools_declared": declared_tool_names
            })

            # Step 1: Re-inject thought_signatures and normalize function names/tool messages
            for m in messages:
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
                    if not m.get('name') or m['name'].strip() == "":
                        m['name'] = FUNCTION_NAME_CACHE.get(cid, default_tool_name)
                    if m.get('content') is None or m.get('content') == '':
                        m['content'] = "{}"

            # Step 2: Determine Auth
            auth_header = f"Bearer {get_active_gemini_key()}"
            is_stream = payload.get('stream', False)
            response = None
            last_error = None
            max_retries = 6
            retry_delay = 1.0
            consecutive_429 = 0

            # Step 3: Pure Google Gemini Execution with 3-Strike Permanent Key Promotion
            for attempt in range(max_retries):
                current_key = get_active_gemini_key()
                auth_header = f"Bearer {current_key}"
                
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
                        consecutive_429 += 1
                        print(f"[Gemini Proxy Pure-Retry] Key #{ACTIVE_KEY_INDEX} ({current_key[:12]}...) rate-limited ({e.code}). Attempt {attempt+1}/{max_retries}...", file=sys.stderr)
                        
                        # 3-Strike Rule: If current default key rate limits 3 times, promote next key as permanent default!
                        if consecutive_429 >= 3:
                            new_k = rotate_default_gemini_key()
                            consecutive_429 = 0
                            retry_delay = 0.5  # Immediately try new default key
                        else:
                            time.sleep(retry_delay)
                            retry_delay = min(retry_delay * 1.5, 6.0)
                    else:
                        raise e
                except Exception as e:
                    last_error = e
                    print(f"[Gemini Proxy Network Handler] Network hiccup ({e}). Retrying in {retry_delay:.1f}s...", file=sys.stderr)
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 6.0)

            if response is None:
                raise last_error or RuntimeError("Failed all Gemini API retry attempts.")

            self.send_response(200)
            for k, v in response.getheaders():
                if k.lower() not in ['transfer-encoding', 'content-length']:
                    self.send_header(k, v)
            self.send_header('Access-Control-Allow-Origin', '*')

            if is_stream:
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                accumulated_content = []
                accumulated_reasoning = []
                accumulated_tool_calls = {}
                for line in response:
                    line_str = line.decode('utf-8', errors='ignore')
                    if line_str.startswith('data: ') and not line_str.startswith('data: [DONE]'):
                        try:
                            chunk_data = json.loads(line_str[6:].strip())
                            choices = chunk_data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                if delta.get('content'):
                                    accumulated_content.append(delta['content'])
                                if delta.get('reasoning') or delta.get('thought'):
                                    accumulated_reasoning.append(delta.get('reasoning') or delta.get('thought'))
                                tcs = delta.get('tool_calls', [])
                                for tc in tcs:
                                    idx = tc.get('index', 0)
                                    if idx not in accumulated_tool_calls:
                                        accumulated_tool_calls[idx] = {'id': '', 'name': '', 'arguments': '', 'thought_signature': ''}
                                    if tc.get('id'):
                                        accumulated_tool_calls[idx]['id'] = tc['id']
                                    fn = tc.get('function', {})
                                    if fn.get('name'):
                                        normalized_name = normalize_tool_name(fn['name'], declared_tool_names)
                                        fn['name'] = normalized_name
                                        accumulated_tool_calls[idx]['name'] = normalized_name
                                    if fn.get('arguments'):
                                        accumulated_tool_calls[idx]['arguments'] += fn['arguments']
                                    sig = tc.get('extra_content', {}).get('google', {}).get('thought_signature')
                                    if sig:
                                        accumulated_tool_calls[idx]['thought_signature'] = sig
                                        cid = tc.get('id') or accumulated_tool_calls[idx]['id']
                                        if cid:
                                            SIGNATURE_CACHE[cid] = sig
                                line = f"data: {json.dumps(chunk_data)}\n\n".encode('utf-8')
                        except Exception:
                            pass
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        break

                elapsed_ms = round((time.time() - start_t) * 1000, 1)
                record_proxy_event("outbound_stream_complete", {
                    "status": response.status,
                    "latency_ms": elapsed_ms,
                    "model": payload.get('model', 'gemini-3.5-flash-lite'),
                    "thought_reasoning": "".join(accumulated_reasoning) if accumulated_reasoning else None,
                    "content": "".join(accumulated_content) if accumulated_content else None,
                    "tool_calls": list(accumulated_tool_calls.values()) if accumulated_tool_calls else []
                })
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
                            fn = tc.get('function', {})
                            if fn.get('name'):
                                fn['name'] = normalize_tool_name(fn['name'], declared_tool_names)
                            sig = tc.get('extra_content', {}).get('google', {}).get('thought_signature')
                            if cid and sig:
                                SIGNATURE_CACHE[cid] = sig
                        
                        res_data = json.dumps(res_json).encode('utf-8')
                        elapsed_ms = round((time.time() - start_t) * 1000, 1)
                        record_proxy_event("outbound_response", {
                            "status": response.status,
                            "latency_ms": elapsed_ms,
                            "role": msg.get("role"),
                            "thought_reasoning": msg.get("reasoning") or msg.get("thought"),
                            "content": msg.get("content"),
                            "tool_calls": tcs,
                            "raw_response": res_json
                        })
                except Exception as e:
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
