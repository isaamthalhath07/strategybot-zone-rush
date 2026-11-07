"""Four additional scheduling policies, created AFTER discovery, never fitted.

Public-state observation plumbing is shared with the procedural population.
Scheduling rules below are separate from all training/development policies.
"""
import math

from botlib import first_step, man
from freshlab.population import ProceduralOpponent, specification


FAMILIES = ("reservation", "discounted", "portfolio", "two_job_sum")


class ExtraOpponent(ProceduralOpponent):
    def choose(self, state):
        if len(state.legal_actions) == 1:
            return state.legal_actions[0]
        if self.shield(state):
            return "SHIELD"
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        family = self.spec["family"]
        ranked = {p: g / c for p, g, c, d, n in jobs}
        if family == "reservation":
            # Complete a reserved work item until it becomes unavailable,
            # instead of re-ranking against its changing travel denominator.
            if self.target in ranked:
                goal = self.target
            else:
                goal = max(jobs, key=lambda j: j[1] / (j[2] ** 0.65))[0]
        elif family == "discounted":
            # Continuous-time discounting makes a different travel/return
            # tradeoff from either rate ranking or a finite-horizon route sum.
            goal = max(jobs, key=lambda j: j[1] * math.exp(-0.17 * j[2]))[0]
        elif family == "portfolio":
            # A budgeted territory/upgrade portfolio instead of one value scale.
            owned = sum(o == self.seat for o in self.owner)
            upgraded = sum(o == self.seat and u for o, u in zip(self.owner, self.upg))
            category = (0 if owned < 8 else 1 if upgraded * 2 < owned else 2)
            def score(job):
                p, g, c, d, n = job
                o = self.owner[p]
                wanted = ((category == 0 and not o) or
                          (category == 1 and o == self.seat) or
                          (category == 2 and o not in (0, self.seat)))
                return g / c * (1.65 if wanted else 0.8)
            goal = max(jobs, key=score)[0]
        else:
            # Two-job SUM of income, rather than the two-job RATE/auction
            # objectives in development/final. Only the short local schedule
            # is compared; holding a goal prevents repeated re-optimisation.
            top = sorted(jobs, key=lambda j: j[1] / j[2], reverse=True)[:10]
            scores = {}
            for p, g, c, d, n in top:
                continuation = 0.0
                for q, h, qc, qd, qn in top:
                    if p == q or c + man(p, q) + qn > min(18, self.R):
                        continue
                    rem_old = max(1, self.R - qd - qn + 1)
                    rem_new = self.R - c - man(p, q) - qn + 1
                    continuation = max(continuation, h * rem_new / rem_old)
                scores[p] = g + continuation
            goal = max(scores, key=scores.get)
        if family != "reservation" and self.target in ranked:
            # Commitment is compared on the same objective scale.
            if family == "two_job_sum" and self.target in scores:
                if scores[self.target] * self.spec["commit"] >= scores[goal]:
                    goal = self.target
            elif family != "two_job_sum" and ranked[self.target] * self.spec["commit"] >= ranked[goal]:
                goal = self.target
        self.target = goal
        return "STAY" if goal == self.me else first_step(self.me, goal, self.closed) or "STAY"


def extra_spec(seed):
    # Sample parameters independently, then select an algorithm unused in any
    # preceding experiment. No optimisation or submission matchup screening.
    spec = specification("train", seed)
    spec["family"] = FAMILIES[seed % len(FAMILIES)]
    return spec
