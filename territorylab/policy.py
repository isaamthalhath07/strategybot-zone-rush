"""Spatial adaptation over the accepted bot; no changes to its defence model."""
import math

from baselines import v8 as bot
from botlib import parse
from territorylab.model import RegionModel, depth


VARIANTS = {
    "baseline": {},
    "naive_edges": {"naive": True},
    "position": {"strength": 0.35, "history": False},
    "territory": {"strength": 0.35, "history": True},
    "cautious": {"strength": 0.15, "history": True},
}


class SpatialAgent(bot.Agent):
    def __init__(self, seed=0, params=None, feature=None):
        super().__init__(seed, params)
        self.feature = feature or {}
        self.regions = RegionModel()
        self.old_board = None
        self.demands = [0.0] * 64
        self.region_factor = [1.0] * 64
        self.observed_turn = 0

    def decide(self, view):
        board = parse(view)
        own, home = board[1], board[3]
        homes = [next(p for p in range(64) if home[p] and own[p] == j) for j in range(1, 5)]
        # Agent's tracker observes immediately after this hook. Detect a normal
        # fresh start as well as supporting separate instances in the harness.
        if self.observed_turn >= 80:
            self.regions = RegionModel()
            self.old_board = None
            self.observed_turn = 0
        self.observed_turn += 1
        if self.old_board is not None:
            self.regions.update(self.old_board, board, homes, self.observed_turn)
        self.old_board = board
        pos = [board[4].index(j) if j in board[4] else None for j in range(1, 5)]
        self.region_factor = [1.0] * 64
        if self.observed_turn <= 24:
            if self.feature.get("naive"):
                rushers = sum(self.regions.skips[j] >= 1 for j in range(4) if j != view.bot_id-1)
                if rushers >= 2:
                    self.region_factor = [1.4 if depth(p) == 0 else 0.85 if depth(p) >= 2 else 1.0 for p in range(64)]
            elif self.feature:
                self.demands = self.regions.demand(board, pos, homes, view.bot_id, self.feature["history"])
                neutral = [p for p in range(64) if not own[p]]
                mean = sum(self.demands[p] for p in neutral)/max(1, len(neutral))
                strength = self.feature["strength"]
                self.region_factor = [max(0.7, min(1.3, math.exp(-strength*(d/max(mean, 1e-9)-1)))) for d in self.demands]
        return super().decide(view)

    def _work_gain(self, p, kind, v, need, used, owner, upg, occ, seat, R,
                   kappa, care, travel):
        gain = super()._work_gain(p, kind, v, need, used, owner, upg, occ,
                                  seat, R, kappa, care, travel)
        # A fixed per-cell factor for this observed turn; never change the value
        # under a hypothetical walk's feet and cause the old oscillation bug.
        if gain is not None and kind in (0, 3):
            gain *= self.region_factor[p]
        return gain
