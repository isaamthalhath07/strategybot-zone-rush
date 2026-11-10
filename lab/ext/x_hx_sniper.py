# Flattened from zenith/lab/humanlike/hx_sniper.py, _hxcore.py and apex/src/evosim.py at a5b462f.
"""Exact simulator of the research/evolution economic planner (bot_evolved.py).

A faithful transcription of that file's act(), with three changes that do not
alter a single decision (test_evosim.py checks move-for-move identity):
  * memory lives on the instance instead of a module dict keyed by seat;
  * the decision is split from its side effects (begin / decide / commit), so it
    can be queried under several token hypotheses without double-advancing;
  * it reads flat arrays instead of cell objects, and its inner loops are
    rewritten for speed, because rollouts call it thousands of times a turn.
"""
from collections import deque

EVO_DEFAULT = {
    'upgrade_open': 2.25, 'upgrade_late': 2.25, 'raid_open': 0.99, 'raid_late': 0.99,
    'risk_open': 4.0, 'risk_late': 4.0, 'income_lifetime': 18.0, 'safety_slope': 6.0,
    'fortify_premium': 1.16, 'denial_base': 0.27, 'denial_close': 0.43,
    'cash_weight': 1.0, 'contest_cost': 1.0, 'depth': 2, 'breadth': 9,
    'route_weight': 0.5, 'route_delay': 0.11, 'inertia': 0.0, 'shield_weight': 1.0,
    'backfire_cost': 2.0, 'shield_prior': 0.3333333333333333, 'stay_prior': 0.76,
    'feint_weight': 1.0,
}
EVO_GENOMES = (
    # research/evolution bot.py == outputs/bot_evolved.py (recommended)
    {'backfire_cost': 1.13552, 'breadth': 7, 'cash_weight': 1.25275,
     'contest_cost': 0.42039, 'denial_base': 0.66671, 'denial_close': 0.20084,
     'depth': 2, 'feint_weight': 1.25119, 'fortify_premium': 1.11474,
     'income_lifetime': 40.67114, 'inertia': 0.0496, 'raid_late': 1.64117,
     'raid_open': 0.95839, 'risk_late': 8.0, 'risk_open': 1.97775, 'route_delay': 0.02,
     'route_weight': 0.61979, 'safety_slope': 3.52153, 'shield_prior': 0.33333,
     'shield_weight': 1.30296, 'stay_prior': 0.76, 'upgrade_late': 3.3705,
     'upgrade_open': 1.46008},
)

EVO_GENOMES = EVO_GENOMES + (
    # research/evolution outputs/bot_transfer_candidate.py (second-run finalist)
    dict(EVO_GENOMES[0], denial_base=0.79149, depth=3, raid_late=1.65061,
         safety_slope=0.0, stay_prior=0.69484, upgrade_late=4.5),
    # two research-population relatives (economic_11c655468adf, economic_f04298fe614d)
    {"backfire_cost": 1.4039, "breadth": 9, "cash_weight": 1.13051, "contest_cost": 0.64912, "denial_base": 0.66671, "denial_close": 0.27195, "depth": 2, "feint_weight": 1.51906, "fortify_premium": 1.11474, "income_lifetime": 42.72245, "inertia": 0.02808, "raid_late": 1.64704, "raid_open": 0.92346, "risk_late": 7.21709, "risk_open": 1.56903, "route_delay": 0.06584, "route_weight": 0.61979, "safety_slope": 4.94921, "shield_prior": 0.33333, "shield_weight": 1.30296, "stay_prior": 0.79415, "upgrade_late": 3.83447, "upgrade_open": 1.46008},
    {"backfire_cost": 1.13552, "breadth": 7, "cash_weight": 1.25275, "contest_cost": 0.66277, "denial_base": 0.41881, "denial_close": 0.31159, "depth": 2, "feint_weight": 1.25119, "fortify_premium": 1.11474, "income_lifetime": 42.72245, "inertia": 0.0496, "raid_late": 1.9068, "raid_open": 0.99, "risk_late": 8.0, "risk_open": 1.56903, "route_delay": 0.02, "route_weight": 0.61979, "safety_slope": 4.48431, "shield_prior": 0.33333, "shield_weight": 1.30296, "stay_prior": 0.76, "upgrade_late": 3.3705, "upgrade_open": 1.46008},
)

