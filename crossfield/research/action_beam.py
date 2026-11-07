"""Zone Rush action-level beam search. The entry point uses the public starter interface."""
from heapq import nlargest

DEFAULT_CONFIG = {
    'width': 12,
    'depth': 8,
    'discount': 0.93,
    'upgrade': 1.25,
    'raid': 0.5,
    'defense': 1.0,
    'risk': 1.0,
    'guidance': 1.0,
    'life': 1.0,
    'denial': 1.0,
}
BOUNDS = {
    'width': (5, 18),
    'depth': (4, 12),
    'discount': (0.73, 0.99),
    'upgrade': (0.45, 2.9),
    'raid': (0.18, 2.05),
    'defense': (0.2, 3.0),
    'risk': (0.0, 1.75),
    'guidance': (0.2, 2.0),
    'life': (0.48, 1.9),
    'denial': (0.2, 2.0),
}
CONFIG = DEFAULT_CONFIG.copy()
INTEGER_GENES = {"depth", "width"}
BITS = tuple(1 << j for j in range(64))
DIST = tuple(tuple(abs(i // 8 - j // 8) + abs(i % 8 - j % 8)
                   for j in range(64)) for i in range(64))


def _neighbors(i):
    r, c = divmod(i, 8)
    return tuple((j, a) for j, a, valid in (
        (i - 8, "NORTH", r > 0), (i + 1, "EAST", c < 7),
        (i + 8, "SOUTH", r < 7), (i - 1, "WEST", c > 0)) if valid)


ADJ = tuple(_neighbors(i) for i in range(64))
NEAR = tuple(tuple((j, d) for j,d in enumerate(row) if d <= 4) for row in DIST)
_history = {}
MEM = _history


def _observe(me, cells, positions, owner, level, frozen, can_shield):
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
               "stay_hits": [[1.52,1.16] for _ in range(5)], "can_shield": False,
               "enemy_progress": [0]*5, "defense_trials": [3.0]*5,
               "defense_hits": [1.20]*5, "last_bait": -10,
               "cooldown": [0]*5, "stops": [1.0]*5, "attempts": [3.0]*5}
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
    me = state.bot_id
    cells = [c for row in state.board for c in row]
    pos, frozen = [-1]*5, [False]*5
    for i, c in enumerate(cells):
        if c.occupant:
            pos[c.occupant], frozen[c.occupant] = i, c.is_frozen
    legal = state.legal_actions
    if pos[me] < 0:
        return "STAY" if "STAY" in legal else legal[0]
    can_shield = "SHIELD" in legal
    owner = [c.owner for c in cells]
    level = [int(c.is_upgraded) for c in cells]
    memory = _observe(me,cells,pos,owner,level,frozen,can_shield)
    memory["can_shield"] = can_shield
    answer = legal[0] if len(legal)==1 else _search(state,cells,pos,memory)
    if answer == "STAY" and memory["known_start"] and memory["turn"]==80:
        answer = choose_terminal(state,cells,me,pos[me],memory["progress"]) or answer
    if answer not in legal:
        answer = "STAY" if "STAY" in legal else legal[0]
    memory["last"] = answer
    return answer


