"""Two fixed, independently designed Zone Rush challengers.

The policy uses only the official starter's public state and Python's standard
library. No submission, referee, or other-policy module is imported. Parameters
were chosen from the rule economics, not fitted to results against a submission.

Factories: IndependentFarmer(seed), IndependentRaider(seed).
"""
from collections import deque as _m5_deque
import random as _m5_random
_m5_SIDE = 8
_m5_SIZE = 64
_m5_STEP = {'NORTH': -8, 'SOUTH': 8, 'WEST': -1, 'EAST': 1}
_m5_ADJ = []
for _m5_p in range(_m5_SIZE):
    _m5_r, _m5_c = divmod(_m5_p, _m5_SIDE)
    _m5_ADJ.append(tuple((q for q, valid in ((_m5_p - 8, _m5_r > 0), (_m5_p + 8, _m5_r < 7), (_m5_p - 1, _m5_c > 0), (_m5_p + 1, _m5_c < 7)) if valid)))

def _m5_distance(a, b):
    ar, ac = divmod(a, _m5_SIDE)
    br, bc = divmod(b, _m5_SIDE)
    return abs(ar - br) + abs(ac - bc)

def _m5_flood(start, closed):
    dist = [99] * _m5_SIZE
    dist[start] = 0
    queue = _m5_deque([start])
    while queue:
        _m5_p = queue.popleft()
        for q in _m5_ADJ[_m5_p]:
            if q not in closed and dist[q] == 99:
                dist[q] = dist[_m5_p] + 1
                queue.append(q)
    return dist

