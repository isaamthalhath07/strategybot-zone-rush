"""Public-history region demand, not opponent identity or a secret goal label."""
import math

from botlib import NEIGH, man


def depth(p):
    r, c = divmod(p, 8)
    return min(r, c, 7-r, 7-c)


def centre_distance(p):
    r, c = divmod(p, 8)
    return max(0, 3-r, r-4) + max(0, 3-c, c-4)


class RegionModel:
    """A deliberately small, approximate likelihood model with forgetting.

    It infers inward / perimeter / local intent. One first move is ignored:
    the corner's two legal directions do not distinguish centre from rim.
    No hidden actions or goals are consumed. Only successful moves and actual
    completed work are labels; forced and ambiguous stationary events abstain.
    """
    def __init__(self):
        self.prob = [[1/3] * 3 for _ in range(4)]
        self.n = [0] * 4
        self.skips = [0] * 4

    def update(self, old, new, homes, turn):
        if turn <= 2:  # the observation at turn 2 contains only move number 1
            return
        base, own, up, home, occ, frz = old
        _, now, nu, _, noc, nf = new
        for j in range(4):
            if j+1 not in occ or j+1 not in noc:
                continue
            p, q = occ.index(j+1), noc.index(j+1)
            if frz[p] or nf[q]:
                continue
            moved = p != q
            worked = (own[p] == 0 and now[p] == j+1 or
                      own[p] == j+1 and not up[p] and nu[p])
            if not moved and not worked:
                continue
            options = [p] + [w for w in NEIGH[p] if not occ[w]]
            if q not in options:
                continue
            if moved and not own[p]:
                self.skips[j] += 1
            likelihood = []
            for mode in range(3):
                scores = []
                for w in options:
                    if mode == 0:
                        value = 1.1*(centre_distance(p)-centre_distance(w)) + 0.9*(depth(w)-depth(p))
                    elif mode == 1:
                        value = 1.8*(depth(p)-depth(w)) + 0.15*(man(homes[j], w)-man(homes[j], p))
                    else:
                        value = -0.45*(man(homes[j], w)-man(homes[j], p))
                    if w == p:
                        if not own[p]:
                            value += base[p] * (0.25, 0.40, 0.75)[mode]
                        elif own[p] == j+1 and not up[p]:
                            value += base[p] * (0.08, 0.16, 0.35)[mode]
                    scores.append(math.exp(value))
                likelihood.append(scores[options.index(q)] / sum(scores))
            # Temper the hand-designed likelihood and forget stale intentions.
            weights = [(0.94*self.prob[j][m]+0.06/3) * likelihood[m]**0.5 for m in range(3)]
            self.prob[j] = [w/sum(weights) for w in weights]
            self.n[j] += 1

    def demand(self, board, positions, homes, seat, history=True):
        base, own = board[0], board[1]
        total = [0.0] * 64
        for j, pos in enumerate(positions):
            if j == seat-1 or pos is None:
                continue
            confidence = min(1.0, self.n[j]/5) if history else 0.0
            weights = [confidence*p + (1-confidence)/3 for p in self.prob[j]]
            fields = []
            for mode in range(3):
                field = []
                for p in range(64):
                    if own[p]:
                        field.append(0.0)
                        continue
                    potential = ((0.80*depth(p)) if mode == 0 else
                                 (-0.80*depth(p)) if mode == 1 else
                                 (-0.22*man(homes[j], p))) if history else 0.0
                    field.append(math.sqrt(base[p])*math.exp(potential-man(pos, p)/4.0))
                norm = sum(field) or 1.0
                fields.append([x/norm for x in field])
            for p in range(64):
                total[p] += sum(weights[m]*fields[m][p] for m in range(3))
        return total
