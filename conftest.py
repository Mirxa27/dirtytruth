"""Pytest config — isolate the room DB so tests never touch the live service's DB."""
import os
import tempfile

# Point the room store at a throwaway file BEFORE app/rooms are imported.
os.environ["DIRTYTRUTH_DB"] = os.path.join(tempfile.mkdtemp(prefix="dt_test_"), "rooms.db")

# Tests exercise endpoint behavior directly; keep the per-IP rate limiter off
# (dedicated tests flip it back on locally).
os.environ["DT_RL_GENERATE"] = "0"
os.environ["DT_RL_CHAT"] = "0"
os.environ["DT_RL_TTS"] = "0"