class _m5_IndependentEconomist:
    """Two-job economic scheduling with a public-history risk estimate."""
    name = 'independent_economist'
    raider = False

    def __init__(self, seed=0):
        self.rng = _m5_random.Random(seed)
        self.turn = 0
        self.previous = None
        self.last_action = None
        self.token = None
        self.progress = [0] * 4
        self.cooldown = [0] * 4
        self.shield_yes = [1.5] * 4
        self.shield_no = [2.5] * 4
        self.commit = [2.0] * 4
        self.leave = [2.0] * 4
        self.target = None

    def __call__(self, state):
        self.turn += 1
        cells = [_m5_c for row in state.board for _m5_c in row]
        me = state.bot_id - 1
        positions = [None] * 4
        homes = [None] * 4
        for _m5_p, _m5_c in enumerate(cells):
            if _m5_c.occupant:
                positions[_m5_c.occupant - 1] = _m5_p
            if _m5_c.is_home and _m5_c.owner:
                homes[_m5_c.owner - 1] = _m5_p
        self._observe(cells, positions, me)
        if state.is_priority_token:
            self.token = me + 1
        elif self.token is not None:
            self.token = self.token % 4 + 1
        at = positions[me]
        legal = state.legal_actions
        if at is None or len(legal) == 1:
            action = legal[0]
        else:
            action = self._choose(cells, positions, homes, at, me, legal)
        self.previous = ([(_m5_c.owner, _m5_c.is_upgraded, _m5_c.is_frozen) for _m5_c in cells], positions[:])
        self.last_action = action
        return action if action in legal else 'STAY'

    def _observe(self, cells, positions, me):
        if self.previous is None:
            return
        old, prevpos = self.previous
        self.cooldown = [max(0, n - 1) for n in self.cooldown]
        shielders = set()
        if self.last_action == 'SHIELD':
            shielders.add(me)
        for j, _m5_p in enumerate(positions):
            pp = prevpos[j]
            if _m5_p is None or pp is None:
                continue
            newfreeze = cells[_m5_p].is_frozen and (not old[pp][2])
            if newfreeze:
                landlord = old[pp][0] - 1
                if landlord >= 0 and landlord != j:
                    shielders.add(landlord)
                else:
                    shielders.add(j)
        for j in shielders:
            self.cooldown[j] = 4
        for j, _m5_p in enumerate(positions):
            pp = prevpos[j]
            if _m5_p is None or pp is None:
                continue
            prevowner, prevupgraded, prevfrozen = old[pp]
            if prevowner and prevowner != j + 1 and (not prevfrozen):
                landlord = prevowner - 1
                if _m5_p == pp:
                    self.commit[j] += 1
                    if landlord in shielders:
                        self.shield_yes[landlord] += 1
                    elif self.cooldown[landlord] == 0:
                        self.shield_no[landlord] += 1
                else:
                    self.leave[j] += 1
            reset = _m5_p != pp or cells[_m5_p].is_frozen or prevfrozen or (j in shielders) or (cells[_m5_p].owner != prevowner) or (cells[_m5_p].is_upgraded != prevupgraded)
            if reset:
                self.progress[j] = 0
            elif not (cells[_m5_p].owner == j + 1 and cells[_m5_p].is_upgraded):
                self.progress[j] += 1

    def _shield_probability(self, owner, cells, positions):
        j = owner - 1
        if self.cooldown[j] or cells[positions[j]].is_frozen:
            return 0.0
        return self.shield_yes[j] / (self.shield_yes[j] + self.shield_no[j])

    def _choose(self, cells, positions, homes, at, me, legal):
        remaining = max(1, 81 - self.turn)
        seat = me + 1
        closed = set((_m5_p for j, _m5_p in enumerate(positions) if j != me and _m5_p is not None))
        dist = _m5_flood(at, closed)
        home = homes[me]
        rivals = [_m5_p for j, _m5_p in enumerate(positions) if j != me and _m5_p is not None]
        jobs = []
        for _m5_p, _m5_c in enumerate(cells):
            if dist[_m5_p] >= 99 or _m5_p in closed or (_m5_c.is_home and _m5_c.owner != seat):
                continue
            if _m5_c.owner == seat:
                if _m5_c.is_upgraded:
                    continue
                need, bonus, denial = (3, 0, 0)
            elif _m5_c.owner == 0:
                need, bonus, denial = (1, 0, 0)
            else:
                level = 2 if _m5_c.is_upgraded else 1
                need = 3 if _m5_c.is_upgraded else 1
                bonus, denial = (8 * _m5_c.base_points * level, _m5_c.base_points * level)
            if _m5_p == at:
                need = max(1, need - self.progress[me])
            risk = self._shield_probability(_m5_c.owner, cells, positions) if _m5_c.owner and _m5_c.owner != seat else 0.0
            extra = risk * (2 + need) * (1.5 if _m5_c.is_upgraded else 1.0)
            if _m5_c.owner and _m5_c.owner != seat and (not self.raider):
                extra *= 1.7
            work = need + extra
            duration = dist[_m5_p] + work
            if duration > remaining:
                continue
            enemy_distance = min((_m5_distance(q, _m5_p) for q in rivals))
            home_distance = _m5_distance(home, _m5_p)
            other_home_distance = min((_m5_distance(h, _m5_p) for j, h in enumerate(homes) if j != me))
            safe = home_distance < other_home_distance
            retention = 1.0
            if not _m5_c.is_home and enemy_distance <= dist[_m5_p] + need + 2:
                retention = 0.88 if safe else 0.75
            job = (_m5_p, work, _m5_c.base_points * retention, bonus, denial, risk)
            gain = self._gain(job, duration, remaining)
            jobs.append((gain / max(1, duration), job))
        jobs.sort(key=lambda x: (-x[0], _m5_distance(home, x[1][0]), x[1][0]))
        jobs = jobs[:14]
        if not jobs:
            return 'STAY'
        opportunity = max(1.0, jobs[0][0])
        if 'SHIELD' in legal and self.cooldown[me] == 0:
            saving = 0.0
            expected_catches = 0.0
            for j, _m5_p in enumerate(positions):
                if j == me or _m5_p is None or cells[_m5_p].owner != seat or cells[_m5_p].is_frozen:
                    continue
                _m5_c = cells[_m5_p]
                commitment = self.commit[j] / (self.commit[j] + self.leave[j])
                if self.previous and self.previous[1][j] != _m5_p:
                    commitment = max(commitment, 0.65)
                need = 3 if _m5_c.is_upgraded else 1
                if not _m5_c.is_home and self.progress[j] >= need - 1:
                    saving += commitment * _m5_c.base_points * (2 if _m5_c.is_upgraded else 1) * remaining
                expected_catches += commitment
            catch_probability = min(1.0, expected_catches)
            cost = opportunity * (1 + 2 * (1 - catch_probability) + self.progress[me])
            if saving > cost and expected_catches > 0:
                self.target = None
                return 'SHIELD'
        best, best_rate = (None, -1.0)
        for first_rate, first in jobs:
            _m5_p = first[0]
            duration = dist[_m5_p] + first[1]
            first_gain = self._gain(first, duration, remaining)
            rate = first_rate
            second_dist = _m5_flood(_m5_p, closed)
            followups = [job for _, job in jobs if job[0] != _m5_p]
            if cells[_m5_p].owner != seat:
                followups.append((_m5_p, 3, first[2], 0, 0, 0))
            for second in followups:
                lost_progress = self.progress[me] if second[0] == at and _m5_p != at else 0
                full_duration = duration + second_dist[second[0]] + second[1] + lost_progress
                if full_duration <= remaining:
                    total = first_gain + self._gain(second, full_duration, remaining)
                    rate = max(rate, total / full_duration)
            if _m5_p == self.target:
                rate *= 1.035
            if rate > best_rate:
                best, best_rate = (first, rate)
        self.target = best[0]
        if self.target == at:
            here = cells[at]
            if self.raider and here.owner not in (0, seat) and (best[5] > 0.55) and (remaining > 3) and (self.rng.random() < best[5]):
                escapes = [q for q in _m5_ADJ[at] if q not in closed and cells[q].owner != here.owner]
                if escapes:
                    self.target = None
                    return self._action(at, min(escapes, key=lambda q: _m5_distance(home, q)))
            return 'STAY'
        path_dist = _m5_flood(self.target, closed)
        steps = [q for q in _m5_ADJ[at] if q not in closed and path_dist[q] < path_dist[at]]
        if not steps:
            return 'STAY'

        def step_key(q):
            danger = 0
            for j, pos in enumerate(positions):
                if j == me or pos is None or q not in _m5_ADJ[pos] or cells[pos].is_frozen:
                    continue
                rival_wins = cells[q].owner == j + 1
                if cells[q].owner != seat and self.token is not None:
                    rival_wins |= (j + 1 - self.token) % 4 < (seat - self.token) % 4
                danger += int(rival_wins)
            return (danger, path_dist[q], _m5_distance(home, q), q)
        return self._action(at, min(steps, key=step_key))

    def _gain(self, job, elapsed, remaining):
        _, _, income, bonus, denial, risk = job
        paid_turns = max(0.0, remaining - elapsed + 1)
        denial_weight = 0.3 if self.raider else 0.12
        return income * paid_turns + bonus * (1 - 0.25 * risk) + denial_weight * denial * paid_turns

    @staticmethod
    def _action(at, to):
        return next((action for action, delta in _m5_STEP.items() if at + delta == to))

class _m5_IndependentFarmer(_m5_IndependentEconomist):
    """Cluster efficient income; accepts raids only after a larger risk charge."""
    name = 'independent_farmer'

class _m5_IndependentRaider(_m5_IndependentEconomist):
    """Prices denial, adapts to shield history, and sometimes baits ready shields."""
    name = 'independent_raider'
    raider = True
_PLAYERS = {}
def act(state):
    seat = state.bot_id
    if seat not in _PLAYERS:
        _PLAYERS[seat] = _m5_IndependentRaider(seed=seat*7919, **{})
    return _PLAYERS[seat](state)
