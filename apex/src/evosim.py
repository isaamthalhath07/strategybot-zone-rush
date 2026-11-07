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
