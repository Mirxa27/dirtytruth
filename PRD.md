# 🐴 Dirty Truth & Dare 🔥 — Product Requirements Document (PRD)

**Version:** 5.0
**Owner:** Mirxa
**Engine:** Cassia AI (local LLM on L40S)
**Status:** In development → production

---

## 1. Vision

A private, mobile-first slow-burn truth-or-dare game for couples that feels like a
real, escalating, *discovering-each-other* experience — not a card deck. Cassia, the
in-game AI host, generates every truth and dare live, cooks the steam round by round,
and keeps the players guessing where it's going. The goal: partners uncover each
other's deepest secrets and desires so they learn exactly how to give each other
maximum pleasure.

**One-liner:** *A slow-cooked, AI-hosted dirty truth-or-dare that turns two people
into each other's favorite secret.*

## 2. Target users & context

- **Primary:** couples (any gender pairing) playing privately, usually at home,
  phones in hand, lights low.
- **Context:** 2 players, 1–2 hour sessions, escalating intimacy.
- **Constraints:** mobile-first (thumb-friendly), dark neon aesthetic, must work
  over a public URL (Cloudflare tunnel / Vercel), must feel alive and surprising.

## 3. Core experience (the loop)

```
Setup (names, genders, heat, language, secret preferences)
   → Spin the bottle (lands on a player)
   → Player CHOOSES: 💜 Truth or 🔥 Dare
   → Cassia generates the challenge (live LLM, phase-aware)
   → Timed, step-by-step execution (voice mode speaks it)
   → Complete / Skip / Not-performed (penalty)
   → Heat rises +1, round advances, phase advances
   → repeat until EXTREME
```

### 3.1 Spinning bottle
- Animated bottle spin (setTimeout-driven so it works in background tabs).
- Lands on a random player; that player is the target.

### 3.2 Player choice + 3-truth rule
- Target picks Truth or Dare.
- **3-truth rule:** pick truth 2× in a row → the 3rd pick is forced to a dare.
  Streaks are server-authoritative (`/api/streak`) and reset on a dare.

### 3.3 Dirty-secrets truth engine
- Truths are **questions** the target answers out loud — never physical actions.
- Content is *dirty secrets exploration*: hidden desires, secret fantasies, things
  done or imagined, exact details of what turns them on, never-said confessions.
- Researched 5-tier question bank (patterns mined from real couple question banks:
  wafflejournal, lovifycouple, stephmorris, paired, forplay) drives both the LLM
  prompt and the offline fallback.
- Every truth is a single, detailed, answerable question (45s answer window).

### 3.4 Dares
- Dares are **physical, step-by-step, timed** challenges (2–5 steps, 15–90s each,
  60–300s total).
- Steps are concrete and beginner-explainable: what to do, where, how, how slowly,
  what to feel, what to say. Each step ≤ 45 words.

### 3.5 Mystery pacing (players never know where it's going)
- The game moves through 5 poetic phases; the heat number is hidden behind the
  phase name:
  1. **First Glance** (rounds 1–2) — sweet, curious, a little shy.
  2. **Warming Up** (rounds 3–4) — skin closer, words softer.
  3. **The Oath** (round 5) — the rules get sealed.
  4. **Unveiling** (rounds 6–8) — secrets come out.
  5. **No Secrets Left** (rounds 9+) — the deepest you two will go.
- The LLM is instructed never to telegraph future rounds.

### 3.6 The Oath (round 5)
- Mid-game, the game pauses. Both players swear to play **completely seriously**:
  every truth answered honestly out loud, every dare performed all the way through.
- Cassia speaks the oath in voice mode.

### 3.7 $100 penalty ledger
- Skip a task or refuse to perform it → the player owes their partner **$100**.
- A per-player ledger keeps a running score, visible under the bottle.
- Actions: "Skip step" (penalty + advance) and "Not performed" (penalty + end).

### 3.8 Heat & escalation
- Heat 1–10: 1–2 warm, 3–4 sensual, 5–6 explicit, 7–8 intense, 9–10 EXTREME.
- Auto-escalation: +1 per round (toggleable), manual dial, and chat control.

### 3.9 Voice mode
- Cassia speaks the challenge, each step, and "time's up" via local Kokoro TTS.
- Voice is language-aware (see §5).

### 3.10 Timer alerts
- Countdown + depleting bar, soft beep in the last 3s, chime + flash + vibration on
  time-up, auto-advance to the next step.

### 3.11 Cassia chat
- Live chat with the AI host: reacts in character, adjusts heat, fires new
  challenges on demand.

## 4. Multi-device rooms (v5)

- **Rooms:** the host creates a room and gets a short join code (e.g. `KISS-4821`).
- **Join:** the partner opens the same URL on their phone, enters the code, and
  joins the room.
- **Sync:** server-side room state (SQLite) + lightweight polling. The host's
  actions (spin, choice, challenge, timer, penalties) stream to the partner's
  screen; the partner sees the same challenge, timer, and ledger in real time.
- **Roles:** host controls the game; guest watches + performs + can trigger
  "not performed" for their own tasks.
- **Resilience:** a dropped connection re-syncs on reconnect (state is
  server-authoritative).

## 5. Internationalization (v5)

