"""Zone Rush territory planner. Only reads the documented starter interface."""

from collections import deque
from heapq import nlargest
from math import exp


# Exposed for offline comparisons. They do not depend on the game server.
UPGRADE_WEIGHT = 1.12
RAID_WEIGHT = 1.00
DEFENSE_WEIGHT = 1.00
ROUTE_WEIGHT = 0.54
RISK_WEIGHT = 1.00
BAIT_WEIGHT = 1.00
BEAM_WIDTH = 7
SEARCH_DEPTH = 4
DISCOUNT_HORIZON = 5.5

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


def _observe(me, cells, positions, owner, level, frozen):
    """Infer elapsed turns, progress, score and opponent cooldown from observations."""
    old = _history.get(me)
    pristine = all(pos >= 0 and cells[pos].is_home and owner[pos] == seat
                   for seat, pos in enumerate(positions) if seat)
    pristine = pristine and sum(bool(v) for v in owner) == 4 and not any(level)
    if old is None or (pristine and (old["turn"] >= 80 or not old["pristine"])):
        occupied = sum(bool(v) for v in owner) - 4
        # A fresh interpreter mid-match still makes decisions from the visible board.
        turn = 1 if pristine else min(67, max(2, 2 + occupied + sum(level)))
        old = {"turn": turn, "scores": [0]*5, "progress": 0, "positions": positions,
               "owner": owner, "level": level, "frozen": frozen, "last": None,
               "stay_trials": [[2.,2.] for _ in range(5)],
               "stay_hits": [[1.52,1.16] for _ in range(5)], "can_shield": False,
               "enemy_progress": [0]*5, "defense_trials": [3.0]*5,
               "defense_hits": [1.20]*5, "last_bait": -10,
               "cooldown": [0]*5, "stops": [1.0]*5, "attempts": [3.0]*5}
    else:
        old["turn"] = min(old["turn"]+1, 80)
        cooldown = [max(0, c-1) for c in old["cooldown"]]
        prior_pos, prior_owner = old["positions"], old["owner"]
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
                          (old["last"] != "SHIELD" or
                           (frozen[seat] and not frozen[me])))
                weight = 1.5 if old["last"] == "SHIELD" else 1.0
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
        continued = (spot == prior_pos[me] and old["last"] not in ("SHIELD", None)
                     and not old["frozen"][me] and not frozen[me]
                     and prior_owner[spot] == owner[spot] and old["level"][spot] == level[spot])
        old["progress"] = min(2, old["progress"]+1) if continued else 0
        for i, seat in enumerate(owner):
            if seat:
                value = cells[i].base_points
                old["scores"][seat] += value * (1 + level[i])
                if prior_owner[i] and prior_owner[i] != seat:
                    old["scores"][seat] += 8 * value * (1 + old["level"][i])
    old.update(positions=positions, owner=owner, level=level, frozen=frozen, pristine=pristine)
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
    memory = _observe(me, cells, pos, owner, level, frozen)
    memory["can_shield"] = "SHIELD" in legal
    if len(legal) == 1:
        memory["last"] = legal[0]
        return legal[0]

    left = 81-memory["turn"]
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
        denial[seat] = 0.27 + 0.43/(1+gap/(65+left*3))
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
        retention = 18 + min(5, nearest)*6
        if c.is_home:
            retention = 100
        life = min(left-cost+1, retention)
        if who == me:
            reward = v * life * UPGRADE_WEIGHT
            if not c.is_home:
                reward *= 1.16  # Three-stay theft requirement provides lasting protection.
        elif who == 0:
            reward = v * life
        else:
            reward = RAID_WEIGHT*v * (life*(1+denial[who]*(1+up)) + 8*(1+up))
        risk = 0
        if who not in (me,0):
            if memory["cooldown"][who] < cost and (not frozen[who] or cost > 1):
                risk = exposure[who]*RISK_WEIGHT
                if up:
                    risk *= 1.4
                reward /= 1.0 + risk*(0.65 if up else 0.18)
        effort = work + risk*(3.5 if up else 2.4)
        # Entering a contested cell is less attractive when the owner could enter too.
        if i != at and nearest <= travel_time and who != me:
            effort += 0.40 if nearest <= 1 else 0.18
        rate = reward / (travel_time+effort)
        tasks.append((rate, i, effort, reward, cost, work))

    tasks.sort(reverse=True)
    best_value, best_action = -1.0, "STAY" if "STAY" in legal else legal[0]
    if tasks:
        # Jobs rather than primitive moves keep a four-step search affordable.
        # A bit for each completed job distinguishes take-then-upgrade from
        # repeated credit for the same land. Keep one beam of paths per turn.
        decay = [exp(-t/DISCOUNT_HORIZON) for t in range(100)]
        paths = []
        for rate, i, effort, reward, cost, work in tasks[:max(9, BEAM_WIDTH)]:
            dt = travel[i]+effort
            action = "STAY" if i == at else first[i]
            used = 1 << i
            paths.append((rate, reward, dt, cost, i, used, used if owner[i] == me else 0, action))
        best_action = paths[0][-1]
        local = {}
        for depth in range(1, SEARCH_DEPTH):
            candidates = []
            for previous_rate, value_sum, cost_sum, elapsed, last, used, improved, action in paths:
                if elapsed >= left-1:
                    candidates.append((previous_rate,value_sum,cost_sum,elapsed,last,used,improved,action))
                    continue
                if last not in local:
                    options = []
                    for _, j, effort, reward, _, work in tasks:
                        distance = _DIST[last][j]
                        if distance > 5:
                            continue
                        reset = memory["progress"] if j == at else 0
                        options.append((j, distance, effort+reset, work+reset, reward))
                    local[last] = options
                discount = decay[elapsed]
                found = False
                for j, distance, effort, work, reward in local[last]:
                    mask = 1 << j
                    if used & mask:
                        if improved & mask or owner[j] == me:
                            continue
                        work, effort = 3, 3.0
                        end = elapsed + distance + work
                        life = min(left-end+1, 18+min(5,pressure[j])*6)
                        reward = cells[j].base_points*max(0,life)*UPGRADE_WEIGHT*1.16
                        new_improved = improved | mask
                    else:
                        end = elapsed + distance + work
                        if left < 15:
                            nominal = max(1,left-(travel[j]+work)+1)
                            reward *= min(1., max(0.,left-end+1)/nominal)
                        new_improved = improved | mask if owner[j] == me else improved
                    if end > left:
                        continue
                    found = True
                    new_value = value_sum + reward*discount
                    new_cost = cost_sum+(distance+effort)*discount
                    candidates.append((new_value/new_cost,new_value,new_cost,end,j,used|mask,new_improved,action))
                if not found:
                    candidates.append((previous_rate,value_sum,cost_sum,elapsed,last,used,improved,action))
            if not candidates:
                break
            paths = nlargest(BEAM_WIDTH, candidates)
            best_action = paths[0][-1]
    # Escape a predicted shield only when there is a productive neighbouring
    # target. This keeps a feint from becoming an endless shuttle.
    defender = owner[at]
    if (BAIT_WEIGHT and best_action == "STAY" and defender not in (0, me)
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
        if exits and response*BAIT_WEIGHT > .43:
            alternative, action = max(exits)
            if alternative*(1+1.3*response*BAIT_WEIGHT) > tasks[0][0]:
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
        if threat and DEFENSE_WEIGHT*threat > (1+2*miss)*max(1.0, 0.49*normal_rate):
            best_action = "SHIELD"
    if best_action not in legal:
        best_action = "STAY" if "STAY" in legal else legal[0]
    memory["last"] = best_action
    return best_action
