"""Server-side room store for multi-device play — SQLite, WAL mode.

Rooms are the single source of truth for a game. The host's browser drives
actions; the partner's browser polls /api/room/state and renders the same
challenge, timer, and ledger. State is a versioned JSON blob so a reconnecting
client can re-sync by comparing versions.
"""
import json
import os
import secrets
import sqlite3
import threading
import time

DB_PATH = os.environ.get("DIRTYTRUTH_DB", os.path.join(os.path.dirname(__file__), "rooms.db"))

_local = threading.local()
_lock = threading.Lock()


def _conn():
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        _local.conn = c
    return c


def init_db():
    c = _conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            code TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            seq INTEGER NOT NULL,
            type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            ts REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_room ON events(room_code, seq);
        """
    )
    c.commit()


def _new_state(host_name, host_gender, lang):
    return {
        "players": [
            {"name": host_name, "gender": host_gender, "role": "host"},
            {"name": "", "gender": "", "role": "guest", "joined": False},
        ],
        "lang": lang or "en",
        "heat": 2,
        "round": 1,
        "target": None,
        "challenge": None,
        "stepIdx": 0,
        "phase": "First Glance",
        "truthStreak": {},
        "ledger": {},
        "oathSworn": False,
        "recent": [],
        "status": "setup",  # setup | playing | oath | done
        "prefs": {},
    }


def _code():
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(4))
        if not get_room(code):
            return code


def create_room(host_name, host_gender, lang="en"):
    with _lock:
        c = _conn()
        code = _code()
        state = _new_state(host_name, host_gender, lang)
        now = time.time()
        c.execute(
            "INSERT INTO rooms (code, state_json, version, created_at, updated_at) VALUES (?,?,?,?,?)",
            (code, json.dumps(state), 0, now, now),
        )
        c.commit()
        return code, state


def get_room(code):
    c = _conn()
    row = c.execute("SELECT state_json, version FROM rooms WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    return {"code": code, "state": json.loads(row["state_json"]), "version": row["version"]}


def update_room(code, mutate):
    """Apply `mutate(state)` atomically; bump version; return (state, version)."""
    with _lock:
        c = _conn()
        row = c.execute("SELECT state_json, version FROM rooms WHERE code=?", (code,)).fetchone()
        if not row:
            return None, None
        state = json.loads(row["state_json"])
        mutate(state)
        version = row["version"] + 1
        c.execute(
            "UPDATE rooms SET state_json=?, version=?, updated_at=? WHERE code=?",
            (json.dumps(state), version, time.time(), code),
        )
        c.commit()
        return state, version


def append_event(code, etype, payload):
    c = _conn()
    seq = c.execute("SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE room_code=?", (code,)).fetchone()[0]
    c.execute(
        "INSERT INTO events (room_code, seq, type, payload_json, ts) VALUES (?,?,?,?,?)",
        (code, seq, etype, json.dumps(payload), time.time()),
    )
    c.commit()
    return seq


def recent_events(code, since_seq=0, limit=50):
    c = _conn()
    rows = c.execute(
        "SELECT seq, type, payload_json, ts FROM events WHERE room_code=? AND seq>? ORDER BY seq LIMIT ?",
        (code, since_seq, limit),
    ).fetchall()
    return [
        {"seq": r["seq"], "type": r["type"], "payload": json.loads(r["payload_json"]), "ts": r["ts"]}
        for r in rows
    ]


def prune_rooms(max_age=7 * 24 * 3600):
    """Remove rooms idle for max_age seconds (default 7 days)."""
    with _lock:
        c = _conn()
        cutoff = time.time() - max_age
        c.execute("DELETE FROM rooms WHERE updated_at < ?", (cutoff,))
        c.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        c.commit()
