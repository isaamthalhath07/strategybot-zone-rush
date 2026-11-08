"""Zone Rush bot, selected by local empirical testing on 6 November 2026.

Standard-library-only single-file entry point. Reads the documented starter
interface and never changes the supplied state. Module memory tracks turns,
scores, progress, opponent shields and observed raid persistence within a game.
Organisers confirmed that frozen stays earn no progress and memory is allowed.
Memory follows observed outcomes after blocked moves or server STAY fallbacks.
Official server compatibility remains to be checked by the organisers.
"""

from collections import deque


# Assign CONFIG in a private, per-game namespace during offline selection.
# The standalone submission requires no trainer or third-party packages.
DEFAULT_CONFIG = {
    'upgrade_open': 2.25,
    'upgrade_late': 2.25,
    'raid_open': 0.99,
    'raid_late': 0.99,
    'risk_open': 4.0,
    'risk_late': 4.0,
    'income_lifetime': 18.0,
    'safety_slope': 6.0,
    'fortify_premium': 1.16,
    'denial_base': 0.27,
    'denial_close': 0.43,
    'cash_weight': 1.0,
    'contest_cost': 1.0,
    'depth': 2,
    'breadth': 9,
    'route_weight': 0.5,
    'route_delay': 0.11,
    'inertia': 0.0,
    'shield_weight': 1.0,
    'backfire_cost': 2.0,
    'shield_prior': 0.3333333333333333,
    'stay_prior': 0.76,
    'feint_weight': 1.0,
}
BOUNDS = {
    'upgrade_open': (0.45, 4.2),
    'upgrade_late': (0.3, 4.5),
    'raid_open': (0.25, 2.4),
    'raid_late': (0.25, 3.5),
    'risk_open': (0.0, 8.0),
    'risk_late': (0.0, 8.0),
    'income_lifetime': (6.0, 48.0),
    'safety_slope': (0.0, 12.0),
    'fortify_premium': (0.65, 2.0),
    'denial_base': (0.0, 1.0),
    'denial_close': (0.0, 1.3),
    'cash_weight': (0.4, 2.25),
    'contest_cost': (0.0, 3.0),
    'depth': (1, 3),
    'breadth': (3, 12),
    'route_weight': (0.0, 1.3),
    'route_delay': (0.02, 0.5),
    'inertia': (0.0, 0.28),
    'shield_weight': (0.1, 3.0),
    'backfire_cost': (0.3, 5.0),
    'shield_prior': (0.05, 0.82),
    'stay_prior': (0.32, 0.93),
    'feint_weight': (0.0, 1.85),
}
INTEGER_GENES = {"depth", "breadth"}
CONFIG = {'backfire_cost': 1.13552,
 'breadth': 7,
 'cash_weight': 1.25275,
 'contest_cost': 0.42039,
 'denial_base': 0.79149,
 'denial_close': 0.20084,
 'depth': 3,
 'feint_weight': 1.25119,
 'fortify_premium': 1.11474,
 'income_lifetime': 40.67114,
 'inertia': 0.0496,
 'raid_late': 1.65061,
 'raid_open': 0.95839,
 'risk_late': 8.0,
 'risk_open': 1.97775,
 'route_delay': 0.02,
 'route_weight': 0.61979,
 'safety_slope': 0.0,
 'shield_prior': 0.33333,
 'shield_weight': 1.30296,
 'stay_prior': 0.69484,
 'upgrade_late': 4.5,
 'upgrade_open': 1.46008}


