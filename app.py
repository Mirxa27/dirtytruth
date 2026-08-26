#!/usr/bin/env python3
"""Dirty Truth & Dare — Flask backend with Cassia AI engine (v5, production)."""
import json
import os
import re
import time
import requests
from flask import Flask, request, jsonify, send_from_directory

from game_logic import (
    TRUTH_LIMIT,
    PENALTY_AMOUNT,
    OATH_TEXT,
    OATH_ROUND,
    fallback_challenge,
    normalize_steps,
    truth_streak_logic,
    phase_for_round,
    oath_due,
    record_penalty,
    penalty_summary,
)
from languages import LANGUAGES, get_lang, language_directive, tts_voice
import rooms

LLM_URL = os.environ.get("LLM_URL", "https://445ed4fc-4d66-45d9-a917-4eb71ac706a4.app.us-east-va.ai.cloud.ovh.us/v1/chat/completions")
LLM_KEY = os.environ.get("LLM_KEY", "31532b41b8afe2af7fa0e34aac1b184d4bfddb3f450c9366139354753cb45b9d")
LLM_MODEL = os.environ.get("LLM_MODEL", "/tmp/models/qwen38-27b-q8kp.gguf")
TTS_URL = os.environ.get("TTS_URL", "http://127.0.0.1:8880/v1/audio/speech")
TTS_VOICE = os.environ.get("TTS_VOICE", "af_heart")

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB request cap
rooms.init_db()  # idempotent — ensures the room store exists for tests + prod


# ---------------------------------------------------------------------------
# Security headers + error handling
# ---------------------------------------------------------------------------
@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found"}), 404
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "payload too large"}), 413


@app.errorhandler(500)
def server_error(_e):
    return jsonify({"error": "internal server error"}), 500


@app.route("/favicon.ico")
def favicon():
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        "<text y='.9em' font-size='90'>\U0001F37E</text></svg>"
    )
    return svg, 200, {"Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=86400"}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
BASE_PROMPT = """You are Cassia, the AI engine inside "Dirty Truth & Dare" — a private slow-burn game for couples.

You are a master of SLOW COOKING — building real, aching tension and steam step by step. You NEVER rush to extreme. You escalate gradually, round by round, like a real couple losing control.

MYSTERY PACING (critical):
- The players must NEVER know where the game is going. Never hint at future rounds, never say "next we'll do X", never telegraph the escalation.
- Each challenge should feel like a natural, surprising step — as if it grew out of the last one.
- The goal is a smooth journey that uncovers each partner's deepest secrets and desires, so they learn exactly how to give each other maximum pleasure.

HEAT SCALE (follow it exactly):
- 1-2 "warm": light teasing, eye contact, compliments, a brush of skin. No touching below the waist.
- 3-4 "sensual": slow touches, neck, lips, chest, whispered words, kissing. Clothes may start coming off.
- 5-6 "steamy": hands everywhere, heavy making-out, grinding, biting, pulling clothes off, foreplay.
- 7-8 "hot": full foreplay, explicit sex acts begin, positions, moaning, edging, control.
- 9-10 "EXTREME": raw, explicit, detailed sex — positions, pace, sounds, orgasm, afterglow. Only reached after many rounds of building.

GENERAL RULES:
- Address the target by name. Use the partner's name when they must act.
- Match the heat level EXACTLY. If heat is 3, do NOT write sex acts. If heat is 9, do NOT write mere eye contact.
- Never repeat or rephrase recent challenges.
- Write for beginners: specific, physical, explainable — exactly what to do, where, how, how slowly, what to feel, what to say.
- Respond with STRICT JSON ONLY, no markdown, no commentary."""

