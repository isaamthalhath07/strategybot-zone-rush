"""
Zone Rush as batched tensor operations, so thousands of games step at once on the
GPU. This exists only to feed self-play training; the submitted bot stays pure
stdlib Python.

Derived from d385e00:gpuenv.py. Offline physics only: this module is not the
submitted bot and its tensor rollouts are not real-policy campaign games.
probe.py compares it with the independently maintained tests.reference_engine.

Action codes (matching engine.ACTIONS order):
    0 NORTH   1 EAST   2 SOUTH   3 WEST   4 STAY   5 SHIELD
"""
import torch

N_CELLS = 64
SIDE = 8
NORTH, EAST, SOUTH, WEST, STAY, SHIELD = range(6)
CORNERS = (0, 7, 63, 56)          # seat 1..4
BIG = 1 << 20


def _delta_tables(device):
    """target[a, p] = cell reached by action a from cell p, or -1 if off board."""
    tgt = torch.full((6, N_CELLS), -1, dtype=torch.long, device=device)
    for p in range(N_CELLS):
        r, c = divmod(p, SIDE)
        if r > 0:
            tgt[NORTH, p] = p - SIDE
        if r < SIDE - 1:
            tgt[SOUTH, p] = p + SIDE
        if c > 0:
            tgt[WEST, p] = p - 1
        if c < SIDE - 1:
            tgt[EAST, p] = p + 1
        tgt[STAY, p] = p
        tgt[SHIELD, p] = p
    return tgt


