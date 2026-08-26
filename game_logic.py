#!/usr/bin/env python3
"""Shared game logic for Dirty Truth & Dare — pure functions, fully testable."""

TRUTH_LIMIT = 3  # N truths in a row -> next pick is forced to a dare
PENALTY_AMOUNT = 100  # dollars owed per skipped / not-performed task
OATH_ROUND = 5  # the oath is sworn when the game reaches this round

# ---------------------------------------------------------------------------
# Game phases — mystery pacing. Players see only the poetic phase name,
# never the heat number or what's coming next.
# ---------------------------------------------------------------------------
PHASES = [
    {"name": "First Glance", "desc": "You're still strangers in the best way. Sweet, curious, a little shy."},
    {"name": "Warming Up", "desc": "The air is changing. Skin is getting closer. Words are getting softer."},
    {"name": "The Oath", "desc": "Before it gets real, you seal the rules. What happens here stays here — and everything is real."},
    {"name": "Unveiling", "desc": "Secrets are coming out. Every answer changes what you know about each other."},
    {"name": "No Secrets Left", "desc": "Nothing is off the table. This is the deepest you two will go."},
]


def phase_for_round(round_no):
    """Return the phase dict for a given round (1-indexed)."""
    r = max(1, int(round_no))
    if r <= 2:
        return PHASES[0]
    if r <= 4:
        return PHASES[1]
    if r == OATH_ROUND:
        return PHASES[2]
    if r <= 8:
        return PHASES[3]
    return PHASES[4]


OATH_TEXT = (
    "We swear to play this game completely seriously. Every truth is answered "
    "honestly, out loud, with no lies and no dodging. Every dare is performed "
    "exactly as given, all the way through. If either of us skips a task or "
    "refuses to perform it, we owe the other $100 — no arguments, no take-backs. "
    "What we reveal here is for each other. We go as deep as the game takes us."
)


def oath_due(round_no):
    """The oath is due exactly when the game reaches OATH_ROUND."""
    return max(1, int(round_no)) == OATH_ROUND


# ---------------------------------------------------------------------------
# Penalty ledger — $100 per skipped / not-performed task
# ---------------------------------------------------------------------------
def record_penalty(ledger, player, reason="skipped"):
    """Return a new ledger with one $100 penalty added for `player`.

    ledger: {player_name: [ {reason, amount}, ... ]}
    """
    player = str(player).strip()[:30] or "Player"
    ledger = {k: list(v) for k, v in (ledger or {}).items()}
    ledger.setdefault(player, []).append({"reason": str(reason)[:60], "amount": PENALTY_AMOUNT})
    return ledger


def penalty_total(ledger, player):
    return sum(e.get("amount", 0) for e in (ledger or {}).get(player, []))


def penalty_summary(ledger):
    """{player: total} for display."""
    return {p: penalty_total(ledger, p) for p in (ledger or {})}


