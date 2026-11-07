"""Worker and match tests: badly behaved bots must never break a game.

Run from the repo root:  python -m unittest discover -s harness -p "test_*.py"
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from match import Match  # noqa: E402

BOTS = {
    "crasher.py": """
def act(state):
    raise RuntimeError("boom")
""",
    "illegal.py": """
calls = 0
def act(state):
    global calls
    calls += 1
    return "JUMP" if calls % 2 else 7
""",
    "sleeper.py": """
import time
calls = 0
def act(state):
    global calls
    calls += 1
    if calls == 2:
        time.sleep(0.35)
    if calls == 3:
        time.sleep(30)
    return "STAY"
""",
    "noisy.py": """
import os, sys
calls = 0
def act(state):
    global calls
    calls += 1
    print("call", calls, "seat", state.bot_id)
    os.write(1, b"raw fd write\\n")
    sys.stderr.write("to stderr\\n")
    try:
        input()
    except EOFError:
        pass
    state.board[0][0].owner = 99
    state.legal_actions.clear()
    if calls == 4:
        sys.exit(3)
    return "SHIELD" if calls == 1 else "STAY"
""",
    "broken.py": "def act(state:\n    return 'STAY'\n",
    "no_act.py": "x = 1\n",
}


class FakeRepo(object):
    root = HERE

    def __init__(self, folder):
        self.folder = folder

    def resolve(self, spec):
        return {"file": os.path.join(self.folder, spec["path"]), "label": spec["path"],
                "source": "test", "path": spec["path"], "sha256": ""}


class BadBots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        for name, body in BOTS.items():
            with open(os.path.join(cls.dir, name), "w") as f:
                f.write(body)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def play(self, names, turns=5):
        config = {"seats": [{"path": n} for n in names], "max_turns": turns,
                  "timing": {"hard_s": 1.5, "first_ms": 2000, "turn_ms": 200}}
        m = Match(config, FakeRepo(self.dir))
        out = os.path.join(self.dir, "replays")
        m.save = lambda folder=None, _save=m.save: _save(out)
        rp = m.run()
        self.assertEqual(rp["status"], "done", rp.get("error"))
        self.assertEqual(len(rp["turns"]), turns)
        return rp

    def column(self, rp, seat, key):
        return [t["bots"][seat - 1][key] for t in rp["turns"]]

    def test_misbehaving_bots(self):
        rp = self.play(["crasher.py", "illegal.py", "sleeper.py", "noisy.py"])
        self.assertEqual(self.column(rp, 1, "status"), ["crash"] * 5)
        self.assertIn("RuntimeError: boom", rp["turns"][0]["bots"][0]["error"])
        self.assertNotIn("worker.py", rp["turns"][0]["bots"][0]["error"])
        self.assertEqual(self.column(rp, 2, "status"), ["illegal"] * 5)
        self.assertEqual(rp["turns"][1]["bots"][1]["returned"], "7")
        # the restart wipes the bot's counter, so turn 5 is its second call again and runs late
        self.assertEqual(self.column(rp, 3, "status"), ["ok", "late", "killed", "ok", "late"])
        self.assertEqual(rp["turns"][3]["bots"][2]["note"], "worker restarted, bot memory was lost")
        self.assertEqual(rp["seats"][2]["restarts"], 1)
        noisy = self.column(rp, 4, "status")
        self.assertEqual(noisy, ["ok", "ok", "ok", "crash", "ok"])
        self.assertIn("call 2 seat 4", rp["turns"][1]["bots"][3]["out"])
        self.assertIn("to stderr", rp["turns"][1]["bots"][3]["out"])
        self.assertIn("SystemExit: 3", rp["turns"][3]["bots"][3]["error"])
        self.assertIn("call 5", rp["turns"][4]["bots"][3]["out"])       # memory survived the crash
        self.assertEqual(rp["turns"][0]["bots"][3]["used"], "SHIELD")
        self.assertEqual(rp["turns"][1]["state"]["owner"][0], 1)         # mutating state changes nothing
        for t in rp["turns"]:
            for b in t["bots"]:
                if b["status"] != "ok":
                    self.assertEqual(b["used"], "STAY")

    def test_load_failures_play_stay(self):
        rp = self.play(["broken.py", "no_act.py", "illegal.py", "illegal.py"], turns=3)
        self.assertFalse(rp["seats"][0]["load"]["ok"])
        self.assertIn("SyntaxError", rp["seats"][0]["load"]["error"])
        self.assertIn("no act(state)", rp["seats"][1]["load"]["error"])
        self.assertEqual(self.column(rp, 1, "status"), ["load-failed"] * 3)
        self.assertEqual(self.column(rp, 2, "status"), ["load-failed"] * 3)

    def test_seats_have_separate_memory(self):
        rp = self.play(["noisy.py", "noisy.py", "noisy.py", "noisy.py"], turns=2)
        for seat in range(4):
            self.assertIn("call 2 seat %d" % (seat + 1), rp["turns"][1]["bots"][seat]["out"])


if __name__ == "__main__":
    unittest.main()
