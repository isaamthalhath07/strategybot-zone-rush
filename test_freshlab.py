"""Public-only observation, censoring, split isolation and exact controls."""
import json
import random
import unittest
from pathlib import Path

import engine
from botlib import NEIGH
from freshlab import baseline, candidate, evaluate, model, population
from freshlab import terminal


class StyleTests(unittest.TestCase):
    def setUp(self):
        self.game = engine.Game()
        self.styles = model.Styles()
        self.styles.base = self.game.base

    def observation(self, game):
        view = game.views()[0]
        cells = [c for row in view.board for c in row]
        return ([c.owner for c in cells], [int(c.is_upgraded) for c in cells],
                [c.occupant for c in cells], [int(c.is_frozen) for c in cells])

    def event(self, acts):
        g = self.game
        old, pos, cd, frz, prog = self.observation(g), g.pos[:], g.cd[:], g.frozen[:], g.prog[:]
        effective = g.step(acts)
        self.styles.update(old, self.observation(g), pos, g.pos, cd, frz, prog,
                           1, acts[0], 50, .6, .7, NEIGH)
        return effective

    def invasion(self, upgraded=False):
        g = self.game
        g.pos = [9, 10, 63, 56]
        g.owner[10] = 1
        g.upg[10] = int(upgraded)

    def test_no_negative_shield_observation_on_cooldown(self):
        self.invasion()
        self.game.cd[0] = 2
        self.event(["STAY"] * 4)
        self.assertFalse(self.styles.defence.counts)

    def test_no_negative_shield_observation_before_capture_imminent(self):
        self.invasion(upgraded=True)
        self.event(["STAY"] * 4)
        self.assertFalse(self.styles.defence.counts)

    def test_frozen_raider_is_not_voluntary_commitment(self):
        self.invasion()
        self.game.frozen[1] = 2
        self.event(["STAY"] * 4)
        self.assertFalse(self.styles.commit.counts)
        self.assertFalse(self.styles.defence.counts)

    def test_defender_has_one_decision_with_two_raiders(self):
        self.invasion()
        self.game.pos[2] = 11
        self.game.owner[11] = 1
        self.event(["SHIELD", "STAY", "STAY", "STAY"])
        self.assertEqual(self.styles.defence.counts[(0, None)], (1, 1))

    def test_move_proves_raider_bailed(self):
        self.invasion()
        self.event(["STAY", "NORTH", "STAY", "STAY"])
        self.assertEqual(self.styles.commit.counts[(1, None)], (0, 1))

    def test_ambiguous_shield_attribution_is_not_a_label(self):
        self.invasion()
        g = self.game
        old, pos, cd, frz, prog = self.observation(g), g.pos[:], g.cd[:], g.frozen[:], g.prog[:]
        g.step(["SHIELD", "STAY", "STAY", "STAY"])
        # Observe as player FOUR: player 2 freezing could mean player 1 caught
        # it, or player 2's own shield backfired. The public board cannot tell.
        self.styles.update(old, self.observation(g), pos, g.pos, cd, frz, prog,
                           4, "STAY", 50, .6, .7, NEIGH)
        self.assertEqual(self.styles.ambiguous, 1)
        self.assertFalse(self.styles.defence.counts)
        self.assertFalse(self.styles.commit.counts)

    def test_home_visitors_are_not_capture_threats(self):
        self.game.pos = [9, 0, 63, 56]
        self.event(["STAY"] * 4)
        self.assertFalse(self.styles.commit.counts)
        self.assertFalse(self.styles.defence.counts)

    def test_sparse_evidence_shrinks_toward_prior(self):
        e = model.Evidence()
        e.add(1, "x", 0, .7)
        p = e.predict(1, "x", .7)
        self.assertGreater(p, .35)
        self.assertLess(p, .7)
        self.assertAlmostEqual(e.predict(2, "x", .7), .7)
        self.assertAlmostEqual(e.predict(1, "unseen", .7), .56)

    def test_exact_labels_against_referee_random_sequences(self):
        # Hidden actions are used only HERE as observer labels, never by a bot.
        rng = random.Random(7193321)
        checked = 0
        for _ in range(12):
            self.game = engine.Game()
            self.styles = model.Styles()
            self.styles.base = self.game.base
            for turn in range(80):
                g = self.game
                acts = [rng.choice(g.legal(j)) for j in range(4)]
                n = len(self.styles.observations)
                effective = self.event(acts)
                for kind, j, ctx, label in self.styles.observations[n:]:
                    truth = effective[j] == ("SHIELD" if kind == "shield" else "STAY")
                    self.assertEqual(bool(label), truth)
                    checked += 1
        self.assertGreater(checked, 2)


