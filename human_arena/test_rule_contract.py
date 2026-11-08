"""Independent rule/public-input regressions for the human referee and v9 fix.

Uses no live app. Referee-only tests use hidden counters as test oracles;
policies and Trackers receive only official public fields and own requests.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


referee = load("contract_referee", ROOT / "human_arena/vendor_harness/referee.py")
fixed = load("contract_fixed_v9", ROOT / "human_arena/candidates/forward_fixed.py")
original = load("contract_original_v9", ROOT / "human_arena/candidates/forward_original.py")


def observe(tracker, game, seat, requested=None, permissive=False):
    view = game.views()[seat - 1]
    cells = [c for row in view.board for c in row]
    legal = list(view.legal_actions)
    if permissive and "SHIELD" not in legal:
        legal.append("SHIELD")
    args = ([c.owner for c in cells], [c.is_upgraded for c in cells],
            [c.occupant for c in cells], [c.is_frozen for c in cells], seat,
            view.is_priority_token, [c.base_points for c in cells],
            [c.owner if c.is_home else 0 for c in cells], requested)
    if isinstance(tracker, fixed._base_Tracker):
        tracker.observe(*args, legal_actions=legal)
    else:
        tracker.observe(*args)


def shared_state(game):
    income = game.income() if callable(game.income) else game.income
    return (game.turn, game.token, tuple(game.pos), tuple(game.owner), tuple(game.upg),
            tuple(game.frozen), tuple(game.cd), tuple(game.prog), tuple(game.score), tuple(income))


def public_snapshot(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


class PhysicsTests(unittest.TestCase):
    def test_repeated_upgraded_raid_shields_are_new_freezes_not_extended_one(self):
        g = referee.Referee(referee.example_map())
        g.turn, g.pos[:2], g.owner[33], g.upg[33], g.prog[0] = 67, [33, 35], 2, True, 2
        g.step(["STAY", "SHIELD", "STAY", "STAY"])
        for expected in (2, 1):
            self.assertEqual(g.frozen[0], expected)
            self.assertEqual(g.legal(0), ["STAY"])
            g.step(["STAY"] * 4)
        self.assertEqual(g.turn, 70)
        self.assertEqual(g.frozen[0], 0)
        self.assertIn("SOUTH", g.legal(0))
        # Leaving after thaw is available; it avoids a fresh catch at T72.
        g.step(["SOUTH", "STAY", "STAY", "STAY"])
        g.step(["STAY"] * 4)
        g.step(["STAY", "SHIELD", "STAY", "STAY"])
        self.assertEqual(g.frozen[0], 0)
        self.assertEqual(g.frozen[1], 2, "shielding after the raider exits backfires")

    def test_uploaded_freeze_report_exact_replay_and_durations(self):
        path = Path(r"C:\Users\LEGION\Downloads\zone-rush-a48976861ec94db586fabe314f58fc4a.json")
        if not path.exists():
            self.skipTest("uploaded freeze regression fixture not present")
        data = json.loads(path.read_text(encoding="utf8"))
        self.assertEqual(data["game_id"], "a48976861ec94db586fabe314f58fc4a")
        metadata, records = data["metadata"], data["turns"]
        self.assertEqual(len(records), 80)
        self.assertEqual(hashlib.sha256((ROOT / "human_arena/vendor_harness/referee.py").read_bytes()).hexdigest(), metadata["referee_sha256"])
        g = referee.Referee(metadata["base"], rules=metadata["rules"],
                            start_token=metadata["start_token"], max_turns=metadata["max_turns"])
        freezes = []
        for record in records:
            self.assertEqual(g.snapshot(), record["before"])
            for seat in range(1, 5):
                self.assertEqual(g.observation(seat), record["observations"][str(seat)])
            self.assertEqual(g.step(record["used"]), record["resolved"])
            self.assertEqual(g.snapshot(), record["after"])
            for event in record["resolved"]["events"]:
                if event["type"] == "freeze":
                    freezes.append((record["turn"], event["seat"], event["why"]))
                    j, t = event["seat"] - 1, record["turn"]
                    self.assertEqual(record["after"]["frozen"][j], 2)
                    for offset, expected in ((1, 2), (2, 1)):
                        if t + offset > 80:
                            continue
                        forced = records[t + offset - 1]
                        self.assertEqual(forced["before"]["frozen"][j], expected)
                        self.assertEqual(forced["observations"][str(j + 1)]["legal_actions"], ["STAY"])
                        self.assertEqual(forced["resolved"]["eff"][j], "STAY")
                        self.assertEqual(forced["before"]["pos"][j], forced["after"]["pos"][j])
                        self.assertEqual(forced["after"]["prog"][j], 0)
                        self.assertFalse(any(e["type"] in ("claim", "raid", "upgrade") and e["seat"] == j + 1
                                             for e in forced["resolved"]["events"]))
                    if t + 3 <= 80:
                        self.assertEqual(records[t + 2]["before"]["frozen"][j], 0)
                elif event["type"] == "shield":
                    j, t = event["seat"] - 1, record["turn"]
                    for offset, expected in ((1, 4), (2, 3), (3, 2), (4, 1)):
                        if t + offset <= 80:
                            cooldown_turn = records[t + offset - 1]
                            self.assertEqual(cooldown_turn["before"]["cd"][j], expected)
                            self.assertNotIn("SHIELD", cooldown_turn["observations"][str(j + 1)]["legal_actions"])
        self.assertEqual(g.snapshot(), data["ending"]["final"])
        self.assertEqual([t for t, seat, _ in freezes if seat == 1], [61, 67, 72, 77])

    def test_occupied_at_start_blocks_following_and_counts_as_work(self):
        g = referee.Referee(referee.example_map())
        g.pos[:2], g.owner[26], g.prog[0] = [26, 27], 1, 2
        out = g.step(["EAST", "EAST", "STAY", "STAY"])
        self.assertEqual(g.pos[:2], [26, 28])
        self.assertEqual(out["eff"][0], "STAY")
        self.assertTrue(g.upg[26], "the blocked action must finish the upgrade")

    def test_owner_wins_contest_even_against_token(self):
        g = referee.Referee(referee.example_map(), start_token=2)
        g.pos[:2], g.owner[27] = [26, 28], 1
        g.step(["EAST", "WEST", "STAY", "STAY"])
        self.assertEqual(g.pos[:2], [27, 28])

    def test_token_and_lost_contest_work(self):
        g = referee.Referee(referee.example_map(), start_token=2)
        g.pos[:2], g.owner[26], g.prog[0] = [26, 28], 1, 2
        g.step(["EAST", "WEST", "STAY", "STAY"])
        self.assertEqual(g.pos[:2], [26, 27])
        self.assertTrue(g.upg[26])

    def test_blocked_stay_is_caught_before_capture(self):
        g = referee.Referee(referee.example_map())
        g.pos[:2], g.owner[26] = [26, 27], 2
        g.step(["EAST", "SHIELD", "STAY", "STAY"])
        self.assertEqual(g.frozen[0], 2)
        self.assertEqual(g.owner[26], 2)
        for _ in range(2):
            self.assertEqual(g.legal(0), ["STAY"])
            g.step(["STAY"] * 4)
            self.assertEqual(g.prog[0], 0)
            self.assertEqual(g.owner[26], 2)
        self.assertEqual(g.frozen[0], 0)
        self.assertNotEqual(g.legal(0), ["STAY"])

    def test_global_shield_and_exact_cooldown(self):
        g = referee.Referee(referee.example_map())
        g.pos[0], g.pos[2] = 10, 20
        g.owner[10] = g.owner[20] = 2
        out = g.step(["STAY", "SHIELD", "STAY", "STAY"])
        event = next(e for e in out["events"] if e["type"] == "shield")
        self.assertEqual(event["caught"], [1, 3])
        for _ in range(4):
            self.assertNotIn("SHIELD", g.legal(1))
            g.step(["STAY"] * 4)
        self.assertIn("SHIELD", g.legal(1))

    def test_shield_is_not_a_stay_and_rival_can_self_backfire(self):
        g = referee.Referee(referee.example_map())
        g.pos[0], g.owner[8] = 8, 2
        out = g.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        self.assertTrue(all(e["backfire"] for e in out["events"] if e["type"] == "shield"))
        self.assertEqual(g.frozen[:2], [2, 2])
        self.assertEqual(g.owner[8], 2)

    def test_raid_bonus_uses_previous_level_and_scores_new_land_now(self):
        base = referee.example_map()
        base[27] = 3
        g = referee.Referee(base)
        g.pos[0], g.owner[27], g.upg[27], g.prog[0] = 27, 2, True, 2
        out = g.step(["STAY"] * 4)
        self.assertEqual(out["bonus"][0], 48)
        self.assertEqual(g.score[0], 52)
        self.assertEqual(g.owner[27], 1)
        self.assertFalse(g.upg[27])
        self.assertEqual(g.prog[0], 0)

    def test_home_upgrade_and_immunity(self):
        g = referee.Referee(referee.example_map())
        for _ in range(3):
            g.step(["STAY"] * 4)
        self.assertTrue(all(g.upg[p] for p in referee.HOMES.values()))
        g.pos[0], g.pos[1] = 7, 8
        for _ in range(5):
            g.step(["STAY"] * 4)
        self.assertEqual(g.owner[7], 2)
        self.assertEqual(g.prog[0], 0)

    def test_round_one_ties_are_draws_despite_cell_counts(self):
        g = referee.Referee(referee.example_map())
        g.score, g.owner[1] = [100, 100, 10, 0], 1
        self.assertEqual(referee.places(g.score), [1, 1, 3, 4])
        self.assertEqual(referee.pairwise(g.score)[:2], [2.5 / 3, 2.5 / 3])

    def test_public_serializer_contains_only_official_fields(self):
        g = referee.Referee(referee.example_map())
        public = g.observation(1)
        self.assertEqual(set(public), {"board", "bot_id", "is_priority_token", "legal_actions"})
        self.assertTrue(all(len(c) == 6 for row in public["board"] for c in row))
        public["board"][0][0][1] = 4
        self.assertEqual(g.owner[0], 1)

    def test_three_physics_engines_match_random_sequences(self):
        rng = random.Random(863111)
        for trial in range(16):
            base, token = engine.make_map(seed=23011 + trial), trial % 4 + 1
            games = [referee.Referee(base, start_token=token), engine.Game(base, start_token=token),
                     fixed._world_Game(base, start_token=token)]
            for _ in range(80):
                self.assertEqual(shared_state(games[0]), shared_state(games[1]))
                self.assertEqual(shared_state(games[0]), shared_state(games[2]))
                actions = [rng.choice(games[0].legal(i)) if rng.random() > .04 else "INVALID" for i in range(4)]
                for game in games:
                    game.step(actions)
            self.assertEqual(shared_state(games[0]), shared_state(games[2]))


class TrackerTests(unittest.TestCase):
    def test_pristine_home_stays_do_not_restart_the_clock(self):
        g, tracker = engine.Game(), fixed._base_Tracker()
        for _ in range(7):
            observe(tracker, g, 1, "STAY")
            self.assertEqual(tracker.turn, g.turn)
            self.assertEqual(tracker.score, g.score)
            self.assertEqual(tracker.income, g.income)
            self.assertEqual(tracker.prog[0], g.prog[0])
            g.step(["STAY"] * 4)

    def test_original_control_reproduces_pristine_reset_defect(self):
        g, tracker = engine.Game(), original._base_Tracker()
        observe(tracker, g, 1)
        g.step(["STAY"] * 4)
        observe(tracker, g, 1, "STAY")
        self.assertEqual(tracker.turn, 1)
        self.assertEqual(g.turn, 2)

    def test_new_pristine_game_after_upgrade_resets_history(self):
        g, tracker = engine.Game(), fixed._base_Tracker()
        for _ in range(5):
            observe(tracker, g, 1, "STAY")
            g.step(["STAY"] * 4)
        restarted = engine.Game(base=engine.make_map(seed=893))
        observe(tracker, restarted, 1)
        self.assertTrue(tracker.new_game)
        self.assertEqual((tracker.turn, tracker.score), (1, [0] * 4))
        self.assertEqual(tracker.income, restarted.income)

    def test_late_shield_request_does_not_erase_visible_upgrade(self):
        g, tracker = engine.Game(), fixed._base_Tracker()
        for _ in range(3):
            observe(tracker, g, 1, "STAY")
            g.step(["STAY"] * 4)
        # A chosen SHIELD was late; the referee actually applied STAY.
        observe(tracker, g, 1, "SHIELD")
        self.assertTrue(g.upg[0])
        self.assertEqual(tracker.cd[0], 0)
        self.assertEqual(tracker.prog[0], 0)
        self.assertEqual(tracker.score, g.score)

    def test_ambiguous_freeze_retains_both_cooldown_histories(self):
        for accepted in (True, False):
            g, tracker = engine.Game(), fixed._base_Tracker()
            g.pos[0], g.owner[8] = 8, 2
            g.income[1] += g.base[8]
            observe(tracker, g, 1)
            actions = ["SHIELD", "STAY", "STAY", "STAY"] if accepted else ["STAY", "SHIELD", "STAY", "STAY"]
            g.step(actions)
            observe(tracker, g, 1, "SHIELD")
            self.assertEqual(tracker.cd_possible[0], {0, 4})
            self.assertEqual(tracker.cd_possible[1], {0, 4})
            self.assertEqual(tracker.cd[1], 0, "ambiguity must not invent a safe enemy cooldown")
            self.assertIn(g.cd[0], tracker.cd_possible[0])

    def test_known_backfire_survives_permissive_legal_list(self):
        g, tracker = engine.Game(), fixed._base_Tracker()
        observe(tracker, g, 1)
        g.step(["SHIELD", "STAY", "STAY", "STAY"])
        observe(tracker, g, 1, "SHIELD", permissive=True)
        self.assertEqual(tracker.cd[0], 4)
        for _ in range(2):
            g.step(["STAY"] * 4)
            observe(tracker, g, 1, "STAY", permissive=True)
        self.assertEqual(tracker.cd[0], 2)

    def test_recorded_game_visible_work_rules_out_false_human_shield(self):
        path = ROOT / "human_arena/history/d3846d56f462413789041954bdc8bc38.jsonl"
        if path.exists():
            lines = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]
            records = [line for line in lines if line.get("type") == "turn"]
        else:
            downloaded = Path(r"C:\Users\LEGION\Downloads\zone-rush-d3846d56f462413789041954bdc8bc38.json")
            if not downloaded.exists():
                self.skipTest("recorded regression fixture not present")
            records = json.loads(downloaded.read_text(encoding="utf8"))["turns"]
        trackers = [fixed._base_Tracker() for _ in range(4)]
        for record in records:
            for j, tracker in enumerate(trackers):
                public = record["observations"][str(j + 1)]
                cells = [c for row in public["board"] for c in row]
                previous = records[record["turn"] - 2]["used"][j] if record["turn"] > 1 else None
                tracker.observe([c[1] for c in cells], [c[2] for c in cells], [c[0] for c in cells],
                    [c[4] for c in cells], j + 1, public["is_priority_token"], [c[5] for c in cells],
                    [c[1] if c[3] else 0 for c in cells], previous, public["legal_actions"])
                before = record["before"]
                self.assertEqual(tracker.turn, record["turn"])
                self.assertEqual(tracker.score, before["score"])
                self.assertEqual(tracker.prog[j], before["prog"][j])
                for rival in range(4):
                    self.assertIn(before["cd"][rival], tracker.cd_possible[rival])
                if record["turn"] == 55:
                    self.assertEqual(tracker.cd[0], 0)
                    self.assertEqual(tracker.cd[1], 4)

    def test_random_sequences_keep_true_cooldown_possible_and_own_progress_correct(self):
        rng = random.Random(625719)
        for trial in range(16):
            g = engine.Game(base=engine.make_map(seed=trial + 82117), start_token=trial % 4 + 1)
            trackers, previous = [fixed._base_Tracker() for _ in range(4)], [None] * 4
            for _ in range(80):
                for j, tracker in enumerate(trackers):
                    observe(tracker, g, j + 1, previous[j])
                    self.assertEqual(tracker.turn, g.turn)
                    self.assertEqual(tracker.score, g.score)
                    self.assertEqual(tracker.prog[j], g.prog[j])
                    for rival in range(4):
                        self.assertIn(g.cd[rival], tracker.cd_possible[rival], (trial, g.turn, j, rival))
                previous = [rng.choice(g.legal(j)) for j in range(4)]
                g.step(previous)


class SubmissionTests(unittest.TestCase):
    def test_frozen_original_and_fixed_manifest_match_bytes(self):
        folder = ROOT / "human_arena/candidates"
        manifest = json.loads((folder / "forward_fixed.manifest.json").read_text(encoding="utf8"))
        self.assertEqual(hashlib.sha256((folder / "forward_original.py").read_bytes()).hexdigest(), manifest["original_sha256"])
        self.assertEqual(hashlib.sha256((folder / "forward_fixed.py").read_bytes()).hexdigest(), manifest["sha256"])

    def test_actual_entry_point_full_game_legal_immutable_no_swallowed_exception(self):
        policy = load("contract_entrypoint_v9", ROOT / "human_arena/candidates/forward_fixed.py")
        internal_errors = []
        original_decide = policy.Agent.decide

        def checked(player, state):
            try:
                return original_decide(player, state)
            except Exception as exc:
                internal_errors.append(exc)
                raise

        policy.Agent.decide = checked
        base = engine.make_map(seed=997113)
        g = engine.Game(base=base, start_token=3)
        worst = 0
        while not g.over():
            view = g.views()[2]
            before = public_snapshot(view)
            start = time.perf_counter()
            action = policy.act(view)
            elapsed = (time.perf_counter() - start) * 1000
            worst = max(worst, elapsed)
            self.assertEqual(public_snapshot(view), before)
            self.assertIn(action, view.legal_actions)
            self.assertLess(elapsed, 2000 if g.turn == 1 else 200)
            g.step(["STAY", "STAY", action, "STAY"])
        self.assertFalse(internal_errors)
        self.assertEqual(policy._AGENTS[3].tr.turn, 80)
        print("\nForward fixed public entry point: 80 calls, no input mutation/illegal/late output or swallowed error; worst %.3f ms" % worst)


if __name__ == "__main__":
    unittest.main()