_NAMES = ("NORTH", "EAST", "SOUTH", "WEST")
_ADJ = []
_DIST = []
for _i in range(64):
    _r, _c = divmod(_i, 8)
    _ADJ.append(tuple((name, r * 8 + c) for name, r, c in (
        ("NORTH", _r-1, _c), ("EAST", _r, _c+1),
        ("SOUTH", _r+1, _c), ("WEST", _r, _c-1)) if 0 <= r < 8 and 0 <= c < 8))
    _DIST.append(tuple(abs(_r-j//8) + abs(_c-j%8) for j in range(64)))
_history = {}


def _observe(me, cells, positions, owner, level, frozen, can_shield, config):
    """Infer elapsed turns, progress, score and opponent cooldown from observations."""
    old = _history.get(me)
    pristine = all(pos >= 0 and cells[pos].is_home and owner[pos] == seat
                   for seat, pos in enumerate(positions) if seat)
    pristine = pristine and sum(bool(v) for v in owner) == 4 and not any(level)
    # After a capture the total number of owned cells cannot drop back to
    # four. An upgraded home cannot revert either. Positions alone can reset
    # to their starting pattern during a perfectly ordinary opening.
    if old is None or (pristine and (old["turn"] >= 80 or any(old["level"])
                                     or sum(bool(v) for v in old["owner"]) > 4)):
        occupied = sum(bool(v) for v in owner) - 4
        # A fresh interpreter mid-match still makes decisions from the visible board.
        turn = 1 if pristine else min(67, max(2, 2 + occupied + sum(level)))
        old = {"turn": turn, "known_start": pristine, "scores": [0]*5, "progress": 0, "positions": positions,
               "owner": owner, "level": level, "frozen": frozen, "last": None,
               "stay_trials": [[2.,2.] for _ in range(5)],
               "stay_hits": [[2*config["stay_prior"],1.16] for _ in range(5)], "can_shield": False,
               "enemy_progress": [0]*5, "defense_trials": [3.0]*5,
               "defense_hits": [1.20]*5, "last_bait": -10,
               "cooldown": [0]*5, "stops": [3*config["shield_prior"]]*5, "attempts": [3.0]*5}
    else:
        old["turn"] = min(old["turn"]+1, 80)
        cooldown = [max(0, c-1) for c in old["cooldown"]]
        prior_pos, prior_owner = old["positions"], old["owner"]
        # An accepted shield starts a four-turn cooldown. If it is still
        # available, a requested shield became a STAY. A new freeze hides
        # cooldown availability; retain the request only as a learning signal
        # in that ambiguous case. Neither kind of freeze can earn progress.
        own_shield = (old["can_shield"] and not can_shield and
                      (not frozen[me] or old["last"] == "SHIELD"))
        just_shielded = set()
        for seat in range(1, 5):
            spot = positions[seat]
            if spot < 0 or prior_pos[seat] != spot:
                continue
            defender = prior_owner[spot]
            if defender and defender != seat and not old["frozen"][seat]:
                if frozen[seat] and not frozen[defender] and prior_pos[defender] == positions[defender]:
                    just_shielded.add(defender)
                    old["stops"][defender] += 1
                    old["attempts"][defender] += 1
                elif owner[spot] == seat:
                    old["attempts"][defender] += 1
            if frozen[seat] and not old["frozen"][seat] and defender in (0, seat):
                just_shielded.add(seat)  # Clearly a shield backfire.
        opportunities = set()
        for seat in range(1,5):
            previous = prior_pos[seat]
            if previous < 0 or old["frozen"][seat]:
                continue
            land = prior_owner[previous]
            if land in (0, seat) or cells[previous].is_home:
                continue
            if not old["frozen"][land] and not old["cooldown"][land]:
                opportunities.add(land)
            if land == me and old["can_shield"]:
                tier = old["level"][previous]
                stayed = ((previous == positions[seat]) and
                          seat not in just_shielded and
                          (not own_shield or (frozen[seat] and not frozen[me])))
                weight = 1.5 if own_shield else 1.0
                old["stay_hits"][seat][tier] = 0.94*old["stay_hits"][seat][tier] + weight*stayed
                old["stay_trials"][seat][tier] = 0.94*old["stay_trials"][seat][tier] + weight
        for defender in opportunities:
            old["defense_hits"][defender] = .93*old["defense_hits"][defender] + (defender in just_shielded)
            old["defense_trials"][defender] = .93*old["defense_trials"][defender] + 1
        for seat in range(1,5):
            p = positions[seat]
            continuing = (p >= 0 and p == prior_pos[seat] and seat not in just_shielded
                          and not frozen[seat] and not old["frozen"][seat] and
                          owner[p] == prior_owner[p] and level[p] == old["level"][p])
            old["enemy_progress"][seat] = min(2, old["enemy_progress"][seat]+1) if continuing else 0
        for defender in just_shielded:
            cooldown[defender] = 4
        old["cooldown"] = cooldown
        spot = positions[me]
        continued = (spot == prior_pos[me] and not own_shield
                     and not old["frozen"][me] and not frozen[me]
                     and prior_owner[spot] == owner[spot] and old["level"][spot] == level[spot])
        old["progress"] = min(2, old["progress"]+1) if continued else 0
        for i, seat in enumerate(owner):
            if seat:
                value = cells[i].base_points
                old["scores"][seat] += value * (1 + level[i])
                if prior_owner[i] and prior_owner[i] != seat:
                    old["scores"][seat] += 8 * value * (1 + old["level"][i])
    old.update(positions=positions, owner=owner, level=level, frozen=frozen)
    _history[me] = old
    return old


def _paths(origin, occupied, legal, cells, me, priority, rivals):
    """Shortest routes respecting closed cells and current legal first moves."""
    travel = [90]*64
    first = [None]*64
    travel[origin] = 0
    queue = deque()
    # The first neighbour inserted wins equal-distance paths. Prefer a safe first move.
    choices = []
    for action, target in _ADJ[origin]:
        if action in legal and target not in occupied:
            risk = sum(_DIST[p][target] == 1 for p in rivals)
            if cells[target].owner == me:
                risk = 0
            elif priority and cells[target].owner == 0:
                risk = 0
            choices.append((risk, action, target))
    for _, action, target in sorted(choices):
        travel[target], first[target] = 1, action
        queue.append(target)
    while queue:
        here = queue.popleft()
        for _, there in _ADJ[here]:
            if travel[there] == 90 and there not in occupied:
                travel[there], first[there] = travel[here]+1, first[here]
                queue.append(there)
    return travel, first


def choose_terminal(state, cells, me, at, progress):
    """Return a dominating replacement for STAY, or None to use the planner.

    Only call on the final turn. The flat cells, current position, and inferred
    consecutive progress refer to the board before the four simultaneous moves.
    """
    if "SHIELD" not in state.legal_actions:
        return None
    here = cells[at]
    if here.owner == me:
        can_score_by_staying = not here.is_upgraded and progress >= 2
    else:
        can_score_by_staying = not here.is_home and (
            not here.owner or not here.is_upgraded or progress >= 2
        )
    if can_score_by_staying:
        return None
    # A shield protects every holding even if it only encounters already
    # frozen rivals. A resulting backfire costs no scoring turns after turn 80.
    threatened = any(cell.owner == me and not cell.is_home
                     and cell.occupant and cell.occupant != me for cell in cells)
    return "SHIELD" if threatened else None



def act(state):
    legal = state.legal_actions
    me = state.bot_id
    board = state.board
    cells = [cell for row in board for cell in row] if len(board) == 8 else board
    owner = [c.owner for c in cells]
    level = [int(c.is_upgraded) for c in cells]
    pos, frozen, income = [-1]*5, [False]*5, [0]*5
    for i, c in enumerate(cells):
        if c.occupant:
            pos[c.occupant], frozen[c.occupant] = i, c.is_frozen
        income[c.owner] += c.base_points * (1+level[i])
    at = pos[me]
    if at < 0:
        return "STAY" if "STAY" in legal else legal[0]
    can_shield = "SHIELD" in legal
    config = {**DEFAULT_CONFIG, **CONFIG}
    memory = _observe(me, cells, pos, owner, level, frozen, can_shield, config)
    memory["can_shield"] = can_shield
    if len(legal) == 1:
        memory["last"] = legal[0]
        return legal[0]

    left = 81-memory["turn"]
    # Interpolate open/late priorities without discontinuities at a fixed turn.
    phase = (memory["turn"]-1)/79
    upgrade = config["upgrade_open"] + phase*(config["upgrade_late"]-config["upgrade_open"])
    raid = config["raid_open"] + phase*(config["raid_late"]-config["raid_open"])
    risk_weight = config["risk_open"] + phase*(config["risk_late"]-config["risk_open"])
    depth = min(3,max(1,round(config["depth"])))
    breadth = min(12,max(1,round(config["breadth"])))
    route_weight = config["route_weight"] if depth > 1 else 0.
    feint_weight = config["feint_weight"]
    enemies = [i for i in range(1,5) if i != me and pos[i] >= 0]
    occupied = {pos[i] for i in enemies}
    travel, first = _paths(at, occupied, legal, cells, me, state.is_priority_token, occupied)
    rival_ranges = [_DIST[p] for p in occupied]
    pressure = [min(x) for x in zip(*rival_ranges)] if occupied else [12]*64

    projection = [memory["scores"][i] + min(left, 18) * income[i] for i in range(5)]
    # A point denied matters most against a rival near our predicted finishing score.
    denial = [0.0]*5
    for seat in enemies:
        gap = abs(projection[me]-projection[seat])
        denial[seat] = config["denial_base"] + config["denial_close"]/(1+gap/(65+left*3))
    exposure = [min(0.87, 0.08+1.30*memory["stops"][i]/memory["attempts"][i])
                for i in range(5)]

    # One macro-action ends at a capture or completed upgrade.
    # Enumerate all reachable cells; evaluate the best few with their next target.
    tasks = []
    for i, c in enumerate(cells):
        who, up, travel_time = owner[i], level[i], travel[i]
        if travel_time >= left or (up and who == me) or (c.is_home and who != me):
            continue
        work = 3 if (who == me or up) else 1
        if i == at:
            work = max(1, work - memory["progress"])
        cost = travel_time + work
        if cost > left:
            continue
        v = c.base_points
        nearest = pressure[i]
        # Forecast a shorter residence time for cells in active raiding lanes.
        retention = config["income_lifetime"] + min(5, nearest)*config["safety_slope"]
        if c.is_home:
            retention = 100
        life = min(left-cost+1, retention)
        if who == me:
            reward = v * life * upgrade
            if not c.is_home:
                reward *= config["fortify_premium"]  # Three-stay theft requirement provides lasting protection.
        elif who == 0:
            reward = v * life
        else:
            reward = raid*v * (life*(1+denial[who]*(1+up)) + 8*config["cash_weight"]*(1+up))
        risk = 0
        if who not in (me,0):
            if memory["cooldown"][who] < cost and (not frozen[who] or cost > 1):
                risk = exposure[who]*risk_weight
                if up:
                    risk *= 1.4
                reward /= 1.0 + risk*(0.65 if up else 0.18)
        effort = work + risk*(3.5 if up else 2.4)
        # Entering a contested cell is less attractive when the owner could enter too.
        if i != at and nearest <= travel_time and who != me:
            effort += config["contest_cost"]*(0.40 if nearest <= 1 else 0.18)
        rate = reward / (travel_time+effort)
        if config["inertia"] and i == memory.get("prior_target"):
            rate *= 1+config["inertia"]
        tasks.append((rate, i, effort, reward, cost, work))

    tasks.sort(reverse=True)
    best_value, best_action = -1.0, "STAY" if "STAY" in legal else legal[0]
    chosen_cell = None
    for rate, i, effort, reward, cost, work in tasks[:breadth]:
        next_rate = 0.0
        if cost < left-1 and route_weight:
            dists = _DIST[i]
            second = None
            second_cost = 0
            for _, j, effort2, reward2, _, work2 in tasks:
                if i == j:
                    continue
                between = dists[j]
                # Progress on the original occupied cell disappears upon moving away.
                extra = memory["progress"] if j == at else 0
                if cost+between+work2+extra <= left:
                    candidate = reward2/(between+effort2+extra)
                    if candidate > next_rate:
                        next_rate, second, second_cost = candidate, j, between+work2+extra
            if owner[i] != me and cost+3 <= left:
                postcapture = min(left-cost-2, config["income_lifetime"]+min(5,pressure[i])*config["safety_slope"])
                candidate = cells[i].base_points*postcapture*upgrade/3
                if candidate > next_rate:
                    next_rate, second, second_cost = candidate, i, 3
            # Depth three follows the best second job, then scores a distinct
            # third capture or upgrade. Each job earns its marginal value once.
            if depth == 3 and second is not None and cost+second_cost < left-1:
                third_rate = 0.
                from_second = _DIST[second]
                for _, k, effort3, reward3, _, work3 in tasks:
                    if k in (i, second):
                        continue
                    between = from_second[k]
                    extra = memory["progress"] if k == at else 0
                    if cost+second_cost+between+work3+extra <= left:
                        third_rate = max(third_rate, reward3/(between+effort3+extra))
                next_rate += route_weight*third_rate/(1+config["route_delay"]*(second_cost-1))
        # Distant clusters contribute less until we have completed the first job.
        value = rate + route_weight*next_rate/(1+config["route_delay"]*(cost-1))
        if value > best_value:
            best_value, best_action = value, ("STAY" if i == at else first[i])
            chosen_cell = i
    memory["prior_target"] = chosen_cell

    # Escape a predicted shield only when there is a productive neighbouring
    # target. This keeps a feint from becoming an endless shuttle.
    defender = owner[at]
    if (feint_weight and best_action == "STAY" and defender not in (0, me)
            and not cells[at].is_home and not frozen[defender] and
            memory["cooldown"][defender] == 0 and memory["turn"]-memory["last_bait"] >= 5
            and left > 2 and memory["progress"] == 0):
        response = memory["defense_hits"][defender] / memory["defense_trials"][defender]
        exits = []
        for _, i, effort, reward, _, _ in tasks:
            if travel[i] == 1:
                # A closely comparable job on the same opponent's land benefits
                # from the entire cooldown if they fire into the empty square.
                bonus = 1.25 if owner[i] == defender else 0.95
                exits.append((reward*bonus/(effort+1), first[i]))
        if exits and response*feint_weight > .43:
            alternative, action = max(exits)
            if alternative*(1+1.3*response*feint_weight) > tasks[0][0]:
                best_action = action
                memory["last_bait"] = memory["turn"]
    if "SHIELD" in legal:
        # We can freeze several raiders, but slowing just one costs valuable development.
        threat = 0.0
        miss = 1.0
        for s in enemies:
            i = pos[s]
            if owner[i] != me or frozen[s] or cells[i].is_home:
                continue
            tier = level[i]
            chance = memory["stay_hits"][s][tier]/memory["stay_trials"][s][tier]
            if tier:
                # Two uneventful stays reveal commitment and a live takeover.
                # Keeping the shield ready on earlier stays preserves the option
                # to reset the entire three-turn raid if they persist.
                progress = memory["enemy_progress"][s]
                chance *= (.21, .53, 1.18)[progress]
                if progress+left < 3:
                    chance *= .25
            chance = min(.97, max(.04, chance))
            immediate = cells[i].base_points*(1+level[i])
            threat += chance * (immediate*(min(left, 5 if not level[i] else 10)
                                          + 8*denial[s]) + min(left,3)*4*denial[s])
            miss *= 1-chance
        # Compare the expected benefit against delaying a productive action and backfire.
        normal_rate = tasks[0][0] if tasks else 0.0
        if threat and config["shield_weight"]*threat > (1+config["backfire_cost"]*miss)*max(1.0, 0.49*normal_rate):
            best_action = "SHIELD"
    if best_action == "STAY" and left == 1 and memory["known_start"]:
        terminal = choose_terminal(state, cells, me, at, memory["progress"])
        if terminal is not None:
            best_action = terminal
    if best_action not in legal:
        best_action = "STAY" if "STAY" in legal else legal[0]
    memory["last"] = best_action
    return best_action
