"""Local rival forecasting and explicit simultaneous-action evaluation for Zone Rush."""
from collections import deque
from itertools import product
from math import exp

DEFAULT_CONFIG = dict(upgrade=1.85, raid=.95, hazard=2.6, defense=1.10,
                      tactical=1.0, downside=.12, retention=1.0, continuation=.24)
BOUNDS = dict(upgrade=(.7,3.4), raid=(.35,1.65), hazard=(.1,5.0),
              defense=(.15,2.7), tactical=(.2,2.4), downside=(0.,.6),
              retention=(.5,1.6), continuation=(0.,.8))
CONFIG = DEFAULT_CONFIG.copy()
NAMES = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
STAY, SHIELD = 4, 5
ADJ = []
DIST = []
for p in range(64):
    r, c = divmod(p, 8)
    ADJ.append(tuple((k, x*8+y) for k,(x,y) in enumerate(
        ((r-1,c),(r,c+1),(r+1,c),(r,c-1))) if 0 <= x < 8 and 0 <= y < 8))
    DIST.append(tuple(abs(r-j//8)+abs(c-j%8) for j in range(64)))
_history = {}


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


def _economy(seat, cells, pos, owner, level, pressure, frozen, hist, left, own_progress, cfg):
    """Best accessible project for each distinct first direction, allowing ties."""
    at = pos[seat]
    occupied = set(pos[1:])
    distance = [99]*64
    first = [0]*64
    distance[at] = 0
    queue = deque([at])
    while queue:
        i = queue.popleft()
        for a, j in ADJ[i]:
            if j in occupied or distance[j] < distance[i]+1:
                continue
            mask = 1 << a if i == at else first[i]
            if distance[j] == 99:
                queue.append(j)
                distance[j] = distance[i]+1
            first[j] |= mask
    rates = [-1e5]*6
    rates[STAY] = 0.
    for a, j in ADJ[at]:
        if j not in occupied:
            rates[a] = -.1
    prizes = [0.]*64
    costs = [0.]*64
    for i,c in enumerate(cells):
        owner_i = owner[i]
        mine = owner_i == seat
        if distance[i] >= left or (mine and level[i]) or (c.is_home and not mine):
            continue
        stays = 3 if mine or level[i] else 1
        needs = max(1, stays - own_progress) if i == at else stays
        cost = distance[i]+needs
        if cost > left:
            continue
        retention = (90 if c.is_home else (18+pressure[i]*4.2)*cfg["retention"])
        life = min(left-cost+1, retention)
        value = c.base_points*life
        extra = 0.
        if mine:
            value *= cfg["upgrade"]
        elif owner_i:
            rival_level = 1+level[i]
            value = cfg["raid"] * c.base_points*(life*(1+.49*rival_level)+8*rival_level)
            if hist["cooldown"][owner_i] < cost and (not frozen[owner_i] or cost > 1):
                p = hist["defense_hits"][owner_i]/hist["defense_trials"][owner_i]
                exposure = cfg["hazard"]*p
                # Immediate catches are modeled in joint action resolution.
                if i == at and not level[i]:
                    exposure *= .25
                value /= 1+exposure*(.48 if level[i] else .17)
                extra = exposure*(2.8 if level[i] else 1.6)
        prizes[i] = value
        costs[i] = needs+extra
    for i, value in enumerate(prizes):
        if not value:
            continue
        travel = distance[i]
        rating = value / (travel + costs[i])
        if cfg["continuation"] and travel+costs[i]+2 < left:
            # A productive second step rewards entry into contiguous rich land.
            next_value = max((prizes[j]/(1+costs[j]) for _,j in ADJ[i] if j != at),
                             default=0.)
            if owner[i] != seat:
                next_value = max(next_value, cells[i].base_points*cfg["upgrade"]
                                 *min(left-travel-3,22+3*pressure[i])/3)
            rating += cfg["continuation"]*next_value/(1+.12*travel)
        if i == at:
            rates[STAY] = max(rates[STAY],rating)
        else:
            mask = first[i]
            for a in range(4):
                if mask & (1<<a):
                    rates[a] = max(rates[a],rating)
    return rates


def _forecast(seat, rates, pos, cells, owner, level, frozen, hist):
    if frozen[seat]:
        return ((STAY,1.),)
    at = pos[seat]
    top = max(rates[:5])
    scale = max(1.6,.21*top)
    weights = [exp((v-top)/scale) if v>=-.1 else 0. for v in rates[:5]]
    total = sum(weights)
    probs = [w/total for w in weights]
    if owner[at] not in (0,seat) and not cells[at].is_home:
        # Escaping an expected shield is an explicit alternative to a raid.
        tier = level[at]
        observed = hist["stay_hits"][seat][tier]/hist["stay_trials"][seat][tier]
        if hist["cooldown"][owner[at]] == 0 and not frozen[owner[at]]:
            stay = .55*probs[STAY]+.45*observed
            moving = sum(probs[:4])
            if moving > 0:
                probs = [x*(1-stay)/moving for x in probs[:4]]+[stay]
    p_shield = 0.
    if hist["cooldown"][seat] == 0:
        for victim in range(1,5):
            i = pos[victim]
            if victim == seat or owner[i] != seat or frozen[victim] or cells[i].is_home:
                continue
            propensity = hist["defense_hits"][seat]/hist["defense_trials"][seat]
            if level[i]:
                propensity *= (.69, .90, 1.28)[hist["enemy_progress"][victim]]
            p_shield = max(p_shield, min(.95,propensity))
    probs = [(1-p_shield)*p for p in probs]+[p_shield]
    order = sorted(range(6), key=probs.__getitem__,reverse=True)
    a,b = order[:2]
    z = probs[a]+probs[b]
    if probs[b] < .05:
        return ((a,1.),)
    return ((a,probs[a]/z),(b,probs[b]/z))


def _resolve(actions, destinations, pos, owner, frozen, token):
    """Resolve a shared action profile without observing anyone's real current action."""
    actual = list(actions)
    targets = [destinations[s].get(actions[s],pos[s]) for s in range(5)]
    for s in range(1,5):
        if actual[s]>=STAY:
            continue
        t = targets[s]
        group = [k for k in range(s+1,5) if targets[k]==t and actual[k]<STAY]
        if group:
            group.append(s)
            holder = owner[t]
            winner = holder if holder in group else min(group,key=lambda k:(k-token)%4)
            for k in group:
                if k!=winner:
                    actual[k]=STAY
    caught = [False]*5
    hits = [0]*5
    for s in range(1,5):
        defender = owner[pos[s]]
        if (not frozen[s] and actual[s] == STAY and defender not in (0,s)
                and actual[defender] == SHIELD):
            caught[s] = True
            hits[defender] += 1
    return actual,caught,hits


def act(state):
    me = state.bot_id
    cells = [c for row in state.board for c in row] if len(state.board)==8 else state.board
    pos, frozen, income = [-1]*5,[False]*5,[0]*5
    owner = [c.owner for c in cells]
    level = [int(c.is_upgraded) for c in cells]
    for i,c in enumerate(cells):
        if c.occupant:
            pos[c.occupant] = i
            frozen[c.occupant] = c.is_frozen
        income[c.owner] += c.base_points*(1+level[i])
    legal = [NAMES.index(a) for a in state.legal_actions]
    hist = _observe(me,cells,pos,owner,level,frozen,SHIELD in legal)
    hist["can_shield"] = SHIELD in legal
    prior = hist.get("possible_token")
    possible = {s%4+1 for s in prior} if prior else set(range(1,5))
    possible = {me} if state.is_priority_token else (possible-{me} or set(range(1,5))-{me})
    hist["possible_token"] = possible
    answer = legal[0] if len(legal)==1 else _choose(
        me,cells,pos,owner,level,frozen,income,legal,hist,possible)
    hist["last"] = NAMES[answer]
    return NAMES[answer]


def _choose(me,cells,pos,owner,level,frozen,income,legal,hist,tokens):
    cfg = CONFIG
    left = 81-hist["turn"]
    opponents = [s for s in range(1,5) if s!=me]
    rates = [None]*5
    probs = []
    prog = hist["enemy_progress"][:]
    prog[me] = hist["progress"]
    for s in range(1,5):
        rivals = [DIST[pos[k]] for k in range(1,5) if k!=s]
        pressure = [min(values) for values in zip(*rivals)]
        # Rival model is fixed; evolved preferences do not leak into opponents.
        rates[s] = _economy(s,cells,pos,owner,level,pressure,frozen,hist,left,prog[s],
                            cfg if s==me else DEFAULT_CONFIG)
    for s in opponents:
        probs.append(_forecast(s,rates[s],pos,cells,owner,level,frozen,hist))
    destinations = [{}]+[dict(ADJ[pos[s]]) for s in range(1,5)]
    tempo = [0.]+[max(2.,min(35.,max(rates[s][:5]))) for s in range(1,5)]
    weights = [0.]*5
    for s in opponents:
        gap = abs(hist["scores"][me]+min(15,left)*income[me]-
                  hist["scores"][s]-min(15,left)*income[s])
        weights[s] = .17+.46/(1+gap/(50+left*3))
    mean = [0.]*6
    worst = [0.]*6
    for profile in product(*probs):
        acts=[STAY]*5
        chance=1.
        for s,(a,p) in zip(opponents,profile):
            acts[s]=a
            chance*=p
        for token in tokens:
            pay=[]
            for candidate in legal:
                acts[me]=candidate
                actual,caught,hits=_resolve(acts,destinations,pos,owner,frozen,token)
                worth=[0.]*5
                delta=[0.]*5
                harm=0.
                for s in range(1,5):
                    if frozen[s]:
                        continue
                    i=pos[s]
                    land=owner[i]
                    a=actual[s]
                    if a==SHIELD:
                        if not hits[s]:
                            worth[s]=-.84*tempo[s]*min(2,left-1)
                        continue
                    if caught[s]:
                        worth[s]=-.90*tempo[s]*min(2,left-1)
                        continue
                    worth[s]=rates[s][a]
                    if a!=STAY:
                        continue
                    if land==s:
                        if not level[i] and prog[s]>=2:
                            delta[s]+=cells[i].base_points
                    elif not cells[i].is_home and (not level[i] or prog[s]>=2):
                        base=cells[i].base_points
                        delta[s]+=base
                        if land:
                            units=base*(1+level[i])
                            delta[s]+=8*units
                            delta[land]-=units
                            if land==me:
                                harm+=cfg["defense"]*units*(min(left,5)+8*weights[s])
                    elif land==me and level[i] and not cells[i].is_home:
                        # Preventing progress on an upgraded holding also matters.
                        harm+=cfg["defense"]*cells[i].base_points*(2+3*prog[s])
                if left==1 and hist["known_start"]:
                    final=[hist["scores"][s]+income[s]+delta[s] for s in range(5)]
                    credit=sum((final[me]>final[s])+.5*(final[me]==final[s]) for s in opponents)
                    utility=10000*credit+delta[me]-sum(weights[s]*delta[s] for s in opponents)
                else:
                    interference=sum(weights[s]*worth[s] for s in opponents)
                    utility=worth[me]-cfg["tactical"]*(interference+harm)
                pay.append(utility)
            best=max(pay)
            for a,u in zip(legal,pay):
                regret=best-u
                mean[a]+=chance*regret/len(tokens)
                worst[a]=max(worst[a],regret)
    downside=cfg["downside"]
    return min(legal,key=lambda a:(1-downside)*mean[a]+downside*worst[a])