- **10 languages:** English, Spanish, French, German, Italian, Portuguese,
  Hindi, Japanese, Chinese (Simplified), Arabic.
- **Native-language UI:** every label, button, phase name, and system message is
  translated; the player picks their language at setup (and can change it anytime).
- **Native-language content:** Cassia generates truths/dares in the chosen language
  (LLM prompt is language-directed).
- **Native-language voice:** TTS voice is mapped per language (Kokoro voice
  families: af_*, am_*, bf_*, ef_*, ff_*, if_*, jm_*, zm_*, etc.).
- **RTL:** Arabic renders right-to-left.

## 6. Secret preferences (v5)

- At setup, each player can **optionally** fill in private preferences that only
  Cassia sees (never shown to the partner):
  - turn-ons / kinks they'd love to explore
  - a fantasy they've never said
  - a boundary / hard limit (Cassia will never cross it)
- Cassia weaves these into generated truths and dares so the game feels
  *personally* tuned — the partner discovers the player's real desires through
  play, not through a form.
- Fully optional; empty preferences = generic mode.

## 7. Fun & excitement layer (v5)

- **Sound design:** WebAudio SFX — spin whoosh, tick-tock, time-up chime,
  penalty "cha-ching", oath gong, heat-rise riser.
- **Confetti & particles:** burst on challenge complete, big burst at EXTREME.
- **Cassia banter:** in-character one-liners between rounds, on streaks, on
  penalties, on heat changes.
- **Heat drama:** screen glow intensifies with heat; EXTREME gets a full
  red-pulse treatment.
- **Micro-animations:** card entrances, bottle physics, button presses, haptics.
- **Mystery reveals:** phase transitions get a short cinematic moment.

## 8. Architecture

```
┌────────────┐   HTTPS    ┌──────────────────────────────┐
│  Browser   │◄──────────►│  Flask app (waitress, :8084) │
│ (mobile)   │            │  - Cassia AI engine (LLM)    │
└────────────┘            │  - TTS proxy (Kokoro :8880)  │
                          │  - Room store (SQLite)       │
                          │  - game_logic.py (pure)      │
                          └──────────────────────────────┘
```

- **Backend:** Flask + waitress (production WSGI), Python 3.11.
- **LLM:** local Qwen3.8 (thinking disabled for fast JSON) via OpenAI-compatible
  endpoint. 3-retry logic, hardened JSON parsing, real fallback content.
- **TTS:** local Kokoro at `:8880`, language-mapped voices.
- **Rooms:** SQLite (WAL mode) — rooms, players, state, ledger, preferences.
- **Frontend:** single-file vanilla JS (no build step), i18n dictionary,
  WebAudio SFX, confetti, polling client.
- **Supervision:** systemd units for app + Cloudflare tunnel (decoupled).
- **Deploy:** GitHub (source) + Vercel (public web) + OVH L40S (LLM/TTS origin).

## 9. API design

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | liveness |
| `/api/generate` | POST | generate truth/dare (phase, language, prefs aware) |
| `/api/chat` | POST | Cassia chat |
| `/api/tts` | POST | text → MP3 (language-mapped voice) |
| `/api/streak` | POST | truth-streak state machine |
| `/api/oath` | POST | oath text + due check |
| `/api/penalty` | POST | record $100 penalty |
| `/api/room/create` | POST | create room → join code |
| `/api/room/join` | POST | join room with code |
| `/api/room/state` | GET | poll room state (sync) |
| `/api/room/action` | POST | host/guest action (spin, choice, penalty…) |
| `/api/room/prefs` | POST | save secret preferences |

## 10. Data model (rooms)

- `rooms(code PK, host_id, created_at, state_json, version)`
- `players(room_code, name, gender, role, prefs_json, streak, penalties_json)`
- `events(room_code, seq, type, payload_json, ts)` — append-only for sync

## 11. Non-functional requirements

- **Performance:** LLM response < 8s (thinking disabled); TTS < 3s; page < 1s.
- **Reliability:** LLM/TTS failures fall back to real content — never a stub.
- **Security:** no PII in logs; preferences are private (host-only read);
  security headers; 1MB request cap; input validation everywhere.
- **Quality:** 100% of modules tested (unit + integration), pyflakes clean,
  no TODOs/stubs/placeholders.
- **Portability:** runs on OVH L40S (origin) and Vercel (web) — Vercel proxies
  LLM/TTS calls to the OVH origin.

## 12. Roadmap

- **v1** — core game, LLM engine, public URL. ✅
- **v2** — slow-burn pacing, timed steps, voice mode, timer alerts. ✅
- **v3** — player choice + 3-truth rule. ✅
- **v4** — dirty-secrets truth engine, mystery phases, oath, $100 ledger,
  production hardening, systemd supervision, 199 tests. ✅
- **v5** — multi-device rooms, 10-language i18n, secret preferences,
  fun/excitement layer, GitHub + Vercel deploy. ← **this release**

## 13. Success metrics

- A couple can play a full 10-round session on two phones without friction.
- Every truth is a real question; every dare is a real, complete, timed challenge.
- Players in all 10 languages see their native UI, content, and voice.
- Zero stubs, zero TODOs, zero mock data paths.
- App stays live (supervised) and deploys cleanly to GitHub + Vercel.
