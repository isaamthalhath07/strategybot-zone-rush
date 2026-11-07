"""
Fusion: the strongest planner from the four branches, wrapped in every failsafe
any of them had, plus the ones none of them had.

    econ.Econ      research/evolution's economic planner -- the PRIMARY. On the
                   cross-author field (crossfield/xfield.py, 1,200 fresh paired
                   games) it beats every other branch's bot: +0.215 PW over main's
                   v7 (z = +8.0), +0.233 over v7-independent-field's (z = +8.5),
                   and it is never worse against any author's opponents.
    mybot.Agent    hardened-field-and-fixes' tracker and walk planner -- the WARM
                   STANDBY. Its tracker is updated every turn, so it can take over
                   mid-game with a correct picture of the board; it is the better
                   planner after a cold start (2462 vs 1803 points when module
                   memory is lost every turn), and its exact shield-attribution
                   solver supplies my own cooldown.
    _fallback      a policy with almost no dependencies, for when both raise.
    STAY           only if everything above raised.

Layers, each guarding against a way the real server could differ from the three
local referees (which agree with each other exactly over 32,000 turns, but none
of which is the organisers' server):

  1. Input normalisation. Any board shape (8x8 rows, flat 64, tuples, namedtuple
     cells, dict cells), int-or-string-or-bool fields, a string bot_id, a missing
     token flag, and legal actions as upper/lower-case strings or Enum-like
     objects. The returned action is always an element of the list the server
     handed over, in that list's own type.
  2. Planner isolation. Each planner is called under its own try/except. One
     that raises is replaced by the next on the same turn, so no turn is lost;
     one that raises twice in a game is retired for the rest of it.
  3. A fresh, independent planner state for every game, detected from the board
     itself rather than a turn counter. Positions revert in an opening, so they
     prove nothing; ownership and upgrades never revert within a game, so a
     starting board is a new game only once a capture or an upgrade has been
     seen (or 80 turns have passed).
  4. Cold-start rescue. If the module wakes up mid-game with no memory, the walk
     planner (which reconstructs from the board alone) plays that first turn,
     and the economic planner is handed the tracker's fitted turn estimate
     (median error 5 turns, against 9 for its own). Measured: after a single
     restart this recovers as well as any setting tried; if memory is lost on
     every turn it holds 96% of normal score, where the economic planner alone
     holds 88%.
  5. Shield sanity. A SHIELD the tracker knows to be on cooldown is never sent,
     unless the server has shown it removes SHIELD from legal_actions during
     cooldown (then legal_actions is authoritative).
  6. Direction calibration. Every move's observed displacement, and every legal
     list (a listed move that would leave the board), is checked against the
     documented NORTH = row - 1 convention. If the server's frame is a rotation
     or reflection of the documented one (three or more contradictions and an
     alternative with none), moves are translated. With the documented
     convention this layer never changes an action; against a server with NORTH
     and SOUTH swapped it recovers the full score.
  7. Unpredictable mixing. The walk planner mixes its shield decision with a
     random draw; on the server that draw is seeded from the clock, so a rival
     reading this public source cannot replay it. Measurement pins the seed.
  8. (Built, measured, and switched OFF.) Predicting exact copies of the public
     bots. Identification proved unsafe -- see FLAGS["mirror"].

On the documented interface none of this changes a single move: the shipped
file plays identically to research/evolution's bot (crossfield/test_econ.py,
and 0.0000 +/- 0.0000 over 1,200 paired games). What it changes is everything
else: every variant in crossfield/robustness.py, where each other branch's bot
falls to the skeleton's score on five or six of them.

Nothing here prints, reads files, or imports beyond the standard library.
"""

from collections import deque
import time


# ==========================================================================
# econ.py -- research/evolution's economic planner (primary)
# ==========================================================================
E_DEFAULT = {
    'upgrade_open': 2.25, 'upgrade_late': 2.25, 'raid_open': 0.99, 'raid_late': 0.99,
    'risk_open': 4.0, 'risk_late': 4.0, 'income_lifetime': 18.0, 'safety_slope': 6.0,
    'fortify_premium': 1.16, 'denial_base': 0.27, 'denial_close': 0.43,
    'cash_weight': 1.0, 'contest_cost': 1.0, 'depth': 2, 'breadth': 9,
    'route_weight': 0.5, 'route_delay': 0.11, 'inertia': 0.0, 'shield_weight': 1.0,
    'backfire_cost': 2.0, 'shield_prior': 0.3333333333333333, 'stay_prior': 0.76,
    'feint_weight': 1.0,
}
# The research branch's recommended genome (bot_evolved.py).
E_EVOLVED = {
    'backfire_cost': 1.13552, 'breadth': 7, 'cash_weight': 1.25275,
    'contest_cost': 0.42039, 'denial_base': 0.66671, 'denial_close': 0.20084,
    'depth': 2, 'feint_weight': 1.25119, 'fortify_premium': 1.11474,
    'income_lifetime': 40.67114, 'inertia': 0.0496, 'raid_late': 1.64117,
    'raid_open': 0.95839, 'risk_late': 8.0, 'risk_open': 1.97775, 'route_delay': 0.02,
    'route_weight': 0.61979, 'safety_slope': 3.52153, 'shield_prior': 0.33333,
    'shield_weight': 1.30296, 'stay_prior': 0.76, 'upgrade_late': 3.3705,
    'upgrade_open': 1.46008,
}
# Its second-run finalist (bot_transfer_candidate.py): only these keys differ.
E_TRANSFER = dict(E_EVOLVED, denial_base=0.79149, depth=3, raid_late=1.65061,
                  safety_slope=0.0, stay_prior=0.69484, upgrade_late=4.5)

E_FLAGS = {"sym": 0}