TRUTH_PROMPT = BASE_PROMPT + """

CHALLENGE TYPE: TRUTH — DIRTY SECRETS EXPLORATION. A truth is a QUESTION the target must answer honestly out loud to their partner.
- The target does NOT perform physical actions. They ANSWER.
- The question must be answerable in 15-60 seconds of speaking: intimate, personal, specific, and escalating with the heat level.
- These are DIRTY SECRETS questions — they uncover what the target has never said out loud: hidden desires, secret fantasies, things they've done or imagined, the exact details of what turns them on, and what they've never admitted.
- Heat 1-2 truths: sweet personal secrets, first impressions, small hidden desires, things they noticed but never said.
- Heat 3-4 truths: desires about their partner's body, kisses, what they'd whisper, small turn-ons they've never admitted.
- Heat 5-6 truths: explicit fantasies never told anyone, foreplay details, sounds they'd make, kinks they'd try.
- Heat 7-8 truths: positions, control, edging, the exact moment they'd come, secrets from their past, the dirtiest thing they've kept from a partner.
- Heat 9-10 truths: the most explicit, detailed, raw secret or fantasy they've never said out loud to anyone — the deepest, darkest, most vulnerable thing they carry.
- The question must demand a DETAILED answer (ask for specifics: where, how, what exactly, what they'd say, every detail).
- Make each question feel like a natural, surprising discovery — the partner should not have seen it coming.
- Format: ONE question, phrased directly to the target by name. Just the question itself — no prefix, no "Answer out loud".

Respond with STRICT JSON ONLY:
{"text": "the truth question (max 40 words)", "steps": [{"instruction": "the same truth question, verbatim", "seconds": 45}]}"""

DARE_PROMPT = BASE_PROMPT + """

CHALLENGE TYPE: DARE. A dare is a SEQUENCE OF PHYSICAL ACTIONS the target must perform (the partner reacts/watches/participates as instructed).
- 2 to 5 steps. Each step is ONE clear, detailed, physical instruction with a duration in seconds.
- Durations: 15-90 seconds per step. Total challenge 60-300 seconds.
- Steps must be specific and explainable to a beginner: exactly what to do, where, how, how slowly, what to feel, what to say.
- Keep each step under 45 words — vivid but concise. No rambling.
- The target player performs the steps; the partner reacts/watches/participates as instructed.

Respond with STRICT JSON ONLY:
{"text": "one-line title of the challenge (max 12 words)", "steps": [{"instruction": "detailed step", "seconds": 30}, ...]}"""

CHAT_PROMPT = BASE_PROMPT + """

CHAT MODE: The user is talking to you directly. Respond in character as Cassia — seductive, confident, patient, a little teasing. You are a slow-burn coach: you build steam gradually and never rush. Keep replies under 60 words.
If the user asks to change the heat (e.g. "go harder", "too much", "softer", "slow down"), set "heat" to the new level 1-10 (move at most 2 levels per request to keep the slow burn).
If the user asks for a new challenge (or says "surprise me", "one more", "give me a dare"), include "question" (a one-line title) and "type" ("truth" or "dare") in your JSON, and set "heat" accordingly.
Otherwise omit "question" and "type".
Respond with STRICT JSON ONLY:
{"reply": "your message", "heat": <int or null>, "question": <string or null>, "type": <"truth"|"dare" or null>}"""


# ---------------------------------------------------------------------------
# LLM plumbing
# ---------------------------------------------------------------------------
def call_llm(payload, retries=3):
    payload = dict(payload)
    # Qwen3.8 is a thinking model — disable reasoning for fast, clean JSON output
    payload.setdefault("chat_template_kwargs", {"enable_thinking": False})
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.post(
                LLM_URL,
                headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            r.raise_for_status()
            d = r.json()
            content = d["choices"][0]["message"]["content"]
            if content and content.strip():
                return content
            last_err = f"empty response (finish_reason={d['choices'][0].get('finish_reason')})"
        except Exception as e:
            last_err = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"LLM failed after {retries} attempts: {last_err}")


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for key in ("text", "reply", "question"):
            km = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)' % key, text, re.DOTALL)
            if km:
                val = km.group(1)
                try:
                    val = json.loads('"' + val + '"')
                except Exception:
                    val = val.replace('\\"', '"').replace("\\n", " ").replace("\\\\", "\\")
                return {key: val}
        raise


