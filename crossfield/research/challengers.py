"""Independent Zone Rush strategies. Each callable observes only the starter interface."""
from collections import deque
from heapq import nlargest


def neighbors(i):
    r, c = divmod(i, 8)
    return tuple((a, j) for a, j, valid in (
        ("NORTH", i - 8, r > 0), ("EAST", i + 1, c < 7),
        ("SOUTH", i + 8, r < 7), ("WEST", i - 1, c > 0)) if valid)


ADJ = tuple(neighbors(i) for i in range(64))
DIST = tuple(tuple(abs(i // 8 - j // 8) + abs(i % 8 - j % 8)
                   for j in range(64)) for i in range(64))


def starting_action(state):
    return "STAY"


def greedy(state):
    """Control: finish captures, otherwise target nearest most valuable non-owned cell."""
    legal = state.legal_actions
    cells = [c for row in state.board for c in row]
    me = state.bot_id
    origin = next(i for i, c in enumerate(cells) if c.occupant == me)
    here = cells[origin]
    if here.owner != me and not here.is_home:
        return "STAY"
    candidates = [(c.base_points / (DIST[origin][i] + 1), i)
                  for i, c in enumerate(cells) if not c.is_home and not c.occupant and c.owner != me]
    if not candidates:
        return "STAY"
    target = max(candidates)[1]
    steps = [(DIST[j][target], a) for a, j in ADJ[origin] if a in legal and not cells[j].occupant]
    return min(steps)[1] if steps else "STAY"


# Weights for capture, upgrades, rival income denial, raid cash, shield use,
# and an estimated extra action cost for entering defended turf.
PARAMETERS = {
    "expansion": (1.25, 0.35, .05, .45, 0., 0.),
    "fortress": (.92, 1.52, .14, .65, .78, 2.5),
    "raider": (1., .45, 1.08, 2.4, .8, .30),
    "sentinel": (1., 1.04, .40, 1.0, .99, .7),
    "cautious": (1., .85, .30, .95, .65, 3.7),
    "sweep": (1.06, .87, .43, 1.05, .78, .85),
    "adaptive": (1., 1., .54, 1.3, .8, 1.4),
    "lure": (.98, 1.5, .28, 1.15, .75, 1.7),
}


class TerritoryPolicy:
    def __init__(self, name):
        self.name = name
        self.weights = PARAMETERS[name]
        self.turn = 0
        self.prev = None
        self.last_action = None
        self.progress = 0
        self.shield_seen = [0] * 5
        self.cool_until = [0] * 5
        self.score = [0] * 5
        self.previous_target = -1

    def __call__(self, state):
        cells = [c for row in state.board for c in row]
        me = state.bot_id
        pos = [0] * 5
        for i, c in enumerate(cells):
            if c.occupant:
                pos[c.occupant] = i
        origin = pos[me]
        self.turn += 1
        remaining = max(1, 81 - self.turn)
        rivals = [s for s in range(1, 5) if s != me]
        if self.prev:
            old_pos, old_owned, old_levels, old_frozen = self.prev
            prev_here = old_pos[me]
            if (prev_here == origin and not cells[origin].is_frozen and not old_frozen[me]
                    and self.last_action != "SHIELD" and old_owned[origin] == cells[origin].owner
                    and old_levels[origin] == cells[origin].is_upgraded):
                self.progress = min(2, self.progress + 1)
            else:
                self.progress = 0
            seen = set()
            for seat in range(1, 5):
                i = pos[seat]
                land = old_owned[i]
                if (old_pos[seat] == i and cells[i].is_frozen and not old_frozen[seat]
                        and land and land != seat and pos[land] == old_pos[land]):
                    seen.add(land)
            for land in seen:
                self.shield_seen[land] += 1
                self.cool_until[land] = self.turn + 3
            for i, c in enumerate(cells):
                if old_owned[i] and old_owned[i] != c.owner:
                    self.score[c.owner] += 8 * c.base_points * (1 + old_levels[i])
                self.score[c.owner] += c.base_points * (1 + c.is_upgraded)
        self.prev = (pos, [c.owner for c in cells], [c.is_upgraded for c in cells],
                     [False] + [cells[pos[s]].is_frozen for s in range(1, 5)])
        self.last_action = self.choose(state, cells, pos, rivals, remaining)
        return self.last_action

    def choose(self, state, cells, pos, rivals, remaining):
        legal = state.legal_actions
        if len(legal) == 1:
            return legal[0]
        me = state.bot_id
        origin = pos[me]
        cap, upgrade, deny, cash, shield, caution = self.weights
        model = self.name == "adaptive"
        chain = self.name in ("adaptive", "sweep")
        intruders = [s for s in rivals if cells[pos[s]].owner == me and not cells[pos[s]].is_frozen]
        if "SHIELD" in legal and shield and any(
                not cells[pos[s]].is_home and (shield >= .9 or
                cells[pos[s]].base_points >= 2 or cells[pos[s]].is_upgraded or len(intruders) >= 2)
                for s in intruders):
            return "SHIELD"

        # Exact routes around initially occupied squares. A blocked first step
        # is never chosen, even when the host includes it among legal actions.
        distances = [80] * 64
        first_action = [None] * 64
        distances[origin] = 0
        first_action[origin] = "STAY"
        queue = deque([origin])
        while queue:
            i = queue.popleft()
            for action, j in ADJ[i]:
                if cells[j].occupant or distances[j] < 80 or (i == origin and action not in legal):
                    continue
                distances[j] = distances[i] + 1
                first_action[j] = action if i == origin else first_action[i]
                queue.append(j)

        nearest = [min(DIST[pos[s]][i] for s in rivals) for i in range(64)]
        actions = []
        for i, c in enumerate(cells):
            owner = c.owner
            mine = owner == me
            if distances[i] == 80 or (mine and c.is_upgraded) or (c.is_home and not mine):
                continue
            raid = bool(owner and not mine)
            stays = 3 if mine or (raid and c.is_upgraded) else 1
            if i == origin:
                stays = max(1, stays - self.progress)
            time = distances[i] + stays
            if time > remaining:
                continue
            # Discount income likely to be lost to opponents, particularly
            # level-one captures. Guaranteed home income is never discounted.
            horizon = remaining - time + 1
            if not c.is_home:
                safe_time = 13 + 3.2 * nearest[i] + (8 if mine else 0)
                horizon = horizon / (1 + horizon / safe_time)
            gain = c.base_points * horizon * (upgrade if mine else cap)
            risk = 0.
            if raid:
                level = 1 + int(c.is_upgraded)
                bonus = cash * 8
                denial = deny
                if model:
                    gap = abs(self.score[me] - self.score[owner])
                    denial *= .55 + .90 / (1 + gap / (30 + 6 * remaining))
                gain += c.base_points * level * (bonus + denial * horizon)
                if self.cool_until[owner] < self.turn + time - 1:
                    risk = caution * (1.0 + .4 * c.is_upgraded)
                    if model:
                        risk *= (1 + min(3, self.shield_seen[owner]) * .75)
                    # A patient defender may also recapture adjacent land.
                    if nearest[i] < 2 and time > 1:
                        risk += .45
            if distances[i] >= nearest[i] and distances[i] > 0:
                risk += .35 if nearest[i] > 1 or state.is_priority_token else .65
            # Rate with slight diminishing returns to travel: tying ourselves
            # to a single immediate stay can strand the bot in a dead-end.
            rating = gain / (time + risk + .20)
            if i == self.previous_target:
                rating *= 1.024
            actions.append((rating, i, gain, stays, time, risk))
        if not actions:
            return "STAY"
        if chain and len(actions) > 1:
            leaders = nlargest(7, actions)
            def subsequent(action):
                current_rate, i, gain, _, time, _ = action
                best = 0.
                for _, j, value, stays, _, risk in actions:
                    if j == i:
                        continue
                    delay = DIST[i][j] + stays
                    if delay + time <= remaining:
                        rank = value / (delay + risk + .20)
                        best = max(best, rank)
                return current_rate + .37 * best
            _, target, _, _, _, _ = max(leaders, key=subsequent)
        else:
            _, target, _, _, _, _ = max(actions)
        self.previous_target = target
        return first_action[target]


def build_policies():
    return {"skeleton": starting_action, "greedy": greedy,
            **{name: (LurePolicy(name) if name == "lure" else TerritoryPolicy(name))
               for name in PARAMETERS}}


class LurePolicy(TerritoryPolicy):
    """Fortify first. Track defenses, bait available shields and raid on cooldown."""
    def __init__(self, name):
        super().__init__(name)
        self.probes = [0] * 5
        self.stops = [0] * 5
        self.old_contact = []
        self.last_bait = -10

    def choose(self, state, cells, pos, rivals, remaining):
        me = state.bot_id
        here = pos[me]
        for defender, victim, old_defender, old_victim in self.old_contact:
            self.probes[defender] += 1
            if pos[defender] != old_defender:
                continue
            caught = (pos[victim] == old_victim and cells[pos[victim]].is_frozen)
            backfire = (cells[pos[defender]].is_frozen and not cells[pos[victim]].is_frozen)
            if caught or backfire:
                self.stops[defender] += 1
                self.cool_until[defender] = self.turn + 3
        self.old_contact = []
        for victim in range(1, 5):
            spot = pos[victim]
            defender = cells[spot].owner
            if (defender and defender != victim and not cells[spot].is_frozen
                    and not cells[pos[defender]].is_frozen and self.cool_until[defender] < self.turn):
                self.old_contact.append((defender, victim, pos[defender], spot))

        phase = (80 - remaining) / 80
        self.weights = (.98, 1.56 - .32 * phase, .22 + .45 * phase,
                        .68 + .88 * phase, .75, 1.55)
        ordinary = super().choose(state, cells, pos, rivals, remaining)
        defender = cells[here].owner
        if (defender in (0, me) or cells[here].is_frozen or cells[pos[defender]].is_frozen
                or self.cool_until[defender] >= self.turn or remaining <= 2
                or self.turn - self.last_bait < 4 or ordinary != "STAY"):
            return ordinary
        p_shield = (1.6 + self.stops[defender]) / (2.7 + self.probes[defender])
        if p_shield < .47:
            return ordinary
        exits = []
        for a, i in ADJ[here]:
            c = cells[i]
            if a not in state.legal_actions or c.occupant or (c.is_home and c.owner != me):
                continue
            if c.owner == defender:
                # Reposition on their land exactly as their shield potentially fires.
                value = c.base_points * (1.35 if not c.is_upgraded else .80)
            elif not c.owner:
                value = .7 * c.base_points
            else:
                value = .14 * c.base_points
            exits.append((value, a))
        if exits and max(exits)[0] >= .55 * cells[here].base_points:
            self.last_bait = self.turn
            return max(exits)[1]
        return ordinary


POLICIES = build_policies()


def act(state):
    return POLICIES["adaptive"](state)
