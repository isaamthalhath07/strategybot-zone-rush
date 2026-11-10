"""
StrategyBot / Zone Rush competition bot.

Plan: reconstruct everything the state object hides (turn number, all four
scores, take and upgrade progress, shield cooldowns, freeze counters, the
priority-token holder) from board diffs; plan a whole walk of work rather than
chasing one target at a time; and treat the shield/raid stand-off as the 2x2
matrix game it actually is, with an opponent model that exploits a predictable
defender and mixes when it has no read.

Entry point: act(state) -> one of NORTH, EAST, SOUTH, WEST, STAY, SHIELD.
Standard library only.
"""

import math
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
    'backfire_prod': 1,
    'beam': 400,
    'budget_ms': 60.0,
    'calibrate': 1,
    'canon_home': 1,
    'care_mode': 4,
    'combo': 0.3372851530026109,
    'combo_pri': 0.5130215791090991,
    'commit_prior': 0.738408561698738,
    'consolidate': -0.3091790691417158,
    'contest_owner': 1,
    'contest_penalty': 0.04276674446676251,
    'def_kappa': 0.3,
    'endgame_care': 6,
    'endgame_denial': 1.1489375774470736,
    'fc_beta': 2.0,
    'fc_chain': 2,
    'fc_defend': 0,
    'fc_kappa': 3.0,
    'fc_rho': 0.9,
    'first_turn_ms': 0.0,
    'first_turn_mult': 1.0,
    'forecast': 1,
    'free_shield_turns': 1,
    'freeze_cost': 1.9897676204898689,
    'fresh_guard': 0,
    'hold': 0.039812395355899075,
    'home_bonus': 0.8124607638770958,
    'horizon': 40,
    'intent': 0.0,
    'intent_turns': 3,
    'kappa': 0.871265646873602,
    'last_shield_value': 1,
    'lead_caution': 0.05637305117375756,
    'ncand': 8,
    'own_prog': 0.5638901677881061,
    'pay_fix': 0,
    'penalty_undo': 1,
    'perish': 0.12508411521263113,
    'proj_care': 0.0,
    'q_prior': 0.6262098276170066,
    'q_weight': 4.912705682120482,
    'raid_risk': 1.5925150988216987,
    'reach': 5,
    'retake_credit': 0.5124636643323689,
    'risk_frozen': 0,
    'safe_discount': 0.9496812183899669,
    'shield_bias': 2.351882159061404,
    'shield_certain': 0.541032334099978,
    'shield_cost': 1.4910998926274515,
    'shield_home': 0,
    'shield_l1': 0,
    'solver_retry': 1,
    'squat_penalty': 0.05,
    'steal': 0.0,
    'steal_min': 3,
    'steal_until': 20,
    'stickiness': 1.228276644454352,
    'tau': 295.09465653811793,
    'throttle': 1,
    'tie_home': 1,
    'turn_guard': 1,
    'upg_risk': 0.0,
    'visits': 7,
    'w_claim': 0.9065853137369807,
    'w_denial': 0.20752972644616563,
    'w_raid': 1.648359402231134,
    'w_raid_late': 1.4321683445126716,
    'w_upgrade': 1.5842582773978768,
    'zone_bonus': 1.0,
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
        # Switches, read from the Agent's params each turn. A tracker used on its
        # own runs with the module defaults.
        self.cfg = PARAMS
        # Rule durations as engine.py reads the rulebook. With cfg["calibrate"]
        # they are replaced by what the board shows; kept across reset() because
        # they belong to the server, not to one game.
        self.cd_len = 4
        self.cd_known = False           # measured exactly off my own legal_actions
        self.frz_len = 2
        self.frz_known = False
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
        self.frz_streak = [0] * 4       # consecutive turns each bot showed is_frozen
        self.explains = {}              # frozen seat -> shielders inferred from it alone
        self._skip = set()              # frozen before I first looked: length unknown
        self.last_shield = [None] * 4   # turn of each seat's last attributed shield
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
        cfg = self.cfg
        guard = cfg.get("fresh_guard")
        fresh = self._is_fresh(owner, occ, home_of, upg if guard else None)
        if guard:
            # A starting-looking board is a new game only if it cannot be the same
            # one. Positions revert all the time in an opening -- everybody stays
            # home, or a bot steps out and back -- so they prove nothing. Ownership
            # and upgrades never revert inside a game, so once a capture or an
            # upgrade has been seen, a fresh board can only be a new game.
            # Resetting on every fresh board froze the clock and zeroed every
            # score: five all-home turns read as turn 1, with true scores of 8
            # reconstructed as 0.
            new_game = fresh and (self._progressed or self.turn >= MAX_TURNS)
        else:
            new_game = fresh
        # C2: a game has 80 turns, so a non-starting board after turn 80 cannot
        # belong to the game being tracked -- it is a new game whose first board
        # was never seen. Without this the counter runs on to 81, 82, ... and R
        # stays clamped at 1: the whole game played as its last turn (measured:
        # 156 points against rivals' ~2,700).
        stale = (cfg.get("turn_guard") and self.prev is not None
                 and self.turn >= MAX_TURNS)
        if new_game or self.prev is None or self.turn > 400 or stale:
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
            if cfg.get("calibrate"):
                # A bot already frozen on the first board I see (a late Round 2
                # robot is frozen at home until placed) is not a NEW freeze: do not
                # make the attribution solver explain it, and do not let its
                # unknown-length streak calibrate the freeze length.
                for i in range(4):
                    pi = self.pos[i]
                    if pi is not None and frz[pi]:
                        self.frozen[i] = 1
                        self._skip.add(i)
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
        flen = self.frz_len if cfg.get("calibrate") else 2
        for i in range(4):
            if frozen_now[i]:
                self.frozen[i] = flen if i in newly else max(1, self.frozen[i] - 1)
                self.frz_streak[i] += 1
            else:
                # C3: a freeze that began while I was watching just ended, so its
                # length is a sample of the server's freeze length. Keep the
                # MINIMUM seen: shield freezes all last the same number of turns,
                # and a Round 2 time penalty can only make one look longer.
                L = self.frz_streak[i]
                if i in self._skip:
                    self._skip.discard(i)
                elif L and cfg.get("calibrate") and 1 <= L <= 6:
                    self.frz_len = L if not self.frz_known else min(self.frz_len, L)
                    self.frz_known = True
                self.frozen[i] = 0
                self.frz_streak[i] = 0
                self.explains.pop(i, None)
        # C1: a freeze still showing after a shield freeze would have ended was a
        # Round 2 time penalty (4.4: "frozen for the next 3 turns"), not a shield.
        # Any cooldown the tracker inferred from it alone is a phantom: it makes
        # the bot believe a ready rival cannot shield. Undo it -- but only once the
        # real freeze length has been seen. Until then a 3-turn shield freeze and
        # a 3-turn penalty look the same, and guessing "penalty" withdraws real
        # cooldowns: measured -0.070 PW under a referee whose freeze is 3 turns.
        if cfg.get("penalty_undo") and (self.frz_known or not cfg.get("calibrate")):
            for i in range(4):
                if frozen_now[i] and self.frz_streak[i] == flen + 1:
                    for s in self.explains.pop(i, []):
                        if s != seat - 1 and self.cd[s] > 0:
                            self.cd[s] = 0
                            cd_prev[s] = 0
                            self.shields_seen[s] -= 1
                            self.last_shield[s] = None   # not a shield after all

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
            # on the hypothesis that the server turned it into a STAY (C4, found
            # by both reviews; solver_retry 0 restores v7's single solve).
            best, ties = solve(cand + [mi], True)
            if best is None and cfg.get("solver_retry"):
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
        cdl = self.cd_len if cfg.get("calibrate") else 4
        for i in range(4):
            if i in shielders:
                self.cd[i] = cdl
            elif self.cd[i] > 0:
                self.cd[i] -= 1
        if cfg.get("penalty_undo") or cfg.get("calibrate"):
            for s in shielders:
                vic = [j for j in on_land.get(s, []) if stayed[j] and j not in shielders]
                expl = vic if vic else [s]
                # C1: remember which cooldowns rest on a single freeze, so they
                # can be withdrawn if that freeze turns out to be a penalty
                if len(expl) == 1 and expl[0] in newly_set:
                    self.explains.setdefault(expl[0], []).append(s)
                # C3: the same seat shielding twice bounds the cooldown from
                # above -- gap - 1 turns at most. That is the dangerous direction
                # (a shorter real cooldown makes the bot believe a ready rival
                # cannot shield), and it is visible long before my own shield
                # can measure it. Only strong evidence counts: a landlord
                # catching a rival that stayed, or my own shield.
                if cfg.get("calibrate") and (vic or (s == seat - 1 and my_last == "SHIELD")):
                    last = self.last_shield[s]
                    if last is not None and not self.cd_known:
                        bound = self.turn - last - 1
                        if 2 <= bound < self.cd_len:
                            drop = self.cd_len - bound
                            self.cd_len = bound
                            for k in range(4):
                                if k != s and self.cd[k] > 0:
                                    self.cd[k] = max(0, self.cd[k] - drop)
                            self.cd[s] = bound
                    self.last_shield[s] = self.turn

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


