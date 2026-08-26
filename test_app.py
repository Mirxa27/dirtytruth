"""Integration tests for the Flask app — LLM and TTS mocked, everything else real."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import app as appmod
import rooms
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# health / index
# ---------------------------------------------------------------------------
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["engine"] == "Cassia AI"

def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Dirty Truth" in html
    assert "choiceCard" in html
    assert "spinBtn" in html

def test_favicon_serves_svg(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert r.content_type == "image/svg+xml"
    assert b"<svg" in r.data

def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"

def test_404_api_returns_json(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.get_json()["error"] == "not found"

def test_404_non_api_serves_index(client):
    r = client.get("/some/deep/route")
    assert r.status_code == 200
    assert "Dirty Truth" in r.get_data(as_text=True)

def test_413_payload_too_large(client):
    r = client.post("/api/generate", data="x" * (2 * 1024 * 1024), content_type="application/json")
    assert r.status_code == 413
    assert r.get_json()["error"] == "payload too large"

def test_create_app_factory():
    a = appmod.create_app()
    assert a is app

def test_main_serves_with_waitress(monkeypatch):
    calls = {}
    class FakeWaitress:
        @staticmethod
        def serve(app_, host=None, port=None, threads=None, channel_timeout=None, recv_bytes=None):
            calls.update(app_=app_, host=host, port=port, threads=threads)
    import types
    fake_mod = types.ModuleType("waitress")
    fake_mod.serve = FakeWaitress.serve
    monkeypatch.setitem(sys.modules, "waitress", fake_mod)
    appmod.main()
    assert calls["app_"] is app
    assert calls["port"] == 8084
    assert calls["host"] == "0.0.0.0"

def test_500_handler_returns_json():
    # Use a throwaway app so we don't pollute the shared app's config/url_map.
    from flask import Flask
    t = Flask(__name__)
    t.register_error_handler(500, appmod.server_error)

    @t.route("/api/_test_500")
    def _boom():
        raise RuntimeError("boom")
    with t.test_client() as c:
        r = c.get("/api/_test_500")
    assert r.status_code == 500
    assert r.get_json()["error"] == "internal server error"


# ---------------------------------------------------------------------------
# /api/generate — LLM mocked
# ---------------------------------------------------------------------------
def test_generate_dare_llm(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({
            "text": "Slow Embrace",
            "steps": [
                {"instruction": "Alex, hold Sam close and kiss her neck slowly.", "seconds": 30},
                {"instruction": "Whisper a secret into her ear.", "seconds": 20},
            ],
        })
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/generate", json={
        "players": [{"name": "Alex", "gender": "male"}, {"name": "Sam", "gender": "female"}],
        "chosen": "dare", "target": "Alex", "heat": 4, "recent": [], "round": 2,
    })
    assert r.status_code == 200
    d = r.get_json()
    assert d["type"] == "dare"
    assert d["engine"] == "cassia"
    assert d["title"] == "Slow Embrace"
    assert len(d["steps"]) == 2
    assert all(s["seconds"] for s in d["steps"])

def test_generate_truth_llm_collapses_to_question(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({
            "text": "A secret desire",
            "steps": [{"instruction": "Alex, tell Sam the exact spot on his body you most want to kiss and why.", "seconds": 45}],
        })
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/generate", json={
        "players": [{"name": "Alex", "gender": "male"}, {"name": "Sam", "gender": "female"}],
        "chosen": "truth", "target": "Alex", "heat": 3, "recent": [], "round": 1,
    })
    d = r.get_json()
    assert d["type"] == "truth"
    assert len(d["steps"]) == 1
    assert d["steps"][0]["seconds"] == 45
    # Backend returns the raw question (no prefix, no trailing punctuation) —
    # the frontend adds the localized "Answer out loud:" prefix + "?"
    assert not d["steps"][0]["instruction"].startswith("Answer out loud")
    assert d["steps"][0]["instruction"].endswith("why")  # trailing "." stripped
    assert len(d["steps"][0]["instruction"]) > 15

def test_generate_truth_llm_without_question_mark_stripped(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({
            "text": "Tell me",
            "steps": [{"instruction": "Alex, describe your favorite memory of us", "seconds": 45}],
        })
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/generate", json={
        "players": [{"name": "Alex", "gender": "male"}, {"name": "Sam", "gender": "female"}],
        "chosen": "truth", "target": "Alex", "heat": 3, "recent": [], "round": 1,
    })
    d = r.get_json()
    # trailing punctuation stripped; frontend appends "?"
    assert not d["steps"][0]["instruction"].endswith(("?", ".", "!"))
    assert "Answer out loud" not in d["steps"][0]["instruction"]

def test_generate_truth_strips_llm_added_prefix(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({
            "text": "T",
            "steps": [{"instruction": "Answer out loud: Alex, describe your favorite memory of us", "seconds": 45}],
        })
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/generate", json={
        "players": [{"name": "Alex", "gender": "male"}, {"name": "Sam", "gender": "female"}],
        "chosen": "truth", "target": "Alex", "heat": 7, "recent": [], "round": 1,
    })
    d = r.get_json()
    # LLM-added prefix stripped; frontend will add the localized one
    assert "Answer out loud" not in d["steps"][0]["instruction"]
    assert d["steps"][0]["instruction"].startswith("Alex, describe")

def test_generate_fallback_on_llm_failure(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", json={
        "players": [{"name": "Alex", "gender": "male"}, {"name": "Sam", "gender": "female"}],
        "chosen": "dare", "target": "Alex", "heat": 5, "recent": [], "round": 3,
    })
    d = r.get_json()
    assert d["engine"] == "fallback"
    assert d["type"] == "dare"
    assert len(d["steps"]) >= 2
    assert d["title"]

def test_generate_fallback_truth_is_question(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", json={
        "players": [{"name": "Alex", "gender": "male"}, {"name": "Sam", "gender": "female"}],
        "chosen": "truth", "target": "Sam", "heat": 7, "recent": [], "round": 5,
    })
    d = r.get_json()
    assert d["type"] == "truth"
    assert len(d["steps"]) == 1
    assert len(d["steps"][0]["instruction"]) > 15

def test_generate_bad_input_defaults(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", json={})
    assert r.status_code == 200
    d = r.get_json()
    assert d["type"] in ("truth", "dare")
    assert d["steps"]

def test_generate_ignores_unknown_chosen(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", json={"chosen": "banana", "target": "Alex", "heat": 3})
    d = r.get_json()
    assert d["type"] == "truth"  # unknown -> defaults to truth

def test_generate_malformed_heat_and_round(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", json={"heat": "abc", "round": None, "target": "Alex"})
    assert r.status_code == 200
    assert r.get_json()["steps"]

def test_generate_malformed_players(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", json={
        "players": ["not-a-dict", {"name": "", "gender": 123}, {"name": "Alex", "gender": "male"}],
        "chosen": "dare", "target": "Alex", "heat": 3,
    })
    assert r.status_code == 200
    assert r.get_json()["steps"]

def test_generate_non_dict_json_body(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/generate", data='"just a string"', content_type="application/json")
    assert r.status_code == 200
    assert r.get_json()["steps"]

def test_chat_malformed_heat(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"reply": "ok"})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/chat", json={"message": "hi", "heat": "zzz", "target": 42})
    assert r.status_code == 200
    assert r.get_json()["reply"] == "ok"


# ---------------------------------------------------------------------------
# /api/streak — pure logic endpoint
# ---------------------------------------------------------------------------
def test_streak_endpoint(client):
    r = client.post("/api/streak", json={"streak": 0, "chosen": "truth"})
    assert r.get_json() == {"streak": 1, "forced": False, "limit": 3}
    r = client.post("/api/streak", json={"streak": 2, "chosen": "truth"})
    assert r.get_json() == {"streak": 0, "forced": True, "limit": 3}
    r = client.post("/api/streak", json={"streak": 2, "chosen": "dare"})
    assert r.get_json() == {"streak": 0, "forced": False, "limit": 3}

def test_oath_endpoint_due(client):
    r = client.post("/api/oath", json={"round": 5})
    d = r.get_json()
    assert d["due"] is True
    assert d["round"] == 5
    assert d["penalty"] == 100
    assert "seriously" in d["text"].lower()

def test_oath_endpoint_not_due(client):
    r = client.post("/api/oath", json={"round": 3})
    assert r.get_json()["due"] is False

def test_oath_endpoint_bad_round(client):
    r = client.post("/api/oath", json={"round": "garbage"})
    assert r.status_code == 200
    assert r.get_json()["due"] is False

def test_penalty_endpoint_records(client):
    r = client.post("/api/penalty", json={
        "ledger": {}, "player": "Alex", "reason": "skipped a dare step",
    })
    d = r.get_json()
    assert d["amount"] == 100
    assert d["player"] == "Alex"
    assert d["totals"] == {"Alex": 100}
    assert len(d["ledger"]["Alex"]) == 1

def test_penalty_endpoint_accumulates(client):
    ledger = {"Alex": [{"reason": "a", "amount": 100}]}
    r = client.post("/api/penalty", json={"ledger": ledger, "player": "Alex", "reason": "b"})
    d = r.get_json()
    assert d["totals"] == {"Alex": 200}
    assert len(d["ledger"]["Alex"]) == 2

def test_penalty_endpoint_bad_ledger(client):
    r = client.post("/api/penalty", json={"ledger": "not-a-dict", "player": "Sam"})
    d = r.get_json()
    assert d["totals"] == {"Sam": 100}

def test_penalty_endpoint_empty_player(client):
    r = client.post("/api/penalty", json={"ledger": {}, "player": "   "})
    assert r.get_json()["player"] == "Player"

def test_generate_returns_phase(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"text": "T", "steps": [{"instruction": "Do it", "seconds": 30}]})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/generate", json={"chosen": "dare", "target": "Alex", "heat": 3, "round": 1})
    d = r.get_json()
    assert d["phase"] == "First Glance"
    r = client.post("/api/generate", json={"chosen": "dare", "target": "Alex", "heat": 3, "round": 9})
    assert r.get_json()["phase"] == "No Secrets Left"

# ---------------------------------------------------------------------------
# languages
# ---------------------------------------------------------------------------
def test_languages_endpoint(client):
    r = client.get("/api/languages")
    d = r.get_json()
    assert d["default"] == "en"
    codes = [l["code"] for l in d["languages"]]
    for c in ["en","es","fr","de","it","pt","hi","ja","zh","ar"]:
        assert c in codes
    ar = next(l for l in d["languages"] if l["code"] == "ar")
    assert ar["rtl"] is True

def test_generate_with_language(client, monkeypatch):
    captured = {}
    def fake_llm(payload, retries=3):
        captured["sys"] = payload["messages"][0]["content"]
        return json.dumps({"text": "T", "steps": [{"instruction": "Do it", "seconds": 30}]})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    client.post("/api/generate", json={"chosen": "truth", "target": "Alex", "heat": 3, "lang": "es"})
    assert "Spanish" in captured["sys"]

def test_tts_language_voice(client, monkeypatch):
    # verify the TTS endpoint picks a language-appropriate voice
    from languages import tts_voice
    assert tts_voice("en") == "af_heart"
    assert tts_voice("es") == "ef_dora"
    assert tts_voice("ja") == "jf_alpha"
    assert tts_voice("zh") == "zf_xiaoni"
    assert tts_voice("ar") == "hf_alpha"  # closest available
    assert tts_voice("xx") == "af_heart"  # unknown -> English fallback

# ---------------------------------------------------------------------------
# rooms
# ---------------------------------------------------------------------------
def test_room_create(client):
    r = client.post("/api/room/create", json={"name": "Alex", "gender": "male", "lang": "en"})
    d = r.get_json()
    assert len(d["code"]) == 4
    assert d["state"]["players"][0]["name"] == "Alex"
    assert d["state"]["players"][1]["joined"] is False

def test_room_join(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.post("/api/room/join", json={"code": c, "name": "Sam", "gender": "female"})
    d = r.get_json()
    assert d["state"]["players"][1]["name"] == "Sam"
    assert d["state"]["players"][1]["joined"] is True

def test_room_join_not_found(client):
    r = client.post("/api/room/join", json={"code": "ZZZZ", "name": "Sam"})
    assert r.status_code == 404

def test_room_state(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.get(f"/api/room/state?code={c}")
    d = r.get_json()
    assert d["code"] == c
    assert "state" in d and "events" in d

def test_room_action_set_heat(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.post("/api/room/action", json={"code": c, "action": "set_heat", "heat": 7})
    d = r.get_json()
    assert d["state"]["heat"] == 7
    assert d["version"] >= 1

def test_room_action_penalty(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.post("/api/room/action", json={"code": c, "action": "penalty", "player": "Alex", "reason": "skipped"})
    d = r.get_json()
    assert d["state"]["ledger"]["Alex"][0]["amount"] == 100

def test_room_action_advance_round(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.post("/api/room/action", json={"code": c, "action": "advance_round"})
    assert r.get_json()["state"]["round"] == 2

def test_room_action_unknown(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.post("/api/room/action", json={"code": c, "action": "bogus_action"})
    assert r.status_code == 200  # no-op, still valid

def test_room_prefs(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    r = client.post("/api/room/prefs", json={"code": c, "player": "Alex", "prefs": {"turnons": "feathers", "fantasy": "x", "boundary": "y"}})
    d = r.get_json()
    assert d["ok"] is True
    st = client.get(f"/api/room/state?code={c}").get_json()["state"]
    assert st["prefs"]["Alex"]["turnons"] == "feathers"

def test_generate_with_prefs(client, monkeypatch):
    captured = {}
    def fake_llm(payload, retries=3):
        captured["user"] = payload["messages"][1]["content"]
        return json.dumps({"text": "T", "steps": [{"instruction": "Do it", "seconds": 30}]})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    client.post("/api/generate", json={
        "chosen": "dare", "target": "Alex", "heat": 5,
        "prefs": {"Alex": {"turnons": "feathers", "fantasy": "being held", "boundary": "no biting"}},
    })
    assert "feathers" in captured["user"]
    assert "being held" in captured["user"]
    assert "no biting" in captured["user"]

def test_room_action_all_branches(client):
    c = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    def act(payload):
        return client.post("/api/room/action", json={"code": c, **payload}).get_json()
    assert act({"action": "set_lang", "lang": "es"})["state"]["lang"] == "es"
    assert act({"action": "set_target", "target": "Sam"})["state"]["target"] == "Sam"
    assert act({"action": "set_challenge", "challenge": {"type": "dare", "title": "T", "steps": [{"instruction": "x", "seconds": 10}]}})["state"]["challenge"]["title"] == "T"
    assert act({"action": "set_step", "step": 2})["state"]["stepIdx"] == 2
    assert act({"action": "set_status", "status": "oath"})["state"]["status"] == "oath"
    assert act({"action": "set_streak", "player": "Alex", "streak": 2})["state"]["truthStreak"]["Alex"] == 2
    assert act({"action": "set_recent", "recent": ["a", "b"]})["state"]["recent"] == ["a", "b"]
    assert act({"action": "set_prefs", "prefs": {"Alex": {"turnons": "x"}}})["state"]["prefs"]["Alex"]["turnons"] == "x"
    assert act({"action": "set_player", "idx": 1, "name": "Sam", "gender": "female", "joined": True})["state"]["players"][1]["name"] == "Sam"
    assert act({"action": "set_oath", "sworn": True})["state"]["oathSworn"] is True
    # bad values are clamped, not crashed
    assert act({"action": "set_heat", "heat": "garbage"})["state"]["heat"] >= 1
    assert act({"action": "set_step", "step": "garbage"})["state"]["stepIdx"] >= 0

def test_is_rtl():
    from languages import is_rtl
    assert is_rtl("ar") is True
    assert is_rtl("en") is False

def test_streak_bad_input(client):
    r = client.post("/api/streak", json={"streak": "abc", "chosen": "truth"})
    assert r.status_code == 400
    r = client.post("/api/streak", json={})
    assert r.status_code == 200  # defaults: streak 0, truth


# ---------------------------------------------------------------------------
# /api/chat — LLM mocked
# ---------------------------------------------------------------------------
def test_chat_reply(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"reply": "Mmm, take your time with me.", "heat": None})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/chat", json={
        "message": "hello", "players": [{"name": "Alex", "gender": "male"}],
        "target": "Alex", "heat": 4, "recent": [],
    })
    d = r.get_json()
    assert d["reply"] == "Mmm, take your time with me."
    assert d["engine"] == "cassia"
    assert "heat" not in d

def test_chat_heat_change(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"reply": "Turning it up.", "heat": 8})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/chat", json={"message": "go harder", "heat": 5})
    d = r.get_json()
    assert d["heat"] == 8

def test_chat_question(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"reply": "Here you go.", "heat": 6, "question": "Blindfolded Kiss", "type": "dare"})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/chat", json={"message": "give me a dare", "heat": 5})
    d = r.get_json()
    assert d["question"] == "Blindfolded Kiss"
    assert d["type"] == "dare"

def test_chat_fallback_plain(client, monkeypatch):
    def boom(payload, retries=3):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    r = client.post("/api/chat", json={"message": "hello"})
    d = r.get_json()
    assert d["reply"]
    assert d["engine"] in ("cassia-plain", "fallback")


# ---------------------------------------------------------------------------
# /api/tts — mocked upstream
# ---------------------------------------------------------------------------
def test_tts_empty_text(client):
    r = client.post("/api/tts", json={"text": "   "})
    assert r.status_code == 400

def test_tts_success(client, monkeypatch):
    class FakeResp:
        content = b"FAKE_MP3_BYTES"
        def raise_for_status(self): pass
    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == appmod.TTS_URL
        assert json["voice"] == appmod.TTS_VOICE
        return FakeResp()
    monkeypatch.setattr(appmod.requests, "post", fake_post)
    r = client.post("/api/tts", json={"text": "Hello darling"})
    assert r.status_code == 200
    assert r.content_type == "audio/mpeg"
    assert r.data == b"FAKE_MP3_BYTES"

def test_tts_upstream_failure(client, monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        raise RuntimeError("tts down")
    monkeypatch.setattr(appmod.requests, "post", fake_post)
    r = client.post("/api/tts", json={"text": "Hello"})
    assert r.status_code == 502

def test_tts_truncates_long_text(client, monkeypatch):
    captured = {}
    class FakeResp:
        content = b"x"
        def raise_for_status(self): pass
    def fake_post(url, headers=None, json=None, timeout=None):
        captured["text"] = json["input"]
        return FakeResp()
    monkeypatch.setattr(appmod.requests, "post", fake_post)
    client.post("/api/tts", json={"text": "a" * 5000})
    assert len(captured["text"]) == 1200


# ---------------------------------------------------------------------------
# call_llm retry behavior
# ---------------------------------------------------------------------------
def test_call_llm_retries_on_empty(monkeypatch):
    calls = {"n": 0}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "" if calls["n"] < 2 else "ok"}, "finish_reason": "stop"}]}
    def fake_post(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        return FakeResp()
    monkeypatch.setattr(appmod.requests, "post", fake_post)
    monkeypatch.setattr(appmod.time, "sleep", lambda s: None)
    out = appmod.call_llm({"model": "x", "messages": []})
    assert out == "ok"
    assert calls["n"] == 2  # empty, empty, then success

def test_call_llm_raises_after_retries(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        raise RuntimeError("down")
    monkeypatch.setattr(appmod.requests, "post", fake_post)
    monkeypatch.setattr(appmod.time, "sleep", lambda s: None)
    try:
        appmod.call_llm({"model": "x", "messages": []})
        assert False, "should have raised"
    except RuntimeError as e:
        assert "3 attempts" in str(e)


# ---------------------------------------------------------------------------
# parse_json edge cases
# ---------------------------------------------------------------------------
def test_parse_json_clean():
    assert appmod.parse_json('{"a": 1}') == {"a": 1}

def test_parse_json_markdown_fenced():
    assert appmod.parse_json('```json\n{"a": 1}\n```') == {"a": 1}

def test_parse_json_embedded():
    assert appmod.parse_json('Sure! Here you go: {"a": 1} hope that helps') == {"a": 1}

def test_parse_json_truncated_salvages_text():
    out = appmod.parse_json('{"text": "Hello world, this is cut off')
    assert out["text"] == "Hello world, this is cut off"

def test_parse_json_truncated_salvages_reply():
    out = appmod.parse_json('{"reply": "Mmm, take your time"')
    assert out["reply"] == "Mmm, take your time"

def test_parse_json_invalid_raises():
    try:
        appmod.parse_json("no json here at all")
        assert False, "should have raised"
    except Exception:
        pass

def test_parse_json_truncated_with_escapes_fallback():
    # Truncated JSON (no closing quote) whose salvaged value contains an escape
    # sequence that json.loads('"...")' rejects (invalid \d escape) -> exercises
    # the manual-unescape fallback branch.
    out = appmod.parse_json('{"text": "line1\\dline2')
    assert "line1" in out["text"] and "line2" in out["text"]

def test_validate_challenge_empty_steps():
    assert appmod.validate_challenge("dare", "T", []) is None
    assert appmod.validate_challenge("truth", "T", []) is None

def test_validate_challenge_all_blank_instructions():
    assert appmod.validate_challenge("dare", "T", [{"instruction": "   ", "seconds": 30}]) is None

def test_validate_challenge_truth_only_prefix_returns_none():
    # A truth whose instruction is only the "Answer out loud:" prefix -> unusable
    assert appmod.validate_challenge("truth", "T", [{"instruction": "Answer out loud:", "seconds": 45}]) is None

def test_generate_llm_returns_empty_steps_falls_back(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"text": "", "steps": []})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/generate", json={"chosen": "dare", "target": "Alex", "heat": 4})
    d = r.get_json()
    assert d["engine"] == "fallback"
    assert d["steps"]

def test_chat_non_dict_json_body(client, monkeypatch):
    def fake_llm(payload, retries=3):
        return json.dumps({"reply": "ok"})
    monkeypatch.setattr(appmod, "call_llm", fake_llm)
    r = client.post("/api/chat", data='"just a string"', content_type="application/json")
    assert r.status_code == 200
    assert r.get_json()["reply"] == "ok"


# ---------------------------------------------------------------------------
# v5.1 — CSP header, rate limiting, join guard, event-seq race, secrets
# loader, room pruning
# ---------------------------------------------------------------------------
def test_csp_header_present(client):
    r = client.get("/api/health")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_rate_limited_endpoints_return_429(client, monkeypatch):
    monkeypatch.setattr(appmod, "RATE_LIMITS", {"/api/generate": 2})
    appmod._rl_hits.clear()

    def boom(payload, retries=3):  # force the offline-fallback path (still 200)
        raise RuntimeError("llm down")
    monkeypatch.setattr(appmod, "call_llm", boom)
    try:
        for _ in range(2):
            r = client.post("/api/generate", json={"chosen": "truth", "players": [{"name": "A"}, {"name": "B"}]})
            assert r.status_code == 200
            assert r.get_json()["engine"] == "fallback"
        r3 = client.post("/api/generate", json={"chosen": "truth"})
        assert r3.status_code == 429
        assert r3.get_json()["error"] == "rate limited"
    finally:
        appmod._rl_hits.clear()


def test_rate_limit_forwarded_for_isolated_ips(client, monkeypatch):
    monkeypatch.setattr(appmod, "RATE_LIMITS", {"/api/chat": 1})
    appmod._rl_hits.clear()
    try:
        def boom(*a, **k):
            raise RuntimeError("down")
        monkeypatch.setattr(appmod, "call_llm", boom)
        r1 = client.post("/api/chat", json={"message": "hi"})
        r2 = client.post("/api/chat", json={"message": "hi"},
                         environ_base={}, headers={"X-Forwarded-For": "203.0.113.9"})
        assert r1.status_code == 200
        # different IP bucket -> still served, not 429
        assert r2.status_code == 200
        r3 = client.post("/api/chat", json={"message": "hi"})
        assert r3.status_code == 429
    finally:
        appmod._rl_hits.clear()


def test_join_rejects_second_guest_but_allows_same_name_rejoin(client):
    code = client.post("/api/room/create", json={"name": "Alex"}).get_json()["code"]
    first = client.post("/api/room/join", json={"code": code, "name": "Sam"})
    assert first.status_code == 200
    hijack = client.post("/api/room/join", json={"code": code, "name": "Bob"})
    assert hijack.status_code == 409
    assert hijack.get_json()["error"] == "room full"
    # page reload of the SAME guest rejoins idempotently
    rejoin = client.post("/api/room/join", json={"code": code, "name": "Sam"})
    assert rejoin.status_code == 200
    assert rejoin.get_json()["state"]["players"][1]["name"] == "Sam"


def test_join_unknown_shape_returns_404_not_500(client):
    r = client.post("/api/room/join", json={"code": "ZZZZ", "name": "Sam"})
    assert r.status_code == 404


def test_event_seqs_are_unique_and_contiguous_under_concurrency():
    import concurrent.futures as cf
    code, _state = rooms.create_room("Alex", "male")
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda i: rooms.append_event(code, "act", {"i": i}), range(40)))
    seqs = [e["seq"] for e in rooms.recent_events(code, 0, 100)]
    assert len(seqs) == 40
    assert sorted(seqs) == list(range(1, 41))


def test_prune_rooms_drops_idle_rooms():
    code, _state = rooms.create_room("Old", "male")
    with rooms._lock:
        c = rooms._conn()
        c.execute("UPDATE rooms SET updated_at=? WHERE code=?", (time.time() - 8 * 24 * 3600, code))
        c.commit()
    assert rooms.get_room(code) is not None  # sanity before pruning
    rooms.prune_rooms(max_age=7 * 24 * 3600)
    assert rooms.get_room(code) is None


def test_load_secrets_env_wins_over_file(tmp_path, monkeypatch):
    f = tmp_path / "s.env"
    f.write_text("DT_A=fromfile\nDT_B=fromfile\n# comment\n\nDT_C=\"quoted\"\n")
    monkeypatch.setenv("DT_A", "fromenv")
    appmod._load_secrets(str(f))
    import os
    assert os.environ["DT_A"] == "fromenv"
    assert os.environ.pop("DT_B") == "fromfile"
    assert os.environ.pop("DT_C") == "quoted"


def test_pwa_assets_served(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    man = r.get_json()
    assert man["start_url"] == "/"
    assert any(i.get("src") == "/icon.svg" for i in man["icons"])
    r2 = client.get("/icon.svg")
    assert r2.status_code == 200
    assert b"<svg" in r2.data
