"""Small economic hypotheses for public-history inference and future play.

These are generic decision principles, not copies of any tested opponent.
All model state is inferred or hypothetical; no actual referee state is read.
"""
import math

from baselines import v8 as bot


# claim, upgrade, raid, interior preference, distance exponent, shield chance
PROFILES = (
    (1.0, 1.2, 0.45, 0.0, 1.0, 0.75),
    (0.8, 1.8, 0.25, 0.0, 1.0, 0.85),
    (1.6, 0.6, 0.30, 0.0, 1.0, 0.60),
    (1.0, 1.0, 0.40, 0.5, 0.75, 0.70),
    (1.0, 1.0, 0.35, -0.5, 0.9, 0.70),
    (0.9, 0.9, 1.20, 0.0, 0.9, 0.45),
)


def depth(p):
    r, c = divmod(p, 8)
    return min(r, c, 7-r, 7-c)


def step(game, seat, target):
    me = game.pos[seat]
    if me == target:
        return "STAY"
    closed = set(game.pos)
    neighbours = [p for p in bot.NEIGH[me] if p not in closed]
    nearer = [p for p in neighbours if bot.MANH[p][target] < bot.MANH[me][target]]
    if nearer:
        # Ties are relative to the actual home, keeping seat reflections fair.
        home = next(p for p, owner in enumerate(game.home) if owner == seat+1)
        frame = bot.CANON[bot.CORNERS.index(home)+1]
        p = min(nearer, key=lambda p: (bot.MANH[p][target], frame[p]))
    else:
        distance = bot._bfs(target, closed-{me})
        if not neighbours:
            return "STAY"
        p = min(neighbours, key=lambda p: distance[p])
        if distance[p] >= 99:
            return "STAY"
    return {1:"EAST", -1:"WEST", 8:"SOUTH", -8:"NORTH"}[p-me]


def jobs(game, seat, profile, target=None):
    wc, wu, wr, regional, power, _ = profile
    me, R = game.pos[seat], 81-game.turn
    closed = set(game.pos)-{me}
    distance = bot.MANH[me]
    result = []
    if isinstance(target, tuple):
        target = target[0]
    for p in range(64):
        if p in closed or (game.home[p] and game.owner[p] != seat+1):
            continue
        o, upgraded = game.owner[p], game.upg[p]
        if o == seat+1:
            if upgraded:
                continue
            need, gain = 3, game.base[p]*wu
        elif o == 0:
            need, gain = 1, game.base[p]*wc
        else:
            need, gain = (3 if upgraded else 1), game.base[p]*wr
        if p == me:
            need = max(1, need-game.prog[seat])
        d = distance[p]
        if d+need > R:
            continue
        gain *= R-d-need+1
        if o not in (0, seat+1):
            gain += 8*game.base[p]*(2 if upgraded else 1)*wr
            if game.cd[o-1] < d+need and game.frozen[o-1] < d+need:
                gain *= 0.35
        rate = gain/(d+need)**power
        rate *= math.exp(regional*depth(p))
        if target is not None and p == target:
            rate *= 1.15
        result.append((rate, p, need))
    return result


def should_shield(game, seat, probability, noise):
    if game.cd[seat] or game.frozen[seat]:
        return False
    threat = any(j != seat and not game.frozen[j] and
                 game.owner[p] == seat+1 and not game.home[p] and
                 (3 if game.upg[p] else 1)-game.prog[j] <= 1
                 for j, p in enumerate(game.pos))
    return threat and noise < probability


def action(game, seat, profile, target, noise=0.5):
    if game.frozen[seat]:
        return "STAY", target
    if should_shield(game, seat, profile[5], noise):
        return "SHIELD", target
    if isinstance(target, tuple):
        p, level = target
        complete = game.owner[p] == seat+1 and (level == 1 or game.upg[p])
        blocked_nearby = p in game.pos and game.pos[seat] != p and bot.MANH[game.pos[seat]][p] <= 1
        if not complete and not blocked_nearby and not (game.home[p] and game.owner[p] != seat+1):
            return step(game,seat,p), target
    options = jobs(game, seat, profile, target)
    if not options:
        return "STAY", None
    _, p, _ = max(options, key=lambda x: x[0])
    level = 2 if game.owner[p] == seat+1 else 1
    return step(game, seat, p), (p,level)


def distribution(game, seat, profile, target):
    if game.frozen[seat]:
        return {"STAY":1.0}, target
    options = jobs(game, seat, profile, target)
    if not options:
        return {"STAY":1.0}, None
    options.sort(reverse=True)
    scale = max(1, options[0][0]*0.18)
    weights = [(math.exp((rate-options[0][0])/scale), p) for rate,p,n in options[:8]]
    result = {a:0.02 for a in ("STAY", "NORTH", "SOUTH", "EAST", "WEST", "SHIELD")}
    for weight, p in weights:
        a = step(game, seat, p)
        result[a] += weight
    if should_shield(game, seat, 1.0, 0.0):
        result["SHIELD"] += sum(result.values())*profile[5]
    total = sum(result.values())
    goal = options[0][1]
    level = 2 if game.owner[goal] == seat+1 else 1
    return {a:p/total for a,p in result.items()}, (goal,level)


class Beliefs:
    def __init__(self):
        self.weights = [[1/len(PROFILES)]*len(PROFILES) for _ in range(4)]
        self.goals = [[None]*len(PROFILES) for _ in range(4)]
        self.prediction = None
        self.previous = None
        self.samples = [0]*4

    def observe(self, board):
        if self.previous is None or self.prediction is None:
            return
        _, own, up, _, occ, frozen = self.previous
        _, now, nu, _, noc, nf = board
        for j in range(4):
            p, q = occ.index(j+1), noc.index(j+1)
            if frozen[p] or nf[q]:
                continue
            if p != q:
                event = {1:"EAST", -1:"WEST", 8:"SOUTH", -8:"NORTH"}.get(q-p)
            elif (not own[p] and now[p] == j+1 or own[p] == j+1 and not up[p] and nu[p]):
                # Censor completed work consistent with a failed escape.
                if any(occ[w] or noc[w] not in (0,j+1) for w in bot.NEIGH[p]):
                    continue
                event = "STAY"
            else:
                continue
            if event is None:
                continue
            w = [(0.92*prior+0.08/len(PROFILES))*max(0.01, pred.get(event,0.01))**0.5
                 for prior,pred in zip(self.weights[j], self.prediction[j])]
            self.weights[j] = [x/sum(w) for x in w]
            self.samples[j] += 1

    def predict(self, game, board):
        self.prediction = []
        for j in range(4):
            row = []
            for k, profile in enumerate(PROFILES):
                probs, target = distribution(game, j, profile, self.goals[j][k])
                self.goals[j][k] = target
                row.append(probs)
            self.prediction.append(row)
        self.previous = board

    def profile(self, seat, particle, particles, learned):
        confidence = min(0.8, self.samples[seat]/12) if learned else 0.0
        weights = [confidence*w+(1-confidence)/len(PROFILES) for w in self.weights[seat]]
        u = ((particle+0.5)/particles + seat*0.38196601125) % 1
        for k, w in enumerate(weights):
            u -= w
            if u <= 0:
                return PROFILES[k]
        return PROFILES[-1]
