#!/usr/bin/env python3
# ABOUTME: Serves the dashboard (app/dist) and data/items.json, and runs the daily pull scheduler.
# ABOUTME: One stdlib-only process: `FIRECRAWL_API_KEY=... python3 serve.py [--port N]`.
from __future__ import annotations

import argparse
import functools
import logging
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from feed.pull import fetch_text, markdown_fetcher, run_pull
from feed.schedule import parse_pull_at, step

ROOT = Path(__file__).resolve().parent


class DashboardHandler(SimpleHTTPRequestHandler):
    """Static files from app/dist, plus /items.json from the data directory (nothing else)."""

    data_dir: Path

    def translate_path(self, path: str) -> str:
        if urlsplit(path).path == "/items.json":
            return str(self.data_dir / "items.json")
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def make_server(dist_dir: Path, data_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (DashboardHandler,), {"data_dir": data_dir})
    return ThreadingHTTPServer((host, port), functools.partial(handler, directory=str(dist_dir)))


def scheduler_loop(data_dir: Path, pull_at, stop: threading.Event) -> None:
    def pull(directory: Path, now: datetime) -> dict:
        return run_pull(directory, now, fetch_text, markdown_fetcher())

    while not stop.is_set():
        stop.wait(step(data_dir, datetime.now(timezone.utc), pull_at, pull))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve the LLM feed dashboard and refresh it daily.",
        epilog="Environment: FIRECRAWL_API_KEY (optional; enables the 2 scraped sources), "
        "PULL_AT=HH:MM UTC (default 06:00), DATA_DIR (default ./data).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="port (default 8787)")
    args = parser.parse_args()
    try:
        pull_at = parse_pull_at(os.environ.get("PULL_AT", "06:00"))
    except ValueError:
        parser.error("PULL_AT must look like HH:MM, for example 06:00")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    stop = threading.Event()
    threading.Thread(target=scheduler_loop, args=(data_dir, pull_at, stop), daemon=True).start()
    server = make_server(ROOT / "app" / "dist", data_dir, args.host, args.port)
    logging.info("serving on http://%s:%s (pull daily at %s UTC)", args.host, args.port, pull_at)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
