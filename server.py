#!/usr/bin/env python3
"""
GBP Content Calendar - FREE Server using Groq API
==================================================
SETUP:
  1. Go to https://console.groq.com  (free signup)
  2. Click API Keys -> Create API Key
  3. Paste key below where it says gsk_YOUR_KEY_HERE
  4. Run:  python server.py
  5. Open: http://localhost:8080

TEST YOUR KEY:  http://localhost:8080/test
"""

import os
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── CONFIG — set these as environment variables on Railway ─────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL        = os.environ.get("MODEL", "llama-3.3-70b-versatile")
PORT         = int(os.environ.get("PORT", 8080))   # Railway sets PORT automatically
HOST         = "0.0.0.0"                           # Must be 0.0.0.0 for Railway
# ──────────────────────────────────────────────────────────────

GROQ_URL  = "https://api.groq.com/openai/v1/chat/completions"
HTML_FILE = "GBP_Generator_Standalone.html"


def call_groq(messages, max_tokens=900):
    """Call Groq API and return response text. Raises on error."""
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.8,
        "max_tokens": max_tokens,
        # NOTE: NO response_format here — causes 403 on some models
    }).encode()

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + GROQ_API_KEY.strip(),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    return data["choices"][0]["message"]["content"]


def check_config():
    key = GROQ_API_KEY.strip()
    if not key or not key.startswith("gsk_"):
        print("  !! GROQ_API_KEY not set or invalid.")
        print("  On Railway: go to Variables tab and add GROQ_API_KEY")
        return False
    print(f"  Key: {key[:16]}...  Model: {MODEL}  Port: {PORT}")
    return True


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        status = args[1] if len(args) > 1 else ""
        print(f"  {self.command:6} {self.path:20} -> {status}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        # ── /image?prompt=... — proxy image generation ──────────
        if self.path.startswith("/image"):
            from urllib.parse import urlparse, parse_qs, quote
            parsed_path = urlparse(self.path)
            params = parse_qs(parsed_path.query)
            prompt = params.get("prompt", ["professional business photo"])[0]
            seed   = params.get("seed", ["42"])[0]

            # Try multiple free providers in order
            providers = [
                f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1200&height=900&nologo=true&seed={seed}&model=flux",
                f"https://pollinations.ai/p/{quote(prompt)}?width=1200&height=900&seed={seed}",
                f"https://source.unsplash.com/1200x900/?{quote(','.join(prompt.split()[:4]))}",
            ]

            img_data = None
            content_type = "image/jpeg"

            for url in providers:
                try:
                    print(f"  Trying: {url[:80]}...")
                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                            "Referer": "https://pollinations.ai/",
                        },
                        method="GET"
                    )
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        img_data = resp.read()
                        content_type = resp.headers.get("Content-Type", "image/jpeg")
                    if img_data and len(img_data) > 5000:
                        print(f"  Image OK: {len(img_data)} bytes from {url[:50]}")
                        break
                    else:
                        print(f"  Too small ({len(img_data) if img_data else 0} bytes), trying next...")
                        img_data = None
                except Exception as e:
                    print(f"  Provider failed: {e}")
                    img_data = None
                    continue

            if img_data:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(img_data)))
                self.send_cors()
                self.end_headers()
                self.wfile.write(img_data)
            else:
                print("  All image providers failed")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "All image providers failed"}).encode())
            return

        # ── /test ────────────────────────────────────────────────
        if self.path == "/test":
            print("  Running API key test...")
            try:
                key = GROQ_API_KEY.strip()
                if "YOUR_KEY_HERE" in key:
                    raise Exception("API key not set — edit server.py and add your Groq key")
                if not key.startswith("gsk_"):
                    raise Exception(f"Key looks wrong — Groq keys start with gsk_ (yours: {key[:10]}...)")

                result = call_groq([
                    {"role": "user", "content": 'Reply with exactly this JSON: {"status":"ok","message":"Groq is working!"}'}
                ], max_tokens=50)

                body = f"""<html><body style="font-family:sans-serif;padding:40px;background:#0c1610;color:#52b788">
<h2>✅ Groq API Test PASSED</h2>
<p>Your key works! Response: <code>{result}</code></p>
<p>Model: <strong>{MODEL}</strong></p>
<p><a href="/" style="color:#52b788">← Back to app</a></p>
</body></html>""".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
                print(f"  Test PASSED: {result[:80]}")

            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                body = f"""<html><body style="font-family:sans-serif;padding:40px;background:#1a0a0a;color:#ff8888">
<h2>❌ Groq API Test FAILED — HTTP {e.code}</h2>
<p><strong>Error:</strong> {err_body}</p>
<h3>How to fix:</h3>
<ul>
<li>403 = Invalid API key. Go to <a href="https://console.groq.com" style="color:#f4a261">console.groq.com</a>, create a new key, paste it in server.py</li>
<li>401 = Key missing or wrong format. Must start with gsk_</li>
<li>429 = Rate limit. Wait 1 minute and try again.</li>
</ul>
<p>Current key starts with: <code>{GROQ_API_KEY.strip()[:16]}...</code></p>
</body></html>""".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
                print(f"  Test FAILED: HTTP {e.code} — {err_body[:200]}")

            except Exception as e:
                body = f"""<html><body style="font-family:sans-serif;padding:40px;background:#1a0a0a;color:#ff8888">
<h2>❌ Test FAILED</h2>
<p>{e}</p>
</body></html>""".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
                print(f"  Test FAILED: {e}")
            return

        # ── / — serve the app ────────────────────────────────────
        if self.path in ("/", "/index.html"):
            try:
                with open(HTML_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_cors()
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                body = b"<h2 style='font-family:sans-serif;padding:40px'>GBP_Generator_Standalone.html not found. Put it in the same folder as server.py</h2>"
                self.send_response(404)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/messages":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            messages = body.get("messages", [])

            text = call_groq(messages)
            print(f"  GROQ RESPONSE: {repr(text[:300])}")

            result = json.dumps({
                "content": [{"type": "text", "text": text}]
            }).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(result)

        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"  !! Groq HTTP {e.code}: {err_body[:300]}")

            if e.code == 429:
                user_msg = "Rate limit hit — wait 60 seconds and click Generate again."
            elif e.code == 403:
                user_msg = "API key rejected (403). Check GROQ_API_KEY environment variable."
            elif e.code == 401:
                user_msg = "Invalid API key (401). Must start with gsk_"
            else:
                user_msg = f"Groq error {e.code}: {err_body[:200]}"

            msg = json.dumps({
                "content": [{"type": "text", "text": "{}"}],
                "_error": user_msg
            }).encode()
            self.send_response(200)  # Return 200 so JS gets the message
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(msg)

        except Exception as e:
            print(f"  !! Error: {e}")
            msg = json.dumps({
                "content": [{"type": "text", "text": "{}"}]
            }).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(msg)


if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  GBP Content Calendar — Railway Edition")
    print(f"{'='*55}")
    check_config()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"\n  Listening on {HOST}:{PORT}")
    print(f"  Test: /test")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