class BatchGame(object):
    """`n` independent Zone Rush games advanced in lockstep."""

    def __init__(self, base, n=1024, device="cuda", max_turns=80, start_token=None,
                 rules=None):
        self.dev = torch.device(device)
        self.n = n
        self.max_turns = max_turns
        self.tgt = _delta_tables(self.dev)
        R = {"frozen_stay_counts": False, "claim_resets_progress": True,
             "catch_requires_stay": True, "lost_contest_is_stay": True,
             "home_upgradable": True}
        if rules:
            R.update(rules)
        self.R = R

        if isinstance(base, torch.Tensor):
            b = base.to(self.dev).long()
        else:
            b = torch.tensor(base, dtype=torch.long, device=self.dev)
        if b.dim() == 1:
            b = b.unsqueeze(0).expand(n, N_CELLS).contiguous()
        self.base = b                                     # [n, 64]

        self.owner = torch.zeros((n, N_CELLS), dtype=torch.long, device=self.dev)
        self.upg = torch.zeros((n, N_CELLS), dtype=torch.bool, device=self.dev)
        self.home = torch.zeros((n, N_CELLS), dtype=torch.long, device=self.dev)
        self.pos = torch.zeros((n, 4), dtype=torch.long, device=self.dev)
        self.frozen = torch.zeros((n, 4), dtype=torch.long, device=self.dev)
        self.cd = torch.zeros((n, 4), dtype=torch.long, device=self.dev)
        self.prog = torch.zeros((n, 4), dtype=torch.long, device=self.dev)
        self.score = torch.zeros((n, 4), dtype=torch.long, device=self.dev)
        self.income = torch.zeros((n, 4), dtype=torch.long, device=self.dev)
        self.turn = 1
        if start_token is None:
            self.token = torch.ones(n, dtype=torch.long, device=self.dev)
        elif isinstance(start_token, int):
            self.token = torch.full((n,), start_token, dtype=torch.long,
                                    device=self.dev)
        else:
            self.token = start_token.to(self.dev).long()

        for seat, cell in enumerate(CORNERS, start=1):
            self.home[:, cell] = seat
            self.owner[:, cell] = seat
            self.pos[:, seat - 1] = cell
            self.income[:, seat - 1] = self.base[:, cell]

    # -- helpers --------------------------------------------------------------
    def _occupancy(self):
        """occ[n, cell] = seat standing there, 0 if empty."""
        occ = torch.zeros((self.n, N_CELLS), dtype=torch.long, device=self.dev)
        seats = torch.arange(1, 5, device=self.dev).expand(self.n, 4)
        occ.scatter_(1, self.pos, seats)
        return occ

    def over(self):
        return self.turn > self.max_turns

    # -- one turn -------------------------------------------------------------
    def step(self, actions):
        """actions: [n, 4] long tensor of action codes. Resolves one full turn."""
        R = self.R
        n = self.n
        act = actions.to(self.dev).long().clone()
        act = torch.where((act < 0) | (act > SHIELD),
                          torch.full_like(act, STAY), act)

        # ---- 0. normalise: frozen bots stay, shield on cooldown is a stay,
        #         an off-board move is a stay
        act = torch.where(self.frozen > 0, torch.full_like(act, STAY), act)
        act = torch.where((act == SHIELD) & (self.cd > 0),
                          torch.full_like(act, STAY), act)
        tgt = self.tgt[act.reshape(-1), self.pos.reshape(-1)].reshape(n, 4)
        act = torch.where(tgt < 0, torch.full_like(act, STAY), act)
        tgt = torch.where(tgt < 0, self.pos, tgt)

        shielding = act == SHIELD
        moving = (act != STAY) & (~shielding)

        # ---- 1. movement. A cell occupied at the START of the turn is closed.
        occ = self._occupancy()
        blocked = occ.gather(1, tgt) > 0
        moving = moving & (~blocked)

        # Contested entry: the owner wins, otherwise the first seat in rotation
        # from the token holder. Encode that as a sort key and take the minimum
        # over every mover aiming at each cell.
        seats = torch.arange(1, 5, device=self.dev).expand(n, 4)
        owns_target = self.owner.gather(1, tgt) == seats
        rank = (seats - self.token.unsqueeze(1)) % 4
        prio = torch.where(owns_target, torch.full_like(rank, -1), rank)
        key = prio * 8 + (seats - 1)
        key = torch.where(moving, key, torch.full_like(key, BIG))
        best = torch.full((n, N_CELLS), BIG, dtype=torch.long, device=self.dev)
        best.scatter_reduce_(1, tgt, key, reduce="amin", include_self=True)
        wins = moving & (best.gather(1, tgt) == key)

        new_pos = torch.where(wins, tgt, self.pos)
        # progress resets on a successful move, and on a shield turn
        self.prog = torch.where(wins | shielding, torch.zeros_like(self.prog),
                                self.prog)
        # anything that is not a successful move and not a shield is a STAY,
        # which is what a blocked move and a lost contest both count as
        eff_stay = (~wins) & (~shielding)
        if not R["lost_contest_is_stay"]:
            eff_stay = eff_stay & (~(moving & (~wins)))
        self.pos = new_pos

        # ---- 2. shields resolve before takes
        owner_at = self.owner.gather(1, self.pos)          # [n,4]
        catchable = eff_stay & (self.frozen == 0)
        if not R["catch_requires_stay"]:
            catchable = self.frozen == 0
        # Rows are shielders, columns are potential victims. No GPU-to-host
        # Boolean checks are needed while advancing the tensor state.
        seat_ids = torch.arange(1, 5, device=self.dev)
        hits = (shielding.unsqueeze(2) & catchable.unsqueeze(1)
                & (owner_at.unsqueeze(1) == seat_ids.view(1, 4, 1))
                & (seat_ids.view(1, 4, 1) != seat_ids.view(1, 1, 4)))
        caught = hits.any(dim=1)
        got = hits.any(dim=2)
        backfire = shielding & (~got)
        new_frozen_amt = torch.where(caught | backfire,
                                     torch.full((n, 4), 2, dtype=torch.long,
                                                device=self.dev),
                                     torch.zeros((n, 4), dtype=torch.long,
                                                 device=self.dev))
        self.prog = torch.where(caught, torch.zeros_like(self.prog), self.prog)

        # ---- 3. takes and upgrades
        idx = (owner_at - 1).clamp(min=0)
        owner_shielded = shielding.gather(1, idx) & (owner_at > 0)
        home_at = self.home.gather(1, self.pos)
        base_at = self.base.gather(1, self.pos)
        upg_at = self.upg.gather(1, self.pos)

        working = eff_stay & (~caught)
        if not R["frozen_stay_counts"]:
            working = working & (self.frozen == 0)

        is_mine = owner_at == seats
        is_neutral = owner_at == 0
        is_rival = (~is_mine) & (~is_neutral)

        # upgrade my own level-1 cell: three stays
        up_ok = working & is_mine & (~upg_at)
        if not R["home_upgradable"]:
            up_ok = up_ok & (home_at != seats)
        # claim a neutral cell: one stay
        cl_ok = working & is_neutral
        # raid a rival cell: one stay at level 1, three at level 2; never a home,
        # and never through a shield
        rd_ok = working & is_rival & (home_at == 0) & (~owner_shielded)

        needed = torch.where(up_ok, torch.full_like(base_at, 3),
                             torch.where(cl_ok, torch.ones_like(base_at),
                                         torch.where(upg_at, torch.full_like(base_at, 3),
                                                     torch.ones_like(base_at))))
        advancing = up_ok | cl_ok | rd_ok
        newprog = torch.where(advancing, self.prog + 1, self.prog)
        done = advancing & (newprog >= needed)

        up_done = done & up_ok
        cl_done = done & cl_ok
        rd_done = done & rd_ok

        # income and score deltas, then one scatter per effect
        lvl = torch.where(upg_at, torch.full_like(base_at, 2),
                          torch.ones_like(base_at))
        bonus = torch.where(rd_done, 8 * base_at * lvl, torch.zeros_like(base_at))
        self.score = self.score + bonus

        inc_gain = torch.where(up_done, base_at,
                               torch.where(cl_done | rd_done, base_at,
                                           torch.zeros_like(base_at)))
        self.income = self.income + inc_gain
        # the raided owner loses what that cell was paying them
        loss = torch.where(rd_done, base_at * lvl, torch.zeros_like(base_at))
        victim = (owner_at - 1).clamp(min=0)
        self.income.scatter_add_(1, victim, -loss)

        changed = up_done | cl_done | rd_done
        new_owner_val = torch.where(cl_done | rd_done, seats,
                                    self.owner.gather(1, self.pos))
        self.owner.scatter_(1, self.pos,
                            torch.where(changed, new_owner_val,
                                        self.owner.gather(1, self.pos)))
        new_upg_val = torch.where(up_done, torch.ones_like(base_at),
                                  torch.where(cl_done | rd_done,
                                              torch.zeros_like(base_at),
                                              upg_at.long()))
        self.upg.scatter_(1, self.pos,
                          torch.where(changed, new_upg_val,
                                      upg_at.long()).bool())

        if R["claim_resets_progress"]:
            newprog = torch.where(done, torch.zeros_like(newprog), newprog)
        else:
            newprog = torch.where(up_done, torch.zeros_like(newprog), newprog)
        self.prog = newprog

        # ---- 4. scoring
        self.score = self.score + self.income

        # ---- 5. bookkeeping, then the token passes
        self.frozen = (self.frozen - 1).clamp(min=0)
        self.frozen = torch.where(new_frozen_amt > 0, new_frozen_amt, self.frozen)
        # engine.py zeroes progress only when a NEW freeze lands, not for every
        # turn of one being served. That distinction only shows up when
        # frozen_stay_counts is on.
        self.prog = torch.where(new_frozen_amt > 0, torch.zeros_like(self.prog),
                                self.prog)
        self.cd = torch.where(shielding, torch.full_like(self.cd, 4),
                              (self.cd - 1).clamp(min=0))
        self.token = self.token % 4 + 1
        self.turn += 1

    # -- observation ----------------------------------------------------------
    def legal_mask(self):
        """[n, 4, 6] bool: which actions each bot may take."""
        n = self.n
        m = torch.zeros((n, 4, 6), dtype=torch.bool, device=self.dev)
        for a in range(4):
            ok = self.tgt[a, self.pos.reshape(-1)].reshape(n, 4) >= 0
            m[:, :, a] = ok
        m[:, :, STAY] = True
        m[:, :, SHIELD] = self.cd == 0
        frozen = self.frozen > 0
        m = m & (~frozen).unsqueeze(2)
        m[:, :, STAY] = True
        return m

    def places(self, round_number=1, round1_ranks=None):
        """Mean rank: Round 1 score; Round 2 score, cells, optional pool rank.

        Pairwise comparison gives every member of a three/four-way tie exactly
        the same average rank. Historical pairwise averaging did not.
        """
        if round_number not in (1, 2):
            raise ValueError("round_number must be 1 or 2")
        a, b = self.score.unsqueeze(2), self.score.unsqueeze(1)
        better, equal = b > a, b == a
        if round_number == 2:
            seat_ids = torch.arange(1, 5, device=self.dev)
            cells = (self.owner.unsqueeze(2) == seat_ids).sum(dim=1)
            ca, cb = cells.unsqueeze(2), cells.unsqueeze(1)
            better |= equal & (cb > ca)
            equal &= cb == ca
        if round1_ranks is not None:
            if round_number != 2:
                raise ValueError("round1_ranks requires Round 2")
            ranks = torch.as_tensor(round1_ranks, device=self.dev)
            if ranks.ndim == 1:
                ranks = ranks.expand(self.n, 4)
            if ranks.shape != (self.n, 4):
                raise ValueError("round1_ranks must have shape [4] or [n,4]")
            ra, rb = ranks.unsqueeze(2), ranks.unsqueeze(1)
            better |= equal & (rb < ra)
            equal &= rb == ra
        return 1.0 + better.sum(dim=2) + (equal.sum(dim=2) - 1) * 0.5
