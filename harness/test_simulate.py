"""Tests for the endless simulator (simulate.py) and its report (simreport.py).

Run from the repo root:  python -m unittest discover -s harness -p "test_*.py"
"""
import itertools
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import simreport  # noqa: E402
import simulate  # noqa: E402
from match import BotProcess, Match  # noqa: E402
from sources import BUILTIN, Repo  # noqa: E402


class BuiltinRepo(object):
    """Resolves {"path": name} to the harness's built-in bots, without git."""
    root = HERE

    def resolve(self, spec):
        return {"file": os.path.join(BUILTIN, spec["path"]), "label": spec["path"], "source": "builtin",
                "path": spec["path"], "sha256": ""}


def play_builtin(names, seed=None, turns=80, token=1):
    m = Match({"seats": [{"path": n} for n in names], "max_turns": turns, "start_token": token,
               "map": {"kind": "random", "seed": seed} if seed is not None else {"kind": "example"}},
              BuiltinRepo())
    m.save = lambda folder=None: None
    return m.run()


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_rows(path):
    return [json.loads(line) for line in read(path).splitlines() if line.strip()]


def row_for(n, block, codes, scores, cells=None, status="done"):
    """A games.jsonl row built through the real compressor from a minimal replay."""
    rp = {"status": status, "turns": [], "base": [1] * 64, "initial": {},
          "seats": [{"load": {"ok": True, "ms": 5.0}, "restarts": 0} for _ in range(4)],
          "result": {"score": scores, "cells": cells or [5, 5, 5, 5], "upgraded": [0, 0, 0, 0]}}
    meta = {"n": n, "block": block, "rot": 0, "seats": codes, "map": {"kind": "example"}, "token": 1}
    return simreport.game_record(rp, meta)


def session_for(codes, **settings):
    return {"id": "t", "entrants": [{"code": c, "name": "bot " + c, "source": "git", "submission": c == "A",
                                     "path": "bot.py", "checks": {"stdlib_only": True, "self_contained": True,
                                                                  "signature_ok": True}, "repro": "x:" + c}
                                    for c in codes],
            "settings": dict({"elo_k": 16, "elo_start": 1500, "turns": 80, "maps": ["example"],
                              "timing": {"enforce": True, "turn_ms": 200, "first_ms": 2000}}, **settings)}


class RulebookScoring(unittest.TestCase):
    def test_round1_places_share_equal_totals(self):
        self.assertEqual(simreport.round1_places([10, 20, 20, 5]), [3, 1, 1, 4])
        self.assertEqual(simreport.round1_places([7, 7, 7, 7]), [1, 1, 1, 1])

    def test_round2_example_from_rulebook_5_4(self):
        # final scores 412, 380, 380, 201; the two on 380 own 14 and 11 cells -> 3, 2, 1, 0
        places = simreport.round2_places([412, 380, 380, 201], [9, 14, 11, 3])
        self.assertEqual(places, [1, 2, 3, 4])
        self.assertEqual(simreport.pool_points(places), [3, 2, 1, 0])
        # same number of cells -> they share 2nd and split 2 + 1
        places = simreport.round2_places([412, 380, 380, 201], [9, 12, 12, 3])
        self.assertEqual(places, [1, 2, 2, 4])
        self.assertEqual(simreport.pool_points(places), [3, 1.5, 1.5, 0])

    def test_every_pool_game_pays_exactly_six(self):
        rnd = random.Random(3)
        for _ in range(2000):
            scores = [rnd.choice([100, 200, 300]) for _ in range(4)]
            cells = [rnd.choice([4, 5]) for _ in range(4)]
            self.assertAlmostEqual(sum(simreport.pool_points(simreport.round2_places(scores, cells))), 6.0)

    def test_one_on_one_ignores_cells(self):
        self.assertEqual(simreport.one_on_one(5, 4), 1.0)
        self.assertEqual(simreport.one_on_one(4, 4), 0.5)
        self.assertEqual(simreport.one_on_one(3, 4), 0.0)