# ---------------------------------------------------------------------------
# Researched dirty-secrets truth bank (patterns mined from real couple
# question banks: wafflejournal, lovifycouple, stephmorris, paired, forplay).
# Each tier = a heat band. Questions escalate from sweet secrets to raw,
# never-said-out-loud confessions.
# ---------------------------------------------------------------------------
TRUTH_BANK = {
    1: [
        "What's the first thing you noticed about me that made your heart skip — and did you say anything about it?",
        "Tell me a small secret about us that you've never mentioned — something you noticed but kept to yourself.",
        "What's one thing I do without realizing it that you find irresistible?",
        "When did you first want to kiss me, and what were you thinking in that moment?",
        "What's a memory of us that you replay in your head when you're alone?",
        "What's the sweetest thing I've ever done for you that I probably don't remember?",
        "If you could relive one moment with me from the past, which one would it be and why?",
        "What's something you've been quietly hoping I'd notice about you?",
    ],
    2: [
        "What's the first physical thing you wanted from me that you were too shy to ask for?",
        "Tell me exactly what you were thinking the first time we touched — the real thought, not the polite one.",
        "What part of my body do you look at when you think no one is watching?",
        "What's a small turn-on of mine you've never told anyone about?",
        "Describe the exact moment you realized you wanted me — where were you, what were you wearing?",
        "What's something about my body you find beautiful that you've never said out loud?",
        "If I let you watch me get ready with no rules, what would you want to see first?",
        "What's the flirty thought you've had about me that you've never admitted?",
    ],
    3: [
        "Tell me the exact spot on my body you most want to kiss right now — and describe exactly how you'd kiss it.",
        "What's the dirtiest thing you've ever imagined doing to me in public, where someone might see?",
        "Describe the perfect slow kiss from you — where it starts, how long it lasts, what you whisper at the end.",
        "What's a secret desire about my body you've kept to yourself?",
        "If I asked you to undress me slowly with just your hands, what would you take off first and why?",
        "What's the most intimate thing you've ever wanted to whisper into my ear?",
        "Tell me about a time you thought about me when you were with someone else — what were you imagining?",
        "What's one thing I could do to your lips that would make you lose your composure?",
    ],
    4: [
        "What's the sexiest outfit or lingerie you've ever seen someone wear — and who do you want to see me in it?",
        "Describe exactly how you'd touch me if I told you to take your time and make me ache for more.",
        "What's a fantasy you've had about us that involves a place, not a person — where would it happen?",
        "Tell me the exact words you'd want me to say while I'm touching you.",
        "What's the most turned-on you've ever been just from thinking about me — what was the scene?",
        "If I blindfolded you, what would you want me to do to you first?",
        "What's a secret about how you like to be touched that you've never told a partner?",
        "Describe the moment you'd want me to lose control — what am I doing, what are you feeling?",
    ],
    5: [
        "What's a sexual fantasy you've never told anyone — tell me every detail, including what you were wearing.",
        "If you could try any kink or fetish with me just once, what would you pick and how would we set it up?",
        "Describe the exact foreplay you'd want from me — how long, where, and what makes you melt.",
        "What's the dirtiest thing you've ever done that you've never told me about?",
        "Tell me exactly what you'd do to me if I told you to make me beg.",
        "What's a position you've always wanted to try with me — and what would you want me to feel in it?",
        "What's the sound you make when you're close that you've never let anyone hear?",
        "Describe the sexiest thing you've ever done to yourself while thinking of me.",
    ],
    6: [
        "What's the most explicit fantasy you've had about me — the full scene, start to finish?",
        "Tell me exactly how you'd want me to dominate you — what do I say, what do I do, where do I hold you?",
        "What's a secret you've done in the bedroom that you'd be embarrassed for me to know?",
        "Describe the exact moment you'd come for me — what am I doing, what are you saying, how long do you hold it?",
        "What's the dirtiest thing you've ever wanted me to do to you in front of someone else?",
        "Tell me about the time you came the hardest — what was happening, who was doing it, what did you say?",
        "What's a turn-on you've never admitted because you thought I'd judge you?",
        "If I recorded our most intense night and you could only keep one moment, which would it be and why?",
    ],
    7: [
        "Describe the exact position I would use to make you scream — and tell me precisely how you'd hold my face while I bite your neck.",
        "What's the deepest secret about your body you've never shown anyone — the part you're most proud of, and the part you hide?",
        "Tell me exactly how long you'd want me to edge you, what I'd do to keep you there, and what you'd finally say.",
        "What's the most raw, unfiltered thing you've ever wanted in bed that you've never said out loud?",
        "Describe the exact moment you'd let me take full control — what do I do first, and what do you stop doing?",
        "What's a secret about your past that changed how you see intimacy — something no one knows?",
        "Tell me the exact words you'd want me to growl at you while I'm inside you.",
        "What's the one thing I could do to your body that would make you forget your own name?",
    ],
    8: [
        "What's the dirtiest secret you've ever kept from a partner — the one you've never told a single person?",
        "Describe the exact scene where you'd come three times in a row — what am I doing between each one?",
        "What's the most taboo thing you've ever fantasized about doing with me — and how far would you actually go?",
        "Tell me the exact moment you'd break — what am I doing, what are you feeling, and what do you finally let out?",
        "What's a secret desire you've had about another person that you've never told me — and what part of it do you want to share with me?",
        "Describe the exact way you'd want me to pin you down — where my hands are, where my mouth is, what you can't do.",
        "What's the deepest, darkest corner of your mind you've never let anyone see — and what's in it?",
        "Tell me exactly what you'd do if I told you to take your time and make me wait an hour before you let me come.",
    ],
    9: [
        "What's the most explicit, detailed, raw fantasy you've ever had that you've never said out loud to anyone — tell me every single detail.",
        "Describe the exact night you'd want to lose all control with me — where we are, what we're wearing, what breaks first.",
        "What's the deepest secret about your body and your pleasure that you've never let anyone see — and what would it take for you to show me?",
        "Tell me the exact words you'd scream when I push you past the edge — the real ones, not the polite ones.",
        "What's the most vulnerable thing you've ever felt in bed — the moment you felt completely exposed and completely wanted?",
        "Describe the exact position and pace that would make you come so hard you can't speak — and how long would you hold it?",
        "What's a secret you've done alone that you'd want to do with me — and how would you want it to feel?",
        "Tell me the one thing about your body you've never let anyone touch the way you want — and show me exactly how.",
    ],
    10: [
        "What's the absolute deepest, darkest, most explicit secret you've ever carried — the one you've told no one, not even in your own mind — and why have you kept it?",
        "Describe the exact moment you'd completely surrender to me — what I'm doing, what you're feeling, and the exact words you'd finally say.",
        "What's the most raw, unfiltered, no-holds-barred thing you've ever wanted in bed — and what would it take for you to ask for it out loud?",
        "Tell me the exact scene where you'd come so hard your body shakes — what am I doing, what are you saying, and how long does it last?",
        "What's the deepest desire you've ever had that you were too afraid to admit — and what would it take for you to let me see it?",
        "Describe the exact way you'd want me to take you to the edge and hold you there — what I say, what I do, and what you finally break into.",
        "What's the most intimate, vulnerable, completely-open thing you've ever felt — and what would it take for you to feel it with me again?",
        "Tell me the one thing about your body and your soul you've never let anyone see — and show me exactly how you'd want me to see it.",
    ],
}


