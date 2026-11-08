"""An availability repair is conditional; a public feint can reverse its gain."""
import hashlib
from pathlib import Path
import unittest

from evolution import mathematical_probes as probes
from evolution.runner import signature
from simulator.vendor_harness.referee import Referee
from tests import reference_engine as engine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run_case(path, future_opponents):
    proof = probes.anticipatory_shield_counterexample()
    player = probes.load(path)
    game = engine.Game(base=proof["base"], start_token=proof["initial_token"], rules={"catch_requires_stay": True})
    for joint in proof["prefix"]:
        public = game.views()[0]
        player.act(public)
        player._history[1]["last"] = joint[0]
        game.step(joint)
    decisions, tape = [], list(proof["prefix"])
    for rivals in future_opponents:
        public = game.views()[0]
        before = signature(public)
        chosen = player.act(public)
        if signature(public) != before or chosen not in public.legal_actions:
            raise AssertionError("Public input or output contract failed")
        memory = player._history[1]
        if (player._input_failures or player._policy_failures or memory["inference_failures"]
                or memory["progress"] != game.prog[0] or memory["scores"][1:] != game.score
                or any(game.cd[s] not in memory["cooldown_possible"][s+1] for s in range(4))):
            raise AssertionError("Public-history oracle contract failed")
        joint = [chosen]+list(rivals)
        if any(a not in game.legal(i) for i, a in enumerate(joint)):
            raise AssertionError("Counterplay action must be legal")
        decisions.append(dict(turn=game.turn, chosen=chosen, cooldown=game.cd[0], frozen=game.frozen[0]))
        tape.append(joint)
        game.step(joint)
    independent = Referee(proof["base"], start_token=proof["initial_token"], rules={"catch_requires_stay": True})
    for joint in tape:
        independent.step(joint)
    if (independent.score != game.score or independent.owner != game.owner
            or independent.pos != game.pos or independent.frozen != game.frozen
            or independent.cd != game.cd or independent.prog != game.prog):
        raise AssertionError("Independent referees disagree")
    return dict(decisions=decisions, score=game.score, owner18=game.owner[18],
                complete_game=game.over(), last_turn=game.turn-1,
                pairwise_wins=sum(1 if game.score[0] > other else .5 if game.score[0] == other else 0 for other in game.score[1:]))


class CounterplayTests(unittest.TestCase):
    def test_ready_landlord_and_committed_raider_favor_early_shield(self):
        # This profile reproduces the motivating case. B shields now; C stays.
        profile = [("SHIELD", "STAY", "STAY")]+[("STAY", "STAY", "STAY")]*63
        baseline = run_case(ROOT/"bot.py", profile)
        self.assertEqual(baseline["decisions"][0]["chosen"], "STAY")
        self.assertEqual(baseline["owner18"], 3)
        self.assertTrue(baseline["complete_game"])
        self.assertEqual(baseline["pairwise_wins"], 0)
        for name in ("availability_only.py", "arrival_and_availability.py"):
            repaired = run_case(HERE/name, profile)
            self.assertEqual(repaired["decisions"][0]["chosen"], "SHIELD")
            self.assertEqual(repaired["owner18"], 1)
            self.assertGreater(repaired["score"][0], baseline["score"][0])
            self.assertEqual(repaired["pairwise_wins"], 1)

    def test_a_feint_then_return_reverses_the_benefit(self):
        # Same initial public state: B remains ready but does not shield. C
        # escapes, returns on the next turn, then completes three legal stays.
        profile = [("STAY", "EAST", "STAY"), ("STAY", "WEST", "STAY")]+[("STAY", "STAY", "STAY")]*3
        baseline = run_case(ROOT/"bot.py", profile)
        self.assertEqual([d["chosen"] for d in baseline["decisions"]], ["STAY"]*4+["SHIELD"])
        self.assertEqual(baseline["owner18"], 1)
        self.assertEqual(baseline["pairwise_wins"], 2)
        for name in ("availability_only.py", "arrival_and_availability.py"):
            repaired = run_case(HERE/name, profile)
            self.assertEqual([d["chosen"] for d in repaired["decisions"]], ["SHIELD"]+["STAY"]*4)
            self.assertEqual(repaired["owner18"], 3)
            self.assertEqual(repaired["pairwise_wins"], 1)
            self.assertLess(repaired["score"][0], baseline["score"][0])
            self.assertGreater(repaired["score"][2], baseline["score"][2])

    def test_counterexamples_leave_all_frozen_sources_unchanged(self):
        paths = [ROOT/"bot.py", HERE/"availability_only.py", HERE/"arrival_and_availability.py"]
        expected = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        profile = [("STAY", "EAST", "STAY"), ("STAY", "WEST", "STAY")]+[("STAY", "STAY", "STAY")]*3
        for path in paths:
            run_case(path, profile)
        self.assertEqual([hashlib.sha256(path.read_bytes()).hexdigest() for path in paths], expected)

    def test_the_same_feint_can_reduce_the_actual_terminal_pairwise_result(self):
        profile = [("STAY", "EAST", "STAY"), ("STAY", "WEST", "STAY")]+[("STAY", "STAY", "STAY")]*62
        baseline = run_case(ROOT/"bot.py", profile)
        self.assertTrue(baseline["complete_game"])
        self.assertEqual(baseline["last_turn"], 80)
        self.assertEqual(baseline["pairwise_wins"], 1)
        self.assertEqual(baseline["owner18"], 1)
        for name in ("availability_only.py", "arrival_and_availability.py"):
            repaired = run_case(HERE/name, profile)
            self.assertTrue(repaired["complete_game"])
            self.assertEqual(repaired["pairwise_wins"], 0)
            self.assertEqual(repaired["owner18"], 3)


if __name__ == "__main__":
    unittest.main()
