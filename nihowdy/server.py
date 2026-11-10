"""Loopback-only web application. Run with python -m nihowdy.server."""
import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .audio import Audio
from .content import ROOT
from .services import ContentService, Proofreader
from .store import Store


class Handler(BaseHTTPRequestHandler):
    server_version = "NiHowdy/1"

    def send_data(self, status, data, content_type="application/json; charset=utf-8", download=False):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="ni-howdy-backup.json"')
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        host = self.headers.get("Host", "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://localhost:{self.server.server_port}", f"http://127.0.0.1:{self.server.server_port}"):
            return False
        return self.headers.get("Sec-Fetch-Site") != "cross-site"

    def do_GET(self):
        try:
            if not self.allowed():
                return self.send_data(403, {"error":"This application only accepts local requests."})
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            store = self.server.store
            if path == "/api/state":
                state = store.state()
                state["services"] = {"audio":self.server.audio.available(), "llm":self.server.content.enabled()}
                return self.send_data(200, state)
            if path == "/api/search":
                return self.send_data(200, {"results":store.search(query.get("q", [""])[0])})
            if path == "/api/ime":
                return self.send_data(200, {"candidates":store.ime(query.get("q", [""])[0])})
            if path == "/api/backup":
                return self.send_data(200, store.backup(), download=True)
            if path == "/api/audio":
                item = store.audio_item(query.get("prompt", [""])[0])
                audio = self.server.audio.render(item)
                return self.send_data(200, audio.read_bytes(), "audio/wav")
            if path == "/api/example":
                # Separate worked example, never the answer to a graded prompt.
                glyph = store.hanzi["木"]
                return self.send_data(200, {"text":"木", "pinyin":"mù", "english":"wood", "strokes":glyph["strokes"],
                                            "phrase":"我喝水。", "phrase_pinyin":"wǒ hē shuǐ", "phrase_english":"I drink water."})
            filename = "index.html" if path == "/" else path.lstrip("/")
            root = ROOT / "web"
            asset = (root / filename).resolve()
            if not asset.is_relative_to(root) or not asset.is_file():
                return self.send_data(404, {"error":"Not found"})
            return self.send_data(200, asset.read_bytes(), mimetypes.guess_type(asset)[0] or "application/octet-stream")
        except (ValueError, KeyError) as exc:
            self.send_data(400, {"error":str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            print(f"Request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            self.send_data(503, {"error":"The local service could not complete this request. Your learning progress has not been changed. Check the terminal and retry."})

    def do_POST(self):
        try:
            if not self.allowed():
                return self.send_data(403, {"error":"This application only accepts local requests."})
            length = int(self.headers.get("Content-Length", "0"))
            if length > 20_000_000 or length < 0:
                return self.send_data(413, {"error":"Request is too large."})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send_data(415, {"error":"Send JSON content."})
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object.")
            store = self.server.store
            path = urlparse(self.path).path
            if path == "/api/session":
                result = store.new_session()
            elif path == "/api/prompt":
                result = store.next_prompt(body.get("mode"))
            elif path == "/api/answer":
                result = store.answer(body.get("id"), body)
            elif path == "/api/info":
                result = store.info(body.get("id"))
            elif path == "/api/settings":
                result = store.update_settings(body)
            elif path == "/api/add":
                result = store.add(body)
                if result.get("item") and result["item"]["kind"] == "word" and self.server.content.enabled():
                    try:
                        self.server.content.explain(result["item"]["id"])
                    except Exception:
                        result["message"] += " Explanation generation is pending; retry from the library."
            elif path == "/api/explain":
                result = self.server.content.explain(body.get("id"))
            elif path == "/api/validate":
                result = self.server.content.validate_pending(body.get("id"))
            elif path == "/api/proofread":
                text = body.get("text", "")
                if not isinstance(text, str) or len(text) > 2000:
                    raise ValueError("Use at most 2,000 characters.")
                result = self.server.proofreader.check(text, bool(body.get("phrase")))
            elif path == "/api/restore":
                result = store.restore(body)
            else:
                return self.send_data(404, {"error":"Not found"})
            return self.send_data(200, result)
        except (ValueError, KeyError, TypeError) as exc:
            self.send_data(400, {"error":str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            print(f"Request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            self.send_data(503, {"error":"The service could not complete the request. Please retry. External content services may need configuration."})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=os.environ.get("NIHOWDY_DATA_DIR", str(ROOT / ".data")))
    args = parser.parse_args()
    directory = Path(args.data_dir)
    server = None
    try:
        print("Loading character data…", flush=True)
        store = Store(directory / "nihowdy.sqlite")
        store.import_dictionary(progress=lambda message: print(message, flush=True))
        print("Preparing local spelling and grammar checks…", flush=True)
        proofreader = Proofreader(store)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
        server.store = store
        server.audio = Audio(directory)
        server.content = ContentService(store)
        server.proofreader = proofreader
        print(f"Ni-howdy is ready: http://localhost:{args.port}\nPress Ctrl+C to stop.", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nNi-howdy stopped. Run ./run.sh to start again.", flush=True)
    finally:
        if server is not None:
            server.server_close()


if __name__ == "__main__":
    main()