def tier_for_heat(heat):
    h = max(1, min(10, int(heat)))
    if h <= 2:
        return 1
    if h <= 4:
        return 3
    if h <= 6:
        return 5
    if h <= 8:
        return 7
    return 9


def truth_for_heat(heat, recent_titles):
    """Pick a researched truth question for a heat level, avoiding repeats."""
    import random
    tier = tier_for_heat(heat)
    pool = list(TRUTH_BANK[tier])
    fresh = [q for q in pool if q[:40] not in (recent_titles or [])]
    if not fresh:
        fresh = pool
    return random.choice(fresh)

# ---------------------------------------------------------------------------
# Fallback pools — used only when the LLM is unreachable. Real, complete
# content at every heat tier, so the game never dead-ends.
# ---------------------------------------------------------------------------
FALLBACK_DARES = {
    1: [
        ("The Slow Gaze", [
            ("Stand facing your partner and hold unbroken eye contact. Do not smile. Breathe slowly.", 30),
            ("Lean in until you can feel their breath, then pull back one inch. Hold the tension.", 20),
        ]),
        ("First Touch", [
            ("Reach out and let your fingertips rest lightly on your partner's hand. Do not grip.", 20),
            ("Slowly trace one finger along the back of their hand, knuckle by knuckle.", 25),
        ]),
    ],
    2: [
        ("The Slow Unbuttoning", [
            ("Stand facing your partner and slowly undo the top two buttons of your shirt, exposing your collarbone.", 25),
            ("Let your fingertips brush their inner thigh once as you finish, then step back.", 15),
            ("Whisper 'Look at me' softly while holding their gaze.", 10),
        ]),
        ("Neck Whisper", [
            ("Lean in and gently kiss your partner's neck, then whisper one intimate fantasy into their ear.", 30),
            ("Press your lips to their jaw and hold still, letting them feel your breath.", 20),
        ]),
    ],
    3: [
        ("The Slow Neck Whisper", [
            ("Sit facing your partner, maintaining unbroken eye contact. Do not blink more than once every ten seconds.", 20),
            ("Slowly tilt your head back to expose your neck. Hold this vulnerable position perfectly still.", 15),
            ("Your partner traces their lips lightly along your jawline, stopping just below your earlobe.", 25),
            ("Whisper 'I want you to taste me' into the sensitive skin of their throat.", 15),
        ]),
        ("Lips and Breath", [
            ("Kiss your partner slowly — one soft, unhurried kiss that lasts at least ten full seconds.", 30),
            ("Part your lips slightly and let them feel your breath against theirs. Hold the moment.", 20),
        ]),
    ],
    4: [
        ("Hands on Skin", [
            ("Slowly slide your hands up your partner's arms to their shoulders, pausing at the elbows.", 30),
            ("Trace slow circles on their collarbone with one fingertip while they watch you.", 25),
            ("Kiss the hollow of their throat, then pull back and hold eye contact.", 20),
        ]),
        ("The Undress", [
            ("Slowly remove one piece of your partner's clothing with your fingers — no rushing.", 30),
            ("Lay it on the floor beside you, then kiss the skin you just exposed.", 20),
        ]),
    ],
    5: [
        ("Heavy Making-Out", [
            ("Pull your partner close and kiss them deeply — slow at first, then with real hunger.", 40),
            ("Slide one hand into their hair and the other down their side, feeling every inch.", 30),
            ("Break the kiss and whisper how bad you want them. Hold their gaze.", 15),
        ]),
        ("Grind and Hold", [
            ("Press your body flush against your partner's and grind slowly, one full circle at a time.", 45),
            ("Freeze mid-grind, forehead to forehead, and let the tension build until one of you breaks.", 20),
        ]),
    ],
    6: [
        ("Hands Everywhere", [
            ("Slowly undress your partner piece by piece, kissing each spot your fingers leave.", 45),
            ("Once they're bare, trace slow lines from their shoulder to their hip with one finger.", 30),
            ("Kiss down their neck and stop just above their collarbone. Make them wait.", 20),
        ]),
        ("The Edge", [
            ("Touch your partner in the spot that drives them craziest — but only with one fingertip.", 40),
            ("Build pressure slowly, then pull away completely. Make them ache for more.", 30),
        ]),
    ],
    7: [
        ("Blindfolded Worship", [
            ("Blindfold your partner. Hold their hips firmly, guiding their knees apart for full access.", 15),
            ("Use your mouth on their chest, sliding down to their groin with slow, wet licks.", 45),
            ("Command them to take you into their mouth, using their throat to pace you near the edge.", 45),
        ]),
        ("Take Control", [
            ("Pin your partner's wrists above their head. Tell them exactly what you're going to do.", 20),
            ("Kiss them slow and deep while they can't move, then bite their shoulder.", 30),
            ("Tell them to stay perfectly still while you take your time with them.", 30),
        ]),
    ],
    8: [
        ("From Behind", [
            ("Flip your partner onto their stomach and arch their back. Drive into them so hard they bite your shoulder.", 45),
            ("Order them to take every thrust until they scream your name and can't finish without your permission.", 45),
        ]),
        ("The Command", [
            ("Blindfold your partner and make them kneel. Tell them they belong to you for the next minute.", 20),
            ("Take them slow enough to make them whine while you tell them they're only yours to ruin.", 45),
            ("Make them hold an orgasm until you say you're done, then spank them until they're breathless.", 30),
        ]),
    ],
    9: [
        ("Total Control", [
            ("Tie your partner's wrists with a soft cloth. Tell them the only rule is to obey you.", 20),
            ("Take them from behind so slowly they beg you to stop, then flip them over and fuck them face-first into the pillow.", 60),
            ("Make them scream your name until they can't speak.", 30),
        ]),
        ("The Long Build", [
            ("Kiss your partner from their forehead to their lips, taking at least a full minute.", 60),
            ("Undress them completely with your mouth and hands, no rushing.", 45),
            ("Take them so deep and so slow that they have to hold on to you to stay upright.", 60),
        ]),
    ],
    10: [
        ("No Limits", [
            ("Blindfold your partner, pin their wrists above their head, and bend them over the bed until they're gasping and dripping for you.", 30),
            ("Take them from behind so slowly they beg you to stop, then flip them over and fuck them face-first into the pillow until they scream your name.", 60),
            ("Make them hold an orgasm until you say you're done, then spank them until they're breathless.", 30),
            ("Whisper exactly how much you want them while they're still shaking.", 20),
        ]),
        ("The Full Scene", [
            ("Kiss your partner from their forehead to their lips, taking at least a full minute.", 60),
            ("Undress them completely with your mouth and hands, no rushing.", 45),
            ("Take them so deep and so slow that they have to hold on to you to stay upright.", 60),
            ("Afterglow: hold them close, kiss their temple, and tell them exactly what you're going to do to them next time.", 30),
        ]),
    ],
}


