"""Independent Zone Rush practice referee. Only the organisers' server is official."""
from collections import namedtuple
import random
from time import perf_counter


Cell = namedtuple("Cell", "occupant owner is_upgraded is_home base_points is_frozen")
Observation = namedtuple("Observation", "board bot_id is_priority_token legal_actions")
HOMES = (0, 7, 63, 56)
MOVES = ("NORTH", "EAST", "SOUTH", "WEST")
DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))
NEIGHBORS = tuple({
    name: 8 * (p // 8 + dy) + p % 8 + dx
    for name, (dy, dx) in zip(MOVES, DIRECTIONS)
    if 0 <= p // 8 + dy < 8 and 0 <= p % 8 + dx < 8
} for p in range(64))
EXAMPLE = ((1, 1, 1, 2), (1, 1, 2, 2), (1, 2, 2, 3), (2, 2, 3, 3))


def map_values(seed=0, family="balanced"):
    rng = random.Random(seed)
    quadrant = []
    for r in range(4):
        row = []
        for c in range(4):
            base = EXAMPLE[r][c]
            if family == "example":
                v = base
            elif family == "balanced":
                # Mild jitter around the rulebook diagram.
                v = base + rng.choice((-1, 0, 0, 0, 1))
            elif family == "patchy":
                v = rng.randint(1, 3)
            elif family == "flat":
                v = 1 + seed % 3
            elif family == "edge":
                # Stress against high-value perimeter routes.
                v = 4 - base + rng.choice((-1, 0, 0, 1))
            else:
                raise ValueError(f"Unknown map family {family}")
            row.append(min(3, max(1, v)))
        quadrant.append(row)
    return [quadrant[min(r, 7-r)][min(c, 7-c)] for r in range(8) for c in range(8)]


class Game:
    def __init__(self, seed=0, family="balanced", start_token=1,
                 frozen_stays_progress=False, values=None):
        if start_token not in range(1, 5):
            raise ValueError("start_token must be a seat from 1 to 4")
        raw = map_values(seed, family) if values is None else list(values)
        self.values = [v for row in raw for v in row] if len(raw) == 8 else list(raw)
        if len(self.values) != 64 or any(v not in (1, 2, 3) for v in self.values):
            raise ValueError("values must contain 64 cell values from 1 to 3")
        self.pos = list(HOMES)
        self.owner = [0] * 64
        for seat, p in enumerate(HOMES, 1):
            self.owner[p] = seat
        self.upgraded = [False] * 64
        self.frozen = [0] * 4
        self.cooldown = [0] * 4
        self.progress = [0] * 4
        self.scores = [0] * 4
        self.token = start_token
        self.turn = 1
        self.errors = []
        self.frozen_stays_progress = frozen_stays_progress
        self._cells = None

    def legal(self, i):
        if self.frozen[i]:
            return ["STAY"]
        actions = [a for a, p in NEIGHBORS[self.pos[i]].items() if p not in self.pos]
        actions.append("STAY")
        if not self.cooldown[i]:
            actions.append("SHIELD")
        return actions

    def state(self, seat):
        if seat not in range(1, 5):
            raise ValueError("seat must be 1..4")
        if self._cells is None:
            occupants = {p: i + 1 for i, p in enumerate(self.pos)}
            self._cells = []
            for p in range(64):
                occupant = occupants.get(p, 0)
                self._cells.append(Cell(occupant, self.owner[p], self.upgraded[p],
                                        p in HOMES, self.values[p],
                                        bool(occupant and self.frozen[occupant - 1])))
        board = [self._cells[p:p+8] for p in range(0, 64, 8)]
        return Observation(board, seat, seat == self.token, self.legal(seat - 1))

    def step(self, actions):
        """Resolve four committed actions atomically. A blocked/illegal move is STAY."""
        if len(actions) != 4 or self.turn > 80:
            raise ValueError("expected four actions on an active turn")
        old_pos = tuple(self.pos)
        targets = {}
        shields = set()
        for i, a in enumerate(actions):
            if self.frozen[i]:
                continue
            if a == "SHIELD" and self.cooldown[i] == 0:
                shields.add(i)
            elif isinstance(a, str):
                dest = NEIGHBORS[old_pos[i]].get(a)
                if dest is not None and dest not in old_pos:
                    targets.setdefault(dest, []).append(i)
        for dest, contenders in targets.items():
            owner = self.owner[dest] - 1
            winner = owner if owner in contenders else min(
                contenders, key=lambda i: (i - (self.token - 1)) % 4)
            self.pos[winner] = dest
        catches = {i: [] for i in shields}
        for i, p in enumerate(self.pos):
            defender = self.owner[p] - 1
            if (defender in shields and i != defender and not self.frozen[i]
                    and i not in shields and p == old_pos[i]):
                catches[defender].append(i)
        newly_frozen = set()
        for defender, caught in catches.items():
            newly_frozen.update(caught if caught else [defender])
        for i, p in enumerate(self.pos):
            prior = self.owner[p]
            if (p != old_pos[i] or i in shields or i in newly_frozen
                    or (self.frozen[i] and not self.frozen_stays_progress)):
                self.progress[i] = 0
                continue
            if prior == i + 1:
                if not self.upgraded[p]:
                    self.progress[i] += 1
                    if self.progress[i] == 3:
                        self.upgraded[p] = True
                        self.progress[i] = 0
            elif p not in HOMES and prior - 1 not in shields:
                self.progress[i] += 1
                needed = 3 if self.upgraded[p] else 1
                if self.progress[i] >= needed:
                    if prior:
                        self.scores[i] += 8 * self.values[p] * (1 + self.upgraded[p])
                    self.owner[p] = i + 1
                    self.upgraded[p] = False
                    self.progress[i] = 0
            else:
                self.progress[i] = 0
        for p, owner in enumerate(self.owner):
            if owner:
                self.scores[owner - 1] += self.values[p] * (1 + self.upgraded[p])
        for i in range(4):
            self.frozen[i] = 2 if i in newly_frozen else max(0, self.frozen[i]-1)
            self.cooldown[i] = 4 if i in shields else max(0, self.cooldown[i]-1)
        self.turn += 1
        self.token = self.token % 4 + 1
        self._cells = None


def play(policies, seed=0, family="balanced", start_token=1, **options):
    """Run four single-game policy callables, logging all faults in game.errors."""
    if len(policies) != 4:
        raise ValueError("four policies are required")
    game = Game(seed, family, start_token, **options)
    while game.turn <= 80:
        actions = []
        for seat, policy in enumerate(policies, 1):
            state = game.state(seat)
            start = perf_counter()
            try:
                action = policy(state)
                if action not in state.legal_actions:
                    raise ValueError(f"illegal action {action!r}")
                if perf_counter() - start > (2 if game.turn == 1 else .2):
                    raise TimeoutError("exceeded the turn budget")
            except Exception as exc:
                game.errors.append((game.turn, seat, repr(exc)))
                action = "STAY"
            actions.append(action)
        game.step(actions)
    return game
