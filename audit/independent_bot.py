"""Two fixed, independently designed Zone Rush challengers.

The policy uses only the official starter's public state and Python's standard
library. No submission, referee, or other-policy module is imported. Parameters
were chosen from the rule economics, not fitted to results against a submission.

Factories: IndependentFarmer(seed), IndependentRaider(seed).
"""
from collections import deque
import random

SIDE = 8
SIZE = 64
STEP = {"NORTH": -8, "SOUTH": 8, "WEST": -1, "EAST": 1}
ADJ = []
for p in range(SIZE):
    r, c = divmod(p, SIDE)
    ADJ.append(tuple(q for q, valid in ((p - 8, r > 0), (p + 8, r < 7),
                                      (p - 1, c > 0), (p + 1, c < 7)) if valid))


def distance(a, b):
    ar, ac = divmod(a, SIDE)
    br, bc = divmod(b, SIDE)
    return abs(ar - br) + abs(ac - bc)


def flood(start, closed):
    dist = [99] * SIZE
    dist[start] = 0
    queue = deque([start])
    while queue:
        p = queue.popleft()
        for q in ADJ[p]:
            if q not in closed and dist[q] == 99:
                dist[q] = dist[p] + 1
                queue.append(q)
    return dist


class IndependentEconomist:
    """Two-job economic scheduling with a public-history risk estimate."""
    name = "independent_economist"
    raider = False

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
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
        # Official globals reset every game; factories create a fresh policy.
        self.turn += 1
        cells = [c for row in state.board for c in row]
        me = state.bot_id - 1
        positions = [None] * 4
        homes = [None] * 4
        for p, c in enumerate(cells):
            if c.occupant:
                positions[c.occupant - 1] = p
            if c.is_home and c.owner:
                homes[c.owner - 1] = p
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
        self.previous = ([(c.owner, c.is_upgraded, c.is_frozen) for c in cells],
                         positions[:])
        self.last_action = action
        return action if action in legal else "STAY"

    def _observe(self, cells, positions, me):
        if self.previous is None:
            return
        old, prevpos = self.previous
        self.cooldown = [max(0, n - 1) for n in self.cooldown]
        shielders = set()
        if self.last_action == "SHIELD":
            shielders.add(me)
        # A new freeze is public. The old landlord is one plausible shielder;
        # on own/neutral land, a self-backfire is the only normal explanation.
        for j, p in enumerate(positions):
            pp = prevpos[j]
            if p is None or pp is None:
                continue
            newfreeze = cells[p].is_frozen and not old[pp][2]
            if newfreeze:
                landlord = old[pp][0] - 1
                if landlord >= 0 and landlord != j:
                    shielders.add(landlord)
                else:
                    shielders.add(j)
        for j in shielders:
            self.cooldown[j] = 4
        for j, p in enumerate(positions):
            pp = prevpos[j]
            if p is None or pp is None:
                continue
            prevowner, prevupgraded, prevfrozen = old[pp]
            if prevowner and prevowner != j + 1 and not prevfrozen:
                landlord = prevowner - 1
                if p == pp:
                    self.commit[j] += 1
                    if landlord in shielders:
                        self.shield_yes[landlord] += 1
                    elif self.cooldown[landlord] == 0:
                        self.shield_no[landlord] += 1
                else:
                    self.leave[j] += 1
            reset = (p != pp or cells[p].is_frozen or prevfrozen or
                     j in shielders or cells[p].owner != prevowner or
                     cells[p].is_upgraded != prevupgraded)
            if reset:
                self.progress[j] = 0
            elif not (cells[p].owner == j + 1 and cells[p].is_upgraded):
                self.progress[j] += 1

    def _shield_probability(self, owner, cells, positions):
        j = owner - 1
        if self.cooldown[j] or cells[positions[j]].is_frozen:
            return 0.0
        return self.shield_yes[j] / (self.shield_yes[j] + self.shield_no[j])

    def _choose(self, cells, positions, homes, at, me, legal):
        remaining = max(1, 81 - self.turn)
        seat = me + 1
        closed = set(p for j, p in enumerate(positions) if j != me and p is not None)
        dist = flood(at, closed)
        home = homes[me]
        rivals = [p for j, p in enumerate(positions) if j != me and p is not None]
        jobs = []
        for p, c in enumerate(cells):
            if dist[p] >= 99 or p in closed or (c.is_home and c.owner != seat):
                continue
            if c.owner == seat:
                if c.is_upgraded:
                    continue
                need, bonus, denial = 3, 0, 0
            elif c.owner == 0:
                need, bonus, denial = 1, 0, 0
            else:
                level = 2 if c.is_upgraded else 1
                need = 3 if c.is_upgraded else 1
                bonus, denial = 8 * c.base_points * level, c.base_points * level
            if p == at:
                need = max(1, need - self.progress[me])
            risk = (self._shield_probability(c.owner, cells, positions)
                    if c.owner and c.owner != seat else 0.0)
            # A ready owner can repeatedly stop a three-stay upgraded raid;
            # normal level-1 raids need only one successful decision.
            extra = risk * (2 + need) * (1.5 if c.is_upgraded else 1.0)
            if c.owner and c.owner != seat and not self.raider:
                extra *= 1.7
            work = need + extra
            duration = dist[p] + work
            if duration > remaining:
                continue
            enemy_distance = min(distance(q, p) for q in rivals)
            home_distance = distance(home, p)
            other_home_distance = min(distance(h, p) for j, h in enumerate(homes) if j != me)
            safe = home_distance < other_home_distance
            retention = 1.0
            if not c.is_home and enemy_distance <= dist[p] + need + 2:
                retention = 0.88 if safe else 0.75
            job = (p, work, c.base_points * retention, bonus, denial, risk)
            gain = self._gain(job, duration, remaining)
            jobs.append((gain / max(1, duration), job))
        jobs.sort(key=lambda x: (-x[0], distance(home, x[1][0]), x[1][0]))
        jobs = jobs[:14]
        if not jobs:
            return "STAY"
        opportunity = max(1.0, jobs[0][0])
        if "SHIELD" in legal and self.cooldown[me] == 0:
            saving = 0.0
            expected_catches = 0.0
            for j, p in enumerate(positions):
                if j == me or p is None or cells[p].owner != seat or cells[p].is_frozen:
                    continue
                c = cells[p]
                commitment = self.commit[j] / (self.commit[j] + self.leave[j])
                if self.previous and self.previous[1][j] != p:
                    commitment = max(commitment, 0.65)
                need = 3 if c.is_upgraded else 1
                if not c.is_home and self.progress[j] >= need - 1:
                    saving += commitment * c.base_points * (2 if c.is_upgraded else 1) * remaining
                expected_catches += commitment
            catch_probability = min(1.0, expected_catches)
            # Shield spends one action; a missed catch also loses the next two.
            cost = opportunity * (1 + 2 * (1 - catch_probability) + self.progress[me])
            if saving > cost and expected_catches > 0:
                self.target = None
                return "SHIELD"

        # Two-job scheduling evaluates clusters, but commits only the first
        # action. Subsequent ownership is simulated only for same-cell upgrades.
        best, best_rate = None, -1.0
        for first_rate, first in jobs:
            p = first[0]
            duration = dist[p] + first[1]
            first_gain = self._gain(first, duration, remaining)
            rate = first_rate
            second_dist = flood(p, closed)
            followups = [job for _, job in jobs if job[0] != p]
            if cells[p].owner != seat:
                followups.append((p, 3, first[2], 0, 0, 0))
            for second in followups:
                # Leaving our present cell discards its partial work. A later
                # return cannot reuse the progress credited to a first job.
                lost_progress = self.progress[me] if second[0] == at and p != at else 0
                full_duration = duration + second_dist[second[0]] + second[1] + lost_progress
                if full_duration <= remaining:
                    total = first_gain + self._gain(second, full_duration, remaining)
                    rate = max(rate, total / full_duration)
            if p == self.target:
                rate *= 1.035
            if rate > best_rate:
                best, best_rate = first, rate
        self.target = best[0]
        if self.target == at:
            here = cells[at]
            # Occasionally step away from a likely ready shield instead of
            # entering a permanent three-stay raid/freeze loop.
            if (self.raider and here.owner not in (0, seat) and best[5] > 0.55
                    and remaining > 3 and self.rng.random() < best[5]):
                escapes = [q for q in ADJ[at] if q not in closed
                           and cells[q].owner != here.owner]
                if escapes:
                    self.target = None
                    return self._action(at, min(escapes, key=lambda q: distance(home, q)))
            return "STAY"
        path_dist = flood(self.target, closed)
        steps = [q for q in ADJ[at] if q not in closed and path_dist[q] < path_dist[at]]
        if not steps:
            return "STAY"
        # Avoid losing an immediate empty-cell contest. Owning it overrides
        # token order, just as in the rulebook.
        def step_key(q):
            danger = 0
            for j, pos in enumerate(positions):
                if j == me or pos is None or q not in ADJ[pos] or cells[pos].is_frozen:
                    continue
                rival_wins = cells[q].owner == j + 1
                if cells[q].owner != seat and self.token is not None:
                    rival_wins |= (j + 1 - self.token) % 4 < (seat - self.token) % 4
                danger += int(rival_wins)
            return danger, path_dist[q], distance(home, q), q
        return self._action(at, min(steps, key=step_key))

    def _gain(self, job, elapsed, remaining):
        _, _, income, bonus, denial, risk = job
        paid_turns = max(0.0, remaining - elapsed + 1)
        # Denial helps one of three pairwise comparisons, so it receives only
        # a fraction of the value of earning the same points ourselves.
        denial_weight = 0.30 if self.raider else 0.12
        return income * paid_turns + bonus * (1 - 0.25 * risk) + denial_weight * denial * paid_turns

    @staticmethod
    def _action(at, to):
        return next(action for action, delta in STEP.items() if at + delta == to)


class IndependentFarmer(IndependentEconomist):
    """Cluster efficient income; accepts raids only after a larger risk charge."""
    name = "independent_farmer"


class IndependentRaider(IndependentEconomist):
    """Prices denial, adapts to shield history, and sometimes baits ready shields."""
    name = "independent_raider"
    raider = True