def fallback_challenge(chosen, heat, target, partner, recent_titles):
    """Pick a real, complete challenge from the fallback pool.

    Avoids repeating any title in recent_titles when possible.
    Returns (title, steps) where steps is a list of {instruction, seconds}.
    Truths are single-question challenges (one step, 45s to answer).
    """
    tier = tier_for_heat(heat)
    if chosen == "truth":
        # Use the researched dirty-secrets bank (same tiers as the LLM prompt).
        # The localized "Answer out loud:" prefix is added by the frontend.
        q = truth_for_heat(heat, recent_titles)
        q = q.rstrip("?.!").strip()
        title = q[:40] + ("…" if len(q) > 40 else "")
        return title, [{"instruction": q, "seconds": 45}]
    # dares
    pool = FALLBACK_DARES
    candidates = _tier_candidates(tier)
    for t in candidates:
        for title, steps in pool.get(t, []):
            if title in recent_titles:
                continue
            out = [{"instruction": i, "seconds": max(5, min(180, int(s)))} for i, s in steps]
            if out:
                return title, out
    title, steps = pool[tier][0]
    return title, [{"instruction": i, "seconds": max(5, min(180, int(s)))} for i, s in steps]


def _tier_candidates(tier):
    """Tier numbers to try, walking outward from the exact tier."""
    seen, out = set(), []
    for offset in range(0, 11):
        for t in (tier + offset, tier - offset):
            if 1 <= t <= 10 and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def normalize_steps(obj, heat):
    """Return (title, steps) from an LLM JSON object, or None if unusable."""
    steps = obj.get("steps")
    title = str(obj.get("text", "")).strip()
    if isinstance(steps, list) and steps:
        out = []
        for s in steps[:6]:
            if isinstance(s, dict):
                instr = str(s.get("instruction", "")).strip()
                secs = s.get("seconds", 30)
            else:
                instr = str(s).strip()
                secs = 30
            if not instr:
                continue
            try:
                secs = max(5, min(180, int(secs)))
            except Exception:
                secs = 30
            out.append({"instruction": instr, "seconds": secs})
        if out:
            return (title or "Your challenge"), out
    text = str(obj.get("text", "")).strip()
    if text:
        return (text[:60], [{"instruction": text, "seconds": 45}])
    return None


def truth_streak_logic(streak, chosen_type, limit=TRUTH_LIMIT):
    """Pure truth-streak state machine.

    A player may pick truth at most (limit - 1) times in a row.
    The next consecutive truth pick is FORCED to a dare and the streak resets.

    Returns (new_streak, was_forced).
    - If streak >= limit - 1 and chosen_type == 'truth': forced dare, streak -> 0.
    - If chosen_type == 'truth': streak increments.
    - If chosen_type == 'dare': streak resets to 0.
    """
    streak = max(0, int(streak))
    chosen_type = "dare" if str(chosen_type).lower() == "dare" else "truth"
    if chosen_type == "truth" and streak >= limit - 1:
        return 0, True
    if chosen_type == "truth":
        return streak + 1, False
    return 0, False
