# 🐴 Dirty Truth & Dare 🔥

A private, mobile-first slow-burn truth-or-dare game for couples, powered by the
**Cassia AI** engine (a local LLM) that generates every question and dare live.

**Full spec:** see [PRD.md](PRD.md).

## Features
- **Spinning bottle** — lands on a random player.
- **Player choice** — the target picks 💜 Truth or 🔥 Dare.
- **3-truth rule** — pick truth 2× in a row and the 3rd pick is forced to a dare.
- **Dirty-secrets truth engine** — researched, escalating truth questions that
  uncover each partner's deepest secrets and desires (patterns mined from real
  couple question banks: wafflejournal, lovifycouple, stephmorris, paired, forplay).
- **Mystery pacing** — the game moves through poetic phases
  (*First Glance → Warming Up → The Oath → Unveiling → No Secrets Left*).
  Players never know where it's going; the heat number is hidden behind the phase name.
- **The Oath** — mid-game (round 5) both players swear to play completely seriously.
- **$100 penalty ledger** — skip a task or refuse to perform it and you owe your
  partner $100. The ledger keeps a running score per player.
- **10-language i18n** — English, Spanish, French, German, Italian, Portuguese,
  Hindi, Japanese, Chinese, Arabic. UI, LLM-generated content (with a dedicated
  translation pass), and TTS voices all switch to the chosen language. Arabic is RTL.
- **Multi-device rooms** — host creates a room, partner joins with a 4-letter code
  on their own device. Server-side SQLite room store; the partner's screen mirrors
  the challenge, timer, phase, and ledger via polling.
- **True two-way sync (v5.2)** — the partner's screen mirrors each timed step and
  its countdown live (PRD §4 timer promise), guest-recorded penalties land on the
  host's screen on the next poll, the oath appears mirrored without echo loops,
  and a connection glitch shows a "reconnecting" state until re-synced.
- **Chat-driven challenges (v5.2)** — ask Cassia in chat ("give me a dare") and she
  fires a real generated challenge; heat changes from chat broadcast to both devices.
