"""Launcher: python run.py [--open FILE] [--port 8765] [--no-browser]"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tap3studio import tapfile                     # noqa: E402
from tap3studio import server                      # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="TAP3 Studio launcher")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", dest="open_path", default="")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if args.open_path:
        if not os.path.exists(args.open_path):
            print(f"file not found: {args.open_path}")
            return 2
        doc = tapfile.open_document(args.open_path)
        server.STATE["doc"] = doc
        server.STATE["path"] = os.path.abspath(args.open_path)
        print(f"loaded {args.open_path}: {doc.release_label}, {len(doc.events())} records")

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"TAP3 Studio listening on {url}")
    server.serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
