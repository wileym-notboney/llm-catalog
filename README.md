# LLM Feed Dashboard

One merged, chronological feed of news and changelogs from Anthropic, OpenAI and
Nous Research, in the Mythological Punk theme. One stdlib-only Python process serves
the page and refreshes the data itself every day. No Docker, no cron, no Node at
runtime.

## Run

Needs Python 3.10+ and nothing else.

```sh
python3 serve.py                              # three free feeds only
FIRECRAWL_API_KEY=fc-... python3 serve.py     # also scrapes Anthropic news + Nous blog
```

Open <http://127.0.0.1:8787>. On start it pulls immediately if the last pull is
over 24 hours old, then once a day at `PULL_AT`.

## Pages

| Route      | Page          | Data                                                                 |
| ---------- | ------------- | -------------------------------------------------------------------- |
| `#/`       | Feed          | `/items.json`, refreshed by the daily pull                           |
| `#/models` | Model catalog | `app/src/models.json`, bundled into the page — no network at runtime |

The model catalog lists current models from Anthropic, OpenAI and Ollama (local,
open-weight) with each one's role, specs, strengths and weaknesses. It is
hand-curated editorial judgement, not scraped: no provider API returns "what is
this model bad at". The page shows the `reviewedAt` date so you can see how stale
it is. To update it, edit `app/src/models.json` and rebuild:

```sh
.venv/bin/python -m pytest tests/test_models_catalog.py   # validates the shape
cd app && pnpm run bundle                                  # rewrites app/dist/index.html
```

| Setting             | Default              | Meaning                                                                                                                                   |
| ------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `FIRECRAWL_API_KEY` | unset                | Enables the two scraped sources (1 credit each per pull, about 60 credits a month). Without it they show as stale. Never commit it.       |
| `PULL_AT`           | `06:00`              | Daily pull time, `HH:MM` in UTC                                                                                                           |
| `DATA_DIR`          | `./data`             | Where `items.json`, `state.json`, `attempts.json` and `.writer.lock` live. Must be a local filesystem: NFS, SMB and sshfs are unsupported |
| `--host` / `--port` | `127.0.0.1` / `8787` | Bind address. Bind to `0.0.0.0` only on a network you trust: there is no auth.                                                            |

By hand: `python3 -m feed pull` (fetch, merge, prune) and `python3 -m feed prune`
(prune only, no network).

## Paid attempts, contention and bad state

- **One paid attempt per source per UTC day.** Each Firecrawl source (Anthropic news, Nous
  blog) gets at most one request per UTC day. The attempt is recorded in
  `data/attempts.json` _before_ the request and counts whether it succeeds, fails or the
  process dies, so a crash, restart or manual pull cannot spend a second credit. A second
  pull the same day defers only that source (shown stale, old items kept) while the free
  feeds still refresh. The next UTC day allows a new attempt.
- **One writer per data directory.** `pull` and `prune` take a lock on
  `DATA_DIR/.writer.lock`. If the server's scheduler or another command already holds it,
  the CLI prints `error: another writer owns <dir>; nothing was fetched or written` and
  exits 3;
  the scheduler logs a warning and keeps its one-minute tick without touching `lastPull`.
  The kernel frees the lock when its holder dies, so there is never a stale lock to clear.
  This serializes writers on one host only: `flock` does not coordinate across hosts, which
  is why `DATA_DIR` must be on a local filesystem.
- **Corrupt or misshapen state.** A bad `items.json`, `state.json` or `attempts.json` is
  refused with an error naming the file and exit 2. Nothing is overwritten; fix or remove
  the file yourself.

| Exit code | Meaning                                |
| --------- | -------------------------------------- |
| 0         | ok (some sources may be stale)         |
| 1         | every source failed                    |
| 2         | a state file is corrupt or misshapen   |
| 3         | another writer owns the data directory |

## What it keeps

- Items older than **10 days** are pruned daily, except the 3 newest per lab.
- Pruned ids are remembered for 90 days (`data/state.json`) so a source that still
  lists them cannot bring them back.
- A source that fails keeps its last good items and shows a "stale" banner.
- Nous's blog has no dates, so its posts show "first seen" and age out 10 days after
  they first appear. The first run therefore shows its current featured posts as new.

## Keep it running

`serve.py` does not daemonize. Supervise it with the host's tool.

macOS, `~/Library/LaunchAgents/com.llm-feed.plist` (mode 600 if it holds the key),
then `launchctl load ~/Library/LaunchAgents/com.llm-feed.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.llm-feed</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>/path/to/llm-catalog/serve.py</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/llm-catalog</string>
  <key>EnvironmentVariables</key><dict>
    <key>FIRECRAWL_API_KEY</key><string>fc-...</string>
  </dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>
```

Linux, `/etc/systemd/system/llm-feed.service` with `/etc/llm-feed.env` (mode 600)
holding `FIRECRAWL_API_KEY=fc-...`:

```ini
[Unit]
Description=LLM feed dashboard
After=network-online.target

[Service]
WorkingDirectory=/path/to/llm-catalog
EnvironmentFile=/etc/llm-feed.env
ExecStart=/usr/bin/python3 /path/to/llm-catalog/serve.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Reach it from the LAN (Tailscale)

`serve.py` stays bound to `127.0.0.1` and has no auth, so don't bind it to `0.0.0.0`.
To reach the dashboard from other devices, front the loopback listener with Tailscale —
authentication is handled by your tailnet, and nothing in `serve.py` changes:

```sh
tailscale serve --bg 8787        # serves http://127.0.0.1:8787 to your tailnet over HTTPS
tailscale serve status           # show what is exposed
tailscale serve --https=443 off  # stop exposing it
```

This keeps the page private to devices on your tailnet. Do **not** use `tailscale funnel`,
which would publish it to the public internet — the dashboard has no authentication of its own.

## Develop

```sh
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest
```

Frontend regression checks use Node's built-in test runner and the existing TypeScript
dev dependency: `cd app && pnpm test`. They run offline and cover catalog validation,
calendar dates, and visit tracking after successful or failed loads.

The UI source is in `app/` (React + Parcel + Tailwind). `app/dist/index.html` is the
committed build, so a fresh clone runs without Node. After changing the UI:

```sh
cd app && pnpm install && pnpm run bundle   # rewrites app/dist/index.html
```

For a live-reload loop while editing, `cd app && pnpm run dev` starts Parcel's dev server
on <http://localhost:1234> (its output goes to a throwaway `.bundle/`, so the committed
`app/dist/index.html` is never touched — only `pnpm run bundle` rewrites that).

Theme tokens come from `~/.hermes/desktop-plugins/mythological-punk/mythological-punk.yaml`
and live in `app/src/theme.css`. Dark only, system fonts, no external assets.