def _search(state, cells, pos, memory):
    me = state.bot_id
    legal = set(state.legal_actions)
    left = 81 - memory["turn"]
    config = {**DEFAULT_CONFIG, **CONFIG}
    width = max(1,round(config["width"]))
    depth = min(left,max(1,round(config["depth"])))
    discount_rate = config["discount"]
    upgrade_weight = config["upgrade"]
    raid_weight = config["raid"]
    risk_weight = config["risk"]
    life_weight = config["life"]
    guidance = config["guidance"]
    start = pos[me]
    rivals = [s for s in range(1, 5) if s != me]
    occupied = {pos[s] for s in rivals}
    pressure = [min(DIST[p][i] for p in occupied) for i in range(64)]
    p_shield = [min(.95, risk_weight*memory["defense_hits"][s]/memory["defense_trials"][s]) for s in range(5)]
    base = [c.base_points for c in cells]
    own = memory["owner"]
    lvl = memory["level"]
    init_own = sum(BITS[i] for i in range(64) if own[i] == me)
    init_upgrade = sum(BITS[i] for i in range(64) if own[i] == me and lvl[i])
    captures = [0.0]*64
    upgrades = [0.0]*64
    work = [1]*64
    denied = [.0]*5
    for s in rivals:
        gap = abs(memory["scores"][me]-memory["scores"][s])
        denied[s] = config["denial"]*(.25 + .40/(1+gap/(35+left*5)))
    for i, c in enumerate(cells):
        v = base[i]
        # Estimate the productive lifetime of a new level-one holding, then the
        # longer life of an upgraded cell that takes three stays to steal.
        horizon = max(1, left-1)
        normal = min(horizon, life_weight*(17 + 2.7*pressure[i]))
        fortified = min(horizon, life_weight*(28 + 3.6*pressure[i]))
        if c.is_home:
            fortified = horizon
            normal = horizon
        upgrades[i] = v*upgrade_weight*(fortified + .48*(fortified-normal))
        if own[i] == me or c.is_home:
            continue
        captures[i] = v*normal
        if own[i]:
            s = own[i]
            level = 1+lvl[i]
            work[i] = 3 if lvl[i] else 1
            captures[i] = raid_weight*v*(normal + level*(8+denied[s]*normal))
    # All moves and captures are simulated one action at a time. A small
    # potential directs partial paths toward points they can finish next.
    shortlist = [None]*64
    available = [not ((own[j] == me and lvl[j]) or (cells[j].is_home and own[j] != me)) for j in range(64)]
    values = [upgrades[j] if own[j] == me else captures[j] for j in range(64)]
    stays = [3 if own[j] == me else work[j] for j in range(64)]
    estimates = {}

    def potential(i, progress, owned, upgraded):
        key = (i,progress,owned,upgraded)
        cached = estimates.get(key)
        if cached is not None:
            return cached
        if shortlist[i] is None:
            options = [(values[j]/(distance+stays[j]),j) for j,distance in NEAR[i] if available[j]]
            shortlist[i] = tuple(j for _,j in nlargest(4,options))
        best = 0.
        for j in shortlist[i]:
            bit = BITS[j]
            if upgraded & bit:
                continue
            ours = owned & bit
            cost = (3 if ours else work[j]) + DIST[i][j] - (progress if i == j else 0)
            estimate = (upgrades[j] if ours else captures[j]) / max(1, cost)
            if estimate > best:
                best = estimate
        # Give partial captures and upgrades credit even on newly held cells.
        if owned & BITS[i] and not upgraded & BITS[i]:
            best = max(best, upgrades[i]/(3-progress))
        estimates[key] = best
        return best

    shield_value = 0.
    if "SHIELD" in legal:
        miss = 1.
        for s in rivals:
            i = pos[s]
            if own[i] == me and not cells[i].is_frozen and not cells[i].is_home:
                catch = memory["stay_hits"][s][lvl[i]] / memory["stay_trials"][s][lvl[i]]
                miss *= 1-catch
                shield_value += catch*(base[i]*(1+lvl[i])*(min(left, 9) + 8*denied[s])
                                        + min(3, left)*3*denied[s])
        shield_value = shield_value*config["defense"] - 2*miss*min(left, 8)

    # A node stores its exact hypothetical ownership, upgrades and stay progress.
    # Dominance is by cumulative reward at identical state and simulated time.
    frontier = [(0., start, memory["progress"], init_own, init_upgrade, "STAY")]
    for step in range(1, depth+1):
        layer = {}
        discount = discount_rate**(step-1)
        remaining = left-step+1
        for reward, i, progress, owned, upgraded, first in frontier:
            bit = BITS[i]
            candidates = []
            ours = owned & bit
            if not upgraded & bit and (ours or (captures[i] and not cells[i].is_home)):
                cost = 3 if ours else work[i]
                risk = (p_shield[own[i]] if not ours and own[i]
                        and memory["cooldown"][own[i]] < step + cost-progress-1 else 0.)
                if progress+1 >= cost:
                    if ours:
                        gain = min(upgrades[i], upgrade_weight*base[i]*remaining)
                        candidates.append((i, 0, owned, upgraded | bit, "STAY", gain))
                    else:
                        maxgain = remaining*base[i]
                        if own[i]:
                            maxgain += (1+lvl[i])*base[i]*(8+denied[own[i]]*remaining)
                        gain = min(captures[i], maxgain) * (1-risk*(.95 if lvl[i] else .54))
                        candidates.append((i, 0, owned | bit, upgraded, "STAY", gain))
                else:
                    candidates.append((i, progress+1, owned, upgraded, "STAY", -risk*6))
            if step == 1 and shield_value > 0:
                candidates.append((i, 0, owned, upgraded, "SHIELD", shield_value))
            for j, action in ADJ[i]:
                if (step <= 2 and j in occupied) or (step == 1 and action not in legal):
                    continue
                penalty = 0.
                if step == 1 and pressure[j] == 1 and own[j] != me and not state.is_priority_token:
                    penalty = 4.
                candidates.append((j, 0, owned, upgraded, action, -penalty))
            if not candidates:
                candidates.append((i, 0, owned, upgraded, "STAY", 0.))
            for j, pr, o, u, act0, increment in candidates:
                total = reward+discount*increment
                key = (j, pr, o, u)
                prior = layer.get(key)
                if prior is None or total > prior[0]:
                    layer[key] = (total, j, pr, o, u, act0 if step == 1 else first)
        horizon_weight = (.78 if step < depth else .50) if step < left else 0.
        def rank(item):
            score,j,pr,o,u,_ = item
            return score + guidance*horizon_weight*discount*potential(j, pr, o, u)
        frontier = nlargest(width, layer.values(), key=rank)
    return frontier[0][-1] if frontier else "STAY"
