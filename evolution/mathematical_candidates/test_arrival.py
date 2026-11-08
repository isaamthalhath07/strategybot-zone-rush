"""Tests of the clock correction, separate from all strength claims."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import random
import time
import unittest

from evolution.genomes import GenomeSpace
from evolution.maps import generate
from evolution.opponents import FAMILIES, Rival
from evolution.runner import signature
from tests import reference_engine as engine
from .build_arrival import HERE, PARENT, ROOT, transform


def load(path):
    spec = importlib.util.spec_from_file_location("arrival_experiment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArrivalTests(unittest.TestCase):
    def test_exact_builder_and_unchanged_nonpolicy_logic(self):
        parent = (ROOT/"bot.py").read_bytes()
        self.assertEqual(hashlib.sha256(parent).hexdigest(), PARENT)
        candidate = transform(parent)
        self.assertEqual(candidate, (HERE/"arrival_lifetime.py").read_bytes())
        self.assertEqual(GenomeSpace(parent).genes, GenomeSpace(candidate).genes)
        def outside_policy(body):
            tree = ast.parse(body)
            tree.body = [n for n in tree.body if not isinstance(n, ast.FunctionDef)
                         or n.name not in ("_policy", "_future_task_reward")]
            return ast.dump(tree)
        self.assertEqual(outside_policy(parent), outside_policy(candidate))
        bad = parent.replace(b"CONFIG =", b"CONFIG = ", 1)
        with self.assertRaises(ValueError):
            transform(bad)

    def test_neutral_late_job_has_only_its_actual_income_turns(self):
        helper = load(HERE/"arrival_lifetime.py")._future_task_reward
        self.assertEqual(helper(30, 3, 10, 40, 11, 10), 6)
        self.assertEqual(helper(30, 3, 10, 40, 11, 2), 30)
        self.assertEqual(helper(30, 3, 10, 40, 11, 12), 0)

    def test_raid_cash_survives_delay_and_risk_divisor(self):
        helper = load(HERE/"arrival_lifetime.py")._future_task_reward
        # 3-point upgraded raid: cash48/2risk=24, income3/turn after
        # denial/risk multipliers. Delay ages income30 to6, cash24 stays24.
        self.assertEqual(helper(54, 3, 10, 40, 11, 10), 30)

    def test_retention_cap_and_upgrade_weights_are_preserved(self):
        helper = load(HERE/"arrival_lifetime.py")._future_task_reward
        self.assertEqual(helper(120, 6, 20, 20, 50, 15), 120)
        # An upgrade multiplier is a marginal-income coefficient, not cash.
        self.assertEqual(helper(60, 6, 10, 40, 11, 10), 12)

    def test_depth2_ablations_change_only_the_intended_gene(self):
        baseline = GenomeSpace((ROOT/"bot.py").read_bytes())
        for name in ("arrival_lifetime_depth2.py", "baseline_depth2.py"):
            genes = GenomeSpace((HERE/name).read_bytes()).genes
            self.assertEqual(genes, dict(baseline.genes, depth=2))

    def test_closed_loop_public_games_keep_tracking_legal_and_unchanged(self):
        maps = generate(8, 202611083701)
        callbacks = 0
        worst = 0.0
        for path in (ROOT/"bot.py", HERE/"arrival_lifetime.py", HERE/"arrival_lifetime_depth2.py", HERE/"baseline_depth2.py"):
            for case, board in enumerate(maps):
                game = engine.Game(base=board["base"], start_token=case%4+1,
                                   rules={"catch_requires_stay": True})
                focal = case%4
                player = load(path)
                rng = random.Random(202611083702+case)
                rivals = {seat: Rival(dict(family=FAMILIES[(seat+case)%len(FAMILIES)],
                                          seed=rng.getrandbits(63), epsilon=0.1,
                                          commitment=0.75)) for seat in range(4) if seat != focal}
                while not game.over():
                    views = game.views()
                    public = views[focal]
                    before = signature(public)
                    start = time.perf_counter()
                    own = player.act(public)
                    elapsed = (time.perf_counter()-start)*1000
                    worst = max(worst, elapsed)
                    self.assertLess(elapsed, 2000 if game.turn == 1 else 200)
                    self.assertEqual(signature(public), before)
                    self.assertIn(own, public.legal_actions)
                    self.assertEqual(player._input_failures, 0)
                    self.assertEqual(player._policy_failures, 0)
                    memory = player._history[focal+1]
                    self.assertEqual(memory["inference_failures"], 0)
                    self.assertEqual(memory["progress"], game.prog[focal])
                    self.assertEqual(memory["scores"][1:], game.score)
                    for seat in range(4):
                        self.assertIn(game.cd[seat], memory["cooldown_possible"][seat+1])
                    chosen = [own if seat == focal else rivals[seat].act(views[seat]) for seat in range(4)]
                    game.step(chosen)
                    callbacks += 1
        self.assertEqual(callbacks, 2560)
        print("Arrival-clock contracts:32 games,2,560 focal callbacks; worst %.3fms" % worst)


if __name__ == "__main__":
    unittest.main()