class Forecaster(object):
    """Where is each rival going, and when will it get there?

    Bayesian goal inference -- inverse planning. Every rival is modelled as a
    goal-directed agent playing by the same rules: it is walking to some cell to
    claim, upgrade or raid it. Nothing here is fitted to any pool of opponents;
    the belief about each rival is learned from that rival's own moves, in this
    game, as they happen.

      prior       how good each cell is as a target from the rival's seat and
                  position, by the arithmetic the bot applies to itself: points
                  the work earns (value x turns it will pay, plus any raid bonus)
                  per action-turn it costs (travel + stays).
      likelihood  a noisy-rational move model. Under goal g, a step that closes
                  the distance is e^beta times as likely as standing still, and
                  standing still e^beta times as likely as stepping away; at the
                  goal, staying is the rational move.
      transition  goals change -- one gets finished, a better one appears -- so
                  each turn the belief relaxes a little toward the prior (a hidden
                  Markov model over goals).

    The posterior says where a rival is heading and its distance says when it
    arrives. Chaining "its best next target after that one" carries the forecast
    further out. threat[c] then lists (turn the rival first stands on c,
    probability) for every cell, which the planner uses to discount any walk
    that needs a cell a rival will occupy first.

    The constants are fixed on principle, not tuned: beta = 2 (a step toward the
    goal is ~7x as likely as idling), rho = 0.9 (a goal persists ~10 turns),
    kappa = 3 (the best target is e^3 ~ 20x as likely a priori as a worthless one).
    """

    def __init__(self, beta=2.0, rho=0.9, kappa=3.0, chain=2, floor=0.03):
        self.beta = beta
        self.rho = rho
        self.kappa = kappa
        self.chain = chain
        self.floor = floor
        self.reset()

    def reset(self):
        self.belief = [None] * 4
        self.lam = [None] * 4           # log-evidence per goal, decaying by rho
        self.last = [None] * 4
        self.was_frozen = [False] * 4
        self.threat = [[] for _ in range(NC)]
        self.goal = [None] * 4          # most likely current goal, for diagnostics

    @staticmethod
    def scores(s, pos, owner, upg, base, home_of, R):
        """Target value of every cell for seat s standing at pos (0 = not a target),
        and the stays each would need."""
        sc = [0.0] * NC
        nd = [1] * NC
        row = MANH[pos]
        for c in range(NC):
            d = row[c]
            if d >= R:
                continue
            o = owner[c]
            v = base[c]
            if o == s:
                if upg[c]:
                    continue
                need = 3
                val = v * (R - d - need)
            elif o == 0:
                need = 1
                val = v * (R - d - need)
            else:
                if home_of[c]:
                    continue                 # rival homes can never be taken
                lvl = 2 if upg[c] else 1
                need = 3 if lvl == 2 else 1
                val = 8.0 * v * lvl + v * max(0, R - d - need)
            if val <= 0:
                continue
            sc[c] = val / float(d + need)
            nd[c] = need
        return sc, nd

    def _prior(self, sc):
        top = max(sc)
        if top <= 0.0:
            return [1.0 / NC] * NC
        k = self.kappa
        low = 2.718281828 ** (-k - 2.0)
        pr = [(2.718281828 ** (k * (x / top - 1.0)) if x > 0.0 else low) for x in sc]
        z = sum(pr)
        return [x / z for x in pr]

    def update(self, tr, owner, upg, base, home_of, seat, R):
        eb = 2.718281828 ** self.beta
        ebn = 1.0 / eb
        # log P(event | goal): a step closer / held / further; at the goal, a
        # stay (work) or leaving it. Normalised per goal.
        lzm = math.log(eb + 1.0 + ebn)
        lzg = math.log(eb + ebn)
        L_CLOSER = self.beta - lzm
        L_FURTHER = -self.beta - lzm
        L_STAY_OTHER = -lzm
        L_STAY_GOAL = self.beta - lzg
        L_LEAVE_GOAL = -self.beta - lzg
        threat = [[] for _ in range(NC)]
        for j in range(4):
            if j == seat - 1:
                continue
            p = tr.pos[j]
            if p is None:
                self.belief[j] = None
                continue
            sc, nd = self.scores(j + 1, p, owner, upg, base, home_of, R)
            prior = self._prior(sc)
            lam = self.lam[j]
            q = self.last[j]
            if lam is None or q is None:
                lam = [0.0] * NC
            elif not self.was_frozen[j] and (p == q or p in NEIGH[q]):
                # Evidence from the rival's last step: what it did to the distance
                # to each goal g -- closer, held, or further. Deliberately NOT the
                # likelihood of the exact move: an action-level model splits
                # probability among the equally good moves toward g, so a diagonal
                # goal gets half the credit of a goal straight ahead, while real
                # bots break those ties deterministically and walk in straight
                # lines. Measured, that version found the true destination 2.5%
                # of the time, against 49% for no inference at all.
                rq = MANH[q]
                rp = MANH[p]
                if p == q:
                    # A stay is how work gets done, so it ends a leg: the walk
                    # that led here says nothing about the next target. If the
                    # work here is still in progress (an upgrade, or a raid on an
                    # upgraded cell), the stay marks q as the goal. If the stay
                    # just FINISHED the work -- the tracker's progress is back to
                    # 0 -- the next target is a fresh choice and only the prior
                    # speaks. Treating every stay as "goal = here" predicted that
                    # rivals keep working a cell they had just claimed.
                    if tr.prog[j] > 0:
                        lam = [L_STAY_OTHER] * NC
                        lam[q] = L_STAY_GOAL
                    else:
                        lam = [0.0] * NC
                else:
                    rho = self.rho
                    for g in range(NC):
                        if g == q:
                            e = L_LEAVE_GOAL
                        elif rp[g] < rq[g]:
                            e = L_CLOSER
                        else:
                            e = L_FURTHER
                        lam[g] = rho * lam[g] + e
            self.lam[j] = lam
            # Most bots re-choose their target every turn from where they now
            # stand, so the belief is the CURRENT rule-derived prior times the
            # recent evidence -- not an old prior carried forward, which lagged
            # behind the plain prior as the rival closed in on its target.
            top = max(lam)
            b = [prior[c] * 2.718281828 ** (lam[c] - top) for c in range(NC)]
            tot = sum(b)
            if tot > 0.0:
                b = [x / tot for x in b]
            self.belief[j] = b
            self.last[j] = p
            self.was_frozen[j] = tr.frozen[j] > 0
            # forecast: (turn the rival first stands on c, probability)
            row = MANH[p]
            best, bp = None, 0.0
            for c in range(NC):
                pc = b[c]
                if pc >= self.floor:
                    threat[c].append((row[c], pc, j))
                    if pc > bp:
                        bp, best = pc, c
            self.goal[j] = best
            # carry it further out: the best next target after finishing this one
            if best is not None and bp >= 0.25 and self.chain > 0:
                t = row[best] + nd[best]
                here, pk = best, bp
                seen = {best}
                for _k in range(self.chain):
                    pk *= 0.5
                    if t >= R or pk < self.floor:
                        break
                    sc2, nd2 = self.scores(j + 1, here, owner, upg, base, home_of, R - t)
                    nxt, nv = None, 0.0
                    for c in range(NC):
                        if c not in seen and sc2[c] > nv:
                            nv, nxt = sc2[c], c
                    if nxt is None:
                        break
                    t += MANH[here][nxt]
                    threat[nxt].append((t, pk, j))
                    seen.add(nxt)
                    t += nd2[nxt]
                    here = nxt
        self.threat = threat

    def survival(self, c, start, owned=False):
        """P(cell c is still mine to work on when I first stand on it at turn
        offset `start`): every rival forecast to stand there first takes it from
        me with its probability; arriving on the same turn is a contest -- won
        outright if I own the cell (2.3: the owner wins), otherwise ~even."""
        s = 1.0
        for t, pc, _j in self.threat[c]:
            if t < start:
                s *= 1.0 - pc
            elif t == start and not owned:
                s *= 1.0 - 0.5 * pc
        return s


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
        self._cdw = None                # C3: [turns since my shield, frozen last turn]
        self._canon_cache = {}
        self.fc = None                  # v9: Forecaster, built on first use
        self._surv = None
        self._defend = False

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
        tr.cfg = P                            # the tracker's switches live in params
        tr.observe(owner, upg, occ, frz, seat, bool(view.is_priority_token), base,
                   home_of, self.last_action)
        if tr.new_game:
            self.plan_target = None
            self._beam_scale = 1.0
            self._nturns = 1
            self._deep = 1.0
            self.rng = self._rng0
            self._cdw = None
        legal = list(view.legal_actions)
        if P["calibrate"]:
            self._calibrate_cooldown(legal, seat)
        self._surv = None
        self._defend = False
        if P["forecast"]:
            # Every turn, including the ones I spend frozen: each observed step
            # of a rival is evidence about where it is going.
            if self.fc is None or tr.new_game:
                self.fc = Forecaster(P["fc_beta"], P["fc_rho"], P["fc_kappa"],
                                     int(P["fc_chain"]))
            self.fc.update(tr, owner, upg, base, home_of, seat,
                           max(1, MAX_TURNS - tr.turn + 1))
            self._surv = self.fc
            self._defend = bool(P["fc_defend"])
        self._cur = (owner, upg, base, home_of, occ, frz, seat, legal)
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

    # ---------------------------------------------------- rule calibration (C3)
    def _calibrate_cooldown(self, legal, seat):
        """Read the server's shield cooldown off my own legal_actions.

        After a shield that took effect, SHIELD is missing from legal_actions
        until the cooldown ends; the first turn it is back gives the length.
        The rulebook says 4 and engine.py counts it that way, but a server that
        counts one turn differently costs this bot 0.16-0.18 pairwise wins
        (strategy_audit/README.md, 7.3), so it is measured rather than assumed. A turn
        spent frozen hides SHIELD for another reason, so a measurement taken
        straight after one is discarded. If the server lists SHIELD during the
        cooldown, nothing is measured and the defaults stand.
        """
        tr = self.tr
        has = "SHIELD" in legal
        frozen = len(legal) == 1
        if self.last_action == "SHIELD" and not has:
            self._cdw = [1, frozen]
        elif self._cdw is not None:
            self._cdw[0] += 1
            if has:
                if not self._cdw[1]:
                    L = self._cdw[0] - 1
                    if 1 <= L <= 10:
                        tr.cd_len = L
                        tr.cd_known = True
                        tr.cd[seat - 1] = 0
                self._cdw = None
            else:
                self._cdw[1] = frozen

    def _stay_value(self, owner, upg, base, seat, me):
        """Points my STAY completes this turn (B4): a claim, the last stay of
        an upgrade, or the last stay of a raid. 0 if staying finishes nothing."""
        o = owner[me]
        v = base[me]
        prog = self.tr.prog[seat - 1]
        if o == 0:
            return v
        if o == seat:
            return v if (not upg[me] and prog >= 2) else 0
        if self.tr.home_of[me]:
            return 0
        if upg[me]:
            return 17 * v if prog >= 2 else 0     # 16v bonus + v income
        return 9 * v                             # 8v bonus + v income

    def _defence_value(self, p, v, start, R, care):
        """fc_defend: what standing on my own level-1 cell p from turn offset
        `start` is worth as defence.

        A shield cannot save a level-1 cell (finding B2: 2 frozen turns + 1 stay
        <= the 4-turn cooldown), but occupancy can: a cell I stand on cannot be
        entered, a same-turn contest for it goes to me as its owner (2.3), and
        staying there upgrades it into one a shield CAN hold. So every rival
        forecast to arrive no earlier than I do loses its raid, weighted by the
        forecast probability. The worth of a prevented take uses the same terms
        the shield decision already uses -- the income kept, net of the chance to
        retake it, plus the rival's bonus and income denied -- so this adds no
        new tuned number."""
        P = self.P
        val = 0.0
        for t, pc, j in self._surv.threat[p]:
            if start <= t:
                rem = R - t
                if rem > 0:
                    lost = v * rem * (1.0 - P["retake_credit"])
                    their = (8.0 * v + v * rem) * P["w_denial"] * care[j]
                    val += pc * (lost + their)
        return val

    def _canon(self, seat):
        """My tie-break frame. CANON assumes seat 1..4 sit at the corners
        clockwise from the top-left; with canon_home it is derived from where
        my home actually is (Round 2: "the organisers assign each team's corner").
        Identical to CANON whenever that assumption holds."""
        if not self.P["canon_home"]:
            return CANON[seat]
        h = self.tr.homes[seat - 1]
        t = self._canon_cache.get(h)
        if t is None:
            hr, hc = divmod(h, N)
            fr, fc = hr == N - 1, hc == N - 1
            t = [0] * NC
            for p in range(NC):
                r, c = divmod(p, N)
                t[p] = ((N - 1 - r) if fr else r) * N + ((N - 1 - c) if fc else c)
            self._canon_cache[h] = t
        return t

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
            can = self._canon(seat)
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
            if self._defend and kind == 1 and not home_of[p]:
                pri += self._defence_value(p, v, d, R, care) / float(d + need)
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
        if self._surv is not None and kind != 4 and g > 0.0:
            # v9: the work needs me standing on p from turn offset `used`. A
            # rival forecast to stand there first -- to claim it, raid it, or
            # come home to it -- closes the cell and takes the work with it.
            g *= self._surv.survival(p, used,
                                     owned=self._defend and owner[p] == seat)
        if self._defend and kind == 1 and not self.tr.home_of[p]:
            # fc_defend: reaching my threatened level-1 cell first saves it
            g += self._defence_value(p, v, used, R, care)
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
        if P["risk_frozen"] and tr.frozen[ridx] > cd:
            cd = tr.frozen[ridx]          # C4: frozen is as unable to shield as cooling
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
        skip_home = P["shield_home"] == 2
        for p in range(NC):
            o = occ[p]
            # A home can never be captured, so a rival standing on mine threatens
            # nothing. Counting it as an imminent take made the bot burn a shield
            # (and, on the last turn, its own scoring stay) on a visitor that
            # could not take anything. (shield_home 0 drops it later instead, as
            # a threat only: it is still a body a shield would catch.)
            if (o and o != seat and owner[p] == seat and not frz[p]
                    and not (skip_home and home_of[p])):
                intruders.append((p, o - 1))
        if not intruders:
            return False

        # In the last couple of turns a backfire costs nothing and the cooldown
        # never bites, so shielding is nearly free -- but only nearly: the shield
        # turn is not a stay, so it gives up whatever my own stay would complete.
        if R <= P["free_shield_turns"]:
            if P["last_shield_value"] == 1:
                # B4: "free" only means no backfire and no cooldown. The shield
                # still costs my own action, and on the last turn that action
                # can complete a raid worth 8v-16v. Shield only for a take that
                # can actually happen this turn, and only when stopping it is
                # worth more than what my own stay would finish. A rival on my
                # home threatens nothing: homes can never be taken.
                save = 0.0
                for p, j in intruders:
                    if tr.home_of[p]:
                        continue
                    if (3 if upg[p] else 1) - tr.prog[j] > 1:
                        continue
                    lvl = 2 if upg[p] else 1
                    v = base[p]
                    save += v * lvl + (8.0 * v * lvl + v) * care[j]
                me = tr.pos[seat - 1]
                alt = self._stay_value(owner, upg, base, seat, me) if me is not None else 0
                return save > 0.0 and save >= alt
            if P["last_shield_value"] == 2:
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
            for p, j in intruders:                # v7: shield on any imminent take
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
            if P["shield_home"] != 1 and tr.home_of[p]:
                continue                      # B3: homes can never be taken
            if not P["shield_l1"] and lvl == 1:
                # B2: a committed raider takes a level-1 cell on its first stay
                # after the freeze, while my shield is still down (2 + 1 <= 4).
                # The shield buys three turns, not the cell. Measured: 79-89% of
                # these cells were lost to the same raider within 6 turns anyway.
                continue
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
        if P["backfire_prod"]:
            # C4: it backfires only if EVERY rival on my land leaves -- including
            # ones whose take is not imminent, since staying gets them caught too
            leave = 1.0
            for _p, j in intruders:
                leave *= 1.0 - self._commit_prob(j)
            backfire = leave * P["freeze_cost"] * kappa
        else:
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
            can = self._canon(seat)
            cands.sort(key=lambda w: can[w],
                       reverse=self.P["tie_home"] < 0)
        if not cands:
            return "STAY"
        myrank = (seat - tr.token) % 4 if tr.token_known else 0
        owner_rule = self.P["contest_owner"]
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
                    if owner_rule and owner[w] == seat:
                        continue              # C4: I own w, so I win any contest
                    if owner_rule and owner[w] == o2:
                        k -= self.P["contest_penalty"]   # they own it: they win
                    elif tr.token_known and (o2 - tr.token) % 4 < myrank:
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


def act(state):
    """Module-level entry point matching the starter kit's signature."""
    try:
        bid = int(state.bot_id)
    except Exception:
        return "STAY"
    a = _AGENTS.get(bid)
    if a is None:
        a = Agent(seed=bid * 7919)
        _AGENTS[bid] = a
    return a(state)