---
title: Daily refresh
updated: 2026-10-24
---

# Daily refresh

[← Index](README.md)

The site updates itself through a **Claude scheduled task**: a stored instruction that claude.ai runs
on a timer, each time in a fresh cloud session. It is the cloud copy of what `serve.py` does on your
computer every morning.

| Setting | Value |
| --- | --- |
| Name | LLM Feed daily refresh |
| ID | `trig_01TvH71siEFkKQr7uiyCsTpe` |
| Schedule | every day at **05:40 UTC** (cron `40 5 * * *`) |
| Runs in | a new cloud session each time, in the same cloud environment as the setup session |
| Notifies | a push notification when each run finishes |
| Publishes to | <https://claude.ai/artifact/XBtWYqy8mpKe1HvfcRucDb> |

Why 05:40 and not 06:00 like `serve.py`: many scheduled jobs start exactly on the hour, which can delay
them, so the time was moved 20 minutes earlier. Ask Claude to change it if you want 06:00 exactly.

## What each run does

1. Clones `wileym-notboney/llm-catalog` and checks out `feature/model-codex-site` (or `main` once that
   branch is merged and gone).
2. Runs the repo's own pipeline once: `python3 -m feed pull`. No retries.
3. Builds the page: `python3 site/build.py`. If the build refuses a corrupt file, it stops and does
   not publish.
4. Reads the site, then publishes `site/index.html` to the same URL.
5. Throws away the rebuilt file in its copy of the repo. It never commits, pushes or opens pull
   requests.
6. Reports which sources worked, which failed and why, and how many stories the feed has.

The first test run (24 Oct 2026, 10:13 UTC) did all six steps and published version 12 with 32
stories.

## Check, change, pause, delete

- **See runs:** the scheduled tasks list in claude.ai, or ask Claude "list my scheduled tasks".
- **Run it now:** ask Claude to fire the task. Note: a second pull on the same UTC day re-fetches the
  free sources; the paid ones are limited to once per run.
- **Change time or steps:** ask Claude to update the task (it keeps its history).
- **Pause:** ask Claude to disable it. **Delete:** ask Claude to delete it; this cannot be undone.

## Cost

- Each run uses some of your Claude plan usage (the test run was a short session).
- With `FIRECRAWL_API_KEY` set: 2 Firecrawl credits per run, about 60 a month. Without it: none.

## Limitations

Compared with `serve.py`, which keeps its memory in `data/` between pulls:

- **Each run starts with an empty `data/`.** The 10-day retention and "newest 3 per lab" rules still
  apply within a run, so the feed looks the same. But:
- **Undated posts never age out.** The Nous blog gives no dates, so each run sees its posts for the
  "first" time. They always show today's date and "(first seen)". This only matters once the
  Firecrawl key is set.
- **The once-per-day paid limit is enforced by the schedule, not by `data/attempts.json`.** One run a
  day means at most 2 credits a day; firing the task by hand adds runs.
- **`github.com` is blocked** in the current cloud environment, so Claude Code releases fail with
  HTTP 403 until it is allowed. See [Environment setup](environment-setup.md).

Related: [How the pieces fit](how-the-pieces-fit.md), [Troubleshooting](troubleshooting.md).
