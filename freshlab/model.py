"""Online opponent models from public transitions, with censored observations.

No opponent identifiers, parameters, hidden actions, server internals or file IO.
Shield actions are labelled only when every consistent explanation agrees.
"""
from math import sqrt


class Evidence:
    def __init__(self):
        self.counts = {}
        self.brier = [0.0, 0]

    def predict(self, player, context, prior, weight=4.0, conservative=0.0):
        y, n = self.counts.get((player, None), (0.0, 0.0))
        pooled = (weight * prior + y) / (weight + n)
        a, k = self.counts.get((player, context), (0.0, 0.0))
        mean = (4.0 * pooled + a) / (4.0 + k)
        if conservative:
            mean += conservative * sqrt(mean * (1 - mean) / (5.0 + k))
        return max(0.02, min(0.98, mean))

    def add(self, player, context, outcome, prediction):
        self.brier[0] += (prediction - outcome) ** 2
        self.brier[1] += 1
        for key in ((player, None), (player, context)):
            y, n = self.counts.get(key, (0.0, 0.0))
            self.counts[key] = (y + outcome, n + 1)


class Styles:
    def __init__(self):
        self.defence = Evidence()
        self.commit = Evidence()
        self.finish = Evidence()
        self.ambiguous = 0
        self.inconsistent = 0
        self.observations = []
        self.last_context = {}

    @staticmethod
    def defend_context(upgraded, value, remaining):
        return (bool(upgraded), value >= 2, remaining <= 16)

    @staticmethod
    def commit_context(ready, upgraded, remaining):
        return (bool(ready), bool(upgraded), remaining <= 16)

    def update(self, old, new, oldpos, pos, cd, frozen, progress, seat, last,
               remaining, prior, commit_prior, neighbours):
        own, up, occ, frz = old
        now, nowup, nowocc, nowfrz = new
        newly = {j for j, p in enumerate(pos)
                 if p is not None and nowfrz[p] and not frozen[j]}
        candidates = [j for j in range(4) if oldpos[j] is not None
                      and pos[j] == oldpos[j] and not frozen[j] and cd[j] == 0
                      and not any(a == j + 1 and b != a for a, b in zip(own, now))]
        possible = []
        for mask in range(1 << len(candidates)):
            S = {j for k, j in enumerate(candidates) if mask >> k & 1}
            if last is not None and ((seat - 1 in S) != (last == "SHIELD")):
                continue
            predicted = set()
            for s in S:
                caught = {j for j, p in enumerate(oldpos) if p is not None
                          and j != s and not frozen[j] and pos[j] == p
                          and j not in S and own[p] == s + 1}
                predicted.update(caught if caught else {s})
            if predicted == newly:
                possible.append(S)
        if not possible:
            self.inconsistent += 1
            return
        certain = set.intersection(*possible)
        maybe = set.union(*possible)
        self.ambiguous += certain != maybe
        by_defender = {}
        for j, p in enumerate(oldpos):
            if p is None or frozen[j] or frz[p]:
                continue
            o = own[p]
            if not o or o == j + 1:
                # Upgrade dwell times are observable even away from conflicts.
                if o == j + 1 and not up[p] and j not in maybe:
                    context = (progress[j] >= 1, remaining <= 16)
                    pred = self.finish.predict(j, context, 0.70)
                    self.finish.add(j, context, float(pos[j] == p), pred)
                continue
            if p in (0, 7, 56, 63):
                continue
            ready = cd[o - 1] == 0 and not frozen[o - 1]
            # Failed exits/contests are ambiguous intent: do not call them
            # voluntary commitment when a contested escape is consistent.
            contested_exit = any(occ[w] == 0 and nowocc[w] not in (0, j + 1)
                                 for w in neighbours[p])
            if j not in maybe and (pos[j] != p or not contested_exit):
                context = self.commit_context(ready, up[p], remaining)
                pred = self.commit.predict(j, context, commit_prior)
                self.commit.add(j, context, float(pos[j] == p), pred)
                self.observations.append(("commit", j, context, int(pos[j] == p)))
            need = (3 if up[p] else 1) - progress[j]
            if ready and need <= 1:
                by_defender.setdefault(o - 1, []).append(p)
        # A shield is one decision even if three raiders stand on owned land.
        for defender, cells in by_defender.items():
            if defender in maybe and defender not in certain:
                continue
            p = max(cells, key=lambda x: (up[x], self.base[x]))
            context = self.defend_context(up[p], self.base[p], remaining)
            pred = self.defence.predict(defender, context, prior)
            yes = int(defender in certain)
            self.defence.add(defender, context, yes, pred)
            self.observations.append(("shield", defender, context, yes))

