class Agent(object):
    def __init__(self, seed=0, params=None):
        self.P = dict(PARAMS)
        if params:
            self.P.update(params)
        self.tr = Tracker()
        self.last_action = None
        self.plan = []
        self.rng = seed * 2654435761 % 4294967291 or 12345

    def rand(self):
        self.rng = (1103515245 * self.rng + 12345) % 2147483648
        return self.rng / 2147483648.0

    # ------------------------------------------------------------------ entry
    def __call__(self, view):
        try:
            a = self.decide(view)
        except Exception:
            a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        self.last_action = a
        return a

    def decide(self, view):
        P = self.P
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
        me = tr.pos[seat - 1]
        if me is None:
            return "STAY"
        legal = view.legal_actions
        if len(legal) == 1:
            return legal[0]

        R = MAX_TURNS - tr.turn + 1           # turns left, including this one
        care = self._care(seat)
        kappa = max(1.0, P["kappa"] * R)

        # ---- defence: the shield/raid subgame -------------------------------
        if "SHIELD" in legal:
            if self._should_shield(owner, upg, occ, frz, base, seat, R, kappa, care):
                self.plan = []
                return "SHIELD"

        # ---- plan a whole walk, not a single target -------------------------
        act = self._plan_walk(owner, upg, base, home_of, occ, frz, seat, me, R,
                              kappa, care)
        return act if act is not None else "STAY"

    # ------------------------------------------------------------ objective
    def _care(self, seat):
        """Placement objective: weight each rival by how contested that pairing is."""
        P = self.P
        tr = self.tr
        mine = tr.score[seat - 1]
        tau = P["tau"]
        care = [0.0] * 4
        tot = 0.0
        for j in range(4):
            if j == seat - 1:
                continue
            x = (mine - tr.score[j]) / tau
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
            out.append((pri, p, kind, v, need))
        out.sort(reverse=True)
        return out[:P["ncand"]]

    def _work_gain(self, p, kind, v, need, used, owner, upg, occ, seat, R,
                   kappa, care, travel):
        """Points of final score from completing the work on p, started after
        `used` turns have already been spent."""
        P = self.P
        tr = self.tr
        rem = R - used - need                 # turns the cell will pay out
        if kind == 0:
            if rem <= 0:
                return None
            g = v * rem * P["w_claim"]
        elif kind == 1:
            if rem <= 0:
                return None
            g = v * rem * P["w_upgrade"]
        else:
            if rem < 0:
                return None
            o = owner[p]
            lvl = 2 if upg[p] else 1
            take = 8.0 * v * lvl
            inc = v * rem
            den = v * lvl * rem * P["w_denial"] * care[o - 1]
            q = self._shield_risk(o - 1, travel, need)
            g = ((take + inc + den) * (1.0 - q * P["raid_risk"])
                 - q * P["raid_risk"] * P["freeze_cost"] * kappa)
            g *= P["w_raid"]
        # perishability: a cell a rival can reach sooner should be taken now
        rd = 99
        for j in range(4):
            if j == seat - 1 or tr.pos[j] is None:
                continue
            dj = MANH[tr.pos[j]][p]
            if dj < rd:
                rd = dj
        if rd <= travel:
            g *= (1.0 + P["perish"])
        elif rd > travel + 3:
            g *= P["safe_discount"]
        if tr.zone[p] == seat:
            g *= P["zone_bonus"]
        if occ[p] and p != tr.pos[seat - 1]:
            g *= P["squat_penalty"]
        return g

    def _plan_walk(self, owner, upg, base, home_of, occ, frz, seat, me, R,
                   kappa, care):
        """
        Beam search over walks: visit a sequence of work-cells, paying the real
        travel cost between them. Scoring whole walks (instead of ranking single
        targets by rate) prices travel correctly, naturally prefers clusters, and
        stops the bot oscillating between two distant targets.
        """
        P = self.P
        cands = self._candidates(owner, upg, base, home_of, occ, seat, me, R, care)
        if not cands:
            return self._idle(owner, upg, base, occ, seat, me, R, care)
        horizon = R if R < P["horizon"] else P["horizon"]
        idx = {}
        for k, (_, p, kind, v, need) in enumerate(cands):
            idx[p] = k
        # state -> (value, first_cell)   state = (pos, used, mask)
        beam = {(me, 0, 0): (0.0, None)}
        best = (0.0, None)
        for _ in range(P["visits"]):
            nxt = {}
            for (pos, used, mask), (val, first) in beam.items():
                for k, (_, p, kind, v, need) in enumerate(cands):
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
                    if nv > best[0]:
                        best = (nv, f)
            if not nxt:
                break
            if len(nxt) > P["beam"]:
                items = sorted(nxt.items(), key=lambda kv: -kv[1][0])[:P["beam"]]
                beam = dict(items)
            else:
                beam = nxt
        target = best[1]
        if target is None:
            return self._idle(owner, upg, base, occ, seat, me, R, care)
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

        stake = 0.0
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
            # how likely is this bot to actually commit rather than step away?
            commit = self._commit_prob(j)
            stake += (lost + their_gain) * commit
        if stake <= 0.0:
            return False

        # cost of shielding: this turn produces nothing, plus 4 turns with no
        # shield available, plus the backfire risk if they walk away
        cost = kappa * P["shield_cost"]
        if stake < cost * P["shield_bias"]:
            return False
        # 2x2 equilibrium mixing, so a predictable defender cannot be baited
        q = stake / (stake + cost)
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