class PopulationTests(unittest.TestCase):
    def test_architecture_splits_are_disjoint(self):
        sets = [set(f) for f in population.SPLITS.values()]
        for i, a in enumerate(sets):
            for b in sets[i+1:]:
                self.assertFalse(a & b)

    def test_replay_zero_feature_control_and_contracts(self):
        params = dict(baseline.PARAMS)
        params.update(json.loads(Path("v7_params.json").read_text()))
        params.update(throttle=0, budget_ms=10000, first_turn_ms=0)
        for t in evaluate.tasks("train", 8, 11933):
            a = evaluate.play(t, "baseline", params)
            b = evaluate.play(t, "observe_only", params)
            self.assertEqual(a["action_hash"], b["action_hash"])
            self.assertEqual(a["scores"], b["scores"])

    def test_new_games_have_new_styles_and_maps(self):
        first = evaluate.tasks("train", 16, 723)
        second = evaluate.tasks("train", 16, 724)
        self.assertFalse(set(t["map_seed"] for t in first) & set(t["map_seed"] for t in second))
        self.assertFalse(set(s["seed"] for t in first for s in t["specs"]) &
                         set(s["seed"] for t in second for s in t["specs"]))

    def test_supplementary_confirmation_balances_every_map_seat_token(self):
        from collections import Counter
        from freshlab import confirm, unseen
        ts = confirm.tasks(1, 18811)
        counts = Counter((t["map_kind"], t["seat"], t["token"]) for t in ts)
        for kind in {t["map_kind"] for t in ts}:
            expected = 2 if kind == "standard" else 1
            for seat in range(4):
                for token in range(1, 5):
                    self.assertEqual(counts[(kind, seat, token)], expected)
        used = set(s["family"] for t in ts for s in t["specs"])
        self.assertEqual(used, set(unseen.FAMILIES))
        self.assertFalse(used & set().union(*map(set, population.SPLITS.values())))

    def test_frozen_v8_export_matches_its_recorded_policy(self):
        import hashlib
        from baselines import v8
        artifact = Path(__file__).resolve().parent / "baselines/v8.py"
        expected_hash = json.loads(Path("freshlab/release_verification.json").read_text())["bot_sha256"]
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), expected_hash)
        self.assertNotIn(b"\r\n", artifact.read_bytes())
        params = dict(baseline.PARAMS)
        params.update(json.loads(Path("v7_params.json").read_text()))
        params.update(throttle=0, budget_ms=10000, first_turn_ms=0)
        for task in evaluate.tasks("final", 2, 739119):
            reference = candidate.AdaptiveAgent(task["map_seed"], params,
                                                 candidate.VARIANTS["raid_calibration"])
            release = v8.Agent(seed=task["map_seed"], params={"throttle":0,"budget_ms":10000,"first_turn_ms":0})
            game = engine.Game(base=task["base"], start_token=task["token"])
            while not game.over():
                view = game.views()[task["seat"]]
                expected = reference(view)
                self.assertEqual(release(view), expected)
                actions = ["STAY"] * 4
                actions[task["seat"]] = expected
                game.step(actions)


class TerminalTests(unittest.TestCase):
    def test_simultaneous_payoffs_match_engine(self):
        import itertools
        rng = random.Random(992733)
        checked = 0
        for repeat in range(16):
            g = engine.Game(base=engine.make_map(seed=repeat))
            for _ in range(45):
                g.step([rng.choice(g.legal(j)) for j in range(4)])
            g.turn = 80
            # Choose distinct genuinely successful exit destinations so MOVE
            # has the meaning the conditional resolver explicitly promises.
            closed, chosen, options = set(g.pos), set(), []
            for j, p in enumerate(g.pos):
                options.append(["STAY"] + (["SHIELD"] if "SHIELD" in g.legal(j) else []))
                for name, delta in engine.MOVES.items():
                    q = p + delta
                    if name in g.legal(j) and q not in closed and q not in chosen:
                        options[-1].append(name)
                        chosen.add(q)
                        break
            for actions in itertools.product(*options):
                sim = g.clone()
                abstract = [a if a in ("SHIELD", "STAY") else "MOVE" for a in actions]
                predicted = terminal.resolve(g.owner, g.upg, g.home, g.base,
                                             g.pos, g.frozen, g.prog, g.score, abstract)
                sim.step(actions)
                self.assertEqual(predicted, sim.score)
                checked += 1
        self.assertGreater(checked, 300)

    def test_imminent_raid_bonus_can_outweigh_defence(self):
        g = engine.Game()
        g.pos = [10, 9, 63, 56]
        g.owner[10] = 3
        g.upg[10] = 1
        g.base[10] = 3
        g.prog[0] = 2
        g.owner[9] = 1
        g.base[9] = 1
        g.score = [100, 101, 102, 0]
        stay = terminal.resolve(g.owner, g.upg, g.home, g.base, g.pos,
                                g.frozen, g.prog, g.score, ["STAY"]*4)
        shield = terminal.resolve(g.owner, g.upg, g.home, g.base, g.pos,
                                  g.frozen, g.prog, g.score, ["SHIELD"] + ["STAY"]*3)
        self.assertGreater(terminal.utility(stay, 0), terminal.utility(shield, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
