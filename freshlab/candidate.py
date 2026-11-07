"""Feature experiments layered over an immutable local submission snapshot."""
from freshlab import baseline
from freshlab.model import Styles
from freshlab import terminal


class LearningTracker(baseline.Tracker):
    def reset(self):
        super().reset()
        self.styles = Styles()
        self.learning_prior = 0.6
        self.learning_commit = 0.7

    def observe(self, owner, upg, occ, frz, seat, is_token, base, home_of, my_last=None):
        old = self.prev
        oldpos, cd, frozen, prog = self.pos[:], self.cd[:], self.frozen[:], self.prog[:]
        super().observe(owner, upg, occ, frz, seat, is_token, base, home_of, my_last)
        self.styles.base = base
        if old is not None and not self.new_game:
            self.styles.update(old, (owner, upg, occ, frz), oldpos, self.pos,
                               cd, frozen, prog, seat, my_last,
                               82 - self.turn, self.learning_prior,
                               self.learning_commit, baseline.NEIGH)


class AdaptiveAgent(baseline.Agent):
    def __init__(self, seed=0, params=None, features=None):
        super().__init__(seed, params)
        self.features = dict(features or {})
        for key, factor in self.features.get("scale", {}).items():
            self.P[key] *= factor
        self.tr = LearningTracker()
        self.raid_context = None
        self.commit_context = None

    def decide(self, view):
        self.tr.learning_prior = self.P["q_prior"]
        self.tr.learning_commit = self.P["commit_prior"]
        action = super().decide(view)
        if self.features.get("terminal", 0) and self.tr.turn == 80:
            bd = view.board
            cells = [c for row in bd for c in row] if isinstance(bd[0], (list, tuple)) else list(bd)
            owner = [c.owner for c in cells]
            upg = [int(c.is_upgraded) for c in cells]
            occ = [c.occupant for c in cells]
            frz = [int(c.is_frozen) for c in cells]
            base = [c.base_points for c in cells]
            self._terminal_shield_legal = "SHIELD" in view.legal_actions and self.tr.cd[view.bot_id - 1] == 0
            action = terminal.choose(self, owner, upg, occ, frz, base, view.bot_id, action)
        return action

    def _work_gain(self, p, kind, v, need, used, owner, upg, occ, seat, R,
                   kappa, care, travel):
        self.raid_context = (bool(upg[p]), v, R, used)
        gain = super()._work_gain(p, kind, v, need, used, owner, upg, occ, seat,
                                  R, kappa, care, travel)
        # Occupancy is closed this turn; a rival still upgrading on its own cell
        # is also likely to remain there. Use history only after evidence accrues.
        if gain is not None and self.features.get("dwell", 0) and occ[p] not in (0, seat):
            j = occ[p] - 1
            ev = self.tr.styles.finish
            y, n = ev.counts.get((j, None), (0, 0))
            if n >= 4 and owner[p] == j + 1 and not upg[p]:
                dwell = ev.predict(j, (self.tr.prog[j] >= 1, R <= 16), 0.7)
                gain *= 1.0 - self.features["dwell"] * dwell
        return gain

    def _shield_risk(self, ridx, travel, need):
        if not self.features.get("defence", 0) or self.raid_context is None:
            return super()._shield_risk(ridx, travel, need)
        upgraded, value, R, elapsed = self.raid_context
        if self.features.get("elapsed", 0):
            # Absolute elapsed time: a future beam job cannot use today's window.
            travel = elapsed
        if self.tr.frozen[ridx] >= travel + need or self.tr.cd[ridx] >= travel + need:
            return 0.0
        exposed = need if self.tr.cd[ridx] <= travel else travel + need - self.tr.cd[ridx]
        context = Styles.defend_context(upgraded, value, R)
        conservative = self.features.get("uncertainty", 0)
        estimate = self.tr.styles.defence.predict(ridx, context, self.P["q_prior"],
                                                 self.P["q_weight"], conservative)
        # Fade learned reads for plans far in the future; styles can change.
        horizon = 1.0 / (1.0 + 0.08 * max(0, travel - 2))
        estimate = horizon * estimate + (1 - horizon) * self.P["q_prior"]
        old = self.tr.q_shield(ridx, self.P["q_prior"], self.P["q_weight"])
        blend = self.features["defence"]
        if self.features.get("minimum_evidence", 0):
            yes, count = self.tr.styles.defence.counts.get((ridx, None), (0, 0))
            if count < self.features["minimum_evidence"]:
                return super()._shield_risk(ridx, travel, need)
            blend *= count / (count + 12.0)
        q = blend * estimate + (1 - blend) * old
        # Imminence-aware defenders get ONE final opportunity, not three
        # independent opportunities on an upgraded raid. Observations above only
        # label final-work-turn opportunities; their hazard must match that.
        if self.features.get("same_hazard", 0):
            return 1.0 - (1.0 - max(0.0, min(1.0, q))) ** max(0, exposed)
        return max(0.0, min(1.0, q))

    def _should_shield(self, owner, upg, occ, frz, base, seat, R, kappa, care):
        self.commit_context = (owner, upg, occ, frz, seat, R)
        old = self.P["shield_certain"]
        if self.features.get("mix", 0):
            self.P["shield_certain"] = 1.0
        try:
            return super()._should_shield(owner, upg, occ, frz, base, seat, R, kappa, care)
        finally:
            self.P["shield_certain"] = old

    def _commit_prob(self, j):
        if not self.features.get("commit", 0) or self.commit_context is None:
            return super()._commit_prob(j)
        owner, upg, occ, frz, seat, R = self.commit_context
        p = self.tr.pos[j]
        context = Styles.commit_context(True, upg[p] if p is not None else False, R)
        estimate = self.tr.styles.commit.predict(j, context, self.P["commit_prior"],
                                                self.P["commit_weight"])
        blend = self.features["commit"]
        if self.features.get("minimum_evidence", 0):
            yes, count = self.tr.styles.commit.counts.get((j, None), (0, 0))
            if count < self.features["minimum_evidence"]:
                return super()._commit_prob(j)
            blend *= count / (count + 12.0)
        return blend * estimate + (1 - blend) * super()._commit_prob(j)


