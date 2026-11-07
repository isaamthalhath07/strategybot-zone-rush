"""
Greedy Pruned Minimax Bot for Zone Rush (4-player simultaneous-move grid strategy game).

Architecture:
  1. State Reconstruction (Tracker):
     Reconstructs hidden game state (turn, all 4 scores, incomes, take/upgrade
     progress, shield cooldowns, freeze counters, priority token, and empirical
     opponent shield/commit rates) from board diffs.
  2. Fast 4-Player Simultaneous-Move Simulator (_sim_step):
     Exact lightweight forward model of the Zone Rush engine (priority-token
     collision resolution, owner tie-breaks, shield catches & backfires, progress
     accrual, raid bonuses, and income ticks).
  3. Greedy Action Pruning (_prune_actions):
     At each node in the game tree, ranks all legal actions {NORTH, SOUTH, WEST,
     EAST, STAY, SHIELD} for each seat using a fast greedy action-value heuristic:
       - Keeps top K_me (default 3) candidate actions for our bot.
       - Keeps top K_opp (default 2) epsilon-rational responses for nearby/
         interacting rivals and top-1 greedy best response for distant rivals.
       - Reduces per-turn branching factor from 6^4 = 1,296 to ~6-12 joint
         profiles while preserving all critical tactical interactions.
  4. Cluster-Invariant Alpha-Beta Minimax with Simultaneous Shield Mixing:
     Combines 7-visit beam-search cluster continuations (`cont_after[f]`) with
     exact D-ply 4-player minimax simulation (`_sim_step`) so the tree-to-leaf
     boundary is horizon-invariant on uncontested walks while resolving cell
     races, priority-token contests, counter-raids, and shield/raid subgames.
"""
import json
import os
import time

import mybot
from mybot import (N, NC, MAX_TURNS, NEIGH, NEIGH_SYM, STEP_NAME, MANH, DIST,
                   SYM, Tracker, _bfs)

ACT_NAMES = ("NORTH", "SOUTH", "WEST", "EAST", "STAY", "SHIELD")
ACT_DELTA = (-8, 8, -1, 1, 0, 0)
NAME_TO_ACT = {nm: i for i, nm in enumerate(ACT_NAMES)}

LEGAL_MOVES_SYM = []
for _s in range(4):
    _seat_moves = []
    for _p in range(NC):
        _m = []
        for _w in NEIGH_SYM[_s][_p]:
            _nm = STEP_NAME[(_p, _w)]
            _m.append((NAME_TO_ACT[_nm], _w))
        _seat_moves.append(tuple(_m))
    LEGAL_MOVES_SYM.append(tuple(_seat_moves))


def _load_default_params():
    if os.path.exists("best_params.json"):
        try:
            with open("best_params.json") as f:
                p = dict(mybot.PARAMS)
                p.update(json.load(f))
                return p
        except Exception:
            pass
    return dict(mybot.PARAMS)


DEFAULT_PARAMS = _load_default_params()