class Ratings(unittest.TestCase):
    def test_sequential_elo_is_zero_sum(self):
        rnd = random.Random(1)
        results = [[(a, b, rnd.choice([0.0, 0.5, 1.0])) for a, b in itertools.combinations(range(4), 2)]
                   for _ in range(200)]
        r = simulate.simreport.sequential_elo(results, 4, 16, 1500)
        self.assertAlmostEqual(sum(r), 6000.0, places=6)

    def test_bradley_terry_recovers_a_known_ratio(self):
        w = [[0, 3000], [1000, 0]]
        g = [[0, 4000], [4000, 0]]
        r, _ = simreport.bradley_terry(w, g, 1500, prior=1e-9)
        self.assertAlmostEqual(r[0] - r[1], 400 * math.log10(3), places=3)
        self.assertAlmostEqual(sum(r) / 2, 1500, places=6)

    def test_settled_rating_is_where_elo_stops_moving(self):
        # at the fitted ratings every bot's expected Elo change over the games played is zero
        rnd = random.Random(7)
        n = 5
        strength = [0, 80, 150, 220, 400]
        results = []
        for _ in range(3000):
            seats = rnd.sample(range(n), 4)
            pairs = []
            for a, b in itertools.combinations(seats, 2):
                p = 1 / (1 + 10 ** ((strength[b] - strength[a]) / 400))
                pairs.append((a, b, 1.0 if rnd.random() < p else 0.0))
            results.append(pairs)
        w, g = simreport.tally(results, n)
        r, _ = simreport.bradley_terry(w, g, 1500, prior=1e-9)
        for i in range(n):
            expected = sum(g[i][j] / (1 + 10 ** ((r[j] - r[i]) / 400)) for j in range(n) if g[i][j])
            self.assertAlmostEqual(expected, sum(w[i]), places=4)
        self.assertEqual(sorted(range(n), key=lambda i: r[i]), list(range(n)))

    def test_prior_keeps_winless_bot_finite(self):
        r, _ = simreport.bradley_terry([[0, 0], [10, 0]], [[0, 10], [10, 0]], 1500)
        self.assertTrue(all(math.isfinite(x) for x in r))
        self.assertLess(r[0], r[1])

    def test_wilson_interval(self):
        lo, hi = simreport.wilson(50, 100)
        self.assertAlmostEqual(lo + hi, 1.0, places=9)
        self.assertLess(lo, 0.5)
        self.assertEqual(simreport.wilson(0, 0), (0.0, 1.0))


class GameRecord(unittest.TestCase):
    def test_compression_of_real_games_is_consistent(self):
        for seed in (None, 11, 12):
            rp = play_builtin(["random_bot.py", "skeleton.py", "random_bot.py", "random_bot.py"], seed=seed)
            self.assertEqual(rp["status"], "done")
            row = simreport.game_record(rp, {"n": 1, "seats": ["A", "B", "C", "D"], "map": {"kind": "example"},
                                             "token": 1})
            self.assertEqual(row["turns"], 80)
            self.assertAlmostEqual(sum(s["pool"] for s in row["seats"]), 6.0)
            for i, s in enumerate(row["seats"]):
                self.assertTrue(s["consistent"], "score must equal income + raid bonuses")
                self.assertEqual(s["score"], rp["result"]["score"][i])
                self.assertEqual(s["free"] + s["frozen"], 80)
                self.assertEqual(sum(s["actions"].values()), s["free"])
                self.assertEqual(s["status"], {"ok": 80})
            raids = sum(s["raids"] for s in row["seats"])
            self.assertEqual(raids, sum(s["cells_lost"] for s in row["seats"]))
            self.assertEqual(sum(s["raid_bonus"] for s in row["seats"]), sum(s["bonus_conceded"] for s in row["seats"]))
            sk = row["seats"][1]
            self.assertEqual(sk["actions"]["STAY"], sk["free"])     # the skeleton only stays
            self.assertEqual(simreport.notable_reasons(row), [])

    def test_skeleton_scores_the_known_floor(self):
        rp = play_builtin(["skeleton.py"] * 4)
        row = simreport.game_record(rp, {"n": 1, "seats": list("AAAA"), "map": {"kind": "example"}, "token": 1})
        # home worth 1, upgraded by the third stay: 1 + 1 + 78 * 2
        self.assertEqual([s["score"] for s in row["seats"]], [158] * 4)
        self.assertEqual([s["upgrades"] for s in row["seats"]], [1] * 4)
        self.assertEqual([s["place"] for s in row["seats"]], [1] * 4)
        self.assertEqual(row["quadrant"], "1112/1122/1223/2233")


