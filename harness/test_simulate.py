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

    def focus_tally(self, sch, blocks, check_each=True):
        n, f = sch.n, sch.focus
        meet = [0] * n
        seat_token = {}
        rel = [[0] * 4 for _ in range(n)]
        for _ in range(blocks):
            for g in sch.next_block():
                seats = g["seats"]
                self.assertEqual(seats.count(f), 1, "the focus bot is in every game, once")
                s = seats.index(f)
                seat_token[(s + 1, g["token"])] = seat_token.get((s + 1, g["token"]), 0) + 1
                for k in (1, 2, 3):
                    rel[seats[(s + k) % 4]][k] += 1
                for e in seats:
                    if e != f:
                        meet[e] += 1
            if check_each:
                others = [meet[i] for i in range(n) if i != f]
                self.assertLessEqual(max(others) - min(others), 4, "never more than one block apart")
        return meet, seat_token, rel

    def test_focus_bot_meets_every_opponent_equally_in_every_seat_and_token_position(self):
        sch = simulate.Scheduler(7, ["example", "random"], random.Random(8), focus=2)
        meet, seat_token, rel = self.focus_tally(sch, 24)
        # 24 blocks x 3 opponent seats over 6 opponents = 12 blocks = 48 games each
        self.assertEqual([meet[i] for i in range(7) if i != 2], [48] * 6)
        self.assertEqual(meet[2], 0)
        # every seat with every starting token, equally: 24 blocks / 4 tokens, once per seat each
        self.assertEqual(seat_token, dict(((s, t), 6) for s in (1, 2, 3, 4) for t in (1, 2, 3, 4)))
        for i in range(7):
            if i != 2:      # each opponent sits 1, 2 and 3 seats after the focus bot about equally
                self.assertLessEqual(max(rel[i][1:]) - min(rel[i][1:]), 8, rel[i])     # two blocks
                self.assertEqual(sum(rel[i]), 48)
        for block in [sch.next_block() for _ in range(5)]:
            self.assertEqual(len(set(block[0]["seats"])), 4, "four different bots when there are enough")

    def test_focus_with_a_large_field_stays_balanced(self):
        sch = simulate.Scheduler(40, ["random"], random.Random(3), focus=0)    # C(39, 3) > 3000 line-ups
        meet, _, _ = self.focus_tally(sch, 130)
        self.assertEqual(set(meet[1:]), {40})                                    # 130 x 3 / 39 = 10 blocks

    def test_focus_with_fewer_than_three_opponents_repeats_them_evenly(self):
        sch = simulate.Scheduler(3, ["example"], random.Random(1), focus=1)
        meet, _, _ = self.focus_tally(sch, 20)
        self.assertEqual(meet, [120, 0, 120])
        one = simulate.Scheduler(2, ["example"], random.Random(1), focus=0)
        self.assertEqual(sorted(one.next_block()[0]["seats"]), [0, 1, 1, 1])
        with self.assertRaises(ValueError):
            simulate.Scheduler(1, ["example"], random.Random(1), focus=0)

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


def entrant(code, name, aliases, source="upload"):
    return {"code": code, "name": name, "primary": aliases[0], "aliases": list(aliases), "source": source}