class GreedyPrunedMinimaxBot(object):
    """
    4-player Greedy Pruned Minimax Bot with Alpha-Beta Pruning, Iterative
    Deepening, Bayesian Simultaneous-Shield Subgame Resolution, and
    Cluster-Invariant Leaf Evaluation.
    """
    name = "minimax"

    def __init__(self, seed=0, max_depth=3, k_me=3, k_opp=2, budget_ms=55.0,
                 params=None):
        self.P = dict(DEFAULT_PARAMS)
        if params:
            self.P.update(params)
        self.max_depth = max_depth
        self.k_me = k_me
        self.k_opp = k_opp
        self.budget_ms = budget_ms
        self.helper = mybot.Agent(seed=seed, params=self.P)
        self.tr = self.helper.tr
        self.last_action = None
        self.plan_target = None
        self._deadline = 0.0
        self.nodes_searched = 0
        self.depth_reached = 0

    def __call__(self, view):
        try:
            a = self.decide(view)
        except Exception:
            a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        self.last_action = a
        self.helper.last_action = a
        return a

    def act(self, view):
        return self(view)

    # ------------------------------------------------------------------ entry
    def decide(self, view):
        t_start = time.perf_counter()
        self._deadline = t_start + self.budget_ms / 1000.0
        self.nodes_searched = 0

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
        me_idx = seat - 1
        tr = self.tr
        tr.observe(owner, upg, occ, frz, seat, view.is_priority_token, base,
                   home_of, self.last_action)
        if tr.turn == 1:
            self.plan_target = None
            self.helper.plan_target = None
            self.helper._beam_scale = 1.0
        if tr.frozen[me_idx] > 0:
            self.plan_target = None
            self.helper.plan_target = None

        me = tr.pos[me_idx]
        if me is None or any(x is None for x in tr.pos):
            self.last_action = "STAY"
            return "STAY"
        legal = view.legal_actions
        if len(legal) == 1:
            self.last_action = legal[0]
            return legal[0]

        R = MAX_TURNS - tr.turn + 1
        if R < 1:
            R = 1
        P = self.P
        care = self.helper._care(seat)
        kappa = max(1.0, P["kappa"] * R)

        # 1. Check immediate defensive shield via the 2x2 matrix subgame
        if "SHIELD" in legal:
            dkappa = max(1.0, P["def_kappa"] * R)
            if self.helper._should_shield(owner, upg, occ, frz, base, seat, R,
                                          dkappa, care):
                self.plan_target = None
                self.helper.plan_target = None
                self.last_action = "SHIELD"
                return "SHIELD"

        # 2. Compute root 7-visit cluster table (bestby & single-visit gain_1)
        self._base = base
        self._home_of = home_of
        self._zone = tr.zone
        self._care = care
        self._me_idx = me_idx
        self._root_R = R
        self._root_turn = tr.turn
        self._root_owner = owner[:]
        self._root_upg = upg[:]
        self._q_sh = [tr.q_shield(i, P["q_prior"], P["q_weight"]) for i in range(4)]
        self._commit_p = [self.helper._commit_prob(i) for i in range(4)]

        walk_act = self._build_root_clusters(owner, upg, base, home_of, occ, frz,
                                             seat, me, R, kappa, care)
        walk_act_code = NAME_TO_ACT.get(walk_act, 4)
        self._walk_act_code = walk_act_code

        # Build current income vector
        inc = [0, 0, 0, 0]
        for p in range(NC):
            o = owner[p]
            if o:
                inc[o - 1] += base[p] * (2 if upg[p] else 1)

        root_state = (
            owner[:],
            upg[:],
            list(tr.pos),
            list(tr.frozen),
            list(tr.cd),
            list(tr.prog),
            list(tr.score),
            inc,
            tr.turn,
            tr.token,
        )
        self._root_realized_me = self._realized_me_val(root_state)
        self._root_opp_val = [float(tr.score[j] + inc[j] * R) for j in range(4)]

        legal_codes = set(NAME_TO_ACT[a] for a in legal if a in NAME_TO_ACT)
        my_root_acts = self._prune_actions(root_state, me_idx, self.k_me,
                                           is_root=True, legal_filter=legal_codes)
        if not my_root_acts:
            res = walk_act if walk_act in legal else "STAY"
            self.last_action = res
            return res
        if len(my_root_acts) == 1:
            res = ACT_NAMES[my_root_acts[0]]
            self.last_action = res
            return res

        # 3. Iterative Deepening Greedy-Pruned Minimax Search (depth 1 .. max_depth)
        best_act = walk_act_code if walk_act_code in my_root_acts else my_root_acts[0]
        max_d = min(self.max_depth, R)
        ordered_acts = list(my_root_acts)

        for depth in range(1, max_d + 1):
            if time.perf_counter() > self._deadline:
                break
            alpha = -1e18
            beta = 1e18
            scored = []
            aborted = False
            for a_me in ordered_acts:
                if time.perf_counter() > self._deadline:
                    aborted = True
                    break
                self._cur_root_act = a_me
                val = self._min_node(root_state, a_me, depth, alpha, beta, is_root=True)
                if a_me == walk_act_code:
                    val += 5.0
                scored.append((val, a_me))
                if val > alpha:
                    alpha = val
            if not aborted and scored:
                scored.sort(reverse=True)
                best_act = scored[0][1]
                ordered_acts = [a for _, a in scored]
                self.depth_reached = depth

        res = ACT_NAMES[best_act]
        if res not in legal:
            res = walk_act if walk_act in legal else "STAY"
        self.last_action = res
        return res

    # ----------------------------------------- root 7-visit cluster precompute
    def _build_root_clusters(self, owner, upg, base, home_of, occ, frz, seat,
                             me, R, kappa, care):
        """
        Run the 7-visit beam search at the root and record:
          - self._bestby[f]: sticky 7-visit cluster value starting with target f
          - self._gain1[f]:  first-visit value on target f alone
          - self._cont[f]:   remaining 6-visit continuation value after f completes
          - self._cand_meta[f]: (kind, v, need_root, dist_root)
        """
        P = self.P
        tr = self.tr
        h = self.helper
        h._deadline = time.perf_counter() + 0.018

        mydist = DIST[me]
        mod = [1.0] * NC
        zone = tr.zone
        perish = 1.0 + P["perish"]
        safe = P["safe_discount"]
        zb = P["zone_bonus"]
        sq = P["squat_penalty"]
        for p in range(NC):
            m = 1.0
            rd = 99
            for j in range(4):
                if j == seat - 1 or tr.pos[j] is None:
                    continue
                dj = MANH[tr.pos[j]][p]
                if dj < rd:
                    rd = dj
            if rd < mydist[p]:
                m = perish
            elif rd > mydist[p] + 3:
                m = safe
            if zone[p] == seat:
                m *= zb
            elif (P["steal"] > 0.0 and tr.turn <= P["steal_until"]
                  and base[p] >= P["steal_min"]):
                m *= (1.0 + P["steal"])
            if occ[p] and p != me:
                m *= sq
            mod[p] = m
        h._cellmod = mod
        self._cellmod = mod

        f_clk = max(0.0, min(1.0, 1.0 - (R / float(MAX_TURNS))))
        cons = P["consolidate"]
        if cons != 0.0:
            wc = max(0.0, P["w_claim"] * (1.0 - cons * f_clk))
            wu = P["w_upgrade"] * (1.0 + cons * f_clk)
        else:
            wc = P["w_claim"]
            wu = P["w_upgrade"]
        w_raid_cur = P["w_raid"] + (P["w_raid_late"] - P["w_raid"]) * f_clk
        self._wc = wc
        self._wu = wu
        self._w_raid_cur = w_raid_cur

        cands = h._candidates(owner, upg, base, home_of, occ, seat, me, R, care)
        self._bestby = {}
        self._gain1 = {}
        self._cont = {}
        self._cand_meta = {}
        if not cands:
            return h._idle(owner, upg, base, occ, seat, me, R, care)

        horizon = R if R < P["horizon"] else P["horizon"]
        lc = P["lead_caution"]
        standing = h._standing(seat) if lc > 0.0 else 0.0
        w_denial = P["w_denial"]
        rr = P["raid_risk"]
        fc_kappa = P["freeze_cost"] * kappa
        prog_me = tr.prog[seat - 1]

        cellbit = {}
        prep = []
        for (_, p, kind, v, need) in cands:
            k = cellbit.get(p)
            if k is None:
                k = len(cellbit)
                cellbit[p] = k
            bit = 1 << k
            max_nu = horizon if horizon < R else R
            if kind in (0, 1, 3) and max_nu >= R:
                max_nu = R - 1
            mp = mod[p]
            if kind == 0:
                sl = v * wc * mp
                A = [sl * (R - need)] * 15
                B = [sl] * 15
            elif kind == 1:
                sl = v * wu * mp
                A = [sl * (R - need)] * 15
                B = [sl] * 15
            elif kind == 3:
                s1 = v * wc * P["combo"] * mp
                s2 = v * wu * P["combo"] * mp
                sl = s1 + s2
                A = [s1 * (R - 1) + s2 * (R - need)] * 15
                B = [sl] * 15
            elif kind == 4:
                v4 = h._threat(p, owner, upg, None, occ, seat, R, care) * P["hold"] * mp
                A = [v4] * 15
                B = [0.0] * 15
            else:
                o = owner[p]
                lvl = 2 if upg[p] else 1
                take = 8.0 * v * lvl
                rate = v * (1.0 + lvl * w_denial * care[o - 1])
                mult = w_raid_cur * mp
                A = [0.0] * 15
                B = [0.0] * 15
                for trv in range(15):
                    q = h._shield_risk(o - 1, trv, need)
                    if lc > 0.0:
                        q = max(0.0, min(1.0, q + lc * standing * (1.0 - q)))
                    surv = 1.0 - q * rr
                    B[trv] = rate * surv * mult
                    A[trv] = ((take + rate * (R - need)) * surv - q * rr * fc_kappa) * mult
            only_t0 = (p == me and prog_me > 0)
            prep.append((p, bit, need, max_nu, DIST[p], A, B, only_t0))
            d0 = DIST[me][p]
            g1 = A[d0] - B[d0] * d0
            if p not in self._cand_meta:
                self._cand_meta[p] = (kind, v, need, d0)
                self._gain1[p] = g1

        beam = {(me, 0, 0): (0.0, None)}
        bestby = {}
        tick = 0
        deadline = h._deadline
        perf = time.perf_counter
        width = max(8, int(P["beam"] * h._beam_scale))
        for _ in range(P["visits"]):
            if perf() > deadline:
                break
            nxt = {}
            nxt_get = nxt.get
            best_get = bestby.get
            for (pos, used, mask), (val, first) in beam.items():
                tick += 1
                if not (tick & 15) and perf() > deadline:
                    break
                w_step = 1.0 - 0.005 * used
                for (p, bit, need, max_nu, dist_p, A, B, only_t0) in prep:
                    if mask & bit:
                        continue
                    if only_t0 and used > 0:
                        continue
                    travel = dist_p[pos]
                    ut = used + travel
                    nu = ut + need
                    if nu > max_nu:
                        continue
                    g = A[travel] - B[travel] * ut
                    nv = val + g * w_step
                    f = first if first is not None else p
                    st = (p, nu, mask | bit)
                    cur = nxt_get(st)
                    if cur is None or cur[0] < nv:
                        nxt[st] = (nv, f)
                    if best_get(f, -1e18) < nv:
                        bestby[f] = nv
            if not nxt:
                break
            if len(nxt) > width:
                items = sorted(nxt.items(), key=lambda kv: -kv[1][0])[:width]
                beam = dict(items)
            else:
                beam = nxt

        if not bestby:
            return h._idle(owner, upg, base, occ, seat, me, R, care)

        stick = P["stickiness"]
        target, tv = None, -1e18
        for f, v in bestby.items():
            s = v * (stick if f == self.plan_target else 1.0)
            self._bestby[f] = s
            g1 = self._gain1.get(f, 0.0)
            self._cont[f] = max(0.0, s - g1)
            if s > tv:
                tv, target = s, f
        self.plan_target = target
        h.plan_target = target
        self._root_act_val = {}
        dist_me = DIST[me]
        self._root_act_val[4] = self._bestby.get(me, tv - 35.0)
        for act_code, w in LEGAL_MOVES_SYM[seat - 1][me]:
            dw = DIST[w]
            best_w = tv - 45.0
            for f, fval in self._bestby.items():
                if f != me and dw[f] == dist_me[f] - 1:
                    if fval > best_w:
                        best_w = fval
            self._root_act_val[act_code] = best_w
        if target == me:
            return "STAY"
        return h._step(me, target, occ, owner, seat)

    # ------------------------------------------------- greedy action pruning
    def _prune_actions(self, st, s_idx, k, is_root=False, legal_filter=None):
        """
        Rank legal actions for seat `s_idx` using a fast greedy 1-step + target
        field heuristic and prune to the top `k` actions.
        """
        owner, upg, pos, frozen, cd, prog, score, inc, turn, token = st
        if frozen[s_idx] > 0:
            return [4]

        seat = s_idx + 1
        here = pos[s_idx]
        if s_idx != self._me_idx and owner[here] == seat and upg[here]:
            return [4]

        R = MAX_TURNS - turn + 1
        if R < 1:
            R = 1
        base = self._base
        home_of = self._home_of
        zone = self._zone
        P = self.P
        is_pacifist_rival = (
            s_idx != self._me_idx
            and self.tr.takes[s_idx] == 0
            and self.tr.raids[s_idx] == 0
        )

        # At the root for our own bot, rank moves directly using the 7-visit
        # cluster values `_bestby[f]` plus immediate tactical raids/claims!
        if is_root and s_idx == self._me_idx and self._bestby:
            cands = []
            dist_here = DIST[here]
            if legal_filter is None or 4 in legal_filter:
                st_val = self._bestby.get(here, -50.0)
                cands.append((st_val, 4))
            for act_code, w in LEGAL_MOVES_SYM[s_idx][here]:
                if legal_filter is not None and act_code not in legal_filter:
                    continue
                dw = DIST[w]
                best_via_w = -50.0
                for f, fval in self._bestby.items():
                    if f != here and dw[f] == dist_here[f] - 1:
                        if fval > best_via_w:
                            best_via_w = fval
                if act_code == self._walk_act_code:
                    best_via_w += 15.0
                cands.append((best_via_w, act_code))
            cands.sort(reverse=True)
            if len(cands) > 1:
                best_root_sc = cands[0][0]
                cands = [ca for ca in cands if ca[0] >= best_root_sc - 45.0]
            out = [a for _, a in cands[:k]]
            if self._walk_act_code not in out and (legal_filter is None or self._walk_act_code in legal_filter):
                out[-1] = self._walk_act_code
            return out if out else [4]

        dist_here = DIST[here]
        best_target_val = [0.0] * NC
        for p in range(NC):
            d = dist_here[p]
            if d > 5:
                continue
            o = owner[p]
            v = base[p]
            if o == 0:
                need = 1
                if d + need > R:
                    continue
                gain = v * (R - d - need) * P["w_claim"]
                if zone[p] == seat:
                    gain *= P["zone_bonus"]
            elif o == seat:
                if upg[p]:
                    continue
                need = max(1, 3 - (prog[s_idx] if p == here else 0))
                if d + need > R:
                    continue
                gain = v * (R - d - need) * P["w_upgrade"]
                if zone[p] == seat:
                    gain *= P["zone_bonus"]
            else:
                if home_of[p]:
                    continue
                lvl = 2 if upg[p] else 1
                need = max(1, (3 if lvl == 2 else 1) - (prog[s_idx] if p == here else 0))
                if d + need > R:
                    continue
                q = self._q_sh[o - 1] if (cd[o - 1] < d + need and frozen[o - 1] < d + need) else 0.0
                if need > 1 and 0 < cd[o - 1] < d + need and self.tr.shields_seen[o - 1] > 0:
                    q = max(q, 0.85)
                surv = max(0.05, 1.0 - (1.0 - (1.0 - q) ** need) * P["raid_risk"])
                gain = (8.0 * v * lvl + v * (R - d - need) * (1.0 + lvl * P["w_denial"])) * surv * P["w_raid"]
                if is_pacifist_rival:
                    gain *= 0.20
            if s_idx == self._me_idx and self._cellmod is not None:
                gain *= self._cellmod[p]
            elif p != here and p in pos:
                gain *= 0.25
            best_target_val[p] = gain / float(d + need)

        cands = []
        if legal_filter is None or 4 in legal_filter:
            stay_score = best_target_val[here] * 1.15 if best_target_val[here] > 0 else -5.0
            if owner[here] == 0 and R > 2:
                stay_score += 20.0
            if prog[s_idx] > 0:
                stay_score *= 1.45
            cands.append((stay_score, 4))

        my_rank = (s_idx - (token - 1)) % 4
        for act_code, w in LEGAL_MOVES_SYM[s_idx][here]:
            if legal_filter is not None and act_code not in legal_filter:
                continue
            occ_by = -1
            for j in range(4):
                if j != s_idx and pos[j] == w:
                    occ_by = j
                    break
            if occ_by >= 0 and (frozen[occ_by] > 0 or best_target_val[w] > 15.0):
                move_score = -20.0
            else:
                dw = DIST[w]
                best_via_w = 0.0
                for p in range(NC):
                    rt = best_target_val[p]
                    if rt > 0.0 and dw[p] == dist_here[p] - 1:
                        if rt > best_via_w:
                            best_via_w = rt
                move_score = best_via_w
                if owner[w] == 0:
                    move_score += 1.5 * base[w]
                elif owner[w] == seat:
                    move_score += 0.3
                for j in range(4):
                    if j != s_idx and frozen[j] == 0 and DIST[pos[j]][w] == 1:
                        j_rank = (j - (token - 1)) % 4
                        if j_rank < my_rank:
                            move_score -= 6.0
                        else:
                            move_score -= 1.5
            cands.append((move_score, act_code))

        cands.sort(reverse=True)
        if s_idx != self._me_idx and len(cands) > 1:
            best_sc = cands[0][0]
            cands = [ca for ca in cands if ca[0] >= best_sc - 5.0]
        out = [a for _, a in cands[:k]]
        return out if out else [4]

    # --------------------------------------------------------- minimax search
    def _max_node(self, st, depth, alpha, beta):
        self.nodes_searched += 1
        if depth <= 0 or st[8] > MAX_TURNS or time.perf_counter() > self._deadline:
            return self._eval_leaf(st)
        my_acts = self._prune_actions(st, self._me_idx, self.k_me)
        best = -1e18
        for a_me in my_acts:
            val = self._min_node(st, a_me, depth, alpha, beta)
            if val > best:
                best = val
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    def _min_node(self, st, a_me, depth, alpha, beta, is_root=False):
        owner, upg, pos, frozen, cd, prog, score, inc, turn, token = st
        me_idx = self._me_idx
        my_pos = pos[me_idx]

        opp_lists = [None] * 4
        opp_lists[me_idx] = (a_me,)
        landlord_idx = -1
        my_cell_owner = owner[my_pos]
        if my_cell_owner not in (0, me_idx + 1) and not self._home_of[my_pos]:
            need_left = (3 if upg[my_pos] else 1) - prog[me_idx]
            if need_left <= 1 and cd[my_cell_owner - 1] == 0 and frozen[my_cell_owner - 1] == 0:
                landlord_idx = my_cell_owner - 1

        interacting_count = 0
        for j in range(4):
            if j == me_idx:
                continue
            pj = pos[j]
            inter = (DIST[my_pos][pj] <= 3 or owner[pj] == me_idx + 1 or j == landlord_idx)
            if inter and interacting_count < 2:
                interacting_count += 1
                acts_j = self._prune_actions(st, j, self.k_opp)
                if j == landlord_idx and 5 not in acts_j:
                    acts_j = list(acts_j) + [5]
                opp_lists[j] = tuple(acts_j)
            else:
                opp_lists[j] = tuple(self._prune_actions(st, j, 1))

        if landlord_idx >= 0 and 5 in opp_lists[landlord_idx] and len(opp_lists[landlord_idx]) > 1:
            q = self._q_sh[landlord_idx]
            non_sh = tuple(a for a in opp_lists[landlord_idx] if a != 5)
            opp_sh = list(opp_lists)
            opp_sh[landlord_idx] = (5,)
            opp_nosh = list(opp_lists)
            opp_nosh[landlord_idx] = non_sh
            v_sh = self._min_over_profiles(st, opp_sh, depth, -1e18, 1e18)
            v_nosh = self._min_over_profiles(st, opp_nosh, depth, -1e18, 1e18)
            return q * v_sh + (1.0 - q) * v_nosh

        return self._min_over_profiles(st, opp_lists, depth, alpha, beta)

    def _min_over_profiles(self, st, opp_lists, depth, alpha, beta):
        worst = 1e18
        for a0 in opp_lists[0]:
            for a1 in opp_lists[1]:
                for a2 in opp_lists[2]:
                    for a3 in opp_lists[3]:
                        nxt_st = self._sim_step(st, (a0, a1, a2, a3))
                        v = self._max_node(nxt_st, depth - 1, alpha, min(beta, worst))
                        if v < worst:
                            worst = v
                        if worst <= alpha:
                            return worst
        return worst

    # ------------------------------------------------ fast 4-player simulator
    def _sim_step(self, st, acts):
        """Exact fast 4-player simultaneous-move transition."""
        owner, upg, pos, frozen, cd, prog, score, inc, turn, token = st
        owner = owner[:]
        upg = upg[:]
        pos = pos[:]
        frozen = frozen[:]
        cd = cd[:]
        prog = prog[:]
        score = score[:]
        inc = inc[:]
        base = self._base
        home_of = self._home_of

        eff = [4] * 4
        for i in range(4):
            if frozen[i] > 0:
                eff[i] = 4
                continue
            a = acts[i]
            if a == 5:
                eff[i] = 4 if cd[i] > 0 else 5
            elif a < 4:
                np = pos[i] + ACT_DELTA[a]
                if 0 <= np < NC and DIST[pos[i]][np] == 1:
                    eff[i] = a
                else:
                    eff[i] = 4
            else:
                eff[i] = 4

        p0, p1, p2, p3 = pos[0], pos[1], pos[2], pos[3]
        intents = {}
        for i in range(4):
            a = eff[i]
            if a < 4:
                t = pos[i] + ACT_DELTA[a]
                if t == p0 or t == p1 or t == p2 or t == p3:
                    eff[i] = 4
                else:
                    intents.setdefault(t, []).append(i)
        for t, seats in intents.items():
            if len(seats) == 1:
                w = seats[0]
            else:
                ot = owner[t]
                w = -1
                for s in seats:
                    if ot == s + 1:
                        w = s
                        break
                if w < 0:
                    best = 99
                    for s in seats:
                        rk = (s + 1 - token) & 3
                        if rk < best:
                            best, w = rk, s
                for s in seats:
                    if s != w:
                        eff[s] = 4
            pos[w] = t
            prog[w] = 0
        for i in range(4):
            if eff[i] == 5:
                prog[i] = 0

        shielders = [i for i in range(4) if eff[i] == 5]
        caught = [False] * 4
        newfrozen = [0] * 4
        for s in shielders:
            seat = s + 1
            got = []
            for j in range(4):
                if j == s or frozen[j] > 0 or eff[j] != 4:
                    continue
                if owner[pos[j]] == seat:
                    got.append(j)
            if got:
                for j in got:
                    caught[j] = True
                    newfrozen[j] = 2
                    prog[j] = 0
            else:
                newfrozen[s] = 2

        for i in range(4):
            if eff[i] != 4 or caught[i] or frozen[i] > 0:
                continue
            p = pos[i]
            seat = i + 1
            o = owner[p]
            v = base[p]
            if o == seat:
                if not upg[p]:
                    prog[i] += 1
                    if prog[i] >= 3:
                        upg[p] = 1
                        prog[i] = 0
                        inc[i] += v
            elif o == 0:
                prog[i] += 1
                if prog[i] >= 1:
                    owner[p] = seat
                    inc[i] += v
                    prog[i] = 0
            else:
                if home_of[p] or (o - 1) in shielders:
                    continue
                lvl = 2 if upg[p] else 1
                needed = 3 if lvl == 2 else 1
                prog[i] += 1
                if prog[i] >= needed:
                    score[i] += 8 * v * lvl
                    inc[o - 1] -= v * lvl
                    owner[p] = seat
                    upg[p] = 0
                    inc[i] += v
                    prog[i] = 0

        for i in range(4):
            score[i] += inc[i]

        for i in range(4):
            if frozen[i] > 0:
                frozen[i] -= 1
            if newfrozen[i]:
                frozen[i] = newfrozen[i]
                prog[i] = 0
            if i in shielders:
                cd[i] = 4
            elif cd[i] > 0:
                cd[i] -= 1

        return (owner, upg, pos, frozen, cd, prog, score, inc, turn + 1, token % 4 + 1)

    # ------------------------------------------ cluster-invariant leaf eval
    def _realized_me_val(self, st):
        owner, upg, pos, frozen, cd, prog, score, inc, turn, token = st
        me = self._me_idx
        me_seat = me + 1
        R = self._root_R
        wc = self._wc
        wu = self._wu
        wr = self._w_raid_cur
        mod = self._cellmod
        base = self._base
        val = float(score[me]) * wr
        for p in range(NC):
            if owner[p] == me_seat:
                mp = mod[p]
                v = base[p]
                val += v * R * wc * mp
                if upg[p]:
                    val += v * R * wu * mp
        return val

    def _eval_leaf(self, st):
        """
        Evaluate a leaf state at `turn` with `R` turns remaining:
          - For rivals j != me: exact realized score + remaining income + in-progress
            work credit - freeze penalty from the D-turn minimax simulation.
          - For our bot (me): exact realized score + remaining income - freeze penalty
            + monotonic multi-step continuation walk filling budget = min(R, 18),
            ordered by the tuned (w_claim, w_upgrade, w_raid, cellmod) priority rate
            and adding 0.92 * exact_sim_step_delta so tree completion strictly beats
            delaying work in the leaf.
        """
        owner, upg, pos, frozen, cd, prog, score, inc, turn, token = st
        R = MAX_TURNS - turn + 1
        if R < 0:
            R = 0
        base = self._base
        home_of = self._home_of
        zone = self._zone
        P = self.P
        me = self._me_idx
        me_seat = me + 1
        w_claim = self._wc
        w_upgrade = self._wu
        w_raid = self._w_raid_cur
        w_denial = P["w_denial"]
        zb = P["zone_bonus"]
        rr = P["raid_risk"]
        cellmod = self._cellmod
        budget = R if R < 18 else 18

        proj = [0.0] * 4
        for i in range(4):
            seat = i + 1
            cur = pos[i]
            used = frozen[i]
            if i != me:
                val = float(score[i] + inc[i] * R)
                if used > 0:
                    val -= used * 0.75 * R
                if used == 0 and prog[i] > 0 and R > 0:
                    o = owner[cur]
                    v = base[cur]
                    if o == seat and not upg[cur]:
                        rem = max(0, R - (3 - prog[i]))
                        val += (prog[i] / 3.0) * v * rem
                    elif o not in (0, seat) and not home_of[cur]:
                        lvl = 2 if upg[cur] else 1
                        need = 3 if lvl == 2 else 1
                        rem = max(0, R - (need - prog[i]))
                        val += (prog[i] / float(need)) * (8.0 * v * lvl + v * rem)
                proj[i] = val
                continue

            val = float(score[me] + inc[me] * R)
            if used > 0:
                val -= used * P["freeze_cost"] * max(1.0, P["kappa"] * R) * 0.6
            if used >= budget or R <= 0:
                proj[i] = val
                continue

            visited = set()
            # 1. If work is already in progress on cur, finish it first (0.96x exact delta)
            if prog[i] > 0:
                o = owner[cur]
                v = base[cur]
                if o == seat and not upg[cur]:
                    need_left = max(1, 3 - prog[i])
                    rem = R - (used + need_left)
                    if rem > 0:
                        g_pts = 0.96 * v * rem
                        if used + need_left <= budget:
                            val += g_pts
                            used += need_left
                            visited.add(cur)
                        else:
                            val += g_pts * float(budget - used) / float(need_left)
                            used = budget
                elif o not in (0, seat) and not home_of[cur]:
                    lvl = 2 if upg[cur] else 1
                    need_left = max(1, (3 if lvl == 2 else 1) - prog[i])
                    rem = R - (used + need_left)
                    if rem >= 0:
                        q = self._q_sh[o - 1] if (cd[o - 1] < need_left and frozen[o - 1] < need_left) else 0.0
                        surv = max(0.0, 1.0 - (1.0 - (1.0 - q) ** need_left) * rr)
                        raw_delta = 8.0 * v * lvl + v * rem * (1.0 + lvl * w_denial)
                        g_pts = 0.96 * (raw_delta * surv - (1.0 - surv) * P["freeze_cost"] * 0.8 * R)
                        if used + need_left <= budget:
                            val += g_pts
                            used += need_left
                            visited.add(cur)
                        else:
                            val += g_pts * float(budget - used) / float(need_left)
                            used = budget

            # 2. Greedy multi-step continuation walk:
            #    - `pri_rate` uses (w_claim, w_upgrade, w_raid, cellmod) to pick the next target
            #    - `best_pts` adds 0.92 * exact_sim_step_delta to `val`
            for _ in range(7):
                if used >= budget:
                    break
                dist_cur = DIST[cur]
                best_p = -1
                best_rate = -1e9
                best_pts = 0.0
                best_cost = 1
                for p in range(NC):
                    if p in visited:
                        continue
                    d = dist_cur[p]
                    if d > 4:
                        continue
                    o = owner[p]
                    v = base[p]
                    mp = cellmod[p] if cellmod is not None else (zb if zone[p] == seat else 1.0)
                    if o == 0:
                        need = 1
                        rem = R - (used + d + need)
                        if rem <= 0:
                            continue
                        pts = 0.92 * v * rem
                        pri_g = v * rem * w_claim * mp
                    elif o == seat:
                        if upg[p]:
                            continue
                        need = 3
                        rem = R - (used + d + need)
                        if rem <= 0:
                            continue
                        pts = 0.92 * v * rem
                        pri_g = v * rem * w_upgrade * mp
                    else:
                        if home_of[p]:
                            continue
                        lvl = 2 if upg[p] else 1
                        need = 3 if lvl == 2 else 1
                        rem = R - (used + d + need)
                        if rem < 0:
                            continue
                        q = self._q_sh[o - 1] if (cd[o - 1] < used + d + need and frozen[o - 1] < used + d + need) else 0.0
                        if need > 1 and 0 < cd[o - 1] < d + need and self.tr.shields_seen[o - 1] > 0:
                            q = max(q, 0.85)
                        surv = max(0.0, 1.0 - (1.0 - (1.0 - q) ** need) * rr)
                        raw_delta = 8.0 * v * lvl + v * rem * (1.0 + lvl * w_denial)
                        pts = 0.92 * (raw_delta * surv - (1.0 - surv) * P["freeze_cost"] * 0.8 * R)
                        pri_g = pts * w_raid * mp
                        if pts <= 0.0:
                            continue
                    if p != cur and p in pos and upg[p]:
                        pri_g *= 0.25
                        pts *= 0.25
                    cost = d + need
                    rate = pri_g / float(cost)
                    if rate > best_rate:
                        best_rate = rate
                        best_p = p
                        best_pts = pts
                        best_cost = cost
                if best_p < 0 or best_pts <= 0.0:
                    break
                if used + best_cost <= budget:
                    val += best_pts * (1.0 - 0.005 * used)
                    used += best_cost
                    cur = best_p
                    visited.add(best_p)
                else:
                    frac = float(budget - used) / float(best_cost)
                    val += best_pts * frac * (1.0 - 0.005 * used)
                    used = budget
                    break

            proj[i] = val

        my_p = proj[me] + 0.30 * self._root_act_val.get(getattr(self, "_cur_root_act", 4), 0.0)
        care = self._care
        rivals = [j for j in range(4) if j != me]
        max_rival = max(proj[j] for j in rivals)
        opp_blend = 0.40 * max_rival + 0.60 * (sum(proj[j] * care[j] for j in rivals) / 3.0)
        return my_p - opp_blend * w_denial


_BOTS = {}


def act(state):
    """Module-level entry point matching the starter kit's signature."""
    try:
        bid = state.bot_id
    except Exception:
        return "STAY"
    b = _BOTS.get(bid)
    if b is None:
        b = GreedyPrunedMinimaxBot(seed=bid * 7919)
        _BOTS[bid] = b
    return b(state)