def validate_challenge(chosen, title, steps):
    """Final guard: ensure the returned challenge is sane for its type."""
    if not steps:
        return None
    steps = [
        {"instruction": str(s.get("instruction", "")).strip().rstrip(".,;: ")[:600],
         "seconds": max(5, min(180, int(s.get("seconds", 30))))}
        for s in steps[:6] if str(s.get("instruction", "")).strip()
    ]
    if not steps:
        return None
    if chosen == "truth":
        # A truth must be a single answerable question — collapse to one step.
        # The localized "Answer out loud:" prefix is added by the frontend.
        q = steps[0]["instruction"]
        # Strip any LLM-added prefix so we never double it
        q = re.sub(r"^(?:answer\s+out\s+loud|truth\s+for\s+\w+)[,:]?\s*", "", q, flags=re.I).strip()
        q = q.rstrip("?.!").strip()
        if not q:
            return None
        return (str(title).strip()[:80] or "A truth for you"), [{"instruction": q, "seconds": 45}]
    return (str(title).strip()[:80] or "Your dare"), steps


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "engine": "Cassia AI", "t": int(time.time())})


@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json(force=True, silent=True) or {}
    text = str(data.get("text", ""))[:1200]
    if not text.strip():
        return jsonify({"error": "empty text"}), 400
    lang = get_lang(data.get("lang", "en"))
    voice = str(data.get("voice", ""))[:20] or tts_voice(lang["code"])
    try:
        r = requests.post(
            TTS_URL,
            headers={"Authorization": "Bearer x", "Content-Type": "application/json"},
            json={"model": "kokoro", "voice": voice, "input": text},
            timeout=60,
        )
        r.raise_for_status()
        return r.content, 200, {"Content-Type": "audio/mpeg", "Cache-Control": "no-store"}
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 502


@app.route("/api/languages")
def languages_list():
    """All supported languages for the UI selector."""
    return jsonify({
        "default": "en",
        "languages": [
            {"code": c, "name": d["name"], "native": d["native"], "rtl": d["rtl"]}
            for c, d in LANGUAGES.items()
        ],
    })


def _clean_players(raw):
    """Coerce the players payload into a safe list of {name, gender} dicts."""
    out = []
    if isinstance(raw, list):
        for p in raw[:4]:
            if isinstance(p, dict):
                name = str(p.get("name", "Player"))[:30].strip() or "Player"
                gender = str(p.get("gender", "partner"))[:20].strip() or "partner"
                out.append({"name": name, "gender": gender})
    return out


def _prefs_block(prefs, target):
    """Build the secret-preferences prompt fragment for the target player."""
    if not isinstance(prefs, dict):
        return ""
    p = prefs.get(target)
    if not isinstance(p, dict):
        return ""
    parts = []
    turnons = str(p.get("turnons", "")).strip()[:400]
    fantasy = str(p.get("fantasy", "")).strip()[:400]
    boundary = str(p.get("boundary", "")).strip()[:400]
    if turnons:
        parts.append(f"SECRET TURN-ONS (only you know these; weave them in naturally, never quote the form): {turnons}")
    if fantasy:
        parts.append(f"UNSAID FANTASY (steer toward this when the heat allows): {fantasy}")
    if boundary:
        parts.append(f"HARD BOUNDARY (NEVER cross this, never reference it directly): {boundary}")
    if not parts:
        return ""
    return "\n".join(parts) + "\n"