_EADJ = []
_EDIST = []
for _i in range(64):
    _r, _c = divmod(_i, 8)
    _EADJ.append(tuple((name, r * 8 + c) for name, r, c in (
        ("NORTH", _r - 1, _c), ("EAST", _r, _c + 1),
        ("SOUTH", _r + 1, _c), ("WEST", _r, _c - 1)) if 0 <= r < 8 and 0 <= c < 8))
    _EDIST.append(tuple(abs(_r - j // 8) + abs(_c - j % 8) for j in range(64)))
_ENB = [tuple(t for _n, t in _EADJ[_i]) for _i in range(64)]


def _e_paths(origin, occupied, legal, owner, me, priority, rivals):
    travel = [90] * 64
    first = [None] * 64
    travel[origin] = 0
    choices = []
    for action, target in _EADJ[origin]:
        if action in legal and target not in occupied:
            risk = 0
            for p in rivals:
                if _EDIST[p][target] == 1:
                    risk += 1
            if owner[target] == me:
                risk = 0
            elif priority and owner[target] == 0:
                risk = 0
            choices.append((risk, action, target))
    queue = []
    for _, action, target in sorted(choices):
        travel[target], first[target] = 1, action
        queue.append(target)
    k = 0
    while k < len(queue):
        here = queue[k]
        k += 1
        th = travel[here] + 1
        fh = first[here]
        for there in _ENB[here]:
            if travel[there] == 90 and there not in occupied:
                travel[there] = th
                first[there] = fh
                queue.append(there)
    return travel, first


class EvoSim(object):
    __slots__ = ("cfg", "mem", "k", "pre")

    def __init__(self, genome):
        c = dict(EVO_DEFAULT)
        c.update(genome)
        self.cfg = c
        self.mem = None
        self.pre = None
        # constants of the genome, hoisted out of the decision
        self.k = (min(3, max(1, round(c["depth"]))), min(12, max(1, round(c["breadth"]))),
                  c.get("home_retention", 100), c.get("vexp", 1.0))

    def clone(self):
        n = EvoSim.__new__(EvoSim)
        n.cfg = self.cfg
        n.k = self.k
        n.pre = None
        m = {}
        for key, v in self.mem.items():
            if type(v) is list:
                if v and type(v[0]) is list:
                    m[key] = [x[:] for x in v]
                else:
                    m[key] = v[:]
            else:
                m[key] = v
        n.mem = m
        return n

    def observe(self, me, base, ishome, positions, owner, level, frozen, can_shield):
        config = self.cfg
        old = self.mem
        pristine = all(pos >= 0 and ishome[pos] and owner[pos] == seat
                       for seat, pos in enumerate(positions) if seat)
        pristine = pristine and sum(bool(v) for v in owner) == 4 and not any(level)
        if old is None or (pristine and (old["turn"] >= 80 or any(old["level"])
                                         or sum(bool(v) for v in old["owner"]) > 4)):
            occupied = sum(bool(v) for v in owner) - 4
            turn = 1 if pristine else min(67, max(2, 2 + occupied + sum(level)))
            old = {"turn": turn, "known_start": pristine, "scores": [0] * 5, "progress": 0,
                   "positions": positions, "owner": owner, "level": level, "frozen": frozen,
                   "last": None,
                   "stay_trials": [[2., 2.] for _ in range(5)],
                   "stay_hits": [[2 * config["stay_prior"], 1.16] for _ in range(5)],
                   "can_shield": False,
                   "enemy_progress": [0] * 5, "defense_trials": [3.0] * 5,
                   "defense_hits": [1.20] * 5, "last_bait": -10,
                   "cooldown": [0] * 5, "stops": [3 * config["shield_prior"]] * 5,
                   "attempts": [3.0] * 5, "prior_target": None}
        else:
            old["turn"] = min(old["turn"] + 1, 80)
            cooldown = [max(0, c - 1) for c in old["cooldown"]]
            prior_pos, prior_owner = old["positions"], old["owner"]
            old_frozen = old["frozen"]
            own_shield = (old["can_shield"] and not can_shield and
                          (not frozen[me] or old["last"] == "SHIELD"))
            just_shielded = set()
            for seat in (1, 2, 3, 4):
                spot = positions[seat]
                if spot < 0 or prior_pos[seat] != spot:
                    continue
                defender = prior_owner[spot]
                if defender and defender != seat and not old_frozen[seat]:
                    if frozen[seat] and not frozen[defender] and prior_pos[defender] == positions[defender]:
                        just_shielded.add(defender)
                        old["stops"][defender] += 1
                        old["attempts"][defender] += 1
                    elif owner[spot] == seat:
                        old["attempts"][defender] += 1
                if frozen[seat] and not old_frozen[seat] and defender in (0, seat):
                    just_shielded.add(seat)
            opportunities = set()
            for seat in (1, 2, 3, 4):
                previous = prior_pos[seat]
                if previous < 0 or old_frozen[seat]:
                    continue
                land = prior_owner[previous]
                if land in (0, seat) or ishome[previous]:
                    continue
                if not old_frozen[land] and not old["cooldown"][land]:
                    opportunities.add(land)
                if land == me and old["can_shield"]:
                    tier = old["level"][previous]
                    stayed = ((previous == positions[seat]) and
                              seat not in just_shielded and
                              (not own_shield or (frozen[seat] and not frozen[me])))
                    weight = 1.5 if own_shield else 1.0
                    old["stay_hits"][seat][tier] = 0.94 * old["stay_hits"][seat][tier] + weight * stayed
                    old["stay_trials"][seat][tier] = 0.94 * old["stay_trials"][seat][tier] + weight
            for defender in opportunities:
                old["defense_hits"][defender] = .93 * old["defense_hits"][defender] + (defender in just_shielded)
                old["defense_trials"][defender] = .93 * old["defense_trials"][defender] + 1
            ep = old["enemy_progress"]
            old_level = old["level"]
            for seat in (1, 2, 3, 4):
                p = positions[seat]
                continuing = (p >= 0 and p == prior_pos[seat] and seat not in just_shielded
                              and not frozen[seat] and not old_frozen[seat] and
                              owner[p] == prior_owner[p] and level[p] == old_level[p])
                ep[seat] = min(2, ep[seat] + 1) if continuing else 0
            for defender in just_shielded:
                cooldown[defender] = 4
            old["cooldown"] = cooldown
            spot = positions[me]
            continued = (spot == prior_pos[me] and not own_shield
                         and not old_frozen[me] and not frozen[me]
                         and prior_owner[spot] == owner[spot] and old_level[spot] == level[spot])
            old["progress"] = min(2, old["progress"] + 1) if continued else 0
            scores = old["scores"]
            for i in range(64):
                seat = owner[i]
                if seat:
                    value = base[i]
                    scores[seat] += value * (1 + level[i])
                    po = prior_owner[i]
                    if po and po != seat:
                        scores[seat] += 8 * value * (1 + old_level[i])
        old["positions"] = positions
        old["owner"] = owner
        old["level"] = level
        old["frozen"] = frozen
        self.mem = old
        return old

    def begin(self, me, legal, base, ishome, owner, level, pos, frozen):
        """The observe half of act(): returns False when the decision is forced."""
        can_shield = "SHIELD" in legal
        memory = self.observe(me, base, ishome, pos, owner, level, frozen, can_shield)
        memory["can_shield"] = can_shield
        if len(legal) == 1:
            memory["last"] = legal[0]
            return False
        return True

    def decide(self, me, legal, priority, base, ishome, owner, level, pos, frozen, income):
        """The decision half of act(): pure. Returns (action, chosen_cell, baited)."""
        memory = self.mem
        config = self.cfg
        at = pos[me]
        turn = memory["turn"]
        left = 81 - turn
        phase = (turn - 1) / 79
        upgrade = config["upgrade_open"] + phase * (config["upgrade_late"] - config["upgrade_open"])
        raid = config["raid_open"] + phase * (config["raid_late"] - config["raid_open"])
        risk_weight = config["risk_open"] + phase * (config["risk_late"] - config["risk_open"])
        depth, breadth, home_ret, vexp = self.k
        route_weight = config["route_weight"] if depth > 1 else 0.
        feint_weight = config["feint_weight"]
        enemies = [i for i in (1, 2, 3, 4) if i != me and pos[i] >= 0]
        occupied = {pos[i] for i in enemies}
        travel, first = _e_paths(at, occupied, legal, owner, me, priority, occupied)
        if occupied:
            pressure = list(map(min, zip(*[_EDIST[p] for p in occupied])))
        else:
            pressure = [12] * 64
        scores = memory["scores"]
        lm = left if left < 18 else 18
        pme = scores[me] + lm * income[me]
        denial = [0.0] * 5
        dbase, dclose = config["denial_base"], config["denial_close"]
        for seat in enemies:
            gap = abs(pme - (scores[seat] + lm * income[seat]))
            denial[seat] = dbase + dclose / (1 + gap / (65 + left * 3))
        stops, attempts = memory["stops"], memory["attempts"]
        exposure = [0.0] * 5
        for i in range(5):
            x = 0.08 + 1.30 * stops[i] / attempts[i]
            exposure[i] = x if x < 0.87 else 0.87
        progress = memory["progress"]
        cooldown = memory["cooldown"]
        prior_target = memory.get("prior_target")
        lifetime = config["income_lifetime"]
        slope = config["safety_slope"]
        fortify = config["fortify_premium"]
        cash8 = 8 * config["cash_weight"]
        contest = config["contest_cost"]
        inertia = config["inertia"]
        tasks = []
        for i in range(64):
            travel_time = travel[i]
            if travel_time >= left:
                continue
            who = owner[i]
            up = level[i]
            hm = ishome[i]
            if (up and who == me) or (hm and who != me):
                continue
            work = 3 if (who == me or up) else 1
            if i == at:
                work = max(1, work - progress)
            cost = travel_time + work
            if cost > left:
                continue
            v = base[i]
            if vexp != 1.0:
                v = v ** vexp
            nearest = pressure[i]
            retention = lifetime + (nearest if nearest < 5 else 5) * slope
            if hm:
                retention = home_ret
            life = min(left - cost + 1, retention)
            if who == me:
                reward = v * life * upgrade
                if not hm:
                    reward *= fortify
            elif who == 0:
                reward = v * life
            else:
                reward = raid * v * (life * (1 + denial[who] * (1 + up)) + cash8 * (1 + up))
            risk = 0
            if who != me and who != 0:
                if cooldown[who] < cost and (not frozen[who] or cost > 1):
                    risk = exposure[who] * risk_weight
                    if up:
                        risk *= 1.4
                    reward /= 1.0 + risk * (0.65 if up else 0.18)
            effort = work + risk * (3.5 if up else 2.4)
            if i != at and nearest <= travel_time and who != me:
                effort += contest * (0.40 if nearest <= 1 else 0.18)
            rate = reward / (travel_time + effort)
            if inertia and i == prior_target:
                rate *= 1 + inertia
            tasks.append((rate, i, effort, reward, cost, work))
        tasks.sort(reverse=True)
        best_value, best_action = -1.0, "STAY" if "STAY" in legal else legal[0]
        chosen_cell = None
        if route_weight:
            tj = [t[1] for t in tasks]
            te = [t[2] for t in tasks]
            trw = [t[3] for t in tasks]
            tw = [t[5] for t in tasks]
            nt = len(tasks)
            if depth == 2:
                # Only the best second-job *value* matters at depth 2, so scan
                # in order of an upper bound (distinct cells are >= 1 apart)
                # and stop once no remaining job can beat the best so far.
                order = []
                for q in range(nt):
                    extra = progress if tj[q] == at else 0
                    order.append((trw[q] / (1 + te[q] + extra), q))
                order.sort(reverse=True)
        delay = config["route_delay"]
        for rate, i, effort, reward, cost, work in tasks[:breadth]:
            next_rate = 0.0
            if cost < left - 1 and route_weight and depth == 2:
                dists = _EDIST[i]
                budget = left - cost
                for ub, q in order:
                    if ub <= next_rate:
                        break
                    j = tj[q]
                    if i == j:
                        continue
                    between = dists[j]
                    extra = progress if j == at else 0
                    if between + tw[q] + extra <= budget:
                        candidate = trw[q] / (between + te[q] + extra)
                        if candidate > next_rate:
                            next_rate = candidate
                if owner[i] != me and cost + 3 <= left:
                    pn = pressure[i]
                    postcapture = min(left - cost - 2, lifetime + (pn if pn < 5 else 5) * slope)
                    candidate = base[i] * postcapture * upgrade / 3
                    if candidate > next_rate:
                        next_rate = candidate
            elif cost < left - 1 and route_weight:
                dists = _EDIST[i]
                second = None
                second_cost = 0
                budget = left - cost
                for q in range(nt):
                    j = tj[q]
                    if i == j:
                        continue
                    between = dists[j]
                    extra = progress if j == at else 0
                    if between + tw[q] + extra <= budget:
                        candidate = trw[q] / (between + te[q] + extra)
                        if candidate > next_rate:
                            next_rate, second, second_cost = candidate, j, between + tw[q] + extra
                if owner[i] != me and cost + 3 <= left:
                    pn = pressure[i]
                    postcapture = min(left - cost - 2, lifetime + (pn if pn < 5 else 5) * slope)
                    candidate = base[i] * postcapture * upgrade / 3
                    if candidate > next_rate:
                        next_rate, second, second_cost = candidate, i, 3
                if depth == 3 and second is not None and cost + second_cost < left - 1:
                    third_rate = 0.
                    from_second = _EDIST[second]
                    for q in range(nt):
                        k = tj[q]
                        if k == i or k == second:
                            continue
                        between = from_second[k]
                        extra = progress if k == at else 0
                        if cost + second_cost + between + tw[q] + extra <= left:
                            c3 = trw[q] / (between + te[q] + extra)
                            if c3 > third_rate:
                                third_rate = c3
                    next_rate += route_weight * third_rate / (1 + delay * (second_cost - 1))
            value = rate + route_weight * next_rate / (1 + delay * (cost - 1))
            if value > best_value:
                best_value, best_action = value, ("STAY" if i == at else first[i])
                chosen_cell = i
        baited = False
        defender = owner[at]
        if (feint_weight and best_action == "STAY" and defender != 0 and defender != me
                and not ishome[at] and not frozen[defender] and
                cooldown[defender] == 0 and turn - memory["last_bait"] >= 5
                and left > 2 and progress == 0):
            response = memory["defense_hits"][defender] / memory["defense_trials"][defender]
            exits = []
            for _, i, effort, reward, _, _ in tasks:
                if travel[i] == 1:
                    bonus = 1.25 if owner[i] == defender else 0.95
                    exits.append((reward * bonus / (effort + 1), first[i]))
            if exits and response * feint_weight > .43:
                alternative, action = max(exits)
                if alternative * (1 + 1.3 * response * feint_weight) > tasks[0][0]:
                    best_action = action
                    baited = True
        self.pre = best_action
        if "SHIELD" in legal:
            threat = 0.0
            miss = 1.0
            sh, st, epg = memory["stay_hits"], memory["stay_trials"], memory["enemy_progress"]
            for s in enemies:
                i = pos[s]
                if owner[i] != me or frozen[s] or ishome[i]:
                    continue
                tier = level[i]
                chance = sh[s][tier] / st[s][tier]
                if tier:
                    e = epg[s]
                    chance *= (.21, .53, 1.18)[e]
                    if e + left < 3:
                        chance *= .25
                chance = min(.97, max(.04, chance))
                immediate = base[i] * (1 + level[i])
                threat += chance * (immediate * (min(left, 5 if not level[i] else 10)
                                                 + 8 * denial[s]) + min(left, 3) * 4 * denial[s])
                miss *= 1 - chance
            normal_rate = tasks[0][0] if tasks else 0.0
            if threat and config["shield_weight"] * threat > (1 + config["backfire_cost"] * miss) * max(1.0, 0.49 * normal_rate):
                best_action = "SHIELD"
        if best_action == "STAY" and left == 1 and memory["known_start"] and "SHIELD" in legal:
            if owner[at] == me:
                can_score = not level[at] and progress >= 2
            else:
                can_score = not ishome[at] and (not owner[at] or not level[at] or progress >= 2)
            if not can_score:
                for s in enemies:
                    c = pos[s]
                    if owner[c] == me and not ishome[c]:
                        best_action = "SHIELD"
                        break
        if best_action not in legal:
            best_action = "STAY" if "STAY" in legal else legal[0]
        return best_action, chosen_cell, baited

    def commit(self, action, chosen_cell, baited):
        memory = self.mem
        memory["prior_target"] = chosen_cell
        if baited:
            memory["last_bait"] = memory["turn"]
        memory["last"] = action

    def step(self, me, legal, priority, base, ishome, owner, level, pos, frozen, income):
        if pos[me] < 0:
            return "STAY" if "STAY" in legal else legal[0]
        if not self.begin(me, legal, base, ishome, owner, level, pos, frozen):
            return legal[0]
        a, cc, b = self.decide(me, legal, priority, base, ishome, owner, level, pos, frozen, income)
        self.commit(a, cc, b)
        return a

    def act(self, cells, me, legal, priority):
        """Equivalent of the original act(state) for one seat (testing)."""
        owner = [c.owner for c in cells]
        level = [int(c.is_upgraded) for c in cells]
        base = [c.base_points for c in cells]
        ishome = [bool(c.is_home) for c in cells]
        pos, frozen, income = [-1] * 5, [False] * 5, [0] * 5
        for i, c in enumerate(cells):
            if c.occupant:
                pos[c.occupant], frozen[c.occupant] = i, c.is_frozen
            income[c.owner] += c.base_points * (1 + level[i])
        return self.step(me, legal, priority, base, ishome, owner, level, pos, frozen, income)


"""Shared core of the human-like exploiters (hx_*.py exec this file, then set STYLE).

Each style is how a person who has watched these bots play might beat them.
Nothing here reads more than the server exposes (board, bot_id, token flag,
legal_actions); everything else is reconstructed from board diffs, the way a
human keeps track at the table.

    steady   solid farmer: claims the best cells near home first, upgrades the
             2s and 3s, shields only on the turn a raid would complete, and
             snipes rival level-1 cells in the last turns
    bait     shield baiter: sits on a rival's upgraded cell for two turns and
             steps off on the turn the owner shields, so the shield backfires;
             then walks back and takes the cell inside the four-turn cooldown.
             If the owner stopped answering baits, it just commits
    cdsnipe  cooldown sniper: raids only cells whose owner cannot shield before
             the take completes (on cooldown or frozen), upgraded cells first
    aggro    early aggression: lives off one-stay raids on the leader's
             level-1 cells from turn one, farms only when nothing is in reach
    sniper   endgame raider: farms, then spends the last fifteen turns on raids,
             whose bonus does not decay, and shields for free on the last turn
    mixed    picks one of the above per game (a person adapting between games)
"""
import os as _hos
import random as _random

_GENOME = {
    "steady": dict(EVO_GENOMES[0], denial_base=0.0, denial_close=0.0, raid_open=0.6),
    "bait": dict(EVO_GENOMES[0]),
    "cdsnipe": dict(EVO_GENOMES[0], raid_open=0.7, raid_late=1.2),
    "aggro": dict(EVO_GENOMES[0], raid_open=1.8, raid_late=2.2, risk_open=1.0),
    "sniper": dict(EVO_GENOMES[0], raid_open=0.7, raid_late=3.5),
}

_N = 8
_ADJ = []
for _p in range(64):
    _r, _c = divmod(_p, 8)
    _ADJ.append([(nm, q) for nm, q, ok in (
        ("NORTH", _p - 8, _r > 0), ("SOUTH", _p + 8, _r < 7),
        ("WEST", _p - 1, _c > 0), ("EAST", _p + 1, _c < 7)) if ok])
_MD = [[abs(a // 8 - b // 8) + abs(a % 8 - b % 8) for b in range(64)] for a in range(64)]
_HOMES = (0, 7, 63, 56)
STYLES = ("steady", "bait", "cdsnipe", "aggro", "sniper")


def _cells(board):
    seq = list(board)
    if len(seq) == 8 and isinstance(seq[0], (list, tuple)) and len(seq[0]) == 8:
        return [c for row in seq for c in row]
    return seq


class _Mind(object):
    def __init__(self, me, style, seed):
        self.me = me
        self.style = style
        self.rnd = _random.Random(seed)
        self.turn = 0
        self.prev = None
        self.cd = [0] * 5
        self.score = [0] * 5
        self.prog = 0                 # my consecutive stays on this cell
        self.rstay = [0] * 5          # each rival's consecutive stays on its cell
        self.last = None
        self.bait = None              # (cell, owner, phase, turn)
        self.answered = {}            # owner -> [baits answered, baits tried]
        self.target = None
        self.evo = EvoSim(_GENOME.get(style, EVO_GENOMES[0]))

    # ---------------------------------------------------------- observation
    def observe(self, cells):
        pos = [-1] * 5
        frz = [False] * 5
        for i, c in enumerate(cells):
            o = int(c.occupant or 0)
            if 1 <= o <= 4:
                pos[o] = i
                frz[o] = bool(c.is_frozen)
        owner = [int(c.owner or 0) for c in cells]
        up = [bool(c.is_upgraded) for c in cells]
        base = [int(c.base_points or 1) for c in cells]
        home = [bool(c.is_home) for c in cells]
        cur = {"pos": pos, "frz": frz, "owner": owner, "up": up}
        fresh = (sum(1 for o in owner if o) == 4 and not any(up) and
                 all(pos[s] >= 0 and home[pos[s]] for s in (1, 2, 3, 4)))
        p = self.prev
        if p is None or (fresh and self.turn > 6):
            self.turn = 1
            self.cd = [0] * 5
            self.score = [0] * 5
            self.prog = 0
            self.rstay = [0] * 5
        else:
            self.turn += 1
            for s in (1, 2, 3, 4):
                self.cd[s] = max(0, self.cd[s] - 1)
            # shields, read off the freezes
            for s in (1, 2, 3, 4):
                if frz[s] and not p["frz"][s]:
                    c = pos[s]
                    o = p["owner"][c]
                    if o not in (0, s) and pos[s] == p["pos"][s] and not p["frz"][o]:
                        self.cd[o] = 4            # the landlord caught it
                    else:
                        self.cd[s] = 4            # its own shield backfired
            if self.last == "SHIELD" and not frz[self.me]:
                self.cd[self.me] = 4
            # scores: raid bonuses, then income
            for i in range(64):
                o, po = owner[i], p["owner"][i]
                if o and po and o != po:
                    self.score[o] += 8 * base[i] * (2 if p["up"][i] else 1)
            for i in range(64):
                if owner[i]:
                    self.score[owner[i]] += base[i] * (2 if up[i] else 1)
            for s in (1, 2, 3, 4):
                c = pos[s]
                same = c == p["pos"][s] and not frz[s] and not p["frz"][s]
                changed = owner[c] != p["owner"][c] or up[c] != p["up"][c]
                if s == self.me:
                    self.prog = 0 if (not same or changed or self.last == "SHIELD") else self.prog + 1
                else:
                    self.rstay[s] = 0 if (not same or changed) else self.rstay[s] + 1
        self.prev = cur
        return pos, frz, owner, up, base, home

    # ---------------------------------------------------------- helpers
    def bfs(self, src, blocked):
        dist = [99] * 64
        first = [None] * 64
        dist[src] = 0
        q = [src]
        k = 0
        while k < len(q):
            x = q[k]
            k += 1
            for nm, y in _ADJ[x]:
                if dist[y] == 99 and y not in blocked:
                    dist[y] = dist[x] + 1
                    first[y] = nm if x == src else first[x]
                    q.append(y)
        return dist, first

    def window(self, o, frz):
        """Turns from now during which owner o cannot shield."""
        f = 2 if frz[o] else 0
        return max(self.cd[o], f)

    # ---------------------------------------------------------- policy
    def choose(self, cells, legal):
        me = self.me
        pos, frz, owner, up, base, home = self.observe(cells)
        at = pos[me]
        left = 81 - self.turn
        if at < 0:
            return "STAY"
        # the evolved planner observes every turn, so its memory follows the game
        income = [0] * 5
        for c in range(64):
            if owner[c]:
                income[owner[c]] += base[c] * (2 if up[c] else 1)
        lvl = [1 if u else 0 for u in up]
        try:
            ev = self.evo.step(me, legal, bool(self.token), base, home, owner, lvl, pos, frz, income)
        except Exception:
            ev = "STAY"
        a = self.layer(ev, at, pos, frz, owner, up, base, home, legal, left)
        if a not in legal:
            a = "STAY"
        if self.evo.mem is not None:
            self.evo.mem["last"] = a
        return a

    def layer(self, ev, at, pos, frz, owner, up, base, home, legal, left):
        me = self.me
        if len(legal) == 1:
            return legal[0]
        can_shield = "SHIELD" in legal and self.cd[me] == 0
        style = self.style
        threat = 0.0
        # -------- defence: shield on the turn a raid would complete
        if can_shield:
            for s in (1, 2, 3, 4):
                if s == me or frz[s] or pos[s] < 0:
                    continue
                c = pos[s]
                if owner[c] != me or home[c]:
                    continue
                if up[c]:
                    if self.rstay[s] >= 2:
                        threat += 16 * base[c] + 2 * base[c] * min(left, 20)
                else:
                    threat += (8 * base[c] + base[c] * min(left, 15)) * 0.7
            if left <= 1 and threat > 0:
                return "SHIELD"
            if threat >= (40 if style != "aggro" else 55):
                return "SHIELD"
        blocked = set(pos[s] for s in (1, 2, 3, 4) if s != me and pos[s] >= 0)
        dist, first = self.bfs(at, blocked)
        # -------- the bait state machine
        if style == "bait":
            a = self.bait_move(at, pos, frz, owner, up, base, home, dist, first, legal, left)
            if a is not None:
                return a
        # -------- style opportunities, else the evolved planner's economy
        opp = self.opportunity(at, pos, frz, owner, up, base, home, dist, first, left)
        a = opp if opp is not None else ev
        if a == "SHIELD" and threat <= 0:
            a = "STAY"
        return a

    def opportunity(self, at, pos, frz, owner, up, base, home, dist, first, left):
        """A raid this style would take over the planner's choice, or None."""
        style = self.style
        me = self.me
        if style in ("steady", "bait"):
            if left > 12:
                return None
        lead = max(range(1, 5), key=lambda s: (self.score[s] if s != me else -1, s))
        best, bi = 0.0, -1
        for i in range(64):
            o = owner[i]
            if o in (0, me) or home[i] or dist[i] >= 99:
                continue
            d = dist[i]
            v = base[i]
            work = 3 if up[i] else 1
            if i == at:
                work = max(1, work - self.prog)
            if d + work > left or d > 4:
                continue
            safe = self.window(o, frz) >= d + work
            bonus = 8 * v * (2 if up[i] else 1)
            val = bonus + v * (left - d - work + 1) * (0.5 if left > 20 else 1.0)
            if style == "cdsnipe":
                if not safe:
                    continue
            elif style == "aggro":
                if up[i] and not safe:
                    continue
                if o == lead:
                    val *= 1.3
            elif style in ("sniper", "steady", "bait"):
                if left > (15 if style == "sniper" else 12):
                    continue
                if up[i] and not safe:
                    continue
            rate = val / (d + work)
            if rate > best:
                best, bi = rate, i
        need = {"cdsnipe": 9.0, "aggro": 7.0, "sniper": 6.0, "steady": 8.0, "bait": 8.0}[style]
        if bi < 0 or best < need:
            return None
        if bi == at:
            return "STAY"
        return first[bi]

    def bait_move(self, at, pos, frz, owner, up, base, home, dist, first, legal, left):
        me = self.me
        b = self.bait
        if b is not None:
            cell, o, phase, t0 = b
            if self.turn - t0 > 14 or owner[cell] == me or left < 6:
                self.bait = None
                b = None
        if b is not None:
            cell, o, phase, t0 = b
            if phase == "go":
                if at == cell:
                    self.bait = (cell, o, "sit", self.turn)
                    return "STAY"
                if dist[cell] >= 99:
                    self.bait = None
                    return None
                return first[cell] if first[cell] in legal else "STAY"
            if phase == "sit":
                rec = self.answered.setdefault(o, [1.0, 2.0])
                commit = rec[0] / rec[1] < 0.35 or self.window(o, frz) >= 3 - self.prog
                if at != cell:
                    self.bait = None
                    return None
                if commit:
                    return "STAY"
                if self.prog >= 2:                    # owner should shield now: step off
                    for nm, q in _ADJ[at]:
                        if nm in legal and q not in set(pos):
                            self.bait = (cell, o, "off", self.turn)
                            return nm
                return "STAY"
            if phase == "off":
                rec = self.answered.setdefault(o, [1.0, 2.0])
                rec[1] += 1
                if self.cd[o] >= 3 or frz[o]:
                    rec[0] += 1
                    self.bait = (cell, o, "take", self.turn)
                else:
                    self.bait = (cell, o, "sit", self.turn) if dist[cell] < 99 else None
                if self.bait is not None and dist[cell] < 99:
                    return first[cell] if first[cell] in legal else "STAY"
                return None
            if phase == "take":
                if at == cell:
                    return "STAY"
                if dist[cell] >= 99:
                    self.bait = None
                    return None
                return first[cell] if first[cell] in legal else "STAY"
        # pick a new bait: a rival's upgraded cell close by, owner able to shield;
        # a person baits now and then, not every turn
        if self.turn < 16 or left < 10 or self.turn - getattr(self, "last_bait", -99) < 15:
            return None
        best, bc = 0.0, None
        for i in range(64):
            o = owner[i]
            if o in (0, me) or not up[i] or home[i] or dist[i] > 3 or base[i] < 2:
                continue
            if frz[o] or self.cd[o] > 0:
                continue
            val = 16 * base[i] / (dist[i] + 4)
            if val > best:
                best, bc = val, i
        if bc is not None and best >= 5.0:
            self.bait = (bc, owner[bc], "go", self.turn)
            self.last_bait = self.turn
            return first[bc] if first[bc] in legal else None
        return None


_MINDS = {}


def act(state):
    try:
        cells = _cells(state.board)
        me = int(state.bot_id)
        legal = list(state.legal_actions)
        m = _MINDS.get(me)
        fresh = (sum(1 for c in cells if c.owner) == 4 and not any(c.is_upgraded for c in cells))
        if m is None or (fresh and m.turn > 6):
            style = STYLE
            if style == "mixed":
                style = STYLES[(sum(c.base_points for c in cells) * 7 + me) % len(STYLES)]
            m = _MINDS[me] = _Mind(me, style, me * 977 + sum(c.base_points for c in cells))
        m.token = bool(getattr(state, "is_priority_token", False))
        a = m.choose(cells, legal)
        if a not in legal:
            a = "STAY"
        m.last = a
        return a
    except Exception:
        return "STAY"


STYLE = "steady"

STYLE = 'sniper'
