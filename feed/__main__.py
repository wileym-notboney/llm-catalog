# ABOUTME: Command line for the feed package: `python3 -m feed pull` and `python3 -m feed prune`.
# ABOUTME: `pull` costs up to 2 Firecrawl credits; it exits 1 only if every source failed.
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from feed.pull import fetch_text, markdown_fetcher, run_prune, run_pull
from feed.store import StoreError, WriterBusy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m feed",
        description="Pull AI-lab news and changelogs into data/items.json.",
        epilog="Set FIRECRAWL_API_KEY to also scrape Anthropic news and the Nous blog "
        "(1 credit each). Without it those two sources are marked stale.",
    )
    parser.add_argument("--data", default=os.environ.get("DATA_DIR", "data"),
                        help="data directory (default: $DATA_DIR or ./data)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pull", help="fetch all sources, merge, then prune")
    commands.add_parser("prune", help="prune stored items only; no network")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    data_dir, now = Path(args.data), datetime.now(timezone.utc)
    try:
        if args.command == "prune":
            print(f"pruned {run_prune(data_dir, now)} items")
            return 0
        summary = run_pull(data_dir, now, fetch_text, markdown_fetcher())
    except WriterBusy:
        print(f"error: another writer owns {data_dir}; nothing was fetched or written",
              file=sys.stderr)
        return 3
    except StoreError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"ok: {', '.join(summary['ok']) or 'none'}")
    for source_id, reason in summary["failed"].items():
        print(f"failed: {source_id}: {reason}", file=sys.stderr)
    return 1 if summary["failed"] and not summary["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
