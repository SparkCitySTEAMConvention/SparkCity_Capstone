"""Loopback-only dashboard preview. Use a SELECT-only DATABASE_URL account."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from sparkcityx.database import connect_database
from sparkcityx.day5 import read_publication
from sparkcityx.day5_dashboard import render_dashboard
from sparkcityx.day5_pipeline import load_snapshot


def make_handler(bundle, connect=connect_database):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body, content_type, status = render_dashboard(bundle, live=True).encode(), "text/html; charset=utf-8", 200
            elif self.path == "/api/snapshot":
                try:
                    with connect() as connection:
                        snapshot = read_publication(connection)
                    body, content_type, status = json.dumps(snapshot, allow_nan=False).encode(), "application/json", 200
                except Exception:
                    body, content_type, status = b'{"error":"Database unavailable; last snapshot may be stale"}', "application/json", 503
            else:
                body, content_type, status = b"Not found", "text/plain", 404
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path, help="Local fallback for initial render/outages")
    parser.add_argument("--port", type=int, default=8055)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bundle = load_snapshot(args.snapshot)
    load_dotenv(root / "secrets/.env", override=False)

    print(f"Local preview: http://127.0.0.1:{args.port} (Ctrl-C to stop)")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(bundle))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
