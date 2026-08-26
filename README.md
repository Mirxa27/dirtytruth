# 🐴 Dirty Truth & Dare 🔥

A private, mobile-first slow-burn truth-or-dare game for couples, powered by the
**Cassia AI** engine (a local LLM) that generates every question and dare live.

## Features
- **Spinning bottle** — lands on a random player.
- **Player choice** — the target picks 💜 Truth or 🔥 Dare.
- **3-truth rule** — pick truth 2× in a row and the 3rd pick is forced to a dare.
- **Dirty-secrets truth engine** — researched, escalating truth questions that uncover each partner's deepest secrets and desires (patterns mined from real couple question banks: wafflejournal, lovifycouple, stephmorris, paired, forplay).
- **Mystery pacing** — the game moves through poetic phases (*First Glance → Warming Up → The Oath → Unveiling → No Secrets Left*). Players never know where it's going; the heat number is hidden behind the phase name.
- **The Oath** — mid-game (round 5) both players swear to play completely seriously.
- **$100 penalty ledger** — skip a task or refuse to perform it and you owe your partner $100. The ledger keeps a running score per player.
- **Slow-burn heat (1–10)** — auto-escalates +1 each round; manual dial + chat control.
- **Timed step-by-step challenges** — each dare is a sequence of timed, detailed
  instructions; each truth is a single answerable question.
- **Voice mode** — Cassia speaks challenges, steps, and "time's up" (Kokoro TTS).
- **Timer alerts** — countdown bar, last-3s beeps, chime + flash + vibration on time-up, auto-advance.
- **Cassia chat** — talk to the AI host to change heat or fire new challenges.
- **Persistence** — game state survives reloads (localStorage); "New" resets.

## Architecture
- `app.py` — Flask app + Cassia AI engine (LLM + TTS plumbing, validation, fallbacks).
- `game_logic.py` — pure, fully-tested game logic (streak state machine, fallback pools).
- `static/index.html` — single-file mobile frontend (vanilla JS, no build step).
- `dirtytruth.service` / `dirtytruth-tunnel.service` — systemd units (app + Cloudflare tunnel).

## Run
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py            # serves on :8084 (waitress)
```

## Services (production)
```bash
sudo cp dirtytruth.service dirtytruth-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dirtytruth.service dirtytruth-tunnel.service
# Public URL:
journalctl -u dirtytruth-tunnel.service --no-pager | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```
The app and tunnel are **decoupled** — restarting the app does not change the public URL.

## Tests
```bash
.venv/bin/python -m pytest --cov=app --cov=game_logic --cov-report=term   # 88 tests, ~99%
node test_frontend.js                                                       # 111 tests
```
LLM and TTS are mocked in tests; the live endpoints are verified against the real
upstream services separately.

## Upstream dependencies (must be running)
- LLM: OpenAI-compatible endpoint (Qwen3.8) — see `LLM_URL` in `app.py`.
- TTS: Kokoro server on `http://127.0.0.1:8880/v1/audio/speech`.