class Schedule(unittest.TestCase):
    def test_blocks_rotate_every_bot_through_every_seat(self):
        sch = simulate.Scheduler(6, ["example", "random", "random", "random"], random.Random(5))
        seat = [[0] * 4 for _ in range(6)]
        tokens = {}
        maps = {}
        for _ in range(60):
            block = sch.next_block()
            self.assertEqual(len(block), 4)
            self.assertEqual(len(set(map(id, [g["map"] for g in block]))), 1)
            self.assertEqual(len(set(g["token"] for g in block)), 1)
            lineups = [g["seats"] for g in block]
            self.assertEqual(len(set(lineups[0])), 4, "four different bots when there are enough")
            for r, g in enumerate(block):
                self.assertEqual(g["seats"], [lineups[0][(s + r) % 4] for s in range(4)])
                for s, e in enumerate(g["seats"]):
                    seat[e][s] += 1
            tokens[block[0]["token"]] = tokens.get(block[0]["token"], 0) + 1
            kind = block[0]["map"]["kind"]
            maps[kind] = maps.get(kind, 0) + 1
        for e in range(6):
            self.assertEqual(len(set(seat[e])), 1, "equal games in each seat")
        self.assertEqual(tokens, {1: 15, 2: 15, 3: 15, 4: 15})
        self.assertEqual(maps, {"example": 15, "random": 45})
        self.assertLessEqual(max(sch.appear) - min(sch.appear), 4)
        pairs = [sch.pair[a][b] for a, b in itertools.combinations(range(6), 2)]
        self.assertLessEqual(max(pairs) - min(pairs), 2)
        numbers = [g["n"] for _ in range(3) for g in sch.next_block()]
        self.assertEqual(numbers, list(range(241, 253)))

    def test_fewer_than_four_bots_repeat_evenly(self):
        sch = simulate.Scheduler(3, ["example"], random.Random(1))
        for _ in range(30):
            lineup = sch.next_block()[0]["seats"]
            self.assertEqual(set(lineup), {0, 1, 2})
        self.assertLessEqual(max(sch.appear) - min(sch.appear), 1)
        one = simulate.Scheduler(1, ["random"], random.Random(1))
        self.assertEqual(one.next_block()[0]["seats"], [0, 0, 0, 0])

    def test_many_bots_sample_lineups(self):
        sch = simulate.Scheduler(30, ["random"], random.Random(2))
        for _ in range(200):
            sch.next_block()
        self.assertLessEqual(max(sch.appear) - min(sch.appear), 4)

    def test_map_specs_are_valid(self):
        maps = simulate.parse_maps("example,random,custom:3333/3333/3333/3333")
        sch = simulate.Scheduler(4, maps, random.Random(9))
        kinds = set()
        for _ in range(12):
            spec = sch.next_block()[0]["map"]
            kinds.add(spec["kind"])
            simulate.build_map(spec)
        self.assertEqual(kinds, {"example", "random", "custom"})
        with self.assertRaises(simulate.SourceError):
            simulate.parse_maps("example,bogus")
        with self.assertRaises(simulate.SourceError):
            simulate.parse_maps("custom:1234/1111/1111/1111")


class SourceChecks(unittest.TestCase):
    def check(self, src, modules=(), data=()):
        return simulate.inspect_source(src.encode(), modules, data)

    def test_a_valid_submission(self):
        ck = self.check("import random, collections\nfrom time import perf_counter\n"
                        "def act(state):\n    return 'STAY'\n")
        self.assertTrue(ck["act"] and ck["signature_ok"] and ck["stdlib_only"] and ck["self_contained"])

    def test_third_party_and_sibling_imports(self):
        ck = self.check("import numpy\nimport engine\nfrom . import x\ndef act(state):\n    return 'STAY'\n",
                        modules={"engine"})
        self.assertEqual(ck["nonstdlib"], ["numpy"])
        self.assertIn("engine", ck["local_imports"])
        self.assertIn("relative import", ck["local_imports"])
        self.assertFalse(ck["stdlib_only"] or ck["self_contained"])

    def test_a_sibling_that_shadows_the_stdlib_counts_as_local(self):
        ck = self.check("import select\ndef act(state):\n    return 'STAY'\n", modules={"select"})
        self.assertEqual(ck["local_imports"], ["select"])

    def test_data_files_and_dynamic_imports(self):
        ck = self.check("import json\nP = json.load(open('nn_policy.json'))\nm = __import__('x')\n"
                        "def act(state):\n    return 'STAY'\n", data={"nn_policy.json"})
        self.assertEqual(ck["data_files"], ["nn_policy.json"])
        self.assertTrue(ck["dynamic_import"])
        self.assertFalse(ck["self_contained"])

    def test_signatures(self):
        self.assertFalse(self.check("def act(state, extra=1):\n    return 'STAY'\n")["signature_ok"])
        self.assertFalse(self.check("def act(*a):\n    return 'STAY'\n")["signature_ok"])
        ck = self.check("async def act(state):\n    return 'STAY'\n")
        self.assertFalse(ck["act"])
        self.assertEqual(ck["signature"], "async act(state)")
        self.assertFalse(self.check("S = '''\ndef act(state):\n    pass\n'''\n")["act"])
        self.assertTrue(self.check("def act(state):\n    return 1\ndef act(state):\n    return 'STAY'\n")["signature_ok"])
        self.assertIsNotNone(self.check("def act(state:\n")["parse_error"])

    def test_folder_contents(self):
        mods, data = simulate.folder_contents("bot.py", ["bot.py", "engine.py", "pkg/__init__.py", "p.json", "a/b/c.py"])
        self.assertEqual(mods, {"engine", "pkg", "a"})
        self.assertEqual(data, {"p.json"})
        mods, data = simulate.folder_contents("outputs/x.py", ["outputs/x.py", "outputs/y.py", "z.py"])
        self.assertEqual(mods, {"y"})

    def test_codes_and_clip(self):
        self.assertEqual([simulate.code_for(i) for i in (0, 25, 26, 27, 701, 702)],
                         ["A", "Z", "AA", "AB", "ZZ", "AAA"])
        self.assertEqual(simulate.clip("short", 10), "short")
        c = simulate.clip("research/evolution:outputs/bot_transfer_candidate.py", 30)
        self.assertEqual(len(c), 30)
        self.assertTrue(c.endswith("candidate.py"))