def _translate_challenge(title, steps, lang_code):
    """Second LLM pass: translate a generated challenge into the target language.

    The base model is English-dominant, so a dedicated translation pass is the
    reliable way to get fully native output. Returns (title, steps) translated,
    or the originals if the pass fails.
    """
    if lang_code == "en":
        return title, steps
    lang = get_lang(lang_code)
    steps_json = json.dumps([s["instruction"] for s in steps], ensure_ascii=False)
    prompt = (
        f"Translate the following into natural, fluent {lang['name']}. "
        f"Keep the meaning, tone, and heat level exactly the same. "
        f"Output STRICT JSON only: {{\"title\": \"...\", \"steps\": [\"...\", ...]}}\n"
        f"Title: {title}\nSteps: {steps_json}"
    )
    try:
        raw = call_llm({
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": f"You are a professional translator. Respond ONLY in {lang['name']}."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "top_p": 0.9,
            "max_tokens": 1200,
        })
        obj = parse_json(raw)
        t_title = str(obj.get("title", "")).strip()
        t_steps = obj.get("steps")
        if not t_title or not isinstance(t_steps, list) or len(t_steps) != len(steps):
            return title, steps
        new_steps = []
        for i, s in enumerate(steps):
            instr = str(t_steps[i]).strip() if i < len(t_steps) else s["instruction"]
            new_steps.append({"instruction": instr, "seconds": s["seconds"]})
        return t_title, new_steps
    except Exception:
        return title, steps


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        data = {}
    players = _clean_players(data.get("players"))
    chosen = "dare" if str(data.get("chosen", "truth")).lower() == "dare" else "truth"
    target = str(data.get("target", "you"))[:30].strip() or "you"
    lang = get_lang(data.get("lang", "en"))
    prefs = data.get("prefs") if isinstance(data.get("prefs"), dict) else {}
    try:
        heat = max(1, min(10, int(data.get("heat", 3))))
        round_no = max(1, int(data.get("round", 1)))
    except (TypeError, ValueError):
        heat, round_no = 3, 1
    recent = [str(q)[:200] for q in (data.get("recent") or []) if isinstance(q, (str, int, float))][-8:]

    players_desc = ", ".join(
        f"{p.get('name', 'Player')} ({p.get('gender', 'partner')})" for p in players
    )
    partner = next((p for p in players if p.get("name") != target), None)
    partner_name = partner.get("name", "your partner") if partner else "your partner"

    system = language_directive(lang["code"]) + (TRUTH_PROMPT if chosen == "truth" else DARE_PROMPT)
    phase = phase_for_round(round_no)
    prefs_block = _prefs_block(prefs, target)
    lang_reminder = (
        f"REMEMBER: respond ENTIRELY in {lang['name']}.\n"
        if lang["code"] != "en" else ""
    )
    user = (
        f"Players: {players_desc}\n"
        f"Chosen type: {chosen.upper()}\n"
        f"Target player (the one who must {'answer' if chosen == 'truth' else 'perform'}): {target}\n"
        f"Partner (the other player): {partner_name}\n"
        f"Current heat level: {heat}/10 — match this EXACTLY, do not exceed it.\n"
        f"Game phase: {phase['name']} — {phase['desc']}\n"
        f"Game round: {round_no} (early rounds = build tension slowly)\n"
        f"Recent challenges (do NOT repeat or rephrase these): {json.dumps(recent) if recent else 'none — this is the first challenge'}\n"
        + (prefs_block + "\n" if prefs_block else "")
        + lang_reminder
        + f"Generate the {chosen} for {target} now. Strict JSON only."
    )
    try:
        raw = call_llm({
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.95,
            "top_p": 0.95,
            "max_tokens": 1600,
        })
        obj = parse_json(raw)
        norm = normalize_steps(obj, heat)
        if norm:
            title, steps = norm
            validated = validate_challenge(chosen, title, steps)
            if validated:
                vtitle, vsteps = validated
                if lang["code"] != "en":
                    vtitle, vsteps = _translate_challenge(vtitle, vsteps, lang["code"])
                return jsonify({"type": chosen, "title": vtitle, "steps": vsteps, "heat": heat, "engine": "cassia", "phase": phase["name"]})
        # LLM returned nothing usable -> fall through to the real fallback
    except Exception:
        pass
    # Real, complete fallback content — never a stub
    title, steps = fallback_challenge(chosen, heat, target, partner_name, recent)
    if lang["code"] != "en":
        title, steps = _translate_challenge(title, steps, lang["code"])
    return jsonify({"type": chosen, "title": title, "steps": steps, "heat": heat, "engine": "fallback", "phase": phase["name"]})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        data = {}
    msg = str(data.get("message", ""))[:500]
    players = _clean_players(data.get("players"))
    target = data.get("target")
    target = str(target)[:30] if target else None
    try:
        heat = max(1, min(10, int(data.get("heat", 3))))
    except (TypeError, ValueError):
        heat = 3
    recent = [str(q)[:200] for q in (data.get("recent") or []) if isinstance(q, (str, int, float))][-8:]

    players_desc = ", ".join(
        f"{p.get('name', 'Player')} ({p.get('gender', 'partner')})" for p in players
    )
    user = (
        f"Players: {players_desc}\nCurrent target: {target or 'n/a'}\nCurrent heat: {heat}/10\n"
        f"Recent challenges: {json.dumps(recent) if recent else 'none'}\n\n"
        f"User says: {msg}"
    )
    try:
        raw = call_llm({
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": CHAT_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0.9,
            "max_tokens": 1000,
        })
        obj = parse_json(raw)
        reply = str(obj.get("reply", "")).strip() or "Mmm, take your time with me."
        out = {"reply": reply, "engine": "cassia"}
        if obj.get("heat") is not None:
            out["heat"] = max(1, min(10, int(obj["heat"])))
        if obj.get("question"):
            out["question"] = str(obj["question"]).strip()
            out["type"] = "dare" if obj.get("type") == "dare" else "truth"
        return jsonify(out)
    except Exception:
        try:
            raw = call_llm({
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You are Cassia, a seductive, patient AI game host for a couples' slow-burn sex game. Reply in at most 40 words, plain text, no JSON."},
                    {"role": "user", "content": msg},
                ],
                "temperature": 0.9,
                "max_tokens": 300,
            })
            return jsonify({"reply": raw.strip()[:400] or "Mmm, take your time with me.", "engine": "cassia-plain"})
        except Exception as e2:
            return jsonify({"reply": "I'm right here, darling — take your time.", "engine": "fallback", "error": str(e2)[:200]})