class FocusAndStyles(unittest.TestCase):
    def manifest(self, text):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "MANIFEST.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_manifest_as_a_table(self):
        styles = simulate.read_manifest(self.manifest(
            "# Opponents\n\nIntro mentioning bot.py.\n\n"
            "| Name | File | Play style | Notes |\n|:--|---|--:|---|\n"
            "| Raider | `opponents/raider.py` | Aggressive | hits level 2, unlike turtle.py |\n"
            "| Turtle | [turtle.py](turtle.py) | **Defensive** | shields |\n"
            "| Greedy | greedy | Greedy | |\n"))
        self.assertEqual(styles, {"raider": "Aggressive", "turtle": "Defensive", "greedy": "Greedy"})

    def test_manifest_as_headings_lists_and_style_lines(self):
        styles = simulate.read_manifest(self.manifest(
            "# Opponents\n\nSee also bot.py.\n\n## Raiders\n\n- raider_a.py - hunts level 2; beats greedy.py\n"
            "- `raider_b.py`\n\n## Turtles\n\n1. turtle.py\n\n### shield_bot.py\n\nStyle: Shield spam\n"
            "It copies other.py.\n\n## Misc\n\n- `mixed.py` (style: Mixed, a bit of everything)\n"
            "**Style:** ignored with no file\n\n```text\n- fenced.py (style: Nope)\n```\n\n"
            "| file | notes |\n|---|---|\n| tabled.py | no style column: takes the heading |\n"))
        self.assertEqual(styles, {"raider_a": "Raiders", "raider_b": "Raiders", "turtle": "Turtles",
                                  "shield_bot": "Shield spam", "mixed": "Mixed", "tabled": "Misc"})

    def test_styles_match_bots_by_file_name(self):
        es = [entrant("A", "main:bot.py", ["origin/main:bot.py"], "git"),
              entrant("B", "file:raider.py", ["file:/tmp/opp/Raider.py"]),
              entrant("C", "main:opponents/turtle.py", ["origin/main:opponents/turtle.py", "file:x/turtle.py"], "git"),
              entrant("D", "builtin:raider.py", ["builtin:raider.py"], "builtin")]
        unmatched = simulate.assign_styles(es, {"raider": "Aggressive", "turtle": "Defensive", "ghost": "?"})
        self.assertEqual([e["style"] for e in es], [None, "Aggressive", "Defensive", None])
        self.assertEqual(unmatched, ["ghost"])

    def test_manifests_are_found_in_added_folders_and_opponents(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        os.makedirs(os.path.join(root, "opponents"))
        os.makedirs(os.path.join(root, "more"))
        for d in ("opponents", "more"):
            with open(os.path.join(root, d, "MANIFEST.md"), "w") as f:
                f.write("x")
        self.assertEqual(simulate.find_manifests(root), [os.path.join(root, "opponents", "MANIFEST.md")])
        found = simulate.find_manifests(root, [os.path.join(root, "more"), os.path.join(root, "opponents")])
        self.assertEqual(found, [os.path.join(root, "more", "MANIFEST.md"),
                                 os.path.join(root, "opponents", "MANIFEST.md")])
        self.assertEqual(simulate.find_manifests(os.path.join(root, "more")), [])

    def test_resolve_focus(self):
        here = os.path.join(tempfile.gettempdir(), "opp", "raider.py")
        es = [entrant("A", "main:bot.py", ["origin/main:bot.py", "origin/dev:bot.py"], "git"),
              entrant("B", "file:raider.py", ["file:" + here]),
              entrant("C", "builtin:skeleton.py (always STAY)", ["builtin:skeleton.py"], "builtin"),
              entrant("D", "dev:mybot.py", ["origin/dev:mybot.py"], "git")]
        pick = lambda text: simulate.resolve_focus(es, text)["code"]
        self.assertEqual(pick("b"), "B")
        self.assertEqual(pick("main:bot.py"), "A")
        self.assertEqual(pick("dev:bot.py"), "A")                   # any branch that has the same file
        self.assertEqual(pick("origin/dev:mybot.py"), "D")
        self.assertEqual(pick(here), "B")
        self.assertEqual(pick("raider"), "B")
        self.assertEqual(pick("skeleton.py"), "C")
        self.assertEqual(pick("*mybot*"), "D")
        with self.assertRaisesRegex(simulate.SourceError, "matches 2 bots"):
            pick("*bot.py")
        with self.assertRaisesRegex(simulate.SourceError, "matches no bot"):
            pick("nobody.py")
        with self.assertRaisesRegex(simulate.SourceError, "was not entered: crashes"):
            simulate.resolve_focus(es, "broken.py", [{"alias": "main:broken.py", "reason": "crashes"}])


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
            # Discovery deduplicates exact bytes, so keep fixture sources LF
            # even when Windows text I/O or Git checkout settings prefer CRLF.
            with open(full, "wb") as f:
                f.write(text.encode("utf-8"))
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
            with open(same, "wb") as f:
                f.write(b"import random\ndef act(state):\n    return 'STAY'\n")
            new = os.path.join(tmp, "new.py")
            with open(new, "wb") as f:
                f.write(b"def act(state):\n    return 'SHIELD' if 'SHIELD' in state.legal_actions else 'STAY'\n")
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

    def test_added_folder_enters_every_bot_file(self):
        tmp = tempfile.mkdtemp()
        try:
            def write(name, text):
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(text.encode("utf-8"))
            write("same.py", "import random\ndef act(state):\n    return 'STAY'\n")      # = main:bot.py
            write("east.py", "def act(state):\n    return 'EAST' if 'EAST' in state.legal_actions else 'STAY'\n")
            write("west.py", "def act(state):\n    return 'WEST' if 'WEST' in state.legal_actions else 'STAY'\n")
            write("west_copy.py", "def act(state):\n    return 'WEST' if 'WEST' in state.legal_actions else 'STAY'\n")
            write("helpers.py", "X = 1\n")
            write("__init__.py", "")
            write("notes.txt", "def act(state):\n")
            entrants, skipped = simulate.discover(self.repo, "submissions", add_dirs=[tmp])
            self.assertEqual(sorted(e["name"] for e in entrants), ["feature:bot.py", "file:east.py", "file:west.py",
                                                                   "main:bot.py"])
            main = [e for e in entrants if e["name"] == "main:bot.py"][0]
            self.assertIn("file:" + os.path.join(tmp, "same.py"), main["aliases"])
            west = [e for e in entrants if e["name"] == "file:west.py"][0]
            self.assertIn("file:" + os.path.join(tmp, "west_copy.py"), west["aliases"])
            self.assertEqual(west["source"], "upload")              # snapshotted like --add
            why = dict((s["alias"], s["reason"]) for s in skipped)
            self.assertIn("not a bot", why["file:" + os.path.join(tmp, "helpers.py")])
            self.assertIn("file:" + os.path.join(tmp, "__init__.py"), why)
            self.assertEqual([e["code"] for e in entrants], ["A", "B", "C", "D"])
            write("needs_helper.py", "import helpers\ndef act(state):\n    return 'STAY'\n")
            with self.assertRaisesRegex(simulate.SourceError, "self-contained"):
                simulate.discover(self.repo, "submissions", add_dirs=[tmp])
            with self.assertRaisesRegex(simulate.SourceError, "not a folder"):
                simulate.discover(self.repo, "submissions", add_dirs=[os.path.join(tmp, "missing")])
            os.makedirs(os.path.join(tmp, "empty"))
            with self.assertRaisesRegex(simulate.SourceError, "no .py files"):
                simulate.discover(self.repo, "submissions", add_dirs=[os.path.join(tmp, "empty")])
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

    def focus_games(self, styles=None):
        """A plays every game; B beats it, G loses to it, the rest are level with it."""
        codes = list("ABCDEFG")
        strength = {"A": 1000, "B": 1500, "C": 1000, "D": 1000, "E": 1000, "F": 1000, "G": 500}
        sch = simulate.Scheduler(7, ["example"], random.Random(2), focus=0)
        rnd = random.Random(6)
        games = []
        for _ in range(30):
            for g in sch.next_block():
                seats = [codes[i] for i in g["seats"]]
                games.append(row_for(g["n"], g["block"], seats, [strength[c] + rnd.randint(-300, 300) for c in seats]))
        session = session_for(codes, focus="A")
        for e in session["entrants"]:
            e["style"] = (styles or {}).get(e["code"])
        if styles:
            session["manifest"] = {"paths": ["opponents/MANIFEST.md"], "styles": {}, "unmatched": []}
        return session, games

    def test_focus_section_lists_opponents_worst_first(self):
        session, games = self.focus_games()
        an = simreport.analyze(session, games, bootstrap=20)
        fv = an["focus"]
        self.assertEqual(fv["code"], "A")
        self.assertEqual(fv["games"], len(games))
        self.assertEqual(fv["without"], 0)
        self.assertEqual(fv["seat_games"], {1: 30, 2: 30, 3: 30, 4: 30})
        opp = fv["opponents"]
        self.assertEqual(opp[0]["code"], "B")
        self.assertEqual(opp[-1]["code"], "G")
        self.assertEqual((opp[0]["clear"], opp[-1]["clear"]), ("loses", "wins"))
        self.assertEqual(sorted(p["code"] for p in opp), list("BCDEFG"))
        self.assertEqual(len(set(p["games"] for p in opp)), 1, "each opponent met A equally often")
        scores = [p["score"] for p in opp]
        self.assertEqual(scores, sorted(scores))
        a = an["rows"][an["index"]["A"]]
        self.assertEqual(sum(p["W"] for p in opp), a["W"])
        self.assertEqual(fv["styles"], [])
        text = simreport.render(an)
        self.assertIn("## Focus bot: A bot A", text)
        self.assertLess(text.index("## Focus bot"), text.index("## 1. Round 1 leaderboard"))
        section = text[text.index("## Focus bot"):text.index("## 1. Round 1")]
        self.assertLess(section.index("| B bot B |"), section.index("| G bot G |"))
        self.assertNotIn("### ", section)
        self.assertIn("Schedule (focus mode)", text)
        summary = simreport.summary_json(an)
        self.assertEqual(summary["focus"]["opponents"][0]["code"], "B")
        json.dumps(summary)
        self.assertIn("Worst match-ups first", simulate.final_summary(an))

    def test_focus_section_groups_by_style(self):
        session, games = self.focus_games({"B": "Raider", "C": "Raider", "D": "Turtle", "E": "Turtle", "G": "Turtle"})
        an = simreport.analyze(session, games, bootstrap=20)
        styles = an["focus"]["styles"]
        self.assertEqual(styles[0]["style"], "Raider")                   # holds B, the worst match-up
        self.assertEqual([s["style"] for s in styles][-1], "Turtle")     # holds G, which A beats
        self.assertEqual(set(s["style"] for s in styles), {"Raider", "Turtle", simreport.UNSTYLED})
        self.assertEqual(sorted(c for s in styles for c in s["codes"]), list("BCDEFG"))
        raider = styles[0]
        self.assertEqual(raider["W"] + raider["D"] + raider["L"], raider["pairings"])
        text = simreport.render(an)
        section = text[text.index("## Focus bot"):text.index("## 1. Round 1")]
        self.assertIn("`opponents/MANIFEST.md`", section)
        self.assertLess(section.index("### Raider"), section.index("### Turtle"))
        self.assertIn("### %s" % simreport.UNSTYLED, section)
        turtle = section[section.index("### Turtle"):]                    # the last group
        self.assertLess(max(turtle.index("| D bot D |"), turtle.index("| E bot E |")), turtle.index("| G bot G |"))
        self.assertNotIn("| B bot B |", turtle)

    def test_no_focus_section_without_a_focus_bot(self):
        an = simreport.analyze(session_for(list("ABCD")), [row_for(1, 0, list("ABCD"), [4, 3, 2, 1])], bootstrap=10)
        self.assertIsNone(an["focus"])
        self.assertNotIn("Focus bot", simreport.render(an))
        self.assertIsNone(simreport.summary_json(an)["focus"])

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

    def opponents_dir(self):
        tmp = tempfile.mkdtemp()
        self.dirs = getattr(self, "dirs", []) + [tmp]
        for name, move in (("east.py", "EAST"), ("south.py", "SOUTH")):
            with open(os.path.join(tmp, name), "w") as f:
                f.write("def act(state):\n    return %r if %r in state.legal_actions else 'STAY'\n" % (move, move))
        with open(os.path.join(tmp, "MANIFEST.md"), "w") as f:
            f.write("| File | Style |\n|---|---|\n| east.py | Walker |\n| south.py | Walker |\n"
                    "| random_bot.py | Chaos |\n")
        return tmp

    def test_focus_run_seats_the_focus_bot_in_every_game(self):
        opp = self.opponents_dir()
        out, cmd = self.run_cli(["--add-dir", opp, "--focus", "skeleton.py", "--max-games", "8", "--turns", "8"])
        self.dirs.append(out)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        session = json.loads(read(os.path.join(out, "session.json")))
        focus = session["settings"]["focus"]
        names = dict((e["code"], e["name"]) for e in session["entrants"])
        self.assertTrue(names[focus].startswith("builtin:skeleton.py"))
        self.assertEqual(sorted(names.values())[2:], ["file:east.py", "file:south.py"])
        self.assertEqual(dict((e["name"], e["style"]) for e in session["entrants"] if e["style"]),
                         {"file:east.py": "Walker", "file:south.py": "Walker"})
        rows = read_rows(os.path.join(out, "games.jsonl"))
        self.assertEqual(len(rows), 8)
        for r in rows:
            codes = [s["entrant"] for s in r["seats"]]
            self.assertEqual(codes.count(focus), 1)
            self.assertEqual(len(set(codes)), 4)
        seats = sorted(s["seat"] for r in rows for s in r["seats"] if s["entrant"] == focus)
        self.assertEqual(seats, [1, 1, 2, 2, 3, 3, 4, 4])                 # two blocks: every seat twice
        report = read(os.path.join(out, "report.md"))
        self.assertIn("## Focus bot: %s builtin:skeleton.py" % focus, report)
        self.assertIn("### Walker", report)
        self.assertIn("### " + simreport.UNSTYLED, report)        # random_bot.py is a built-in, not an opponent file
        self.assertIn("[FOCUS]", res.stdout)
        self.assertIn("Worst match-ups first", res.stdout)

    def test_minutes_stops_by_itself_and_prints_the_session_folder(self):
        out, cmd = self.run_cli(["--minutes", "0.04", "--turns", "5"])
        self.dirs = [out]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        session = json.loads(read(os.path.join(out, "session.json")))
        self.assertEqual(session["stop_reason"], "reached --minutes 0.04")
        self.assertGreater(session["counts"]["done"], 0)
        self.assertIn("reached --minutes 0.04", read(os.path.join(out, "report.md")))
        self.assertIn("Session folder: %s" % os.path.abspath(out), res.stdout)
        self.assertIn("Stops by itself after 0.04 minute(s)", res.stdout)

    def test_bad_new_options_are_refused_before_any_game(self):
        for extra, message in ((["--minutes", "0"], "--minutes must be more than 0"),
                               (["--focus", "nobody.py"], "matches no bot"),
                               (["--add-dir", os.path.join(HERE, "no_such_folder")], "not a folder")):
            out, cmd = self.run_cli(extra + ["--max-games", "1"])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
            self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
            self.assertIn(message, res.stdout)
            self.assertFalse(os.path.exists(os.path.join(out, "games.jsonl")))
            shutil.rmtree(out, ignore_errors=True)

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
