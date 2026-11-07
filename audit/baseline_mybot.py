"""
The bot. Development copy -- ship.py inlines this into a single self-contained bot.py.

Three parts:
  Tracker  -- reconstructs everything the starter kit hides (turn, all four scores,
              take/upgrade progress, shield cooldowns, freeze counters, token seat)
              from board diffs alone.
  Economy  -- scores every reachable target as points-of-final-score per action-turn,
              which is the correct action-value function for a 80-turn income race.
  Tactics  -- the shield/raid subgame solved as a 2x2 matrix game, an opponent model
              that best-responds when the read is strong, and an endgame raid chain.
"""
import time
from collections import deque

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
        fresh = self._is_fresh(owner, occ, home_of)
        if fresh or self.prev is None or self.turn > 400:
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
            return
        self.turn += 1
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
        cand = [s for s in range(4)
                if cd_prev[s] == 0 and not frozen_prev[s] and not lost_a_cell[s]]
        if my_last is not None:
            mi = seat - 1
            if my_last == "SHIELD":
                if mi not in cand:
                    cand.append(mi)
            elif mi in cand:
                cand.remove(mi)           # I know I did not shield
        newly_set = set(newly)
        best, bestscore = None, -1e9
        ties = []
        for mask in range(1 << len(cand)):
            S = set(cand[k] for k in range(len(cand)) if (mask >> k) & 1)
            if my_last == "SHIELD" and (seat - 1) not in S:
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
        if best is None:
            shielders = set()
        elif len(ties) == 1:
            shielders = best
        else:
            shielders = set(ties[0])
            for S in ties[1:]:
                shielders &= S            # stay pessimistic where they disagree
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

    def _is_fresh(self, owner, occ, home_of):
        for p in range(NC):
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
        self.rng = seed * 2654435761 % 4294967291 or 12345
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
        bd = view.board
        if bd and isinstance(bd[0], (list, tuple)):
            cells = [bd[r][c] for r in range(N) for c in range(N)]
        else:
            cells = list(bd)
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
                home_of[p] = cl.owner or 1

        seat = view.bot_id
        tr = self.tr
        tr.observe(owner, upg, occ, frz, seat, view.is_priority_token, base,
                   home_of, self.last_action)
        if tr.new_game:
            self.plan_target = None
            self._beam_scale = 1.0
            self._nturns = 1
            self._deep = 1.0
            self.rng = self._rng0
        me = tr.pos[seat - 1]
        if me is None:
            return "STAY"
        legal = view.legal_actions
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
        rem = R - used - need                 # turns the cell will pay out
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
            rem1 = R - used - 1               # level-1 income starts after 1 stay
            if rem <= 0 or rem1 <= 0:
                return None
            g = (v * rem1 * wc + v * rem * wu) * P["combo"]
        elif kind == 1:
            if rem <= 0:
                return None
            g = v * rem * wu
        else:
            if rem < 0:
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
            t += (8.0 * v * lvl + v * max(0, R - need)
                  + v * lvl * max(0, R - need) * self.P["w_denial"] * care[o - 1])
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
        for p in range(NC):
            o = occ[p]
            if o and o != seat and owner[p] == seat and not frz[p]:
                intruders.append((p, o - 1))
        if not intruders:
            return False

        # In the last couple of turns a backfire costs nothing and the cooldown
        # never bites, so shielding is free: deny every bonus we can.
        if R <= P["free_shield_turns"]:
            for p, j in intruders:
                need = (3 if upg[p] else 1) - tr.prog[j]
                if need <= 1:
                    return True
            return R <= 1

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
            lost = v * lvl * (R - 1) * (1.0 - P["retake_credit"])
            their_gain = (8.0 * v * lvl + v * (R - 1)) * P["w_denial"] * care[j]
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
    bd = view.board
    if bd and isinstance(bd[0], (list, tuple)):
        cells = [bd[r][c] for r in range(N) for c in range(N)]
    else:
        cells = list(bd)
    seat = view.bot_id
    legal = view.legal_actions
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


def act(state):
    """Module-level entry point matching the starter kit's signature."""
    try:
        bid = state.bot_id
    except Exception:
        return "STAY"
    a = _AGENTS.get(bid)
    if a is None:
        a = Agent(seed=bid * 7919)
        _AGENTS[bid] = a
    return a(state)