@app.route("/api/streak", methods=["POST"])
def streak():
    """Pure truth-streak state machine (authoritative server-side logic)."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        streak = max(0, int(data.get("streak", 0)))
        chosen = "dare" if str(data.get("chosen", "truth")).lower() == "dare" else "truth"
    except (TypeError, ValueError):
        return jsonify({"error": "bad input"}), 400
    new_streak, was_forced = truth_streak_logic(streak, chosen)
    return jsonify({"streak": new_streak, "forced": was_forced, "limit": TRUTH_LIMIT})


@app.route("/api/oath", methods=["POST"])
def oath():
    """Return the oath text + whether the oath is due for this round."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        round_no = max(1, int(data.get("round", 1)))
    except (TypeError, ValueError):
        round_no = 1
    return jsonify({
        "due": oath_due(round_no),
        "round": OATH_ROUND,
        "text": OATH_TEXT,
        "penalty": PENALTY_AMOUNT,
    })


@app.route("/api/penalty", methods=["POST"])
def penalty():
    """Record a $100 penalty for a skipped / not-performed task.

    Body: {ledger: {player: [entries]}, player: str, reason: str}
    Returns the updated ledger + per-player totals.
    """
    data = request.get_json(force=True, silent=True) or {}
    ledger = data.get("ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    player = str(data.get("player", "Player"))[:30].strip() or "Player"
    reason = str(data.get("reason", "skipped"))[:60] or "skipped"
    new_ledger = record_penalty(ledger, player, reason)
    return jsonify({
        "ledger": new_ledger,
        "totals": penalty_summary(new_ledger),
        "amount": PENALTY_AMOUNT,
        "player": player,
    })


# ---------------------------------------------------------------------------
# Multi-device rooms
# ---------------------------------------------------------------------------
@app.route("/api/room/create", methods=["POST"])
def room_create():
    data = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name", "Player"))[:30].strip() or "Player"
    gender = str(data.get("gender", "partner"))[:20].strip() or "partner"
    lang = get_lang(data.get("lang", "en"))["code"]
    code, state = rooms.create_room(name, gender, lang)
    rooms.append_event(code, "created", {"code": code})
    return jsonify({"code": code, "state": state, "version": 0})


@app.route("/api/room/join", methods=["POST"])
def room_join():
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code", "")).upper().strip()
    name = str(data.get("name", "Player"))[:30].strip() or "Player"
    gender = str(data.get("gender", "partner"))[:20].strip() or "partner"
    room = rooms.get_room(code)
    if not room:
        return jsonify({"error": "room not found"}), 404
    state, version = rooms.update_room(code, lambda s: (
        s["players"][1].update({"name": name, "gender": gender, "joined": True})
    ))
    rooms.append_event(code, "joined", {"name": name})
    return jsonify({"code": code, "state": state, "version": version})


@app.route("/api/room/state", methods=["GET"])
def room_state():
    code = str(request.args.get("code", "")).upper().strip()
    since = request.args.get("since", 0)
    try:
        since_seq = int(since)
    except (TypeError, ValueError):
        since_seq = 0
    room = rooms.get_room(code)
    if not room:
        return jsonify({"error": "room not found"}), 404
    return jsonify({
        "code": code,
        "state": room["state"],
        "version": room["version"],
        "events": rooms.recent_events(code, since_seq),
    })


@app.route("/api/room/action", methods=["POST"])
def room_action():
    """Host/guest action. Body: {code, action, ...payload}."""
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code", "")).upper().strip()
    action = str(data.get("action", ""))[:30]
    room = rooms.get_room(code)
    if not room:
        return jsonify({"error": "room not found"}), 404

    def mutate(s):
        if action == "set_lang":
            s["lang"] = get_lang(data.get("lang", s.get("lang", "en")))["code"]
        elif action == "set_heat":
            try:
                s["heat"] = max(1, min(10, int(data.get("heat", s.get("heat", 2)))))
            except (TypeError, ValueError):
                pass
        elif action == "set_target":
            s["target"] = str(data.get("target", ""))[:30] or None
        elif action == "set_challenge":
            s["challenge"] = data.get("challenge") if isinstance(data.get("challenge"), dict) else None
            s["stepIdx"] = 0
            s["status"] = "playing"
        elif action == "set_step":
            try:
                s["stepIdx"] = max(0, int(data.get("step", 0)))
            except (TypeError, ValueError):
                pass
        elif action == "set_status":
            s["status"] = str(data.get("status", "playing"))[:20]
        elif action == "advance_round":
            s["round"] = max(1, int(s.get("round", 1)) + 1)
            s["challenge"] = None
            s["status"] = "playing"
        elif action == "set_streak":
            name = str(data.get("player", ""))[:30]
            try:
                s["truthStreak"][name] = max(0, int(data.get("streak", 0)))
            except (TypeError, ValueError):
                pass
        elif action == "penalty":
            player = str(data.get("player", "Player"))[:30].strip() or "Player"
            reason = str(data.get("reason", "skipped"))[:60] or "skipped"
            s["ledger"] = record_penalty(s.get("ledger") or {}, player, reason)
        elif action == "set_oath":
            s["oathSworn"] = bool(data.get("sworn", True))
        elif action == "set_recent":
            s["recent"] = [str(q)[:200] for q in (data.get("recent") or []) if isinstance(q, (str, int, float))][-8:]
        elif action == "set_prefs":
            prefs = data.get("prefs")
            if isinstance(prefs, dict):
                s["prefs"] = prefs
        elif action == "set_player":
            idx = data.get("idx")
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                idx = 1
            if 0 <= idx < len(s["players"]):
                if data.get("name") is not None:
                    s["players"][idx]["name"] = str(data.get("name"))[:30]
                if data.get("gender") is not None:
                    s["players"][idx]["gender"] = str(data.get("gender"))[:20]
                if data.get("joined") is not None:
                    s["players"][idx]["joined"] = bool(data.get("joined"))
        else:
            return

    state, version = rooms.update_room(code, mutate)
    if state is None:
        return jsonify({"error": "room not found"}), 404
    rooms.append_event(code, action, data)
    return jsonify({"code": code, "state": state, "version": version})


@app.route("/api/room/prefs", methods=["POST"])
def room_prefs():
    """Save secret preferences for a player (private — never shown to the partner)."""
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code", "")).upper().strip()
    player = str(data.get("player", ""))[:30].strip()
    prefs = data.get("prefs")
    if not isinstance(prefs, dict):
        prefs = {}
    clean = {
        "turnons": str(prefs.get("turnons", ""))[:400],
        "fantasy": str(prefs.get("fantasy", ""))[:400],
        "boundary": str(prefs.get("boundary", ""))[:400],
    }
    room = rooms.get_room(code)
    if not room:
        return jsonify({"error": "room not found"}), 404
    state, version = rooms.update_room(code, lambda s: s["prefs"].update({player: clean}))
    return jsonify({"ok": True, "version": version})


def create_app():
    """Application factory (used by tests and the production server)."""
    return app


def main():
    """Production entrypoint — waitress WSGI server (threaded, no dev-server warnings)."""
    rooms.init_db()
    rooms.prune_rooms()
    from waitress import serve
    serve(
        app,
        host="0.0.0.0",
        port=8084,
        threads=16,
        channel_timeout=180,
        recv_bytes=65536,
    )


if __name__ == "__main__":
    main()