VARIANTS = {
    "baseline": {},
    "observe_only": {},
    "context_commit": {"commit": 1.0},
    "context_defence": {"defence": 1.0},
    "guarded": {"commit": 0.5, "defence": 0.5, "uncertainty": 0.5},
    "context_both": {"commit": 1.0, "defence": 1.0},
    "future_window": {"commit": 0.5, "defence": 0.5, "elapsed": 1.0},
    "dwell": {"dwell": 0.5},
    "terminal": {"terminal": 1.0},
    "terminal_commit": {"terminal": 1.0, "commit": 1.0},
    "aligned_risk": {"defence": 1.0, "same_hazard": 1.0},
    "confident_risk": {"defence": 1.0, "same_hazard": 1.0, "minimum_evidence": 4},
    "careful_commit": {"commit": 1.0, "minimum_evidence": 4},
    "confident_both": {"commit": 1.0, "defence": 1.0, "same_hazard": 1.0,
                       "minimum_evidence": 4},
    "shield_mix": {"mix": 1.0},
    "expansion": {"scale": {"w_claim": 1.20, "w_upgrade": 0.90}},
    "consolidation": {"scale": {"w_claim": 0.90, "w_upgrade": 1.10}},
    "raid_calibration": {"scale": {"raid_risk": 0.75, "w_raid": 0.85,
                                   "w_raid_late": 0.85}},
    "learned_calibration": {"defence": 1.0, "same_hazard": 1.0,
                            "minimum_evidence": 4,
                            "scale": {"raid_risk": 0.75, "w_raid": 0.85,
                                      "w_raid_late": 0.85}},
}
