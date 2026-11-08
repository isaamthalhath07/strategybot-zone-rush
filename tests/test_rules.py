"""New-match post-movement shields, with explicit historical-rule replay."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import random
import unittest

from simulator import history, server
from tests import reference_engine as engine
from tests.test_simulator_server import FakeProcess


class ShieldResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match, cls.referee, _sources, cls.provenance = server.bootstrap()

    def game(self, **overrides):
        return self.referee.Referee(self.referee.example_map(), rules=dict(server.NEW_GAME_RULES, **overrides))

    @staticmethod
    def moving_fixture(game):
        # Uploaded 44e7 T34's essential geometry: human at D2, Red at D4,
        # moving WEST to human-owned C4. Neither bot starts frozen.
        game.turn, game.token = 34, 2
        game.pos = [11, 27, 53, 43]
        game.owner[11] = game.owner[26] = game.owner[27] = 1

    def test_red_D4_to_C4_is_caught_and_human_does_not_backfire(self):
        game = self.game()
        self.moving_fixture(game)
        result = game.step(["SHIELD", "WEST", "NORTH", "STAY"])
        shield = next(e for e in result["events"] if e["type"] == "shield")
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(shield["caught"], [2])
        self.assertFalse(shield["backfire"])
        self.assertEqual(game.frozen[:2], [0, 2])
        self.assertEqual(game.owner[26], 1)
        self.assertEqual(game.legal(1), ["STAY"])

    def test_arrival_from_outside_is_caught_after_movement(self):
        game = self.game()
        game.pos[1], game.owner[26] = 34, 1
        result = game.step(["SHIELD", "NORTH", "STAY", "STAY"])
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(game.frozen[:2], [0, 2])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2])

    def test_leaving_all_shield_owner_land_escapes(self):
        game = self.game()
        game.pos[1], game.owner[27] = 27, 1
        result = game.step(["SHIELD", "WEST", "STAY", "STAY"])
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(game.frozen[:2], [2, 0])
        self.assertTrue(next(e for e in result["events"] if e["type"] == "shield")["backfire"])

    def test_already_frozen_rival_is_ineligible(self):
        game = self.game()
        game.pos[1], game.owner[26], game.frozen[1] = 26, 1, 1
        result = game.step(["SHIELD", "STAY", "STAY", "STAY"])
        self.assertEqual(game.frozen[:2], [2, 0])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [])

    def test_shield_protects_every_owned_cell_and_resets_both_raids(self):
        game = self.game()
        game.pos[1:3] = [10, 20]
        game.owner[10] = game.owner[20] = 1
        game.upg[20], game.prog[2] = True, 2
        result = game.step(["SHIELD", "STAY", "STAY", "STAY"])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2, 3])
        self.assertEqual([game.owner[p] for p in (10, 20)], [1, 1])
        self.assertEqual(game.frozen[1:3], [2, 2])
        self.assertEqual(game.prog[1:3], [0, 0])
        self.assertFalse(any(e["type"] == "raid" for e in result["events"]))

    def test_using_own_shield_on_rival_land_does_not_grant_immunity(self):
        game = self.game()
        game.pos[1], game.owner[26] = 26, 1
        game.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        self.assertEqual(game.frozen[:2], [0, 2])

    def test_new_human_game_explicit_model_and_legacy_override_are_separate(self):
        updated = server.HumanGame(dict(id="fixture"), "unused", 1, 1, 1, self.match, self.referee, FakeProcess)
        legacy = server.HumanGame(dict(id="fixture"), "unused", 1, 1, 1, self.match, self.referee, FakeProcess,
                                  rules={"catch_requires_stay": True})
        try:
            self.assertFalse(updated.g.rules["catch_requires_stay"])
            self.assertTrue(legacy.g.rules["catch_requires_stay"])
            self.assertTrue(self.referee.DEFAULT_RULES["catch_requires_stay"], "vendored defaults must not be silently rewritten")
            self.moving_fixture(legacy.g)
            legacy.g.step(["SHIELD", "WEST", "NORTH", "STAY"])
            self.assertEqual(legacy.g.frozen[:2], [2, 0], "historical rule model still reproduces its recorded outcome")
            self.assertEqual(set(updated.public("ai")), {"game_id", "turn", "over", "observation"})
        finally:
            updated.close()
            legacy.close()

    def test_new_recordings_hash_explicit_rules_without_changing_referee_source(self):
        root = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(root.parent, server.HERE.resolve())
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="post-movement-shield-", dir=root) as folder:
            updated = server.HumanGame(dict(id="fixture"), "unused", 2, 1, 1, self.match, self.referee,
                                       FakeProcess, history_dir=folder)
            try:
                recorded = history.read_history(folder, updated.id)["metadata"]
                self.assertFalse(recorded["rules"]["catch_requires_stay"])
                digest = hashlib.sha256(json.dumps(recorded["rules"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                self.assertEqual(recorded["rules_sha256"], digest)
                self.assertEqual(recorded["referee_sha256"], self.provenance["files"]["referee.py"])
            finally:
                updated.close()

    def test_mutual_shields_remain_active_when_each_owner_is_caught(self):
        game = self.game()
        game.pos[:2] = [10, 20]
        game.owner[10], game.owner[20] = 2, 1
        result = game.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        self.assertEqual(game.frozen[:2], [2, 2])
        shields = {event["seat"]: event for event in result["events"] if event["type"] == "shield"}
        self.assertEqual(shields[1]["caught"], [2])
        self.assertEqual(shields[2]["caught"], [1])


_, referee, _, _ = server.bootstrap()
RULES = dict(catch_requires_stay=False)


def shared_state(game):
    income = game.income() if callable(game.income) else game.income
    return (game.turn, game.token, tuple(game.pos), tuple(game.owner), tuple(game.upg),
            tuple(game.frozen), tuple(game.cd), tuple(game.prog), tuple(game.score), tuple(income))


class IndependentPhysicsTests(unittest.TestCase):
    def test_independent_oracle_retains_exact_source_provenance(self):
        root = Path(__file__).parent
        metadata = json.loads((root / "reference_engine.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((root / "reference_engine.py").read_bytes()).hexdigest(), metadata["sha256"])
        self.assertNotEqual(metadata["sha256"], hashlib.sha256((server.VENDOR / "referee.py").read_bytes()).hexdigest())

    def test_two_engines_agree_for_twenty_four_complete_random_sequences(self):
        rng = random.Random(881973)
        for trial in range(24):
            base, token = engine.make_map(seed=710331 + trial), trial % 4 + 1
            games = [referee.Referee(base, rules=RULES, start_token=token),
                     engine.Game(base=base, rules=RULES, start_token=token)]
            for turn in range(1, 81):
                with self.subTest(trial=trial, turn=turn):
                    self.assertEqual(shared_state(games[0]), shared_state(games[1]))
                    for seat, view in enumerate(games[1].views(), 1):
                        public = games[0].observation(seat)
                        self.assertEqual(set(public), {"board", "bot_id", "is_priority_token", "legal_actions"})
                        self.assertEqual(set(public["legal_actions"]), set(view.legal_actions))
                        actual = [[[cell.occupant, cell.owner, cell.is_upgraded, cell.is_home,
                                    cell.is_frozen, cell.base_points] for cell in row] for row in view.board]
                        self.assertEqual(public["board"], actual)
                        self.assertEqual(public["is_priority_token"], view.is_priority_token)
                        self.assertEqual(public["bot_id"], view.bot_id)
                    actions = [rng.choice(games[0].legal(i)) if rng.random() > .04 else "INVALID" for i in range(4)]
                    output = [game.step(actions) for game in games]
                    self.assertEqual(output[0]["eff"], output[1])
                    self.assertEqual(shared_state(games[0]), shared_state(games[1]))
            self.assertTrue(all(game.over() for game in games))

    def test_claim_resets_then_three_more_stays_upgrade_with_completion_income(self):
        base = [1] * 64
        base[8] = 3
        game = referee.Referee(base, rules=RULES)
        game.pos[0] = 8
        game.step(["STAY"] * 4)
        self.assertEqual((game.owner[8], game.prog[0], game.score[0]), (1, 0, 4))
        for progress in (1, 2):
            game.step(["STAY"] * 4)
            self.assertEqual(game.prog[0], progress)
            self.assertFalse(game.upg[8])
        game.step(["STAY"] * 4)
        self.assertTrue(game.upg[8])
        self.assertEqual(game.prog[0], 0)
        self.assertEqual(game.score[0], 19)

    def test_repeated_upgraded_raid_shields_are_new_freezes_not_extended_one(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        g.turn, g.pos[:2], g.owner[33], g.upg[33], g.prog[0] = (67, [33, 35], 2, True, 2)
        g.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        for expected in (2, 1):
            self.assertEqual(g.frozen[0], expected)
            self.assertEqual(g.legal(0), ['STAY'])
            g.step(['STAY'] * 4)
        self.assertEqual(g.turn, 70)
        self.assertEqual(g.frozen[0], 0)
        self.assertIn('SOUTH', g.legal(0))
        g.step(['SOUTH', 'STAY', 'STAY', 'STAY'])
        g.step(['STAY'] * 4)
        g.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        self.assertEqual(g.frozen[0], 0)
        self.assertEqual(g.frozen[1], 2, 'shielding after the raider exits backfires')

    def test_occupied_at_start_blocks_following_and_counts_as_work(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        g.pos[:2], g.owner[26], g.prog[0] = ([26, 27], 1, 2)
        out = g.step(['EAST', 'EAST', 'STAY', 'STAY'])
        self.assertEqual(g.pos[:2], [26, 28])
        self.assertEqual(out['eff'][0], 'STAY')
        self.assertTrue(g.upg[26], 'the blocked action must finish the upgrade')

    def test_owner_wins_contest_even_against_token(self):
        g = referee.Referee(referee.example_map(), start_token=2, rules=RULES)
        g.pos[:2], g.owner[27] = ([26, 28], 1)
        g.step(['EAST', 'WEST', 'STAY', 'STAY'])
        self.assertEqual(g.pos[:2], [27, 28])

    def test_token_and_lost_contest_work(self):
        g = referee.Referee(referee.example_map(), start_token=2, rules=RULES)
        g.pos[:2], g.owner[26], g.prog[0] = ([26, 28], 1, 2)
        g.step(['EAST', 'WEST', 'STAY', 'STAY'])
        self.assertEqual(g.pos[:2], [26, 27])
        self.assertTrue(g.upg[26])

    def test_blocked_stay_is_caught_before_capture(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        g.pos[:2], g.owner[26] = ([26, 27], 2)
        g.step(['EAST', 'SHIELD', 'STAY', 'STAY'])
        self.assertEqual(g.frozen[0], 2)
        self.assertEqual(g.owner[26], 2)
        for _ in range(2):
            self.assertEqual(g.legal(0), ['STAY'])
            g.step(['STAY'] * 4)
            self.assertEqual(g.prog[0], 0)
            self.assertEqual(g.owner[26], 2)
        self.assertEqual(g.frozen[0], 0)
        self.assertNotEqual(g.legal(0), ['STAY'])

    def test_global_shield_and_exact_cooldown(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        g.pos[0], g.pos[2] = (10, 20)
        g.owner[10] = g.owner[20] = 2
        out = g.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        event = next((e for e in out['events'] if e['type'] == 'shield'))
        self.assertEqual(event['caught'], [1, 3])
        for _ in range(4):
            self.assertNotIn('SHIELD', g.legal(1))
            g.step(['STAY'] * 4)
        self.assertIn('SHIELD', g.legal(1))

    def test_raid_bonus_uses_previous_level_and_scores_new_land_now(self):
        base = referee.example_map()
        base[27] = 3
        g = referee.Referee(base, rules=RULES)
        g.pos[0], g.owner[27], g.upg[27], g.prog[0] = (27, 2, True, 2)
        out = g.step(['STAY'] * 4)
        self.assertEqual(out['bonus'][0], 48)
        self.assertEqual(g.score[0], 52)
        self.assertEqual(g.owner[27], 1)
        self.assertFalse(g.upg[27])
        self.assertEqual(g.prog[0], 0)

    def test_home_upgrade_and_immunity(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        for _ in range(3):
            g.step(['STAY'] * 4)
        self.assertTrue(all((g.upg[p] for p in referee.HOMES.values())))
        g.pos[0], g.pos[1] = (7, 8)
        for _ in range(5):
            g.step(['STAY'] * 4)
        self.assertEqual(g.owner[7], 2)
        self.assertEqual(g.prog[0], 0)

    def test_round_one_ties_are_draws_despite_cell_counts(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        g.score, g.owner[1] = ([100, 100, 10, 0], 1)
        self.assertEqual(referee.places(g.score), [1, 1, 3, 4])
        self.assertEqual(referee.pairwise(g.score)[:2], [2.5 / 3, 2.5 / 3])

    def test_public_serializer_contains_only_official_fields(self):
        g = referee.Referee(referee.example_map(), rules=RULES)
        public = g.observation(1)
        self.assertEqual(set(public), {'board', 'bot_id', 'is_priority_token', 'legal_actions'})
        self.assertTrue(all((len(c) == 6 for row in public['board'] for c in row)))
        public['board'][0][0][1] = 4
        self.assertEqual(g.owner[0], 1)


if __name__ == "__main__":
    unittest.main()
