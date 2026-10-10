# 0001 — Expose the dashboard via Tailscale, not a public bind

- Status: accepted
- Date: 2026-10-10

## Context

`serve.py` binds `127.0.0.1:8787` and has **no authentication** — by design, to keep the
runtime stdlib-only and avoid any credential-in-file story. But the dashboard is meant to be
reachable from other devices on the home LAN (and, conveniently, remotely). The question was
how to reach it without bolting auth onto a deliberately simple server.

## Decision

Keep `serve.py` bound to `127.0.0.1` and expose it with **`tailscale serve`**, which fronts
the loopback listener and lets the tailnet handle authentication and transport:

```sh
tailscale serve --bg 8787
```

The bind address does not change. Exposure is an operational recipe (documented in the
README's "Reach it from the LAN"), not application code.

## Consequences

- No auth code, no secret file, no new dependency — the stdlib-only invariant holds.
- Access is scoped to the tailnet; devices authenticate through Tailscale, not the app.
- `tailscale funnel` (public internet) is explicitly **not** used — the app has no auth of
  its own, so it must never be published publicly.
- Reaching the dashboard requires Tailscale on both ends; a plain-LAN device with no tailnet
  membership cannot see it. Accepted — tailnet membership is the access-control mechanism.

## Alternatives rejected

- **Bind `0.0.0.0` and trust the LAN** — publishes an unauthenticated page to every device
  on the network; the exact exposure this avoids.
- **`0.0.0.0` + HTTP basic auth in `serve.py`** — breaks stdlib-only and forces a
  credential-in-file story the project deliberately avoids.
- **Reverse proxy (Caddy/nginx)** — adds infrastructure outside the repo; Tailscale already
  runs in the homelab and needs no config here.
