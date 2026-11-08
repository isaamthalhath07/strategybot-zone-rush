"""Public-input and mechanics checks for the explicitly clarified shield rule."""
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load("presence_forward_test", ROOT / "human_arena/candidates/forward_presence.py")
referee = load("presence_referee_test", ROOT / "human_arena/vendor_harness/referee.py")
RULE = {"catch_requires_stay": False}


def observe(tracker, game, seat, requested=None):
    view = game.views()[seat - 1]
    cells = [c for row in view.board for c in row]
    tracker.observe([c.owner for c in cells], [c.is_upgraded for c in cells],
        [c.occupant for c in cells], [c.is_frozen for c in cells], seat,
        view.is_priority_token, [c.base_points for c in cells],
        [c.owner if c.is_home else 0 for c in cells], requested, view.legal_actions)


def state(game):
    income = game.income() if callable(game.income) else game.income
    return (game.turn, game.token, tuple(game.pos), tuple(game.owner), tuple(game.upg),
            tuple(game.frozen), tuple(game.cd), tuple(game.prog), tuple(game.score), tuple(income))


def snapshot(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


class PresencePhysicsTests(unittest.TestCase):
    def test_embedded_world_defaults_to_presence(self):
        self.assertFalse(policy._world_RULES["catch_requires_stay"])
        self.assertFalse(policy._world_Game().rules["catch_requires_stay"])

    def test_recorded_turn_34_now_catches_moving_red(self):
        path = Path(r"C:\Users\LEGION\Downloads\zone-rush-44e7eb1d4c604285ab1af22ba0b3b7dc.json")
        if not path.exists():
            self.skipTest("uploaded regression fixture not present")
        data = json.loads(path.read_text(encoding="utf8"))
        self.assertEqual(data["game_id"], "44e7eb1d4c604285ab1af22ba0b3b7dc")
        record = next(r for r in data["turns"] if r["turn"] == 34)
        g = referee.Referee(data["metadata"]["base"], rules=RULE)
        for field in ("pos", "owner", "upg", "frozen", "cd", "prog", "score"):
            setattr(g, field, record["before"][field][:])
        g.turn, g.token = 34, record["before"]["token"]
        self.assertEqual(g.owner[26:28], [1, 1])
        result = g.step(record["used"])
        self.assertEqual(g.pos[1], 26)
        self.assertEqual(g.frozen, [0, 2, 0, 0])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2])
        self.assertEqual(g.prog[1], 0)
        for _ in range(2):
            self.assertEqual(g.legal(1), ["STAY"])
            g.step(["STAY"] * 4)
            self.assertEqual(g.prog[1], 0)
        self.assertEqual(g.frozen[1], 0)

    def test_arrival_is_caught_before_any_capture(self):
        g = referee.Referee(referee.example_map(), rules=RULE)
        g.pos[1], g.owner[27] = 28, 1
        result = g.step(["SHIELD", "WEST", "STAY", "STAY"])
        self.assertEqual(g.pos[1], 27)
        self.assertEqual(g.owner[27], 1)
        self.assertEqual(g.frozen[:2], [0, 2])
        self.assertEqual(g.prog[1], 0)
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2])

    def test_leaving_territory_really_escapes(self):
        g = referee.Referee(referee.example_map(), rules=RULE)
        g.pos[1], g.owner[27], g.owner[26] = 27, 1, 0
        g.step(["SHIELD", "WEST", "STAY", "STAY"])
        self.assertEqual(g.pos[1], 26)
        self.assertEqual(g.frozen[:2], [2, 0])

    def test_mutual_unfrozen_shields_catch_each_other(self):
        g = referee.Referee(referee.example_map(), rules=RULE)
        g.pos[:2], g.owner[8], g.owner[15] = [8, 15], 2, 1
        result = g.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        shields = [e for e in result["events"] if e["type"] == "shield"]
        self.assertEqual([e["caught"] for e in shields], [[2], [1]])
        self.assertFalse(any(e["backfire"] for e in shields))
        self.assertEqual(g.frozen[:2], [2, 2])
        self.assertEqual(g.cd[:2], [4, 4])

    def test_already_frozen_requested_shield_is_ignored_and_ineligible(self):
        g = referee.Referee(referee.example_map(), rules=RULE)
        g.pos[1], g.owner[8], g.frozen[1] = 8, 1, 2
        result = g.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        self.assertEqual(result["eff"][1], "STAY")
        self.assertEqual(g.frozen[:2], [2, 1])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [])

    def test_three_engines_and_public_tracker_properties(self):
        rng = random.Random(881973)
        for trial in range(24):
            base, token = engine.make_map(seed=710331 + trial), trial % 4 + 1
            games = [referee.Referee(base, rules=RULE, start_token=token),
                     engine.Game(base, rules=RULE, start_token=token),
                     policy._world_Game(base, start_token=token)]
            trackers, prior = [policy._base_Tracker() for _ in range(4)], [None] * 4
            for _ in range(80):
                self.assertEqual(state(games[0]), state(games[1]))
                self.assertEqual(state(games[0]), state(games[2]))
                for j, tracker in enumerate(trackers):
                    observe(tracker, games[1], j + 1, prior[j])
                    self.assertEqual(tracker.turn, games[1].turn)
                    self.assertEqual(tracker.score, games[1].score)
                    self.assertEqual(tracker.prog[j], games[1].prog[j])
                    for rival in range(4):
                        self.assertIn(games[1].cd[rival], tracker.cd_possible[rival], (trial, games[1].turn, j, rival))
                prior = [rng.choice(games[0].legal(j)) for j in range(4)]
                for g in games:
                    g.step(prior)