- **Reload-proof room sessions** — refresh either phone mid-game and the session
  resumes automatically from server state (host returns to the waiting screen if
  the partner hasn't joined yet).
- **Secret preferences** — each player can privately (optionally) tell Cassia their
  turn-ons, unsaid fantasy, and hard boundary. Cassia weaves them in; the partner
  never sees the form.
- **Slow-burn heat (1–10)** — auto-escalates +1 each round; manual dial + chat control.
- **Timed step-by-step challenges** — each dare is a sequence of timed, detailed
  instructions; each truth is a single answerable question.
- **Drift-proof timers** — step countdowns are wall-clock based, so background-tab
  throttling can never stretch or skip time.
- **Screen stays awake** — Screen Wake Lock keeps phones on during play (auto
  re-acquired when the tab becomes visible again).
- **Installable (PWA-lite)** — web manifest + icon so players can add the game
  to their home screen; standalone portrait display, dark theme color.
- **Voice mode** — Cassia speaks challenges, steps, and "time's up" (Kokoro TTS).
- **Timer alerts** — countdown bar, last-3s beeps, chime + flash + vibration on time-up, auto-advance.
- **Cassia chat** — talk to the AI host to change heat or fire new challenges.
- **Fun layer** — WebAudio SFX, confetti, Cassia banter, heat-drama toasts, haptics.
- **Persistence** — game state survives reloads (localStorage); "New" resets.
- **Hardened for a public URL** — per-IP rate limits on the LLM/TTS endpoints *and*
  the room API (tight on join to blunt code brute-forcing, `Retry-After` on 429s),
  CSP + security headers, secrets kept out of source, guarded room joins
  (no guest hijack), race-free event sequencing, hourly room pruning.

## Architecture
- `app.py` — Flask app + Cassia AI engine (LLM + TTS plumbing, validation, fallbacks,
  language translation pass, room endpoints).
- `game_logic.py` — pure, fully-tested game logic (streak state machine, researched
  truth bank, fallback pools, phases, oath, penalty ledger).
- `languages.py` — 10-language definitions (names, BCP-47, Kokoro voices, RTL, examples).
- `rooms.py` — SQLite room store (WAL, versioned JSON state, event log).
- `static/index.html` — single-file mobile frontend (vanilla JS, no build step).
- `api/index.py` — Vercel serverless entrypoint (WSGI wrapper).
- `dirtytruth.service` / `dirtytruth-tunnel.service` — systemd units (app + Cloudflare tunnel).
- `dirtytruth-tts-tunnel.service` — optional public tunnel for Kokoro (voice mode off-box).
- `.env.example` — annotated environment variables for Vercel/CLI deploys.

## Run (local)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py            # serves on :8084 (waitress)
```

## Services (production, local box)
```bash
sudo cp dirtytruth.service dirtytruth-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dirtytruth.service dirtytruth-tunnel.service
# Public URL:
journalctl -u dirtytruth-tunnel.service --no-pager | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```
The app and tunnel are **decoupled** — restarting the app does not change the public URL.

## Deploy (Vercel)
**Live (production): https://dirtytruth.vercel.app**

```bash
vercel --prod
```
Env vars — see **[.env.example](.env.example)** for the full annotated list; set
them in the Vercel dashboard or `vercel env add <NAME> production`:
- `LLM_URL` / `LLM_KEY` / `LLM_MODEL` — OpenAI-compatible LLM endpoint.
- `TTS_URL` — public URL of the Kokoro TTS server (see "Voice on Vercel").
- `DT_RL_*` — per-IP rate limits (optional; sane defaults baked in).

### Secrets (never commit them)
Secrets resolve in this order: real environment variables → gitignored
`secrets.env` next to `app.py` → safe defaults. For the local box, keep them in
`secrets.env`; for Vercel, use dashboard/CLI env vars. `.env.example` documents
every variable and is safe to commit.

### Serverless caveats (read before trusting Vercel with a session)
- **Rooms are per-Lambda-instance on serverless.** The room store is SQLite in
  `/tmp` (`DIRTYTRUTH_DB`, wired by `api/index.py`). Vercel may route your two
  phones to *different* Lambda instances, each with its own throwaway DB — room
  sync then can't find the partner. Two-device play is guaranteed only on the
  origin box (systemd); treat Vercel as the solo-mode / demo channel.
- **Voice on Vercel:** `/api/tts` runs inside the Lambda, so it must be able to
  reach Kokoro over the network. Publish port 8880 through its own quick tunnel:
  ```bash
  sudo cp dirtytruth-tts-tunnel.service /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now dirtytruth-tts-tunnel.service
  journalctl -u dirtytruth-tts-tunnel.service --no-pager | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
  ```
  then set `TTS_URL=https://<that-url>/v1/audio/speech` in Vercel. Quick-tunnel
  URLs change on every restart — use a named Cloudflare tunnel if you need it stable.
  Refresh flow after a reboot:
  ```bash
  NEW=$(journalctl -u dirtytruth-tts-tunnel.service --no-pager | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
  vercel env rm TTS_URL production --yes && printf '%s/v1/audio/speech\n' "$NEW" | vercel env add TTS_URL production && vercel --prod
  ```
- **Verified working on prod:** health, CSP/noindex headers, static assets,
  LLM generate (~3.4 s, inside the Hobby 10 s function cap), chat, Kokoro TTS
  via the tunnel (real MP3, <1 s), full room create/join/state/action cycle,
  non-English generation with the translation pass.
- **Privacy:** responses carry `X-Robots-Tag: noindex, nofollow` and the page
  ships a matching meta tag, so public URLs stay out of search engines.

## Tests
```bash
.venv/bin/python -m pytest --cov=app --cov=game_logic --cov=languages --cov=rooms --cov-report=term   # 115 tests, ~93%
node test_frontend.js                                                                                   # 80 tests
```
LLM and TTS are mocked in tests; the live endpoints are verified against the real
upstream services separately. Rate limits are disabled in the test suite
(`conftest.py`) and covered by dedicated tests that re-enable them locally.

## Upstream dependencies (must be running)
- LLM: OpenAI-compatible endpoint (Qwen3.8) — see `LLM_URL` in `app.py`.
- TTS: Kokoro server on `http://127.0.0.1:8880/v1/audio/speech` (or `TTS_URL`).