_E_NAMES = ("NORTH", "EAST", "SOUTH", "WEST")
_E_ADJ = []
_E_DIST = []
for _ei in range(64):
    _er, _ec = divmod(_ei, 8)
    _E_ADJ.append(tuple((name, r * 8 + c) for name, r, c in (
        ("NORTH", _er - 1, _ec), ("EAST", _er, _ec + 1),
        ("SOUTH", _er + 1, _ec), ("WEST", _er, _ec - 1)) if 0 <= r < 8 and 0 <= c < 8))
    _E_DIST.append(tuple(abs(_er - j // 8) + abs(_ec - j % 8) for j in range(64)))

# Each seat's own frame: seat 1 (0,0), 2 (0,7), 3 (7,7), 4 (7,0). _E_CANON[s][p] is
# cell p's index as seat s sees it; _E_CANON_ACT[s][a] is action a's name in that
# frame. Used only to break exact ties the same way in every corner.
_E_CANON = [None] * 5
_E_CANON_ACT = [None] * 5
for _es in range(1, 5):
    _fr, _fc = _es in (3, 4), _es in (2, 3)
    _E_CANON[_es] = [((7 - p // 8) if _fr else p // 8) * 8 + ((7 - p % 8) if _fc else p % 8)
                     for p in range(64)]
    _E_CANON_ACT[_es] = {"NORTH": "SOUTH" if _fr else "NORTH",
                         "SOUTH": "NORTH" if _fr else "SOUTH",
                         "EAST": "WEST" if _fc else "EAST",
                         "WEST": "EAST" if _fc else "WEST"}


def _e_paths(origin, occupied, legal, cells, me, priority, rivals, sym=0):
    """Shortest routes respecting closed cells and current legal first moves."""
    travel = [90] * 64
    first = [None] * 64
    travel[origin] = 0
    queue = deque()
    # The first neighbour inserted wins equal-distance paths. Prefer a safe first move.
    choices = []
    for action, target in _E_ADJ[origin]:
        if action in legal and target not in occupied:
            risk = sum(_E_DIST[p][target] == 1 for p in rivals)
            if cells[target].owner == me:
                risk = 0
            elif priority and cells[target].owner == 0:
                risk = 0
            name = _E_CANON_ACT[me][action] if sym else action
            choices.append((risk, name, action, target))
    for _, _n, action, target in sorted(choices):
        travel[target], first[target] = 1, action
        queue.append(target)
    while queue:
        here = queue.popleft()
        for _, there in _E_ADJ[here]:
            if travel[there] == 90 and there not in occupied:
                travel[there], first[there] = travel[here] + 1, first[here]
                queue.append(there)
    return travel, first


def _e_terminal(legal, cells, me, at, progress):
    """A dominating replacement for STAY on the final turn, or None."""
    if "SHIELD" not in legal:
        return None
    here = cells[at]
    if here.owner == me:
        can_score_by_staying = not here.is_upgraded and progress >= 2
    else:
        can_score_by_staying = not here.is_home and (
            not here.owner or not here.is_upgraded or progress >= 2)
    if can_score_by_staying:
        return None
    # A shield protects every holding even if it only encounters already
    # frozen rivals. A resulting backfire costs no scoring turns after turn 80.
    threatened = any(cell.owner == me and not cell.is_home
                     and cell.occupant and cell.occupant != me for cell in cells)
    return "SHIELD" if threatened else None


class Econ(object):
    """One seat's economic planner for one game. Call step() once per turn."""

    def __init__(self, config=None, flags=None):
        self.cfg = dict(E_DEFAULT)
        self.cfg.update(E_EVOLVED if config is None else config)
        self.flags = dict(E_FLAGS)
        if flags:
            self.flags.update(flags)
        self.mem = None
        self.target = None

    # -- memory -------------------------------------------------------------
    def observe(self, me, cells, positions, owner, level, frozen, can_shield):
        """Infer elapsed turns, progress, score and opponent cooldown."""
        config = self.cfg
        old = self.mem
        pristine = all(pos >= 0 and cells[pos].is_home and owner[pos] == seat
                       for seat, pos in enumerate(positions) if seat)
        pristine = pristine and sum(bool(v) for v in owner) == 4 and not any(level)
        # After a capture the total number of owned cells cannot drop back to
        # four. An upgraded home cannot revert either. Positions alone can reset
        # to their starting pattern during a perfectly ordinary opening.
        if old is None or (pristine and (old["turn"] >= 80 or any(old["level"])
                                         or sum(bool(v) for v in old["owner"]) > 4)):
            occupied = sum(bool(v) for v in owner) - 4
            # A fresh interpreter mid-match still decides from the visible board.
            turn = 1 if pristine else min(67, max(2, 2 + occupied + sum(level)))
            old = {"turn": turn, "known_start": pristine, "scores": [0] * 5,
                   "progress": 0, "positions": positions, "owner": owner,
                   "level": level, "frozen": frozen, "last": None,
                   "stay_trials": [[2., 2.] for _ in range(5)],
                   "stay_hits": [[2 * config["stay_prior"], 1.16] for _ in range(5)],
                   "can_shield": False, "enemy_progress": [0] * 5,
                   "defense_trials": [3.0] * 5, "defense_hits": [1.20] * 5,
                   "last_bait": -10, "cooldown": [0] * 5,
                   "stops": [3 * config["shield_prior"]] * 5, "attempts": [3.0] * 5,
                   "new_game": True}
        else:
            old["new_game"] = False
            old["turn"] = min(old["turn"] + 1, 80)
            cooldown = [max(0, c - 1) for c in old["cooldown"]]
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
                    if (frozen[seat] and not frozen[defender]
                            and prior_pos[defender] == positions[defender]):
                        just_shielded.add(defender)
                        old["stops"][defender] += 1
                        old["attempts"][defender] += 1
                    elif owner[spot] == seat:
                        old["attempts"][defender] += 1
                if frozen[seat] and not old["frozen"][seat] and defender in (0, seat):
                    just_shielded.add(seat)  # Clearly a shield backfire.
            opportunities = set()
            for seat in range(1, 5):
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
                    old["stay_hits"][seat][tier] = (0.94 * old["stay_hits"][seat][tier]
                                                    + weight * stayed)
                    old["stay_trials"][seat][tier] = (0.94 * old["stay_trials"][seat][tier]
                                                      + weight)
            for defender in opportunities:
                old["defense_hits"][defender] = (.93 * old["defense_hits"][defender]
                                                 + (defender in just_shielded))
                old["defense_trials"][defender] = .93 * old["defense_trials"][defender] + 1
            for seat in range(1, 5):
                p = positions[seat]
                continuing = (p >= 0 and p == prior_pos[seat] and seat not in just_shielded
                              and not frozen[seat] and not old["frozen"][seat] and
                              owner[p] == prior_owner[p] and level[p] == old["level"][p])
                old["enemy_progress"][seat] = (min(2, old["enemy_progress"][seat] + 1)
                                               if continuing else 0)
            for defender in just_shielded:
                cooldown[defender] = 4
            old["cooldown"] = cooldown
            spot = positions[me]
            continued = (spot == prior_pos[me] and not own_shield
                         and not old["frozen"][me] and not frozen[me]
                         and prior_owner[spot] == owner[spot]
                         and old["level"][spot] == level[spot])
            old["progress"] = min(2, old["progress"] + 1) if continued else 0
            for i, seat in enumerate(owner):
                if seat:
                    value = cells[i].base_points
                    old["scores"][seat] += value * (1 + level[i])
                    if prior_owner[i] and prior_owner[i] != seat:
                        old["scores"][seat] += 8 * value * (1 + old["level"][i])
        old.update(positions=positions, owner=owner, level=level, frozen=frozen)
        self.mem = old
        return old

    # -- one turn ----------------------------------------------------------------
    def step(self, cells, me, legal, priority, ext_cooldown=None, turn_hint=None):
        """cells: 64 cell objects; legal: action names. Returns an action name.

        ext_cooldown, if given, replaces this planner's own estimate of each
        rival's shield cooldown (index = seat) after it has observed the turn.
        turn_hint, if given, replaces the turn this planner guesses when it wakes
        up with no memory on a board that is not a starting board.
        """
        owner = [c.owner for c in cells]
        level = [int(c.is_upgraded) for c in cells]
        pos, frozen, income = [-1] * 5, [False] * 5, [0] * 5
        for i, c in enumerate(cells):
            if c.occupant:
                pos[c.occupant], frozen[c.occupant] = i, c.is_frozen
            income[c.owner] += c.base_points * (1 + level[i])
        at = pos[me]
        if at < 0:
            return "STAY" if "STAY" in legal else legal[0]
        can_shield = "SHIELD" in legal
        config = self.cfg
        sym = self.flags["sym"]
        memory = self.observe(me, cells, pos, owner, level, frozen, can_shield)
        memory["can_shield"] = can_shield
        if turn_hint is not None and memory["new_game"] and not memory["known_start"]:
            memory["turn"] = max(1, min(80, int(turn_hint)))
        if ext_cooldown is not None:
            for s in range(1, 5):
                if s != me:
                    memory["cooldown"][s] = ext_cooldown[s]
        if len(legal) == 1:
            memory["last"] = legal[0]
            return legal[0]

        left = 81 - memory["turn"]
        # Interpolate open/late priorities without discontinuities at a fixed turn.
        phase = (memory["turn"] - 1) / 79
        upgrade = config["upgrade_open"] + phase * (config["upgrade_late"] - config["upgrade_open"])
        raid = config["raid_open"] + phase * (config["raid_late"] - config["raid_open"])
        risk_weight = config["risk_open"] + phase * (config["risk_late"] - config["risk_open"])
        depth = min(3, max(1, round(config["depth"])))
        breadth = min(12, max(1, round(config["breadth"])))
        route_weight = config["route_weight"] if depth > 1 else 0.
        feint_weight = config["feint_weight"]
        enemies = [i for i in range(1, 5) if i != me and pos[i] >= 0]
        occupied = {pos[i] for i in enemies}
        travel, first = _e_paths(at, occupied, legal, cells, me, priority, occupied, sym)
        rival_ranges = [_E_DIST[p] for p in occupied]
        pressure = [min(x) for x in zip(*rival_ranges)] if occupied else [12] * 64

        projection = [memory["scores"][i] + min(left, 18) * income[i] for i in range(5)]
        # A point denied matters most against a rival near our predicted finish.
        denial = [0.0] * 5
        for seat in enemies:
            gap = abs(projection[me] - projection[seat])
            denial[seat] = config["denial_base"] + config["denial_close"] / (1 + gap / (65 + left * 3))
        exposure = [min(0.87, 0.08 + 1.30 * memory["stops"][i] / memory["attempts"][i])
                    for i in range(5)]

        # One macro-action ends at a capture or completed upgrade.
        tie = _E_CANON[me] if sym else None
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
            retention = config["income_lifetime"] + min(5, nearest) * config["safety_slope"]
            if c.is_home:
                retention = 100
            life = min(left - cost + 1, retention)
            if who == me:
                reward = v * life * upgrade
                if not c.is_home:
                    reward *= config["fortify_premium"]
            elif who == 0:
                reward = v * life
            else:
                reward = raid * v * (life * (1 + denial[who] * (1 + up))
                                     + 8 * config["cash_weight"] * (1 + up))
            risk = 0
            if who not in (me, 0):
                if memory["cooldown"][who] < cost and (not frozen[who] or cost > 1):
                    risk = exposure[who] * risk_weight
                    if up:
                        risk *= 1.4
                    reward /= 1.0 + risk * (0.65 if up else 0.18)
            effort = work + risk * (3.5 if up else 2.4)
            # Entering a contested cell is less attractive when the owner could too.
            if i != at and nearest <= travel_time and who != me:
                effort += config["contest_cost"] * (0.40 if nearest <= 1 else 0.18)
            rate = reward / (travel_time + effort)
            if config["inertia"] and i == memory.get("prior_target"):
                rate *= 1 + config["inertia"]
            # The raw tuple breaks rate ties by cell index; the symmetric key
            # breaks them in this seat's own frame instead.
            key = i if tie is None else (-tie[i] if sym > 0 else tie[i])
            tasks.append((rate, key, i, effort, reward, cost, work))

        tasks.sort(reverse=True)
        best_value, best_action = -1.0, "STAY" if "STAY" in legal else legal[0]
        chosen_cell = None
        for rate, _k, i, effort, reward, cost, work in tasks[:breadth]:
            next_rate = 0.0
            if cost < left - 1 and route_weight:
                dists = _E_DIST[i]
                second = None
                second_cost = 0
                for _, _k2, j, effort2, reward2, _, work2 in tasks:
                    if i == j:
                        continue
                    between = dists[j]
                    # Progress on the original cell disappears upon moving away.
                    extra = memory["progress"] if j == at else 0
                    if cost + between + work2 + extra <= left:
                        candidate = reward2 / (between + effort2 + extra)
                        if candidate > next_rate:
                            next_rate, second, second_cost = candidate, j, between + work2 + extra
                if owner[i] != me and cost + 3 <= left:
                    postcapture = min(left - cost - 2, config["income_lifetime"]
                                      + min(5, pressure[i]) * config["safety_slope"])
                    candidate = cells[i].base_points * postcapture * upgrade / 3
                    if candidate > next_rate:
                        next_rate, second, second_cost = candidate, i, 3
                # Depth three follows the best second job, then scores a distinct
                # third capture or upgrade. Each job earns its marginal value once.
                if depth == 3 and second is not None and cost + second_cost < left - 1:
                    third_rate = 0.
                    from_second = _E_DIST[second]
                    for _, _k3, k, effort3, reward3, _, work3 in tasks:
                        if k in (i, second):
                            continue
                        between = from_second[k]
                        extra = memory["progress"] if k == at else 0
                        if cost + second_cost + between + work3 + extra <= left:
                            third_rate = max(third_rate, reward3 / (between + effort3 + extra))
                    next_rate += route_weight * third_rate / (1 + config["route_delay"] * (second_cost - 1))
            # Distant clusters contribute less until we have completed the first job.
            value = rate + route_weight * next_rate / (1 + config["route_delay"] * (cost - 1))
            if value > best_value:
                best_value, best_action = value, ("STAY" if i == at else first[i])
                chosen_cell = i
        memory["prior_target"] = chosen_cell
        self.target = chosen_cell
        # kept for a controller that may need this turn's second-best move
        self.last_tasks, self.last_travel, self.last_first = tasks, travel, first

        # Escape a predicted shield only when there is a productive neighbouring
        # target. This keeps a feint from becoming an endless shuttle.
        defender = owner[at]
        if (feint_weight and best_action == "STAY" and defender not in (0, me)
                and not cells[at].is_home and not frozen[defender] and
                memory["cooldown"][defender] == 0 and memory["turn"] - memory["last_bait"] >= 5
                and left > 2 and memory["progress"] == 0):
            response = memory["defense_hits"][defender] / memory["defense_trials"][defender]
            exits = []
            for _, _k, i, effort, reward, _, _ in tasks:
                if travel[i] == 1:
                    # A comparable job on the same opponent's land benefits from
                    # the entire cooldown if they fire into the empty square.
                    bonus = 1.25 if owner[i] == defender else 0.95
                    exits.append((reward * bonus / (effort + 1), first[i]))
            if exits and response * feint_weight > .43:
                alternative, action = max(exits)
                if alternative * (1 + 1.3 * response * feint_weight) > tasks[0][0]:
                    best_action = action
                    memory["last_bait"] = memory["turn"]
        self.pre_shield = best_action
        if "SHIELD" in legal:
            # We can freeze several raiders, but slowing one costs development.
            threat = 0.0
            miss = 1.0
            for s in enemies:
                i = pos[s]
                if owner[i] != me or frozen[s] or cells[i].is_home:
                    continue
                tier = level[i]
                chance = memory["stay_hits"][s][tier] / memory["stay_trials"][s][tier]
                if tier:
                    # Two uneventful stays reveal commitment and a live takeover.
                    progress = memory["enemy_progress"][s]
                    chance *= (.21, .53, 1.18)[progress]
                    if progress + left < 3:
                        chance *= .25
                chance = min(.97, max(.04, chance))
                immediate = cells[i].base_points * (1 + level[i])
                threat += chance * (immediate * (min(left, 5 if not level[i] else 10)
                                                 + 8 * denial[s]) + min(left, 3) * 4 * denial[s])
                miss *= 1 - chance
            normal_rate = tasks[0][0] if tasks else 0.0
            if threat and config["shield_weight"] * threat > (1 + config["backfire_cost"] * miss) * max(1.0, 0.49 * normal_rate):
                best_action = "SHIELD"
        if best_action == "STAY" and left == 1 and memory["known_start"]:
            terminal = _e_terminal(legal, cells, me, at, memory["progress"])
            if terminal is not None:
                best_action = terminal
        if best_action not in legal:
            best_action = "STAY" if "STAY" in legal else legal[0]
        memory["last"] = best_action
        return best_action


# ==========================================================================
# mybot.py -- hardened-field-and-fixes' tracker and walk planner (warm standby)
# ==========================================================================
N = 8
NC = 64
MOVE_DELTA = (("NORTH", -8), ("SOUTH", 8), ("WEST", -1), ("EAST", 1))
CORNERS = (0, 7, 63, 56)
MAX_TURNS = 80

NEIGH = []
for _p in range(NC):
    _r, _c = divmod(_p, N)
    _a = []
    if _r > 0:
        _a.append(_p - N)
    if _r < N - 1:
        _a.append(_p + N)
    if _c > 0:
        _a.append(_p - 1)
    if _c < N - 1:
        _a.append(_p + 1)
    NEIGH.append(tuple(_a))

STEP_NAME = {}
for _p in range(NC):
    for _nm, _d in MOVE_DELTA:
        _q = _p + _d
        if _q in NEIGH[_p]:
            STEP_NAME[(_p, _q)] = _nm

# Cell p's index as seen from each seat's own corner. The board is four-fold
# mirrored, so seat 1 at (0,0), seat 2 at (0,7), seat 3 at (7,7) and seat 4 at
# (7,0) see geometrically identical games -- but only if the bot's own
# tie-breaking is expressed in its own frame. It was not: equal-priority cells
# were ordered by raw cell index, which always favours the bottom-right, so
# seats 3 and 4 broke ties toward their own homes and seats 1 and 2 broke them
# away. In self-play, where symmetry fixes every seat at 1.50 pairwise wins, that
# showed up as 1.37 / 1.48 / 1.56 / 1.59.
CANON = [None] * 5
for _s in range(1, 5):
    _flip_r = _s in (3, 4)
    _flip_c = _s in (2, 3)
    _t = [0] * NC
    for _p in range(NC):
        _r, _c = divmod(_p, N)
        if _flip_r:
            _r = N - 1 - _r
        if _flip_c:
            _c = N - 1 - _c
        _t[_p] = _r * N + _c
    CANON[_s] = _t

MANH = [[0] * NC for _ in range(NC)]
for _a in range(NC):
    _ar, _ac = divmod(_a, N)
    for _b in range(NC):
        _br, _bc = divmod(_b, N)
        MANH[_a][_b] = abs(_ar - _br) + abs(_ac - _bc)


PARAMS = {
    # --- planning -----------------------------------------------------------
    "horizon": 20,             # turns of walk the planner looks ahead
    "visits": 4,               # work-cells per planned walk
    "beam": 140,
    "throttle": 1,             # 0 disables adaptive beam scaling, which makes play
                               # deterministic again for reproducibility tests
    "budget_ms": 60.0,         # hard internal deadline. Deliberately far under
                               # the 200 ms limit: the competition server may be
                               # loaded, and a late turn is scored as STAY
    "stickiness": 1.06,        # bonus for continuing last turn's objective
    "ncand": 14,               # work-cells considered per turn
    "reach": 7,                # ignore work further away than this
    # --- economy ------------------------------------------------------------
    "w_claim": 1.00,
    "w_upgrade": 1.00,
    "w_raid": 1.00,
    "w_raid_late": 1.00,       # raid weight at the final turn; interpolated by clock
    "combo": 0.00,             # weight on claim-and-upgrade-in-one-visit plans
    "hold": 0.00,              # value of squatting a threatened cell (occupancy
                               # is immunity: a cell I stand on cannot be entered)
    "combo_pri": 1.00,         # its priority when trimming the candidate list
    "w_denial": 0.55,          # how much a rival's loss counts toward my place
    "perish": 0.30,            # bonus for cells a rival could reach sooner
    "safe_discount": 0.85,     # discount on cells no rival can contest
    "zone_bonus": 1.15,        # prefer my own quadrant
    "squat_penalty": 0.35,     # a rival is sitting on it and may not leave
    "contest_penalty": 0.60,   # avoid steps that lose the priority-token race
    # --- risk ---------------------------------------------------------------
    "kappa": 0.75,             # value of one action-turn, as a fraction of R
    "def_kappa": 0.40,         # same, but for the defensive side. Kept separate:
                               # sharing one kappa let the raid side tune it down
                               # until the shield cost collapsed and the mixing died
    "freeze_cost": 2.10,       # a freeze costs this many action-turns
    "q_prior": 0.55,           # prior P(a rival shields a raider off its land)
    "q_weight": 4.0,
    "raid_risk": 1.00,
    # --- defence ------------------------------------------------------------
    "shield_cost": 1.60,       # shielding costs this many action-turns
    "shield_bias": 1.00,       # gain must exceed this multiple of the cost
    "shield_certain": 0.90,
    "retake_credit": 0.45,     # I own the cell, so I win the contest to retake it
    "commit_prior": 0.55,      # prior P(a raider commits rather than bails)
    "free_shield_turns": 2,    # last turns where a backfire costs nothing
    # --- objective shaping --------------------------------------------------
    "tau": 170.0,              # score-margin scale for the placement sigmoid
    "care_mode": 0,            # who to aim at: 0 margin, 1 leader, 2 weakest,
                               # 3 nearest on the board, 4 uniform
    "steal": 0.00,             # extra weight on high-value cells in a RIVAL's
                               # quadrant early on (the centre-steal opening)
    "steal_until": 20,         # turns during which the steal bonus applies
    "steal_min": 3,            # minimum cell value worth stealing
    "consolidate": 0.00,       # tilt from claiming toward upgrading as the clock
                               # runs down: claiming pays v x turns-remaining, so
                               # it is worth most early, while an upgrade of a cell
                               # you already hold keeps its value longer
    "lead_caution": 0.00,      # when ahead, treat raids as riskier than they are
                               # (low variance protects a lead); when behind,
                               # treat them as safer (gamble to catch up)
    # --- added after the organisers confirmed the ruleset -------------------
    "proj_care": 0.00,         # 0 compares rivals on their CURRENT score, 1 on
                               # score + income x turns-left. Round 1 scores each
                               # game as three one-on-one results, so what matters
                               # is the FINAL ordering; current score is a poor
                               # proxy for it early, when almost nothing is banked
    "home_bonus": 1.00,        # multiplier on work on my own home. A home can
                               # never be captured, so upgrading it is the only
                               # doubling on the board that cannot be raided back
    "upg_risk": 0.00,          # upgrading doubles the raid bounty on a cell
                               # (8 x v x 2 instead of 8 x v x 1), so upgrading an
                               # exposed cell invites the raid it is worth
    "first_turn_ms": 0.0,      # extra think time on turn 1 only (the server
                               # allows 2 s there against 200 ms afterwards);
                               # 0 keeps the per-turn budget
    "first_turn_mult": 1.0,    # beam/horizon multiplier for that deeper turn-1 plan
    "own_prog": 0.00,          # cost of the capture/upgrade progress a SHIELD
                               # throws away, in action-turns per lost stay
    "intent": 0.00,            # discount on cells a rival is visibly walking
                               # toward: arriving second wastes the whole trip
    "intent_turns": 3,         # how many turns of approach count as intent
    "endgame_care": 0,         # turns at the end during which the bot switches
                               # from "maximise my own score" to "win the
                               # pairings that are still in play". Round 1 scores
                               # each game as three one-on-one results, so a cell
                               # that lifts me past the rival just above me is
                               # worth a whole pairwise win, while the same cell
                               # is worth nothing once I am clear of everybody.
                               # 0 keeps the single all-game objective
    "tie_home": 1,             # how equal-priority cells are ordered:
                               #   0  raw cell index -- the old behaviour, which
                               #      is not symmetric between the four corners
                               #   1  nearest my own corner first
                               #  -1  farthest from my own corner first
                               # Only breaks exact ties, but those are common:
                               # priority is v x (R-d-need)/(d+need) over small
                               # integers, so many cells score identically
    "endgame_denial": 1.0,     # multiplier on the denial term inside that window:
                               # taking points off the rival I am chasing closes
                               # the gap from both ends at once
    # --- added after the cross-branch review --------------------------------
    "pay_fix": 1,              # count the turn a capture completes as a paying
                               # turn. Takes resolve before scoring (rulebook
                               # step order), so work finishing with R turns left
                               # pays R - used - need + 1 turns, not R - used - need.
                               # 0 restores the old count, under which a capture on
                               # the final turn was worth None and the bot walked
                               # away from it
}


def _all_pairs():
    d = []
    for s in range(NC):
        row = [99] * NC
        row[s] = 0
        q = [s]
        head = 0
        while head < len(q):
            u = q[head]
            head += 1
            du = row[u] + 1
            for w in NEIGH[u]:
                if row[w] > du:
                    row[w] = du
                    q.append(w)
        d.append(row)
    return d


DIST = _all_pairs()
_ONES = [1.0] * NC
_ZEROS = [0.0] * NC
_IDENT = list(range(NC))


def _flatten(bd):
    """The board as 64 cells, row-major, whatever shape it arrives in.

    The starter kit documents an 8x8 list of rows. The old test was "is bd[0] a
    list or tuple", which a flat 64-list of namedtuple cells also passes -- a
    namedtuple IS a tuple -- so each cell was read as a row, indexing past its
    six fields raised, the fallback used the same parser, and the bot played
    STAY for the whole game. A row is told from a cell by having no `owner`.
    """
    if len(bd) == NC:
        return list(bd)
    first = bd[0]
    if not hasattr(first, "owner") and not isinstance(first, dict) and len(first) == N:
        return [bd[r][c] for r in range(N) for c in range(N)]
    raise ValueError("unrecognised board shape")


def _bfs(start, blocked):
    d = [99] * NC
    d[start] = 0
    q = deque((start,))
    while q:
        u = q.popleft()
        du = d[u] + 1
        for w in NEIGH[u]:
            if d[w] > du and w not in blocked:
                d[w] = du
                q.append(w)
    return d


class Tracker(object):
    """Everything the state object does not give us, rebuilt from board diffs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.turn = 0
        self.prev = None            # (owner, upg, occ, frz) from last turn
        self.pos = [None] * 4
        self.frozen = [0] * 4       # turns of freeze still to serve, incl. this turn
        self.cd = [0] * 4           # shield cooldown remaining
        self.prog = [0] * 4
        self.score = [0] * 4
        self.token = 1
        self.token_known = False
        # opponent model: shield-on-sight, as Beta counts
        self.sh_yes = [0.0] * 4
        self.sh_no = [0.0] * 4
        self.raids = [0] * 4        # turns a bot committed while on rival land
        self.takes = [0] * 4        # completed raids (used for score reconstruction)
        self.baits = [0.0] * 4      # turns a bot bailed out instead of committing
        self.shields_seen = [0] * 4
        self.base = None
        self.home_of = None
        self.zone = None
        self.trail = [[], [], [], []]   # recent positions, newest last
        # Does progress carry over from a capture into the upgrade? Unknown until
        # the board shows us. None = not yet observed, assume the slow reading.
        self.carry = None
        self._claimed_at = [None] * 4   # (cell, stays since the capture)
        self.new_game = True            # the Agent clears its own state on this
        self._progressed = False        # any capture or upgrade seen this game?
        self.shield_rejected = 0        # my SHIELDs the server turned into STAY
        self.last_shielders = set()     # seat indices that shielded last turn

    # -- static board facts, computed once -----------------------------------
    def init_static(self, base, home_of):
        self.base = base
        self.home_of = home_of
        homes = [0] * 4
        for p in range(NC):
            if home_of[p]:
                homes[home_of[p] - 1] = p
        self.homes = homes
        zone = [0] * NC
        for p in range(NC):
            best, bd = 1, 99
            for i in range(4):
                d = MANH[p][homes[i]]
                if d < bd:
                    bd, best = d, i + 1
            zone[p] = best
        self.zone = zone

    # -- per-turn update ------------------------------------------------------
    def observe(self, owner, upg, occ, frz, seat, is_token, base, home_of,
                my_last=None):
        self.new_game = False
        fresh = self._is_fresh(owner, occ, home_of, upg)
        # A starting-looking board is a new game only if it cannot be the same
        # one. Positions revert all the time in an opening -- everybody stays
        # home, or a bot steps out and back -- so they prove nothing. Ownership
        # and upgrades never revert inside a game, so once a capture or an
        # upgrade has been seen, a fresh board can only be a new game. Resetting
        # on every fresh board froze the clock and zeroed every score: five
        # all-home turns read as turn 1, with true scores of 8 reconstructed as 0.
        new_game = fresh and (self._progressed or self.turn >= MAX_TURNS)
        if new_game or self.prev is None or self.turn > 400:
            self.reset()
            self.init_static(base, home_of)
            self.turn = 1
            if not fresh:
                # No history but the board is not at its starting position: either
                # the server does not keep module state between calls, or we were
                # dropped in mid-game. Estimate the turn from the board rather than
                # play the opening for 80 straight turns. Fitted on real games;
                # median error about 7 turns, which is far better than assuming 1.
                nown = 0
                nupg = 0
                for p in range(NC):
                    if owner[p] and not home_of[p]:
                        nown += 1
                    if upg[p]:
                        nupg += 1
                est = int(1.345 * nown + 0.387 * nupg - 5.1)
                if est < 1:
                    est = 1
                elif est > MAX_TURNS:
                    est = MAX_TURNS
                self.turn = est
            self.pos = self._positions(occ)
            self.token = 1
            if is_token:
                self.token = seat
                self.token_known = True
            # turn 1 has not resolved yet, so nothing has been scored
            self.income = [0, 0, 0, 0]
            self.prev = (owner[:], upg[:], occ[:], frz[:])
            self._progressed = not fresh and self._irreversible(owner, upg, home_of)
            return
        self.turn += 1
        if not self._progressed and self._irreversible(owner, upg, home_of):
            self._progressed = True
        pow_, pupg, pocc, pfrz = self.prev
        newpos = self._positions(occ)
        cd_prev = self.cd[:]
        frozen_prev = self.frozen[:]

        # token: rotates 1->2->3->4->1 every turn
        self.token = self.token % 4 + 1
        if is_token:
            if not self.token_known or self.token != seat:
                self.token = seat
            self.token_known = True

        # freeze counters straight off the is_frozen flags
        frozen_now = [0] * 4
        for i in range(4):
            if newpos[i] is not None and frz[newpos[i]]:
                frozen_now[i] = 1
        newly = [i for i in range(4) if frozen_now[i] and not self.frozen[i]]
        for i in range(4):
            if frozen_now[i]:
                self.frozen[i] = 2 if i in newly else max(1, self.frozen[i] - 1)
            else:
                self.frozen[i] = 0

        # Every shield is observable: it either catches someone (that bot freezes)
        # or it backfires (the shielder freezes). Attribution can be ambiguous
        # though -- a bot frozen while standing on rival land was either caught by
        # the landlord or backfired on its own shield. So instead of guessing, find
        # the set of shielders that exactly explains the freezes we observed.
        stayed = [newpos[i] is not None and newpos[i] == self.pos[i]
                  for i in range(4)]
        on_land = {}
        for j in range(4):
            pj = self.pos[j]
            if pj is None or frozen_prev[j]:
                continue
            o = pow_[pj]
            if o and o != j + 1:
                on_land.setdefault(o - 1, []).append(j)
        # a shield protects ALL of that bot's cells, so any seat that lost a cell
        # last turn provably did not shield
        lost_a_cell = [False] * 4
        for p in range(NC):
            a = pow_[p]
            if a and owner[p] != a:
                lost_a_cell[a - 1] = True
        base_cand = [s for s in range(4)
                     if cd_prev[s] == 0 and not frozen_prev[s] and not lost_a_cell[s]]
        newly_set = set(newly)
        mi = seat - 1

        def solve(cand, force_me):
            best, bestscore = None, -1e9
            ties = []
            for mask in range(1 << len(cand)):
                S = set(cand[k] for k in range(len(cand)) if (mask >> k) & 1)
                if force_me and mi not in S:
                    continue
                pred = set()
                plaus = -0.20 * len(S)
                for s in S:
                    vic = [j for j in on_land.get(s, []) if stayed[j] and j not in S]
                    if vic:
                        pred.update(vic)
                        plaus += 3.0              # a landlord defending its land
                    else:
                        pred.add(s)
                        ps = self.pos[s]
                        if ps is not None and pow_[ps] and pow_[ps] != s + 1:
                            plaus -= 2.5          # shielding while squatting enemy land
                        else:
                            plaus -= 0.5          # a mistimed defensive shield
                if pred != newly_set:
                    continue
                if plaus > bestscore:
                    bestscore, best, ties = plaus, S, [S]
                elif plaus == bestscore:
                    ties.append(S)
            return best, ties

        cand = [s for s in base_cand if s != mi]
        if my_last == "SHIELD":
            # I asked to shield, but a server that substitutes STAY -- for a late
            # turn, or for SHIELD offered during cooldown -- means it may not have
            # happened. Insisting that it did left no consistent explanation, which
            # threw away a rival's real shield along with my own phantom one. So
            # try the shield first, and if no explanation includes it, solve again
            # on the hypothesis that the server turned it into a STAY.
            best, ties = solve(cand + [mi], True)
            if best is None:
                best, ties = solve(cand, False)
                if best is not None:
                    self.shield_rejected += 1
        elif my_last is None and mi in base_cand:
            best, ties = solve(base_cand, False)  # no record of my own action
        else:
            best, ties = solve(cand, False)       # I know I did not shield
        if best is None:
            shielders = set()
        elif len(ties) == 1:
            shielders = best
        else:
            shielders = set(ties[0])
            for S in ties[1:]:
                shielders &= S            # stay pessimistic where they disagree
        self.last_shielders = set(shielders)
        for s in shielders:
            self.shields_seen[s] += 1
        for i in range(4):
            if i in shielders:
                self.cd[i] = 4
            elif self.cd[i] > 0:
                self.cd[i] -= 1

        # opponent model: when a landlord COULD have shielded a raider off its
        # land last turn, did it?
        for i in range(4):
            pp = self.pos[i]
            if pp is None or frozen_prev[i]:
                continue
            o = pow_[pp]
            if not o or o == i + 1 or pfrz[pp]:
                continue
            if cd_prev[o - 1] == 0 and not frozen_prev[o - 1]:
                if (o - 1) in shielders:
                    self.sh_yes[o - 1] += 1.0
                else:
                    self.sh_no[o - 1] += 1.0
            # did the raider bail out instead of committing?
            if newpos[i] != pp:
                self.baits[i] += 1.0
            else:
                self.raids[i] += 1

        # progress: a bot that held position and was neither frozen nor shielding
        # must have chosen STAY. Progress only moves when there is actually a take
        # or an upgrade under way -- squatting a finished cell or a rival's home
        # leaves it untouched.
        for i in range(4):
            if newpos[i] is None or self.pos[i] is None:
                self.prog[i] = 0
                continue
            if newpos[i] != self.pos[i] or i in shielders:
                self.prog[i] = 0
                continue
            if frozen_prev[i] or self.frozen[i]:
                self.prog[i] = 0
                continue
            need = self._need(pow_, pupg, self.pos[i], i + 1)
            if need is None:
                continue                      # nothing in progress here
            self.prog[i] += 1
            if self.prog[i] >= need:
                self.prog[i] = 0
        # ownership changes that completed this turn also zero progress -- or not,
        # if the server carries it over. self.carry holds whatever the board has
        # shown us so far; until then take the conservative reading.
        carrying = bool(self.carry)
        for i in range(4):
            p = newpos[i]
            if p is None:
                self._claimed_at[i] = None
                continue
            just_claimed = owner[p] == i + 1 and pow_[p] != i + 1
            if just_claimed:
                # If progress carries over it keeps the value that just satisfied
                # the requirement, which is 3 after taking an UPGRADED rival cell
                # and 1 otherwise -- not always 1. Getting this wrong matters:
                # under the carry-over reading, taking an upgraded cell leaves
                # enough progress to re-upgrade it on the very next stay.
                if carrying:
                    po = pow_[p]
                    self.prog[i] = 3 if (po and po != i + 1 and pupg[p]) else 1
                else:
                    self.prog[i] = 0
                self._claimed_at[i] = [p, 0]
                continue
            # watch a capture ripen into an upgrade and read the rule off it
            w = self._claimed_at[i]
            if w is None:
                continue
            if p != w[0] or owner[p] != i + 1 or self.frozen[i] > 0:
                self._claimed_at[i] = None
                continue
            if upg[p] and not pupg[p]:
                # it upgraded after w[1] + 1 stays beyond the capturing stay
                if self.carry is None:
                    self.carry = (w[1] + 1) <= 2
                self._claimed_at[i] = None
            else:
                w[1] += 1
                if w[1] > 4:
                    self._claimed_at[i] = None

        # raid bonuses, then income
        for p in range(NC):
            a, b = pow_[p], owner[p]
            if b and a and a != b and not home_of[p]:
                lvl = 2 if pupg[p] else 1
                self.score[b - 1] += 8 * base[p] * lvl
                self.takes[b - 1] += 1
        self._accrue_income(owner, upg)
        for i in range(4):
            if newpos[i] is not None:
                t = self.trail[i]
                t.append(newpos[i])
                if len(t) > 6:
                    del t[0]
        self.pos = newpos
        self.prev = (owner[:], upg[:], occ[:], frz[:])

    def approaching(self, j, p, turns):
        """Is rival j visibly closing on cell p over its last few moves?

        Returns the number of consecutive recent turns over which its distance
        to p strictly decreased. A rival three turns into a walk toward a cell is
        going to claim it in one stay when it arrives, and arriving second on a
        contested cell costs the whole trip for nothing.
        """
        t = self.trail[j]
        if len(t) < 2:
            return 0
        n = 0
        k = len(t) - 1
        while k > 0 and n < turns:
            if MANH[t[k]][p] < MANH[t[k - 1]][p]:
                n += 1
                k -= 1
            else:
                break
        return n

    def _need(self, owner, upg, p, seat):
        """Stays needed to finish what a bot on cell p is doing, or None if nothing."""
        o = owner[p]
        if o == seat:
            return None if upg[p] else 3      # an upgraded own cell has nothing left
        if o == 0:
            return 1
        if self.home_of[p]:
            return None                       # a rival's home can never be taken
        return 3 if upg[p] else 1

    def _accrue_income(self, owner, upg):
        inc = [0, 0, 0, 0]
        b = self.base
        for p in range(NC):
            o = owner[p]
            if o:
                inc[o - 1] += b[p] * (2 if upg[p] else 1)
        for i in range(4):
            self.score[i] += inc[i]
        self.income = inc

    def _positions(self, occ):
        pos = [None] * 4
        for p in range(NC):
            o = occ[p]
            if o:
                pos[o - 1] = p
        return pos

    @staticmethod
    def _irreversible(owner, upg, home_of):
        """Has anything happened that cannot be undone within a game?"""
        for p in range(NC):
            if upg[p] or (owner[p] and not home_of[p]):
                return True
        return False

    def _is_fresh(self, owner, occ, home_of, upg=None):
        """A starting board: every bot on its own home, nothing else owned, and
        nothing upgraded. The upgrade test matters: three all-home stays upgrade
        the homes, and a board that is "fresh" but upgraded is turn 4, not turn 1."""
        for p in range(NC):
            if upg is not None and upg[p]:
                return False
            if home_of[p]:
                if occ[p] != home_of[p] or owner[p] != home_of[p]:
                    return False
            elif owner[p] != 0:
                return False
        return True

    def q_shield(self, seat_idx, prior, weight):
        """Posterior P(this bot shields when a raider is on its land)."""
        y, n = self.sh_yes[seat_idx], self.sh_no[seat_idx]
        return (y + prior * weight) / (y + n + weight)


class Agent(object):
    def __init__(self, seed=0, params=None):
        self.P = dict(PARAMS)
        if params:
            self.P.update(params)
        self.tr = Tracker()
        self.last_action = None
        self.plan_target = None
        self._deadline = 0.0
        self._beam_scale = 1.0
        self.rng = int(seed) * 2654435761 % 4294967291 or 12345
        self._rng0 = self.rng           # so a new game restarts the same stream
        self._nturns = 0

    def rand(self):
        self.rng = (1103515245 * self.rng + 12345) % 2147483648
        return self.rng / 2147483648.0

    # ------------------------------------------------------------------ entry
    def __call__(self, view):
        t0 = time.perf_counter()
        try:
            a = self.decide(view)
        except Exception:
            # Never fall all the way back to STAY. Returning STAY here is the
            # worst failure mode available: one bad assumption about the state
            # object degrades the bot to the skeleton for all 80 turns while
            # every stress test still reports "no crashes", because the
            # exception never escapes. That happened once, from a single missing
            # parameter key. _fallback is a crude policy that still captures
            # cells -- about 8x the skeleton's score -- and this path costs
            # nothing while decide() is healthy.
            try:
                a = _fallback(view)
            except Exception:
                a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        self.last_action = a
        # Self-throttle. The grader's machine may be slower or busier than the one
        # these weights were tuned on, and a late turn is scored as STAY. So shrink
        # the search when a turn runs long and let it grow back when there is room.
        if not self.P["throttle"]:
            return a
        budget = self.P["budget_ms"] / 1000.0
        spent = time.perf_counter() - t0
        if spent > 0.55 * budget:
            self._beam_scale *= 0.65
            if self._beam_scale < 0.12:
                self._beam_scale = 0.12
        elif spent < 0.15 * budget and self._beam_scale < 1.0:
            self._beam_scale *= 1.25
            if self._beam_scale > 1.0:
                self._beam_scale = 1.0
        return a

    def decide(self, view):
        """Observe this turn's board, then choose an action."""
        if not self.ingest(view):
            return "STAY"
        return self.plan()

    def ingest(self, view):
        """Parse the view and update the tracker. False if I am not on the board.

        Split from plan() so a controller can keep the tracker current every turn
        without paying for a search it is not going to use.
        """
        P = self.P
        t_start = time.perf_counter()
        ms = P["budget_ms"]
        if self._nturns == 0 and P["first_turn_ms"] > ms:
            ms = P["first_turn_ms"]           # the server allows 2 s on turn 1
        self._deep = (P["first_turn_mult"] if self._nturns == 0 else 1.0)
        self._nturns += 1
        self._deadline = t_start + ms / 1000.0
        self._cellmod = _ONES
        self._expose = _ZEROS
        self._t_start = t_start
        cells = _flatten(view.board)
        base = [0] * NC
        owner = [0] * NC
        upg = [0] * NC
        home_of = [0] * NC
        occ = [0] * NC
        frz = [0] * NC
        for p in range(NC):
            cl = cells[p]
            base[p] = cl.base_points
            owner[p] = cl.owner
            upg[p] = 1 if cl.is_upgraded else 0
            occ[p] = cl.occupant
            frz[p] = 1 if cl.is_frozen else 0
            if cl.is_home:
                # a server that leaves homes unowned must not assign all four
                # to seat 1: fall back to the seat whose corner this is
                home_of[p] = cl.owner or (CORNERS.index(p) + 1 if p in CORNERS else 1)

        seat = int(view.bot_id)
        tr = self.tr
        tr.observe(owner, upg, occ, frz, seat, bool(view.is_priority_token), base,
                   home_of, self.last_action)
        if tr.new_game:
            self.plan_target = None
            self._beam_scale = 1.0
            self._nturns = 1
            self._deep = 1.0
            self.rng = self._rng0
        self._cur = (owner, upg, base, home_of, occ, frz, seat, list(view.legal_actions))
        return tr.pos[seat - 1] is not None

    def plan(self):
        """Choose an action for the board ingest() last saw."""
        P = self.P
        tr = self.tr
        owner, upg, base, home_of, occ, frz, seat, legal = self._cur
        me = tr.pos[seat - 1]
        if me is None:
            return "STAY"
        if len(legal) == 1:
            return legal[0]

        R = MAX_TURNS - tr.turn + 1           # turns left, including this one
        if R < 1:
            R = 1
        care = self._care(seat, R)
        kappa = max(1.0, P["kappa"] * R)

        # ---- defence: the shield/raid subgame -------------------------------
        # Trust legal_actions, but do not rely on it alone. The rulebook says a
        # shield cannot be repeated for four turns, and my engine therefore drops
        # SHIELD from the legal list during cooldown -- but if the real server
        # leaves it in and simply treats the attempt as STAY, shielding on
        # cooldown would waste the turn AND make the tracker believe a shield went
        # up. The tracker knows its own cooldown exactly, so check both.
        if "SHIELD" in legal and tr.cd[seat - 1] == 0:
            dkappa = P["def_kappa"] * R
            if dkappa < 1.0:
                dkappa = 1.0
            if self._should_shield(owner, upg, occ, frz, base, seat, R, dkappa, care):
                self.plan_target = None
                return "SHIELD"

        # ---- plan a whole walk, not a single target -------------------------
        act = self._plan_walk(owner, upg, base, home_of, occ, frz, seat, me, R,
                              kappa, care)
        return act if act is not None else "STAY"

    # ------------------------------------------------------------ objective
    def _proj(self, seat, R):
        """Projected final scores if ownership never changed again.

        Round 1 turns each game into three one-on-one results, so the only thing
        that matters about a rival is whether I finish above it. Current score is
        a bad estimate of that: on turn 10 nobody has banked anything, while the
        income already on the board decides most of the remaining 70 turns.
        """
        tr = self.tr
        f = self.P["proj_care"]
        if f <= 0.0:
            return list(tr.score)
        return [tr.score[j] + f * tr.income[j] * R for j in range(4)]

    def _care(self, seat, R=1):
        """Placement objective: weight each rival by how contested that pairing is."""
        P = self.P
        tr = self.tr
        proj = self._proj(seat, R)
        mine = proj[seat - 1]
        tau = P["tau"]
        mode = P["care_mode"]
        if P["endgame_care"] and R <= P["endgame_care"]:
            # Inside the endgame window, compare on projected FINAL scores
            # whatever proj_care says, and weight each rival by how nearly level
            # that pairing is -- those are the only ones still worth actions.
            inc = self.tr.income
            proj = [self.tr.score[j] + inc[j] * R for j in range(4)]
            mine = proj[seat - 1]
            mode = 0
        care = [0.0] * 4
        rivals = [j for j in range(4) if j != seat - 1]
        if mode == 4:
            for j in rivals:
                care[j] = 1.0
            return care
        if mode == 1 or mode == 2:
            # aim at the leader, or at the weakest (whose land is easiest to take)
            pick = max(rivals, key=lambda j: proj[j]) if mode == 1 else                 min(rivals, key=lambda j: proj[j])
            for j in rivals:
                care[j] = 2.0 if j == pick else 0.5
            return care
        if mode == 3:
            here = tr.pos[seat - 1]
            if here is None:
                for j in rivals:
                    care[j] = 1.0
                return care
            pick = min(rivals, key=lambda j: MANH[here][tr.pos[j]]
                       if tr.pos[j] is not None else 99)
            for j in rivals:
                care[j] = 2.0 if j == pick else 0.5
            return care
        tot = 0.0
        for j in rivals:
            x = (mine - proj[j]) / tau
            if x > 12:
                x = 12.0
            elif x < -12:
                x = -12.0
            e = 2.718281828 ** (-x)
            sig = e / (1.0 + e) ** 2          # logistic slope: peaks when level
            care[j] = sig
            tot += sig
        if tot > 1e-9:
            for j in range(4):
                care[j] = care[j] / tot * 3.0
        return care

    # ------------------------------------------------------------- planning
    def _candidates(self, owner, upg, base, home_of, occ, seat, me, R, care):
        """Pick the cells worth considering as work items this turn."""
        P = self.P
        tr = self.tr
        dist = DIST[me]
        out = []
        maxd = P["reach"]
        th = P["tie_home"]
        if th == 0:
            tie = _IDENT                      # raw cell index, as before
        else:
            can = CANON[seat]
            tie = [-can[p] for p in range(NC)] if th > 0 else can
        for p in range(NC):
            d = dist[p]
            if d > maxd:
                continue
            o = owner[p]
            if o == seat:
                if upg[p]:
                    continue
                kind = 1                      # upgrade
                v = base[p]
                need = 3
            elif o == 0:
                kind = 0                      # claim
                v = base[p]
                need = 1
            else:
                if home_of[p]:
                    continue
                kind = 2                      # raid
                v = base[p]
                need = 3 if upg[p] else 1
            if p == me and tr.prog[seat - 1]:
                need = max(1, need - tr.prog[seat - 1])
            if d + need > R:
                continue
            # a rough priority used only to trim the candidate list
            pri = v * (R - d - need) / float(d + need)
            if kind == 2:
                pri += 8.0 * v * (2 if upg[p] else 1) / float(d + need)
            if occ[p] and p != me:
                pri *= 0.3
            if tr.zone[p] == seat:
                pri *= P["zone_bonus"]
            tb = tie[p]
            out.append((pri, tb, p, kind, v, need))
            if p == me and o == seat and P["hold"] > 0.0:
                thr = self._threat(p, owner, upg, base, occ, seat, R, care)
                if thr > 0.0:
                    out.append((thr, tb, p, 4, v, 1))
            # claiming and upgrading in one visit costs 4 stays and no extra
            # travel; doing it as two visits costs a round trip as well
            if kind == 0 and P["combo"] > 0.0 and d + 4 <= R:
                out.append((pri * P["combo_pri"], tb, p, 3, v, need + 3))
        out.sort(reverse=True)
        return out[:P["ncand"]]

    def _work_gain(self, p, kind, v, need, used, owner, upg, occ, seat, R,
                   kappa, care, travel):
        """Points of final score from completing the work on p, started after
        `used` turns have already been spent."""
        P = self.P
        tr = self.tr
        # turns the cell will pay out. Takes resolve before scoring, so the turn
        # the work completes on pays too (pay_fix); the old count left it out.
        rem = R - used - need + (1 if P["pay_fix"] else 0)
        if kind == 4:
            # holding denies entry outright, which is strictly stronger than a
            # shield here: no backfire risk and no cooldown
            return self._threat(p, owner, upg, None, occ, seat, R, care) * P["hold"]
        cons = P["consolidate"]
        if cons != 0.0:
            f = 1.0 - (R / float(MAX_TURNS))
            if f < 0.0:
                f = 0.0
            elif f > 1.0:
                f = 1.0
            wc = P["w_claim"] * (1.0 - cons * f)
            wu = P["w_upgrade"] * (1.0 + cons * f)
            if wc < 0.0:
                wc = 0.0
        else:
            wc = P["w_claim"]
            wu = P["w_upgrade"]
        if kind == 0:
            if rem <= 0:
                return None
            g = v * rem * wc
        elif kind == 3:
            rem1 = R - used - 1 + (1 if P["pay_fix"] else 0)   # level-1 income
                                                                 # starts after 1 stay
            if rem <= 0 or rem1 <= 0:
                return None
            g = (v * rem1 * wc + v * rem * wu) * P["combo"]
        elif kind == 1:
            if rem <= 0:
                return None
            g = v * rem * wu
        else:
            if rem < (1 if P["pay_fix"] else 0):
                return None
            o = owner[p]
            lvl = 2 if upg[p] else 1
            take = 8.0 * v * lvl
            inc = v * rem
            wden = P["w_denial"]
            if P["endgame_care"] and R <= P["endgame_care"]:
                wden *= P["endgame_denial"]
            den = v * lvl * rem * wden * care[o - 1]
            q = self._shield_risk(o - 1, travel, need)
            lc = P["lead_caution"]
            if lc > 0.0:
                q += lc * self._standing(seat, R) * (1.0 - q)
                if q > 1.0:
                    q = 1.0
                elif q < 0.0:
                    q = 0.0
            g = ((take + inc + den) * (1.0 - q * P["raid_risk"])
                 - q * P["raid_risk"] * P["freeze_cost"] * kappa)
            # A raid bonus is one-off, so unlike income it does not decay with the
            # clock. Raiding is therefore worth far more late than early, which a
            # single scalar cannot express.
            f = 1.0 - (R / float(MAX_TURNS))
            if f < 0.0:
                f = 0.0
            elif f > 1.0:
                f = 1.0
            g *= P["w_raid"] + (P["w_raid_late"] - P["w_raid"]) * f
        # An upgrade doubles the raid bounty on the cell it improves: a level-2
        # 3-pointer pays its taker 48 points instead of 24. Upgrading a cell a
        # rival can reach therefore buys income and sells a target at once, and
        # the bot had no way to express that.
        if P["upg_risk"] > 0.0 and kind in (1, 3):
            g -= P["upg_risk"] * 8.0 * v * self._expose[p]
        # A home can never be captured, so work on it is the only improvement on
        # the board that cannot be taken back.
        if P["home_bonus"] != 1.0 and self.tr.home_of[p] == seat:
            g *= P["home_bonus"]
        # Cell-intrinsic modifiers only. These must NOT depend on where the walk
        # currently stands, or the cell under my feet gets penalised relative to
        # its neighbour and the bot oscillates between the two forever.
        g *= self._cellmod[p]
        return g

    def _standing(self, seat, R=1):
        """+1 when comfortably ahead of the field, -1 when clearly behind."""
        tr = self.tr
        proj = self._proj(seat, R)
        mine = proj[seat - 1]
        others = [proj[j] for j in range(4) if j != seat - 1]
        if not others:
            return 0.0
        gap = (mine - max(others)) / self.P["tau"]
        if gap > 1.0:
            return 1.0
        if gap < -1.0:
            return -1.0
        return gap

    def _threat(self, p, owner, upg, base, occ, seat, R, care):
        """What an adjacent rival would gain by taking cell p from me."""
        tr = self.tr
        v = (base or tr.base)[p]
        lvl = 2 if upg[p] else 1
        t = 0.0
        for w in NEIGH[p]:
            o = occ[w]
            if not o or o == seat:
                continue
            if tr.frozen[o - 1] > 0:
                continue
            need = 3 if lvl == 2 else 1
            pay = max(0, R - need + (1 if self.P["pay_fix"] else 0))
            t += (8.0 * v * lvl + v * pay
                  + v * lvl * pay * self.P["w_denial"] * care[o - 1])
        return t

    def _plan_walk(self, owner, upg, base, home_of, occ, frz, seat, me, R,
                   kappa, care):
        """
        Beam search over walks: visit a sequence of work-cells, paying the real
        travel cost between them. Scoring whole walks (instead of ranking single
        targets by rate) prices travel correctly, naturally prefers clusters, and
        stops the bot oscillating between two distant targets.
        """
        P = self.P
        tr = self.tr
        # per-cell modifiers, computed once per turn and stable across the walk
        mydist = DIST[me]
        mod = [1.0] * NC
        expose = [0.0] * NC
        zone = tr.zone
        perish = 1.0 + P["perish"]
        safe = P["safe_discount"]
        zb = P["zone_bonus"]
        sq = P["squat_penalty"]
        intent = P["intent"]
        itn = max(1, int(P["intent_turns"]))
        for p in range(NC):
            m = 1.0
            rd = 99
            for j in range(4):
                if j == seat - 1 or tr.pos[j] is None:
                    continue
                dj = MANH[tr.pos[j]][p]
                if dj < rd:
                    rd = dj
            # how quickly a live rival could be standing on this cell. Used to
            # price the fact that upgrading a cell doubles the bounty on it.
            if rd <= 1:
                expose[p] = 1.0
            elif rd < 8:
                expose[p] = 1.0 / float(rd)
            if rd < mydist[p]:
                m = perish                    # a rival gets there first: take it now
            elif rd > mydist[p] + 3:
                m = safe                      # nobody can contest it: it can wait
            if zone[p] == seat:
                m *= zb
            elif (P["steal"] > 0.0 and tr.turn <= P["steal_until"]
                  and base[p] >= P["steal_min"]):
                # the centre-steal opening: a rival's best cells are 6-8 moves
                # from their home but only 5-7 from mine, so there is a window
                # before they arrive
                m *= (1.0 + P["steal"])
            if occ[p] and p != me:
                m *= sq
            if intent > 0.0 and rd <= mydist[p]:
                # only cells a rival can reach no later than I can are at risk
                worst = 0
                for j in range(4):
                    if j == seat - 1 or tr.pos[j] is None:
                        continue
                    if tr.frozen[j] > 0:
                        continue
                    k = tr.approaching(j, p, itn)
                    if k > worst:
                        worst = k
                if worst:
                    m *= 1.0 - intent * (float(worst) / itn)
            mod[p] = m
        self._cellmod = mod
        self._expose = expose

        cands = self._candidates(owner, upg, base, home_of, occ, seat, me, R, care)
        if not cands:
            return self._idle(owner, upg, base, occ, seat, me, R, care)
        deep = self._deep
        horizon = int(P["horizon"] * deep)
        if horizon > R:
            horizon = R
        cellbit = {}
        for (_, _tb, p, kind, v, need) in cands:
            if p not in cellbit:
                cellbit[p] = len(cellbit)
        # state -> (value, first_cell)   state = (pos, used, mask)
        beam = {(me, 0, 0): (0.0, None)}
        bestby = {}
        tick = 0
        for _ in range(int(P["visits"] * deep + 0.5)):
            if time.perf_counter() > self._deadline:
                break                         # out of time: use the best walk so far
            nxt = {}
            for (pos, used, mask), (val, first) in beam.items():
                tick += 1
                if not (tick & 7) and time.perf_counter() > self._deadline:
                    break                     # bail mid-iteration too
                for (_, _tb, p, kind, v, need) in cands:
                    k = cellbit[p]
                    if (mask >> k) & 1:
                        continue
                    travel = 0 if p == pos else DIST[pos][p]
                    nu = used + travel + need
                    if nu > horizon or nu > R:
                        continue
                    g = self._work_gain(p, kind, v, need, used + travel, owner, upg,
                                        occ, seat, R, kappa, care, travel)
                    if g is None:
                        continue
                    nv = val + g
                    f = first if first is not None else p
                    st = (p, nu, mask | (1 << k))
                    cur = nxt.get(st)
                    if cur is None or cur[0] < nv:
                        nxt[st] = (nv, f)
                    if bestby.get(f, -1e18) < nv:
                        bestby[f] = nv
            if not nxt:
                break
            width = int(P["beam"] * self._beam_scale * deep)
            if width < 8:
                width = 8
            if len(nxt) > width:
                items = sorted(nxt.items(), key=lambda kv: -kv[1][0])[:width]
                beam = dict(items)
            else:
                beam = nxt
        if not bestby:
            return self._idle(owner, upg, base, occ, seat, me, R, care)
        # stickiness: keep last turn's objective unless clearly beaten, so the bot
        # does not re-litigate its plan every turn and walk in circles
        stick = P["stickiness"]
        target, tv = None, -1e18
        for f, v in bestby.items():
            s = v * (stick if f == self.plan_target else 1.0)
            if s > tv:
                tv, target = s, f
        self.plan_target = target
        if target == me:
            return "STAY"
        return self._step(me, target, occ, owner, seat)

    def _idle(self, owner, upg, base, occ, seat, me, R, care):
        """Nothing productive in reach: sit on the most valuable thing I own."""
        if owner[me] == seat and not upg[me]:
            return "STAY"
        best, bv = None, -1.0
        for p in range(NC):
            if owner[p] == seat and not upg[p]:
                s = base[p] * 1.0 - DIST[me][p] * 0.25
                if s > bv:
                    bv, best = s, p
        if best is None:
            return "STAY"
        if best == me:
            return "STAY"
        return self._step(me, best, occ, owner, seat)

    # -------------------------------------------------------------- defence
    def _shield_risk(self, ridx, travel, need):
        """P(this raid gets shielded before it completes)."""
        P = self.P
        tr = self.tr
        if tr.frozen[ridx] >= travel + need:
            return 0.0
        cd = tr.cd[ridx]
        if cd >= travel + need:
            return 0.0
        exposed = need if cd <= travel else max(0, travel + need - cd)
        if exposed <= 0:
            return 0.0
        q = tr.q_shield(ridx, P["q_prior"], P["q_weight"])
        return 1.0 - (1.0 - q) ** exposed

    def _should_shield(self, owner, upg, occ, frz, base, seat, R, kappa, care):
        P = self.P
        tr = self.tr
        intruders = []
        home_of = tr.home_of
        for p in range(NC):
            o = occ[p]
            # A home can never be captured, so a rival standing on mine threatens
            # nothing. Counting it as an imminent take made the bot burn a shield
            # (and, on the last turn, its own scoring stay) on a visitor that
            # could not take anything.
            if o and o != seat and owner[p] == seat and not frz[p] and not home_of[p]:
                intruders.append((p, o - 1))
        if not intruders:
            return False

        # In the last couple of turns a backfire costs nothing and the cooldown
        # never bites, so shielding is nearly free -- but only nearly: the shield
        # turn is not a stay, so it gives up whatever my own stay would complete.
        if R <= P["free_shield_turns"]:
            at_risk = 0.0
            for p, j in intruders:
                need = (3 if upg[p] else 1) - tr.prog[j]
                if need <= 1:
                    v = base[p]
                    lvl = 2 if upg[p] else 1
                    # I lose the cell's income for every remaining turn, and the
                    # taker banks a bonus that counts against me in that pairing
                    at_risk += v * lvl * R + 8.0 * v * lvl / 3.0
            if at_risk <= 0.0:
                return False
            return at_risk > self._own_stay_value(owner, upg, base, seat, R)

        # The 2x2 game, written out properly:
        #   SHIELD + they stay  -> I keep the cell and freeze them
        #   SHIELD + they leave -> backfire: I freeze 2 turns and burn the cooldown
        #   no shield + stay    -> they take it
        #   no shield + leave   -> nothing happens
        # so the decision turns on P(commit), and the backfire branch MUST be
        # priced. Leaving it out makes shielding look free and the bot shields on
        # sight, which is precisely what a baiting opponent farms.
        gain = 0.0
        best_commit = 0.0
        for p, j in intruders:
            lvl = 2 if upg[p] else 1
            v = base[p]
            left = max(1, (3 if lvl == 2 else 1) - tr.prog[j])
            if left > 1:
                continue                      # not imminent: no need to burn a shield
            # what the take actually costs me, net of the fact that I own the cell
            # and so win the contest to retake it later (and collect a bonus myself)
            # a take this turn costs me this turn's income too (pay_fix)
            pay = R if P["pay_fix"] else R - 1
            lost = v * lvl * pay * (1.0 - P["retake_credit"])
            their_gain = (8.0 * v * lvl + v * pay) * P["w_denial"] * care[j]
            commit = self._commit_prob(j)
            gain += (lost + their_gain) * commit
            if commit > best_commit:
                best_commit = commit
        if gain <= 0.0:
            return False

        # backfire, weighted by the chance every intruder walks away
        backfire = (1.0 - best_commit) * P["freeze_cost"] * kappa
        # the shield turn itself produces nothing, and costs 4 turns of cover
        cost = kappa * P["shield_cost"]
        # ...and it resets my own progress. Shielding on the third stay of an
        # upgrade throws away the two stays already banked, which is a real cost
        # the 2x2 was silently ignoring.
        if P["own_prog"] > 0.0:
            cost += P["own_prog"] * tr.prog[seat - 1] * kappa
        net = gain - backfire - cost
        # shield_bias is a threshold on how far ahead the shield must be before
        # it is worth burning. Scaling the cost term was useless, since gain is
        # an order of magnitude larger; this is a real lever.
        if net <= 0.0 or gain < P["shield_bias"] * (backfire + cost):
            return False
        # mix at the equilibrium so a predictable defender cannot be baited
        q = net / (net + backfire + cost)
        if q >= P["shield_certain"]:
            return True
        return self.rand() < q

    def _own_stay_value(self, owner, upg, base, seat, R):
        """Points my own STAY completes this turn (what a SHIELD gives up)."""
        tr = self.tr
        me = tr.pos[seat - 1]
        if me is None:
            return 0.0
        need = tr._need(owner, upg, me, seat)
        if need is None or need - tr.prog[seat - 1] > 1:
            return 0.0
        v = base[me]
        pay = R if self.P["pay_fix"] else R - 1
        o = owner[me]
        if o == seat:
            return float(v * pay)                     # the upgrade's extra income
        if o == 0:
            return float(v * pay)                     # a claim
        lvl = 2 if upg[me] else 1
        return float(8 * v * lvl + v * pay)           # a raid

    def _commit_prob(self, j):
        P = self.P
        tr = self.tr
        seen = tr.raids[j] + tr.baits[j]
        if seen < 3:
            return P["commit_prior"]
        return (tr.raids[j] + P["commit_prior"] * 3.0) / (seen + 3.0)

    # ----------------------------------------------------------------- moves
    def _step(self, me, target, occ, owner, seat):
        """One step toward target, avoiding closed cells and lost contests."""
        tr = self.tr
        blocked = set(p for p in range(NC) if occ[p] and p != me)
        d = _bfs(target, blocked)
        if d[me] >= 99:
            d = DIST[target]
        want = d[me] - 1
        cands = [w for w in NEIGH[me] if w not in blocked and d[w] == want]
        if not cands:
            cands = [w for w in NEIGH[me] if w not in blocked and d[w] < d[me]]
        # NEIGH is built in a fixed north/south/west/east order, so two equally
        # good steps were separated by a rule that is not the same in all four
        # corners. Order them in this seat's own frame instead, for the same
        # reason the candidate list is ordered that way.
        if len(cands) > 1 and self.P["tie_home"]:
            can = CANON[seat]
            cands.sort(key=lambda w: can[w],
                       reverse=self.P["tie_home"] < 0)
        if not cands:
            return "STAY"
        myrank = (seat - tr.token) % 4 if tr.token_known else 0
        bestw, bestk = None, -1e18
        for w in cands:
            k = 0.0
            if owner[w] == 0:
                k += 0.4
            elif owner[w] == seat:
                k += 0.1
            for n2 in NEIGH[w]:
                o2 = occ[n2]
                if o2 and o2 != seat:
                    if tr.token_known and (o2 - tr.token) % 4 < myrank:
                        k -= self.P["contest_penalty"]
                    else:
                        k -= self.P["contest_penalty"] * 0.3
            if k > bestk:
                bestk, bestw = k, w
        return STEP_NAME[(me, bestw)]


_AGENTS = {}


_DELTA = dict(MOVE_DELTA)


def _fallback(view):
    """Last-resort policy. Reads only what the starter kit documents, allocates
    almost nothing, and has no dependency on the tracker or the planner."""
    cells = _flatten(view.board)
    seat = int(view.bot_id)
    legal = list(view.legal_actions)
    me = None
    for p in range(NC):
        if cells[p].occupant == seat:
            me = p
            break
    if me is None:
        return "STAY"
    here = cells[me]
    # Staying is how cells are captured and upgraded, so standing on anything
    # unfinished is already the right move.
    if here.owner != seat or not here.is_upgraded:
        if not (here.owner != seat and here.is_home):
            return "STAY" if "STAY" in legal else legal[0]
    # otherwise walk toward the most valuable cell that is not already mine
    best, bestv = None, -1.0
    mr, mc = divmod(me, N)
    for p in range(NC):
        c = cells[p]
        if c.owner == seat or (c.is_home and c.owner != seat) or c.occupant:
            continue
        r2, c2 = divmod(p, N)
        d = abs(mr - r2) + abs(mc - c2)
        v = c.base_points / (1.0 + d)
        if v > bestv:
            bestv, best = v, p
    if best is None:
        return "STAY" if "STAY" in legal else legal[0]
    br, bc = divmod(best, N)
    for name, cond in (("NORTH", br < mr), ("SOUTH", br > mr),
                       ("WEST", bc < mc), ("EAST", bc > mc)):
        if cond and name in legal:
            nxt = me + _DELTA[name]
            if nxt in NEIGH[me] and not cells[nxt].occupant:
                return name
    for name in ("NORTH", "SOUTH", "EAST", "WEST"):
        if name in legal:
            nxt = me + _DELTA[name]
            if nxt in NEIGH[me] and not cells[nxt].occupant:
                return name
    return "STAY" if "STAY" in legal else legal[0]


# ==========================================================================
# fusion.py -- normalisation, failsafes and the controller
# ==========================================================================
# Measurement sets "deterministic": no wall clock in any decision, fixed seeds.
SAFETY = {"deterministic": False}

# The economic planner's weights: research/evolution's recommended genome.
ECON_GENOME = dict(E_EVOLVED)

FLAGS = {
    "primary": "econ",         # "econ" or "route"
    "genome": "evolved",       # econ genome: "evolved" or "transfer"
    "sym": 0,                  # econ tie-break frame (see econ.py)
    "ext_cd": 0,               # econ reads rival cooldowns from the exact tracker
    "cold_route_turns": 1,     # walk planner plays this long after a cold start
    "max_errors": 2,           # a planner that raises this often is retired
    "calibrate": 1,            # verify the movement convention online
    "mirror": 0,               # predict and exploit exact copies of public bots.
                               # OFF: crossfield/exp_mirror.py shows near-relatives
                               # (same code, other genome) go unrefuted for 60-79
                               # turns, so identification is not safe
}

# hardened-field-and-fixes v7 weights for the walk planner (v7_params.json)
ROUTE_PARAMS = {
    "beam": 400, "budget_ms": 60.0, "care_mode": 4, "combo": 0.3372851530026109,
    "combo_pri": 0.5130215791090991, "commit_prior": 0.738408561698738,
    "consolidate": -0.3091790691417158, "contest_penalty": 0.04276674446676251,
    "def_kappa": 0.3, "endgame_care": 6, "endgame_denial": 1.1489375774470736,
    "first_turn_ms": 0.0, "first_turn_mult": 1.0, "free_shield_turns": 1,
    "freeze_cost": 1.9897676204898689, "hold": 0.039812395355899075,
    "home_bonus": 0.8124607638770958, "horizon": 40, "intent": 0.0, "intent_turns": 3,
    "kappa": 0.871265646873602, "lead_caution": 0.05637305117375756, "ncand": 8,
    "own_prog": 0.5638901677881061, "perish": 0.12508411521263113, "proj_care": 0.0,
    "q_prior": 0.6262098276170066, "q_weight": 4.912705682120482,
    "raid_risk": 1.5925150988216987, "reach": 5, "retake_credit": 0.5124636643323689,
    "safe_discount": 0.9496812183899669, "shield_bias": 2.351882159061404,
    "shield_certain": 0.541032334099978, "shield_cost": 1.4910998926274515,
    "squat_penalty": 0.05, "steal": 0.0, "steal_min": 3, "steal_until": 20,
    "stickiness": 1.228276644454352, "tau": 295.09465653811793, "throttle": 1,
    "tie_home": 1, "upg_risk": 0.0, "visits": 7, "w_claim": 0.9065853137369807,
    "w_denial": 0.20752972644616563, "w_raid": 1.648359402231134,
    "w_raid_late": 1.4321683445126716, "w_upgrade": 1.5842582773978768,
    "zone_bonus": 1.0, "pay_fix": 1,
}

_F_MOVES = ("NORTH", "EAST", "SOUTH", "WEST")
_F_ALL = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
_F_DELTA = {"NORTH": (-1, 0), "SOUTH": (1, 0), "WEST": (0, -1), "EAST": (0, 1)}
_F_CORNER = (0, 7, 63, 56)
# the eight symmetries of the square, as maps of a (row, col) step
_F_DIHEDRAL = (
    lambda r, c: (r, c), lambda r, c: (c, -r), lambda r, c: (-r, -c),
    lambda r, c: (-c, r), lambda r, c: (r, -c), lambda r, c: (-r, c),
    lambda r, c: (c, r), lambda r, c: (-c, -r),
)
_F_FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
_F_ALIASES = {
    "occupant": ("occupant", "occupied_by", "bot"), "owner": ("owner", "owned_by"),
    "is_upgraded": ("is_upgraded", "upgraded", "isUpgraded", "level"),
    "is_home": ("is_home", "home", "isHome"),
    "is_frozen": ("is_frozen", "frozen", "isFrozen"),
    "base_points": ("base_points", "points", "basePoints", "value"),
}


# ----------------------------------------------------------------- 1. input
class _FCell(object):
    __slots__ = _F_FIELDS

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points


class _FView(object):
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")

    def __init__(self, board, bot_id, token, legal):
        self.board = board
        self.bot_id = bot_id
        self.is_priority_token = token
        self.legal_actions = legal


def _f_get(cell, name):
    for key in _F_ALIASES[name]:
        if isinstance(cell, dict):
            if key in cell:
                return cell[key]
        elif hasattr(cell, key):
            return getattr(cell, key)
    raise KeyError(name)


def _f_int(x):
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    return int(float(x))


def _f_bool(x):
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(x)


def _f_is_cell(x):
    if isinstance(x, dict):
        return "owner" in x or "owned_by" in x
    return hasattr(x, "owner") or hasattr(x, "owned_by")


def _f_flat(board):
    if isinstance(board, dict):
        board = board.get("cells") or board.get("board")
    seq = list(board)
    if len(seq) == 64 and _f_is_cell(seq[0]):
        return seq
    if len(seq) == 8 and not _f_is_cell(seq[0]):
        rows = [list(r) for r in seq]
        if all(len(r) == 8 for r in rows):
            return [c for r in rows for c in r]
    raise ValueError("unrecognised board shape")


def _f_name(x):
    """An action's canonical upper-case name, whatever type the server uses."""
    if isinstance(x, str):
        s = x
    else:
        s = getattr(x, "name", None)
        if not isinstance(s, str):
            s = getattr(x, "value", None)
        if not isinstance(s, str):
            s = str(x)
    s = s.strip().upper()
    if "." in s:
        s = s.rsplit(".", 1)[1]
    return s


def _f_attr(state, name, default=None):
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)


class _FObs(object):
    __slots__ = ("cells", "rows", "seat", "token", "names", "lookup", "pos", "fresh")


def _f_normalize(state):
    raw_cells = _f_flat(_f_attr(state, "board"))
    cells = []
    for c in raw_cells:
        cells.append(_FCell(_f_int(_f_get(c, "occupant") or 0),
                            _f_int(_f_get(c, "owner") or 0),
                            _f_bool(_f_get(c, "is_upgraded")),
                            _f_bool(_f_get(c, "is_home")),
                            _f_bool(_f_get(c, "is_frozen")),
                            _f_int(_f_get(c, "base_points"))))
    for p in _F_CORNER:                  # a home reported unowned keeps its seat
        if cells[p].is_home and not cells[p].owner:
            cells[p].owner = _F_CORNER.index(p) + 1
    seat = _f_int(_f_attr(state, "bot_id"))
    pos = [-1] * 5
    for i, c in enumerate(cells):
        if 1 <= c.occupant <= 4:
            pos[c.occupant] = i
    if not (1 <= seat <= 4) or pos[seat] < 0:
        if 0 <= seat <= 3 and pos[seat + 1] >= 0:
            seat += 1                    # a 0-indexed seat
        else:
            raise ValueError("cannot find my own bot on the board")
    raw_legal = _f_attr(state, "legal_actions")
    raw_legal = list(raw_legal) if raw_legal is not None else []
    lookup = {}
    for a in raw_legal:
        nm = _f_name(a)
        if nm in _F_ALL and nm not in lookup:
            lookup[nm] = a
    if "STAY" not in lookup:
        lookup["STAY"] = "STAY"          # documented as always legal
    o = _FObs()
    o.cells = cells
    o.rows = [cells[r * 8:(r + 1) * 8] for r in range(8)]
    o.seat = seat
    o.token = _f_bool(_f_attr(state, "is_priority_token", False))
    o.names = [a for a in _F_ALL if a in lookup]
    o.lookup = lookup
    o.pos = pos
    o.fresh = all(pos[s] == _F_CORNER[s - 1] for s in range(1, 5)) and all(
        (c.owner == 0) != (i in _F_CORNER) for i, c in enumerate(cells)) and not any(
        c.is_upgraded for c in cells)
    return o


def _f_emergency(state):
    """The server's own STAY object if it can be found, else the first legal."""
    try:
        legal = list(_f_attr(state, "legal_actions") or [])
        for a in legal:
            if _f_name(a) == "STAY":
                return a
        if legal:
            return legal[0]
    except Exception:
        pass
    return "STAY"


# ----------------------------------------------------------------- 6. frame
class _FCalib(object):
    """Learns whether NORTH really is row - 1, from my own observed moves."""

    def __init__(self):
        self.agree = [0] * 8
        self.disagree = [0] * 8
        self.active = 0

    def observe(self, sent, before, after):
        """Evidence from my own last move: where did it actually take me?"""
        if sent not in _F_DELTA or before < 0 or after < 0 or before == after:
            return
        dr = after // 8 - before // 8
        dc = after % 8 - before % 8
        if abs(dr) + abs(dc) != 1:
            return
        r0, c0 = _F_DELTA[sent]
        for k, t in enumerate(_F_DIHEDRAL):
            if t(r0, c0) == (dr, dc):
                self.agree[k] += 1
            else:
                self.disagree[k] += 1
        self._decide()

    def observe_legal(self, here, names):
        """Evidence from legal_actions: a listed move that would leave the board
        in some frame contradicts that frame. Only inclusion counts -- a server
        may legitimately omit moves (into occupied cells, say) -- and a list
        holding all four moves carries no information at all.

        This matters because displacement evidence alone can never start: in a
        flipped frame at my corner the server offers NORTH (meaning down) and not
        SOUTH, and a planner that only proposes documented in-bounds moves would
        slide along the edge forever without producing a contradiction.
        """
        if here < 0:
            return
        moves = [a for a in names if a in _F_DELTA]
        if not moves or len(moves) == 4:
            return
        r, c = divmod(here, 8)
        for k, t in enumerate(_F_DIHEDRAL):
            fits = True
            for a in moves:
                dr, dc = t(*_F_DELTA[a])
                if not (0 <= r + dr < 8 and 0 <= c + dc < 8):
                    fits = False
                    break
            if fits:
                self.agree[k] += 1
            else:
                self.disagree[k] += 1
        self._decide()

    def _decide(self):
        self.active = 0
        if self.disagree[0] >= 3:
            for k in range(1, 8):
                if self.disagree[k] == 0 and self.agree[k] >= 3:
                    self.active = k
                    break

    def to_server(self, name):
        """Server action that moves me by `name`'s documented board step."""
        if not self.active or name not in _F_DELTA:
            return name
        want = _F_DELTA[name]
        t = _F_DIHEDRAL[self.active]
        for a in _F_MOVES:
            if t(*_F_DELTA[a]) == want:
                return a
        return name

    def from_server(self, names):
        """Legal names re-expressed as documented board steps."""
        if not self.active:
            return list(names)
        out = []
        t = _F_DIHEDRAL[self.active]
        for a in names:
            if a in _F_DELTA:
                step = t(*_F_DELTA[a])
                for b in _F_MOVES:
                    if _F_DELTA[b] == step:
                        out.append(b)
            else:
                out.append(a)
        return out


# ----------------------------------------------------------------- 8. copies
class _FMirror(object):
    """Recognises rivals that are exact copies of a public econ-family bot.

    This repository is public, and its strongest bot is deterministic. A rival
    running a copy of it sees the same board I do, and I can reconstruct every
    other input it gets -- its seat, whether it holds the token (it rotates),
    its legal actions and its cooldown (the exact tracker). It also moves
    simultaneously with me, so its choice this turn cannot depend on mine. One
    simulator per public genome therefore predicts such a rival's action this
    turn, before I choose mine.

    Identification is strict, so the option is inert against everybody else:
    every prediction is scored against what the rival actually did next turn
    (a blocked or contested move is inconclusive, never a match), one mismatch
    retires that hypothesis for the rest of the game, and nothing is acted on
    until NEED informative turns have matched. Observations from before the
    token holder is known (at most four turns) are buffered and replayed, so the
    simulator's memory starts on turn 1 exactly as the copy's did.
    """
    NEED = 10

    def __init__(self, seat):
        self.seat = seat
        self.rivals = [s for s in (1, 2, 3, 4) if s != seat]
        self.sims = dict((s, [Econ(config=E_EVOLVED), Econ(config=E_TRANSFER)])
                         for s in self.rivals)
        self.ok = dict((s, [True, True]) for s in self.rivals)
        self.hits = dict((s, [0, 0]) for s in self.rivals)
        self.pred = dict((s, [None, None]) for s in self.rivals)
        self.buf = []
        self.prev_pos = None
        self.live = False
        self.k = 0

    @staticmethod
    def _legal(s, pos, frozen, cd):
        if frozen[s]:
            return ["STAY"]
        occ = set(p for p in pos[1:] if p >= 0)
        r, c = divmod(pos[s], 8)
        out = []
        for a in _F_MOVES:
            dr, dc = _F_DELTA[a]
            if 0 <= r + dr < 8 and 0 <= c + dc < 8 and (r + dr) * 8 + c + dc not in occ:
                out.append(a)
        out.append("STAY")
        if cd[s - 1] == 0:
            out.append("SHIELD")
        return out

    def _predict(self, cells, pos, frozen, cd, holder):
        for s in self.rivals:
            if pos[s] < 0:
                continue
            legal = self._legal(s, pos, frozen, cd)
            for g in (0, 1):
                if not self.ok[s][g]:
                    self.pred[s][g] = None
                    continue
                try:
                    a = self.sims[s][g].step(cells, s, legal, holder == s)
                    self.pred[s][g] = (a, len(legal) > 1)
                except Exception:
                    self.ok[s][g] = False
                    self.pred[s][g] = None

    @staticmethod
    def _score(s, pred, before, after, shielded):
        """+1 a match, 0 inconclusive, -1 a mismatch."""
        a, b = before[s], after[s]
        if a < 0 or b < 0:
            return 0
        if a != b:
            step = (b // 8 - a // 8, b % 8 - a % 8)
            for nm in _F_MOVES:
                if _F_DELTA[nm] == step:
                    return 1 if pred == nm else -1
            return 0
        if s in shielded:
            return 1 if pred == "SHIELD" else -1
        if pred == "STAY":
            return 1
        if pred == "SHIELD":
            return -1
        dr, dc = _F_DELTA[pred]
        t = (a // 8 + dr) * 8 + a % 8 + dc
        if t in before[1:] or t in after[1:]:
            return 0                     # blocked, or lost a contest
        return -1

    def _check(self, before, after, shielded):
        for s in self.rivals:
            for g in (0, 1):
                p = self.pred[s][g]
                if p is None or not self.ok[s][g] or not p[1]:
                    continue
                r = self._score(s, p[0], before, after, shielded)
                if r < 0:
                    self.ok[s][g] = False
                elif r > 0:
                    self.hits[s][g] += 1

    def update(self, cells, pos, frozen, cd, shielded_last, holder):
        """One turn. cd: cooldowns by seat index 0-3; shielded_last: seats
        (1-4) that shielded last turn; holder: token seat, or None if unknown."""
        self.k += 1
        if not self.live:
            self.buf.append((cells, list(pos), list(frozen), list(cd), set(shielded_last)))
            if holder is None:
                return
            n = len(self.buf)
            for idx, (c_, p_, f_, cd_, sh_) in enumerate(self.buf):
                if idx:
                    self._check(self.buf[idx - 1][1], p_, sh_)
                self._predict(c_, p_, f_, cd_, (holder - 1 - (n - 1 - idx)) % 4 + 1)
            self.buf = []
            self.live = True
            self.prev_pos = list(pos)
            return
        self._check(self.prev_pos, pos, shielded_last)
        self._predict(cells, pos, frozen, cd, holder)
        self.prev_pos = list(pos)

    def predicted(self, s):
        """This turn's action of rival s, if it is an identified copy."""
        if not self.live or s not in self.ok:
            return None
        acts = set(self.pred[s][g][0] for g in (0, 1)
                   if self.ok[s][g] and self.hits[s][g] >= self.NEED
                   and self.pred[s][g] is not None)
        return acts.pop() if len(acts) == 1 else None


# ----------------------------------------------------------------- 2-5. seat
class _FBrain(object):
    """Everything one seat knows. Rebuilt from scratch at every new game."""

    def __init__(self, seat):
        self.seat = seat
        self.calib = _FCalib()           # the server's frame does not change per game
        self.removes_shield = False      # server drops SHIELD during cooldown?
        self.seen = False                # any observation yet?
        self.progressed = False          # any capture or upgrade this game?
        self.turns = 0
        self._new_game(cold=False)

    def _new_game(self, cold):
        genome = E_TRANSFER if FLAGS["genome"] == "transfer" else ECON_GENOME
        self.econ = Econ(config=genome, flags={"sym": FLAGS["sym"]})
        params = dict(ROUTE_PARAMS)
        if SAFETY["deterministic"]:
            params["throttle"] = 0
            params["budget_ms"] = 1e6
            seed = self.seat * 7919
        else:
            seed = (int(time.time() * 1e6) ^ (self.seat * 7919)) & 0x7fffffff
        self.route = Agent(seed=seed, params=params)
        self.errors = {"econ": 0, "route": 0}
        self.cold_left = FLAGS["cold_route_turns"] if cold else 0
        self.turns = 0
        self.last_sent = None
        self.last_pos = -1
        self.used = {"econ": 0, "route": 0, "fallback": 0, "stay": 0}
        # A copy can only be simulated from turn 1, so never after a cold start
        self.mirror = _FMirror(self.seat) if FLAGS["mirror"] and not cold else None
        self.exploits = 0

    def _alive(self, who):
        return self.errors[who] < FLAGS["max_errors"]

    def turn(self, obs):
        # -- 3. new game? Positions revert all the time in an opening, so they
        #    prove nothing; ownership and upgrades never revert within a game. So
        #    a starting board is a new game only once a capture or an upgrade has
        #    been seen (or the clock has run out), and a module that wakes up on
        #    a non-starting board has lost its memory mid-game.
        if not self.seen:
            self.seen = True
            if not obs.fresh:
                self._new_game(cold=True)
        elif obs.fresh and (self.progressed or self.turns >= 80):
            self._new_game(cold=False)
            self.progressed = False
        if not self.progressed and not obs.fresh and any(
                c.is_upgraded or (c.owner and not c.is_home) for c in obs.cells):
            self.progressed = True
        self.turns += 1
        me = obs.seat
        here = obs.pos[me]

        # -- 6. movement convention, from my own last move
        if FLAGS["calibrate"]:
            if self.turns > 1:
                self.calib.observe(self.last_sent, self.last_pos, here)
            self.calib.observe_legal(here, obs.names)
        names = self.calib.from_server(obs.names)

        # -- 5. SHIELD availability: legal_actions and the exact tracker
        if "SHIELD" not in names and len(names) > 1:
            self.removes_shield = True       # seen SHIELD withheld while free to act
        view = _FView(obs.rows, me, obs.token, names)
        route_ok = False
        if self._alive("route"):
            try:
                route_ok = self.route.ingest(view)
            except Exception:
                self.errors["route"] += 1
        if (route_ok and "SHIELD" in names and not self.removes_shield
                and self.route.tr.cd[me - 1] > 0):
            names = [a for a in names if a != "SHIELD"]
            view = _FView(obs.rows, me, obs.token, names)
            self.route._cur = self.route._cur[:7] + (list(names),)

        # -- 8. predict rivals that are exact copies of a public bot
        if self.mirror is not None:
            if not route_ok:
                self.mirror = None
            else:
                try:
                    tr = self.route.tr
                    frozen = [False] + [obs.pos[k] >= 0 and obs.cells[obs.pos[k]].is_frozen
                                        for k in (1, 2, 3, 4)]
                    self.mirror.update(obs.cells, obs.pos, frozen, tr.cd,
                                       set(i + 1 for i in tr.last_shielders),
                                       tr.token if tr.token_known else None)
                except Exception:
                    self.mirror = None

        action = None
        who = None
        econ_tried = False
        econ_first = FLAGS["primary"] == "econ" and self.cold_left <= 0
        order = ("econ", "route") if econ_first else ("route", "econ")
        for planner in order:
            if action is not None or not self._alive(planner):
                continue
            try:
                if planner == "econ":
                    econ_tried = True
                    a = self._econ_step(obs, names, route_ok)
                elif route_ok:
                    a = self.route.plan()
                else:
                    continue
                if a in names:
                    action, who = a, planner
            except Exception:
                self.errors[planner] += 1
        # The econ planner keeps its memory current even on turns it does not
        # play, so that it can take over with the right clock and scores. It
        # must observe each turn exactly once, so not if it already ran (or
        # raised part-way) above.
        if not econ_tried and self._alive("econ"):
            try:
                self._econ_step(obs, names, route_ok)
            except Exception:
                self.errors["econ"] += 1

        if who == "econ" and self.mirror is not None:
            try:
                a = self._exploit(obs, names, action)
                if a in names and a != action:
                    action = a
                    self.exploits += 1
            except Exception:
                self.mirror = None
        if action is None:
            try:
                a = _fallback(view)
                if a in names:
                    action, who = a, "fallback"
            except Exception:
                pass
        if action is None:
            action, who = "STAY", "stay"
        if self.cold_left > 0:
            self.cold_left -= 1

        # every planner records what was actually played, not what it proposed
        self.route.last_action = action
        if self.econ.mem is not None:
            self.econ.mem["last"] = action
        self.used[who] += 1
        sent = self.calib.to_server(action)
        if sent not in obs.lookup:
            sent = "STAY"
        self.last_sent = sent
        self.last_pos = here
        return obs.lookup[sent]

    def _exploit(self, obs, names, action):
        """Best response to rivals whose action this turn is known exactly."""
        m = self.mirror
        me = obs.seat
        cells, pos = obs.cells, obs.pos
        tr = self.route.tr
        at = pos[me]
        land = cells[at].owner
        # Offence: about to stay on a copy's land, and it is about to shield.
        # Staying gets me caught (frozen two turns, progress lost); stepping off
        # makes its shield backfire, and its land is then open for four turns.
        if (action == "STAY" and land not in (0, me) and not cells[at].is_home
                and m.predicted(land) == "SHIELD"):
            alt = self._escape(obs, names, land)
            if alt is not None:
                return alt
        # Defence: shield exactly when a copy is about to complete a take, and
        # never into a copy that is about to leave.
        intruders = [(pos[k], k) for k in (1, 2, 3, 4) if k != me and pos[k] >= 0
                     and cells[pos[k]].owner == me and not cells[pos[k]].is_home
                     and not cells[pos[k]].is_frozen]
        if not intruders:
            return action
        preds = [m.predicted(k) for _, k in intruders]
        if any(x is None for x in preds):
            return action                    # someone unpredictable is on my land
        if "SHIELD" in names:
            for (p, k), x in zip(intruders, preds):
                need = 3 if cells[p].is_upgraded else 1
                if x == "STAY" and need - tr.prog[k - 1] <= 1:
                    return "SHIELD"
        if action == "SHIELD":
            alt = getattr(self.econ, "pre_shield", None)
            if alt in names and alt != "SHIELD":
                return alt
        return action

    def _escape(self, obs, names, landlord):
        """The best one-step move off a cell I am about to be caught on."""
        e = self.econ
        best, bv = None, -1.0
        for task in getattr(e, "last_tasks", ()):
            rate, i = task[0], task[2]
            if e.last_travel[i] == 1 and e.last_first[i] in names and rate > bv:
                best, bv = e.last_first[i], rate
        if best is not None:
            return best
        at = obs.pos[obs.seat]
        occ = set(p for p in obs.pos[1:] if p >= 0)
        r, c = divmod(at, 8)
        for a in _F_MOVES:
            dr, dc = _F_DELTA[a]
            t = (r + dr) * 8 + c + dc
            if a in names and 0 <= r + dr < 8 and 0 <= c + dc < 8 and t not in occ \
                    and obs.cells[t].owner != landlord:
                return a
        return None

    def _econ_step(self, obs, names, route_ok):
        ext = None
        if FLAGS["ext_cd"] and route_ok:
            ext = [0] + list(self.route.tr.cd)
        # Woken mid-game with no memory: use the tracker's fitted turn estimate
        # (median error 5 turns) instead of the planner's own 2 + owned + upgrades
        # (median error 9). Only ever applies on that first cold observation.
        hint = self.route.tr.turn if route_ok else None
        return self.econ.step(obs.cells, obs.seat, names, obs.token, ext_cooldown=ext,
                              turn_hint=hint)


_F_BRAINS = {}


def act(state):
    """Starter-kit entry point: one action from state.legal_actions."""
    try:
        obs = _f_normalize(state)
    except Exception:
        return _f_emergency(state)
    try:
        brain = _F_BRAINS.get(obs.seat)
        if brain is None:
            brain = _FBrain(obs.seat)
            _F_BRAINS[obs.seat] = brain
        return brain.turn(obs)
    except Exception:
        return _f_emergency(state)