class PresenceModelTests(unittest.TestCase):
    def test_moving_victim_reveals_owner_cooldown(self):
        g, tracker = engine.Game(rules=RULE), policy._base_Tracker()
        g.pos[1], g.owner[27], g.owner[26] = 27, 1, 1
        g.income[0] += g.base[27] + g.base[26]
        observe(tracker, g, 2)
        g.step(["SHIELD", "WEST", "STAY", "STAY"])
        observe(tracker, g, 2, "WEST")
        self.assertEqual(tracker.cd_possible[0], {4})
        self.assertEqual(tracker.frozen[1], 2)
        self.assertEqual(tracker.prog[1], 0)

    def test_internal_move_is_not_a_successful_territorial_escape_label(self):
        g, tracker = engine.Game(rules=RULE), policy._base_Tracker()
        g.pos[1], g.owner[27], g.owner[26] = 27, 1, 1
        g.income[0] += g.base[27] + g.base[26]
        observe(tracker, g, 2)
        g.step(["STAY", "WEST", "STAY", "STAY"])
        observe(tracker, g, 2, "WEST")
        self.assertEqual(tracker.baits[1], 0)
        self.assertEqual(tracker.raids[1], 1)

    def test_raid_risk_includes_arrival_and_cooldown_boundary(self):
        player = policy._base_Agent(params={"q_prior": .5, "q_weight": 4., "throttle": 0})
        self.assertEqual(player._shield_risk(1, 1, 1), .75)
        player.tr.cd[1] = 1
        self.assertEqual(player._shield_risk(1, 1, 1), .5)
        player.tr.cd[1] = 2
        self.assertEqual(player._shield_risk(1, 1, 1), 0)
        player.tr.cd[1], player.tr.frozen[1] = 0, 1
        self.assertEqual(player._shield_risk(1, 1, 1), .5)

    def test_no_geometric_exit_means_catch_does_not_depend_on_stay_read(self):
        player = policy._base_Agent(params={"shield_certain": 0, "throttle": 0})
        owner, upgraded, occupant, frozen, base = [0] * 64, [0] * 64, [0] * 64, [0] * 64, [3] * 64
        occupant[27], owner[27] = 2, 1
        for p in policy._base_NEIGH[27]:
            owner[p] = 1
        player.tr.home_of = [0] * 64

        def impossible(_rival):
            raise AssertionError("A STAY probability must not override an inescapable presence catch")

        player._commit_prob = impossible
        self.assertTrue(player._should_shield(owner, upgraded, occupant, frozen, base, 1, 20, 1, [1] * 4))

    def test_rejected_shield_can_still_be_caught_by_another_owner(self):
        g, tracker = engine.Game(rules=RULE), policy._base_Tracker()
        g.pos[0], g.owner[8] = 8, 2
        g.income[1] += g.base[8]
        observe(tracker, g, 1)
        # Own SHIELD request was late, becoming STAY. Both this and an accepted
        # own SHIELD are eligible to be caught by the other owner's shield.
        g.step(["STAY", "SHIELD", "STAY", "STAY"])
        observe(tracker, g, 1, "SHIELD")
        for j in range(4):
            self.assertIn(g.cd[j], tracker.cd_possible[j])
        self.assertEqual(tracker.frozen[0], 2)
        self.assertEqual(tracker.prog[0], 0)


class PresenceArtifactTests(unittest.TestCase):
    def test_source_preserved_and_manifest_matches(self):
        folder = ROOT / "human_arena/candidates"
        self.assertEqual(hashlib.sha256((folder / "forward_fixed.py").read_bytes()).hexdigest(),
                         "95da830e6f29d0ac06b095fb4de57ace8eb7962881818fa50a4c19f714ec07d9")
        manifest = json.loads((folder / "forward_presence.manifest.json").read_text(encoding="utf8"))
        self.assertEqual(hashlib.sha256((folder / "forward_presence.py").read_bytes()).hexdigest(), manifest["sha256"])

    def test_actual_public_entry_point_full_game(self):
        module = load("presence_entrypoint", ROOT / "human_arena/candidates/forward_presence.py")
        internal_errors = []
        original_decide = module.Agent.decide

        def checked(player, view):
            try:
                return original_decide(player, view)
            except Exception as exc:
                internal_errors.append(exc)
                raise

        module.Agent.decide = checked
        g = engine.Game(base=engine.make_map(seed=991043), rules=RULE, start_token=3)
        worst = 0
        while not g.over():
            view = g.views()[1]
            before = snapshot(view)
            start = time.perf_counter()
            action = module.act(view)
            elapsed = (time.perf_counter() - start) * 1000
            worst = max(worst, elapsed)
            self.assertEqual(snapshot(view), before)
            self.assertIn(action, view.legal_actions)
            self.assertLess(elapsed, 2000 if g.turn == 1 else 200)
            g.step(["STAY", action, "STAY", "STAY"])
        self.assertFalse(internal_errors)
        self.assertEqual(module._AGENTS[2].tr.turn, 80)
        print("\nPresence forward: 80 public calls, no mutation/illegal/late output/internal exception; worst %.3f ms" % worst)


if __name__ == "__main__":
    unittest.main()