class Discovery(unittest.TestCase):
    """A throwaway git repository with two branches."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        def git(*a):
            subprocess.run(("git",) + a, cwd=cls.dir, check=True, capture_output=True)
        def write(path, text):
            full = os.path.join(cls.dir, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(text)
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        write("bot.py", "import random\ndef act(state):\n    return 'STAY'\n")
        write("helper.py", "X = 1\n")
        write("uses_helper.py", "import helper\ndef act(state):\n    return 'STAY'\n")
        write("test_bots.py", "SRC = '''\ndef act(state):\n    return 1\n'''\n")
        write("harness/bots/own.py", "def act(state):\n    return 'STAY'\n")
        write("outputs/copy_of_bot.py", "import random\ndef act(state):\n    return 'STAY'\n")
        git("add", "-A")
        git("commit", "-q", "-m", "one")
        git("checkout", "-q", "-b", "feature")
        write("bot.py", "def act(state):\n    return 'NORTH' if 'NORTH' in state.legal_actions else 'STAY'\n")
        write("broken.py", "def act(state:\n")
        git("add", "-A")
        git("commit", "-q", "-m", "two")
        cls.repo = Repo(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_candidates_dedupe_and_explain_what_was_left_out(self):
        entrants, skipped = simulate.discover(self.repo, "candidates")
        names = sorted(e["name"] for e in entrants)
        self.assertEqual(names, ["feature:bot.py", "main:bot.py"])
        main = [e for e in entrants if e["name"] == "main:bot.py"][0]
        self.assertEqual(set(main["aliases"]), {"main:bot.py", "main:outputs/copy_of_bot.py",
                                                "feature:outputs/copy_of_bot.py"})
        self.assertTrue(main["submission"])
        self.assertEqual(main["spec"]["ref"], main["commit"])        # pinned to a commit, not a branch
        why = dict((s["alias"], s["reason"]) for s in skipped)
        self.assertIn("single-file", why["main:uses_helper.py"])
        self.assertIn("does not parse", why["feature:broken.py"])
        self.assertIn("no top-level", why["main:test_bots.py"])
        self.assertFalse(any("harness/" in a for a in why))
        self.assertEqual([e["code"] for e in entrants], ["A", "B"])

    def test_modes_and_filters(self):
        subs, _ = simulate.discover(self.repo, "submissions")
        self.assertEqual(sorted(e["path"] for e in subs), ["bot.py", "bot.py"])
        allb, _ = simulate.discover(self.repo, "all")
        self.assertIn("main:uses_helper.py", [a for e in allb for a in e["aliases"]])
        only, skipped = simulate.discover(self.repo, "candidates", refs=["feature"])
        self.assertEqual(sorted(e["name"] for e in only), ["feature:bot.py", "feature:outputs/copy_of_bot.py"])
        none, skipped = simulate.discover(self.repo, "candidates", exclude=["*bot.py"])
        self.assertEqual(none, [])
        self.assertTrue(any("--include/--exclude" in s["reason"] for s in skipped))
        withb, _ = simulate.discover(self.repo, "submissions", builtins=True)
        self.assertEqual([e["source"] for e in withb].count("builtin"), 2)

    def test_added_file_twin_and_snapshot(self):
        tmp = tempfile.mkdtemp()
        try:
            same = os.path.join(tmp, "same.py")
            with open(same, "w") as f:
                f.write("import random\ndef act(state):\n    return 'STAY'\n")
            new = os.path.join(tmp, "new.py")
            with open(new, "w") as f:
                f.write("def act(state):\n    return 'SHIELD' if 'SHIELD' in state.legal_actions else 'STAY'\n")
            entrants, _ = simulate.discover(self.repo, "submissions", add=[same, new])
            self.assertEqual(len(entrants), 3)
            main = [e for e in entrants if e["name"] == "main:bot.py"][0]
            self.assertIn("file:" + same, main["aliases"])
            up = [e for e in entrants if e["source"] == "upload"][0]
            self.assertEqual(up["name"], "file:new.py")
            with open(new, "w") as f:
                f.write("garbage")                                  # later edits must not leak in
            self.assertIn("SHIELD", read(self.repo.resolve(up["spec"])["file"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_preflight_finds_bots_that_cannot_run(self):
        entrants, _ = simulate.discover(self.repo, "all", refs=["feature"])
        simulate.preflight(self.repo, entrants, dict(simulate.DEFAULT_TIMING), 2)
        for e in entrants:
            self.assertTrue(e["preflight"]["load_ok"], e["preflight"])
            self.assertTrue(simulate.runs(e))
        broken = {"preflight": {"load_ok": True, "status": "crash"}}
        self.assertFalse(simulate.runs(broken))
        self.assertTrue(simulate.runs({"preflight": {"load_ok": True, "status": "late"}}))


class Report(unittest.TestCase):
    def test_strong_bot_ranks_first_and_ties_are_draws(self):
        codes = list("ABCDE")
        rnd = random.Random(4)
        games = []
        n = 1
        for block in range(60):
            lineup = rnd.sample(codes, 4)
            for r in range(4):
                seats = [lineup[(s + r) % 4] for s in range(4)]
                scores = [{"A": 3000, "B": 2000, "C": 2000, "D": 1000, "E": 500}[c] + rnd.randint(0, 50)
                          if c != "C" else 2000 for c in seats]
                games.append(row_for(n, block, seats, scores))
                n += 1
        an = simreport.analyze(session_for(codes), games, bootstrap=50)
        rows = an["rows"]
        order = [rows[i]["code"] for i in an["order"]]
        self.assertEqual(order[0], "A")
        self.assertEqual(order[-1], "E")
        a = rows[an["index"]["A"]]
        self.assertEqual(a["L"], 0)
        self.assertEqual(a["pairwise"], 1.0)
        self.assertGreater(a["p_next"], 0.95)
        self.assertLessEqual(a["rating_lo"], a["rating"])
        self.assertGreaterEqual(a["rating_hi"], a["rating"])
        text = simreport.render(an)
        for heading in ("## Verdict", "## 1. Round 1 leaderboard", "## 2. Head-to-head", "## 4. Round 2 view",
                        "## 7. Rule compliance", "## 10. How the games were run"):
            self.assertIn(heading, text)
        json.dumps(simreport.summary_json(an))

    def test_rating_tie_goes_to_head_to_head_then_first_places(self):
        rows = [{"code": "A", "rating": 1500.2, "firsts": 1}, {"code": "B", "rating": 1499.9, "firsts": 9},
                {"code": "C", "rating": 1600.0, "firsts": 0}]
        h2h = [[[0, 0, 0], [3, 0, 1], [0, 0, 0]], [[1, 0, 3], [0, 0, 0], [0, 0, 0]], [[0, 0, 0]] * 3]
        order = simreport.leaderboard_order(rows, h2h, {"A": 0, "B": 1, "C": 2})
        self.assertEqual([rows[i]["code"] for i in order], ["C", "A", "B"])
        self.assertIn("head-to-head", rows[0]["tiebreak"])
        h2h = [[[0, 0, 0], [2, 0, 2], [0, 0, 0]], [[2, 0, 2], [0, 0, 0], [0, 0, 0]], [[0, 0, 0]] * 3]
        order = simreport.leaderboard_order(rows, h2h, {"A": 0, "B": 1, "C": 2})
        self.assertEqual([rows[i]["code"] for i in order], ["C", "B", "A"])
        self.assertIn("1st places", rows[1]["tiebreak"])

    def test_edge_cases_render(self):
        simreport.render(simreport.analyze(session_for(list("AB")), [], bootstrap=10))
        games = [row_for(1, 0, list("AABB"), [10, 10, 5, 5]), row_for(2, 0, list("ABAB"), [1, 2, 3, 4], status="stopped")]
        an = simreport.analyze(session_for(list("AB")), games, bootstrap=10)
        self.assertEqual(len(an["counted"]), 1)
        self.assertEqual(len(an["excluded"]), 1)
        self.assertEqual(an["duplicates"], 1)
        a = an["rows"][0]
        self.assertEqual((a["W"], a["D"], a["L"]), (4, 0, 0))     # self-pairings ignored
        text = simreport.render(an)
        self.assertIn("seated the same bot twice", text)

    def test_round_trip_survives_a_truncated_last_line(self):
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "session.json"), "w") as f:
                json.dump(session_for(list("ABCD")), f)
            with open(os.path.join(tmp, "games.jsonl"), "w") as f:
                for n in range(1, 5):
                    f.write(json.dumps(row_for(n, 0, list("ABCD"), [4, 3, 2, 1])) + "\n")
                f.write('{"n": 5, "status": "do')
            session, games, bad = simreport.load_session(tmp)
            self.assertEqual((len(games), bad), (4, 1))
            path, an = simreport.write_report(tmp, bootstrap=20)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(json.loads(read(os.path.join(tmp, "summary.json")))["games"], 4)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Workers(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "process sessions are POSIX")
    def test_bot_workers_do_not_share_the_terminal_session(self):
        p = BotProcess(os.path.join(BUILTIN, "skeleton.py"))
        p.spawn()
        try:
            self.assertTrue(p.finish_load(30)["ok"])
            self.assertNotEqual(os.getsid(p.proc.pid), os.getsid(0))
        finally:
            p.close()


class EndToEnd(unittest.TestCase):
    """The real command line, with only the two built-in bots so it is quick."""

    def run_cli(self, extra, stdin=subprocess.DEVNULL):
        out = tempfile.mkdtemp()
        shutil.rmtree(out)
        cmd = [sys.executable, os.path.join(HERE, "simulate.py"), "--no-fetch", "--refs", "__no_such_branch__",
               "--builtins", "--jobs", "2", "--replays", "none", "--bootstrap", "20", "--out", out] + extra
        return out, cmd

    def tearDown(self):
        for d in getattr(self, "dirs", []):
            shutil.rmtree(d, ignore_errors=True)

    def test_bounded_run_writes_results_and_report(self):
        out, cmd = self.run_cli(["--max-games", "6", "--turns", "20"])
        self.dirs = [out]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        rows = read_rows(os.path.join(out, "games.jsonl"))
        self.assertEqual([r["n"] for r in sorted(rows, key=lambda r: r["n"])], list(range(1, 7)))
        self.assertTrue(all(r["status"] == "done" and r["turns"] == 20 for r in rows))
        session = json.loads(read(os.path.join(out, "session.json")))
        self.assertEqual(session["stop_reason"], "reached --max-games 6")
        self.assertEqual(session["counts"]["done"], 6)
        report = read(os.path.join(out, "report.md"))
        self.assertIn("Games were 20 turns, not the rulebook's 80", report)
        self.assertIn("seated the same bot twice", report)

    def test_enter_stops_and_finishes_games_in_progress(self):
        out, cmd = self.run_cli([])
        self.dirs = [out]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        seen = []
        try:
            for line in p.stdout:
                seen.append(line)
                if line.lstrip().startswith("#"):          # the first finished game
                    p.stdin.write("\n")
                    p.stdin.flush()
                    break
            rest, _ = p.communicate(timeout=120)
        finally:
            if p.poll() is None:
                p.kill()
        self.assertEqual(p.returncode, 0, "".join(seen))
        self.assertIn("Stopping (Enter was pressed)", rest)
        rows = read_rows(os.path.join(out, "games.jsonl"))
        self.assertTrue(rows and all(r["status"] == "done" for r in rows))
        self.assertTrue(os.path.exists(os.path.join(out, "report.md")))
        self.assertIn("Enter was pressed", read(os.path.join(out, "report.md")))


if __name__ == "__main__":
    unittest.main()
