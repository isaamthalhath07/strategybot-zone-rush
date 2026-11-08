"""Guard the seat/token and opponent balance of promotion evidence."""
from collections import Counter
import unittest
try:
    from .validate_champion import fixtures
except ImportError:
    from validate_champion import fixtures


class ScheduleTests(unittest.TestCase):
    def test_screen_uses_both_opponent_fields_equally(self):
        rows = fixtures("screen_balanced")
        self.assertEqual(sorted(Counter(tuple(r["opponents"]) for r in rows).values()), [8, 8])
        self.assertEqual(Counter(r["seat"] for r in rows), {s: 4 for s in range(4)})
        self.assertEqual(Counter(r["token"] for r in rows), {s: 4 for s in range(1, 5)})

    def test_confirmation_balances_every_seat_token_pair_per_map(self):
        rows = fixtures("confirm_release")
        for mi in range(8):
            self.assertEqual({(r["seat"], r["token"]) for r in rows if r["map_index"] == mi},
                             {(s, t) for s in range(4) for t in range(1, 5)})
        self.assertEqual(sorted(Counter(tuple(r["opponents"]) for r in rows).values()), [64, 64])

    def test_confirmation_maps_were_not_used_for_selection(self):
        self.assertTrue({r["map_seed"] for r in fixtures("screen_balanced")}.isdisjoint(
                        {r["map_seed"] for r in fixtures("confirm_release")}))


if __name__ == "__main__":
    unittest.main()
