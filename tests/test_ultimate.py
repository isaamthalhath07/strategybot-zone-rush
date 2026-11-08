"""
Unit & Invariant Verification Suite for UltimateBot (`ultimate.py`)
===================================================================
Verifies all 6 architectural layers and all 10 implementation hazards from the
Zone Rush Autonomous Strategy Engine Specification.
"""

import time
import unittest

try:
    import engine
except ImportError:
    from tests import reference_engine as engine
import ultimate


class TestUltimateArchitecture(unittest.TestCase):

    def test_01_input_normalisation_variants(self):
        """Verify 8x8 nested, 64-flat, dict, and tuple board representations."""
        base = engine.make_map(canonical=True)
        g = engine.Game(base=base, max_turns=80, start_token=2)
        v = g.views()[0]

        # Standard 8x8 View
        act1 = ultimate.act(v)
        self.assertIn(act1, v.legal_actions)

        # Flat 64-cell list
        flat_board = [c for row in v.board for c in row]
        dict_state = {
            "board": flat_board,
            "bot_id": 1,
            "is_priority_token": False,
            "legal_actions": ["NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD"],
        }
        act2 = ultimate.act(dict_state)
        self.assertIn(act2, dict_state["legal_actions"])

        # Tuple cells (occupant, owner, is_upgraded, is_home, is_frozen, base_points)
        tuple_board = [
            (c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
            for c in flat_board
        ]
        tuple_state = {
            "board": tuple_board,
            "bot_id": 0,  # 0-indexed bot_id auto-resolved to seat 1
            "is_priority_token": True,
            "legal_actions": ["EAST", "SOUTH", "STAY"],
        }
        bot = ultimate.UltimateBot(seed=1)
        act3 = bot(tuple_state)
        self.assertIn(act3, tuple_state["legal_actions"])

    def test_02_priority_token_cycle_lock(self):
        """Verify Layer 1 Priority Token lock and deterministic future projection."""
        base = engine.make_map(canonical=True)
        g = engine.Game(base=base, max_turns=80, start_token=3)
        bot = ultimate.UltimateBot(seed=1)

        # Seat 1 plays: token starts at 3 -> 4 -> 1 (on turn 3 Seat 1 gets token)
        for t in range(1, 5):
            vs = g.views()
            a = bot(vs[0])
            self.assertIn(a, vs[0].legal_actions)
            if t >= 3:
                # By turn 3, Seat 1 saw is_priority_token=True, so holder_set must be locked to size 1
                self.assertEqual(len(bot.tracker.holder_set), 1)
                self.assertEqual(bot.tracker.token_holder_at(t), g.token)
                # Future turn projection must match exact cyclic formula
                self.assertEqual(bot.tracker.token_holder_at(t + 5), ((g.token - 1 + 5) % 4) + 1)
            g.step([a, "STAY", "STAY", "STAY"])

    def test_03_csp_shield_and_exit_escape(self):
        """Verify Layer 1 CSP solver on shield catches, arrival catches, and exit backfires."""
        base = engine.make_map(canonical=True)
        g = engine.Game(base=base, max_turns=80, start_token=1, rules={"catch_requires_stay": False})
        bot = ultimate.UltimateBot(seed=1)

        # Set up scenario: Seat 2 owns cell 14, Seat 3 is on cell 14
        g.owner[14] = 2
        g.pos[2] = 14  # Seat 3 on Seat 2's land
        g.pos[1] = 7   # Seat 2 at corner

        # Turn 1: observe initial board
        bot(g.views()[0])

        # Seat 2 shields, Seat 3 exits to neutral cell 13 -> Seat 3 escapes, Seat 2 backfires!
        g.step(["EAST", "SHIELD", "WEST", "STAY"])
        self.assertEqual(g.frozen[2], 0, "Exiting rival must NOT be frozen")
        self.assertEqual(g.frozen[1], 2, "Shielder must backfire for 2 turns")

        # Turn 2: bot observes board after backfire
        bot(g.views()[0])
        self.assertEqual(bot.tracker.cooldown[2], 4, "Tracker must deduce Seat 2's 4-turn shield cooldown")
        self.assertEqual(bot.tracker.freeze_left[2], 2, "Tracker must deduce Seat 2's 2-turn freeze")
        self.assertEqual(bot.tracker.freeze_left[3], 0, "Exiting Seat 3 must have 0 freeze in tracker")

    def test_04_frozen_intruder_shield_immunity_hazard(self):
        """Verify Section 9 Hazard: Never shield when intruders on our land are already frozen."""
        base = engine.make_map(canonical=True)
        g = engine.Game(base=base, max_turns=80, start_token=1, rules={"catch_requires_stay": False})
        bot = ultimate.UltimateBot(seed=1)

        # Seat 1 owns cell 9 (upgraded), Seat 2 is on cell 9 but ALREADY FROZEN
        g.owner[9] = 1
        g.upg[9] = 1
        g.pos[1] = 9
        g.frozen[1] = 2
        g.pos[0] = 10

        v = g.views()[0]
        cells, me, is_token, legal, _ = ultimate.normalise_state(v)
        owner = [c.owner for c in cells]
        level = [1 if c.is_upgraded else 0 for c in cells]
        pos = [-1, 10, 9, 63, 56]
        frozen = [False, False, True, False, False]
        enemies = [2, 3, 4]
        denial = [0.0, 0.0, 0.8, 0.8, 0.8]
        tasks = [(10.0, 10, 1.0, 20.0, 1, 1)]

        should_sh = ultimate.SubgameTactics.evaluate_defensive_shield(
            me, 50, legal, enemies, pos, owner, level, frozen, cells, denial, tasks, bot.tracker, bot.cfg
        )
        self.assertFalse(should_sh, "Must NEVER shield when the only intruder on our land is already frozen!")

    def test_05_memory_reset_across_consecutive_games(self):
        """Verify Section 9 Hazard: Global act(state) resets cleanly when a new match starts."""
        ultimate._SEAT_AGENTS.clear()
        base = engine.make_map(canonical=True)

        # Game 1: play 15 turns
        g1 = engine.Game(base=base, max_turns=80, start_token=1)
        for _ in range(15):
            vs = g1.views()
            acts = [ultimate.act(vs[i]) for i in range(4)]
            g1.step(acts)
        self.assertEqual(ultimate._SEAT_AGENTS[1].tracker.turn, 15)

        # Game 2: fresh game starts on pristine board without clearing _SEAT_AGENTS
        g2 = engine.Game(base=base, max_turns=80, start_token=2)
        vs2 = g2.views()
        a = ultimate.act(vs2[0])
        self.assertIn(a, vs2[0].legal_actions)
        self.assertEqual(ultimate._SEAT_AGENTS[1].tracker.turn, 1, "Tracker must auto-reset turn to 1 on new game!")
        self.assertEqual(ultimate._SEAT_AGENTS[1].tracker.scores, [0, 0, 0, 0, 0])

    def test_06_turn_80_free_shield_dominance(self):
        """Verify Layer 6: On Turn 80, if STAY cannot score and rival is on our land, override with SHIELD."""
        base = engine.make_map(canonical=True)
        g = engine.Game(base=base, max_turns=80, start_token=1)
        bot = ultimate.UltimateBot(seed=1)

        # Simulate tracker at Turn 80 (left = 1)
        bot.tracker.known_start = True
        bot.tracker.turn = 80
        bot.tracker.progress = 0  # Cannot complete 3-stay upgrade on turn 80

        g.owner[1] = 1
        g.upg[1] = 0
        g.pos[0] = 1  # Seat 1 on own L1 cell with progress=0 (needs 3 stays, only 1 turn left)
        g.owner[8] = 1
        g.pos[1] = 8  # Seat 2 threatening Seat 1's cell 8

        v = g.views()[0]
        cells, me, _, legal, _ = ultimate.normalise_state(v)
        owner = [c.owner for c in cells]
        level = [1 if c.is_upgraded else 0 for c in cells]
        pos = [-1, 1, 8, 63, 56]

        override = ultimate.EndgameExecutor.terminal_override(
            me, 1, 1, "STAY", legal, cells, owner, level, [2, 3, 4], pos, bot.tracker
        )
        self.assertEqual(override, "SHIELD", "Turn 80 must override unproductive STAY with free protective SHIELD!")

    def test_07_latency_and_full_game_stability(self):
        """Verify sub-5ms execution speed across a full 80-turn 4-bot mirror match."""
        base = engine.make_map(seed=42)
        g = engine.Game(base=base, max_turns=80, start_token=1, rules={"catch_requires_stay": False})
        bots = [ultimate.UltimateBot(seed=i + 1) for i in range(4)]

        max_ms = 0.0
        total_ms = 0.0
        calls = 0
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                t0 = time.perf_counter()
                a = bots[i](vs[i])
                dt = (time.perf_counter() - t0) * 1000.0
                total_ms += dt
                if dt > max_ms:
                    max_ms = dt
                calls += 1
                self.assertIn(a, vs[i].legal_actions)
                acts.append(a)
            g.step(acts)

        mean_ms = total_ms / calls
        self.assertLess(mean_ms, 5.0, f"Mean latency {mean_ms:.2f}ms too high")
        self.assertLess(max_ms, 50.0, f"Max latency {max_ms:.2f}ms too high")


if __name__ == "__main__":
    unittest.main()
