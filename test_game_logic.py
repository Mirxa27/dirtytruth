"""Unit tests for game_logic.py — pure functions, no network."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from game_logic import (
    TRUTH_LIMIT,
    PENALTY_AMOUNT,
    OATH_ROUND,
    OATH_TEXT,
    TRUTH_BANK,
    FALLBACK_DARES,
    tier_for_heat,
    truth_for_heat,
    fallback_challenge,
    normalize_steps,
    truth_streak_logic,
    phase_for_round,
    oath_due,
    record_penalty,
    penalty_summary,
)


# ---------------------------------------------------------------------------
# tier_for_heat (maps 1-10 heat -> 5 research tiers)
# ---------------------------------------------------------------------------
def test_tier_clamps_low():
    assert tier_for_heat(0) == 1
    assert tier_for_heat(-5) == 1

def test_tier_clamps_high():
    assert tier_for_heat(11) == 9
    assert tier_for_heat(99) == 9

def test_tier_mapping():
    assert tier_for_heat(1) == 1
    assert tier_for_heat(2) == 1
    assert tier_for_heat(3) == 3
    assert tier_for_heat(4) == 3
    assert tier_for_heat(5) == 5
    assert tier_for_heat(6) == 5
    assert tier_for_heat(7) == 7
    assert tier_for_heat(8) == 7
    assert tier_for_heat(9) == 9
    assert tier_for_heat(10) == 9


# ---------------------------------------------------------------------------
# researched truth bank — completeness at every tier
# ---------------------------------------------------------------------------
def test_truth_bank_complete():
    for tier in (1, 3, 5, 7, 9):
        assert len(TRUTH_BANK[tier]) >= 4, f"truth tier {tier} too small"
        for q in TRUTH_BANK[tier]:
            assert isinstance(q, str) and len(q) > 15
            # Questions are either interrogatives or "tell/describe me..." prompts
            assert q.strip().endswith("?") or q.strip().lower().startswith(("tell", "describe", "what", "why", "how"))

def test_fallback_dares_complete():
    for tier in range(1, 11):
        assert len(FALLBACK_DARES[tier]) >= 1, f"dare tier {tier} too small"
        for title, steps in FALLBACK_DARES[tier]:
            assert isinstance(title, str) and title
            assert len(steps) >= 2
            for instr, secs in steps:
                assert isinstance(instr, str) and len(instr) > 10
                assert 5 <= secs <= 180

def test_truth_for_heat_returns_question():
    for heat in (1, 3, 5, 7, 9, 10):
        q = truth_for_heat(heat, [])
        assert len(q) > 15
        assert q.strip().endswith("?") or q.strip().lower().startswith(("tell", "describe", "what", "why", "how"))

def test_truth_for_heat_avoids_recent():
    seen = set()
    for _ in range(6):
        q = truth_for_heat(5, list(seen))
        assert q[:40] not in seen
        seen.add(q[:40])


# ---------------------------------------------------------------------------
# fallback_challenge
# ---------------------------------------------------------------------------
def test_fallback_truth_is_question():
    for heat in (1, 3, 5, 7, 9, 10):
        title, steps = fallback_challenge("truth", heat, "Alex", "Sam", [])
        assert len(steps) == 1
        assert steps[0]["seconds"] == 45
        assert len(steps[0]["instruction"]) > 15
        assert title

def test_fallback_truth_absolute_last_resort():
    # Exhaust every truth question in the bank -> still returns a valid question
    all_titles = set()
    for tier in (1, 3, 5, 7, 9):
        for q in TRUTH_BANK[tier]:
            all_titles.add(q[:40])
    t, steps = fallback_challenge("truth", 5, "Alex", "Sam", list(all_titles))
    assert len(steps) == 1
    assert len(steps[0]["instruction"]) > 15

def test_fallback_dare_absolute_last_resort():
    # Exhaust every dare title across all tiers -> forces the final fallback line
    all_titles = set()
    for tier in range(1, 11):
        for title, _ in FALLBACK_DARES[tier]:
            all_titles.add(title)
    t, steps = fallback_challenge("dare", 5, "Alex", "Sam", list(all_titles))
    assert t
    assert len(steps) >= 1
    for s in steps:
        assert s["instruction"] and 5 <= s["seconds"] <= 180

def test_fallback_dare_is_multi_step():
    for heat in (1, 3, 5, 7, 9, 10):
        title, steps = fallback_challenge("dare", heat, "Alex", "Sam", [])
        assert len(steps) >= 2, f"dare at heat {heat} too short"
        for s in steps:
            assert s["instruction"] and 5 <= s["seconds"] <= 180
        assert title

def test_fallback_avoids_recent():
    seen = set()
    for i in range(6):
        title, _ = fallback_challenge("dare", 5, "Alex", "Sam", list(seen))
        assert title not in seen, f"repeated title {title}"
        seen.add(title)

def test_fallback_never_empty():
    # Even with every title in recent, must return something
    all_titles = [t for ts in FALLBACK_DARES.values() for t, _ in ts]
    title, steps = fallback_challenge("dare", 5, "Alex", "Sam", all_titles)
    assert title and steps


# ---------------------------------------------------------------------------
# normalize_steps
# ---------------------------------------------------------------------------
def test_normalize_full_steps():
    obj = {"text": "Title", "steps": [
        {"instruction": "Do A", "seconds": 30},
        {"instruction": "Do B", "seconds": 45},
    ]}
    title, steps = normalize_steps(obj, 5)
    assert title == "Title"
    assert len(steps) == 2
    assert steps[0] == {"instruction": "Do A", "seconds": 30}

def test_normalize_clamps_seconds():
    obj = {"steps": [{"instruction": "X", "seconds": 9999}, {"instruction": "Y", "seconds": 1}]}
    _, steps = normalize_steps(obj, 5)
    assert steps[0]["seconds"] == 180
    assert steps[1]["seconds"] == 5

def test_normalize_bad_seconds_defaults():
    obj = {"steps": [{"instruction": "X", "seconds": "abc"}]}
    _, steps = normalize_steps(obj, 5)
    assert steps[0]["seconds"] == 30

def test_normalize_string_steps():
    obj = {"steps": ["Just do this thing"]}
    _, steps = normalize_steps(obj, 5)
    assert steps[0]["instruction"] == "Just do this thing"
    assert steps[0]["seconds"] == 30

def test_normalize_text_only():
    obj = {"text": "A long single instruction without steps"}
    title, steps = normalize_steps(obj, 5)
    assert len(steps) == 1
    assert steps[0]["instruction"].startswith("A long single")

def test_normalize_empty_returns_none():
    assert normalize_steps({}, 5) is None
    assert normalize_steps({"steps": []}, 5) is None
    assert normalize_steps({"steps": [{"instruction": ""}]}, 5) is None

def test_normalize_caps_at_six_steps():
    obj = {"steps": [{"instruction": f"S{i}", "seconds": 20} for i in range(10)]}
    _, steps = normalize_steps(obj, 5)
    assert len(steps) == 6


# ---------------------------------------------------------------------------
# truth_streak_logic
# ---------------------------------------------------------------------------
def test_streak_truth_increments():
    s, forced = truth_streak_logic(0, "truth")
    assert (s, forced) == (1, False)
    s, forced = truth_streak_logic(1, "truth")
    assert (s, forced) == (2, False)

def test_streak_dare_resets():
    s, forced = truth_streak_logic(2, "dare")
    assert (s, forced) == (0, False)

def test_streak_forced_at_limit():
    # 2 truths in a row -> the 3rd pick is forced to a dare
    s, forced = truth_streak_logic(2, "truth")
    assert (s, forced) == (0, True)
    s, forced = truth_streak_logic(2, "dare")
    assert (s, forced) == (0, False)

def test_streak_above_limit_still_forced():
    s, forced = truth_streak_logic(5, "truth")
    assert (s, forced) == (0, True)

def test_streak_full_cycle():
    # 3 truths -> forced dare -> reset
    s, _ = truth_streak_logic(0, "truth")
    s, _ = truth_streak_logic(s, "truth")
    s, forced = truth_streak_logic(s, "truth")
    assert forced is True and s == 0


# ---------------------------------------------------------------------------
# mystery phases
# ---------------------------------------------------------------------------
def test_phase_mapping():
    assert phase_for_round(1)["name"] == "First Glance"
    assert phase_for_round(2)["name"] == "First Glance"
    assert phase_for_round(3)["name"] == "Warming Up"
    assert phase_for_round(4)["name"] == "Warming Up"
    assert phase_for_round(5)["name"] == "The Oath"
    assert phase_for_round(6)["name"] == "Unveiling"
    assert phase_for_round(8)["name"] == "Unveiling"
    assert phase_for_round(9)["name"] == "No Secrets Left"
    assert phase_for_round(20)["name"] == "No Secrets Left"

def test_phase_always_has_name_and_desc():
    for r in range(1, 30):
        p = phase_for_round(r)
        assert p["name"] and p["desc"]

def test_phase_clamps_bad_input():
    assert phase_for_round(0)["name"] == "First Glance"
    assert phase_for_round(-3)["name"] == "First Glance"


# ---------------------------------------------------------------------------
# the oath
# ---------------------------------------------------------------------------
def test_oath_due():
    assert oath_due(5) is True
    assert oath_due(4) is False
    assert oath_due(6) is False
    assert oath_due(1) is False

def test_oath_constants():
    assert OATH_ROUND == 5
    assert PENALTY_AMOUNT == 100
    assert "seriously" in OATH_TEXT.lower()
    assert "$100" in OATH_TEXT


# ---------------------------------------------------------------------------
# penalty ledger
# ---------------------------------------------------------------------------
def test_record_penalty_adds_entry():
    ledger = {}
    ledger = record_penalty(ledger, "Alex", "skipped a dare step")
    assert len(ledger["Alex"]) == 1
    assert ledger["Alex"][0]["amount"] == 100
    assert ledger["Alex"][0]["reason"] == "skipped a dare step"

def test_record_penalty_accumulates():
    ledger = {}
    ledger = record_penalty(ledger, "Alex", "a")
    ledger = record_penalty(ledger, "Alex", "b")
    ledger = record_penalty(ledger, "Sam", "c")
    assert penalty_summary(ledger) == {"Alex": 200, "Sam": 100}

def test_record_penalty_ignores_bad_input():
    ledger = {}
    ledger = record_penalty(ledger, "", "x")  # empty name -> "Player"
    assert "Player" in ledger
    ledger = record_penalty(None, "Alex", "y")  # None ledger -> fresh
    assert "Alex" in ledger

def test_penalty_summary_empty():
    assert penalty_summary({}) == {}
    assert penalty_summary(None) == {}
