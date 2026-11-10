"""Independent public-input behavioral families, freshly seeded each game.

Specs and RNG seeds belong exclusively to each rival, never to the focal bot.
Different instances are not a claim of different algorithms.
"""
import random

FAMILIES = ("wanderer", "farmer", "raider", "interceptor", "feinter", "mixed")
DELTA = {"NORTH": (-1, 0), "EAST": (0, 1), "SOUTH": (1, 0), "WEST": (0, -1)}


class Rival:
    def __init__(self, spec):
        self.rng = random.Random(spec["seed"])
        self.family = spec["family"]
        self.epsilon = spec["epsilon"]
        self.commitment = spec["commitment"]
        self.last_position = None
        self.stationary = 0
        self.turn = 0

    def act(self, state):
        self.turn += 1
        cells = [c for row in state.board for c in row]
        me = state.bot_id
        pos = next(p for p, c in enumerate(cells) if c.occupant == me)
        self.stationary = self.stationary+1 if pos == self.last_position else 0
        self.last_position = pos
        legal = list(state.legal_actions)
        if len(legal) == 1:
            return legal[0]
        r, c = divmod(pos, 8)
        free = {}
        for action, (dr, dc) in DELTA.items():
            rr, cc = r+dr, c+dc
            if action in legal and 0 <= rr < 8 and 0 <= cc < 8 and not cells[rr*8+cc].occupant:
                free[action] = rr*8+cc
        if self.rng.random() < self.epsilon:
            return self.rng.choice(legal)
        if self.family == "wanderer":
            return self.rng.choice(list(free)+["STAY"]*2)
        threats = [p for p, cell in enumerate(cells) if cell.owner == me and cell.occupant not in (0, me) and not cell.is_frozen]
        # Public-presence baiting is deliberately imperfect; these are opponents,
        # never an oracle or correctness model for the deployed bot.
        if threats and "SHIELD" in legal and self.rng.random() < self.commitment:
            return "SHIELD"
        cell = cells[pos]
        if self.family == "feinter" and cell.owner not in (0, me) and free:
            same_owner = [a for a, p in free.items() if cells[p].owner == cell.owner]
            if same_owner and self.rng.random() < self.commitment:
                return self.rng.choice(same_owner)
        if cell.owner == 0 or (cell.owner != me and not cell.is_home):
            return "STAY"
        if cell.owner == me and not cell.is_upgraded:
            up_chance = 0.95 if self.family == "farmer" else 0.35
            if self.rng.random() < up_chance:
                return "STAY"
        targets = []
        for p, target in enumerate(cells):
            if (target.is_home and target.owner != me) or (target.occupant and p != pos):
                continue
            d = abs(r-p//8)+abs(c-p%8)
            if d == 0:
                continue
            if target.owner == me:
                value = (0 if target.is_upgraded else target.base_points*1.6)
            elif target.owner == 0:
                value = target.base_points*2.1
            else:
                value = target.base_points*(3.4 if self.family in ("raider", "mixed") else 1.1)
                if target.is_upgraded:
                    value *= 0.68
            if self.family == "interceptor":
                rivals = [q for q, other in enumerate(cells) if other.occupant not in (0, me)]
                nearest = min(abs(p//8-q//8)+abs(p%8-q%8) for q in rivals)
                value += 4/(1+nearest)
            value /= d+1
            targets.append((value + self.rng.random()*0.02, p))
        if not targets or not free:
            return "STAY"
        goal = max(targets)[1]
        return min(free, key=lambda a: (abs(free[a]//8-goal//8)+abs(free[a]%8-goal%8), self.rng.random()))

_EVOLUTION_PLAYER = Rival({'seat': 0, 'family': 'raider', 'seed': 2622337353132641766, 'epsilon': 0.013869040270494156, 'commitment': 0.7915641487537195, 'id': '8d269f6f1cd96c3c4aeeaf2208efd05fcc414e2cc36796652e7e4d982e4fe392'})
def act(state):
    return _EVOLUTION_PLAYER.act(state)
