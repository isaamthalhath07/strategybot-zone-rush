"""
Structural improvement to test after v3: let the planner consider "claim this
neutral cell AND upgrade it in one visit" as a single work item.

Why it should matter: claiming costs 1 stay, upgrading costs 3 more. Done in one
visit that is 4 stays and zero extra travel; done as two visits it costs a round
trip. The planner currently only ever sees the 1-stay claim, so it undervalues
exactly the cells it is going to consolidate, which is how the strongest farmer
in the zoo was out-farming it.

Requires masking visited work by CELL rather than by candidate index, since a
cell can now appear in the candidate list twice.
"""
import re

p = "mybot.py"
s = open(p, encoding="utf-8").read()

# 1. a new work kind: 3 = claim then upgrade, in one visit
old = """            elif o == 0:
                kind = 0                      # claim
                v = base[p]
                need = 1"""
new = """            elif o == 0:
                kind = 0                      # claim
                v = base[p]
                need = 1"""
assert old in s

# emit the combined option alongside the plain claim
old2 = """            if occ[p] and p != me:
                pri *= 0.3
            if tr.zone[p] == seat:
                pri *= P["zone_bonus"]
            out.append((pri, p, kind, v, need))
        out.sort(reverse=True)
        return out[:P["ncand"]]"""
new2 = """            if occ[p] and p != me:
                pri *= 0.3
            if tr.zone[p] == seat:
                pri *= P["zone_bonus"]
            out.append((pri, p, kind, v, need))
            # claiming and upgrading in one visit costs 4 stays and no extra
            # travel; doing it as two visits costs a round trip as well
            if kind == 0 and P["combo"] > 0.0 and d + 4 <= R:
                out.append((pri * P["combo_pri"], p, 3, v, need + 3))
        out.sort(reverse=True)
        return out[:P["ncand"]]"""
assert old2 in s
s = s.replace(old2, new2)

# 2. value it correctly: income at level 1 from the claim, then the extra v/turn
old3 = """        if kind == 0:
            if rem <= 0:
                return None
            g = v * rem * P["w_claim"]"""
new3 = """        if kind == 0:
            if rem <= 0:
                return None
            g = v * rem * P["w_claim"]
        elif kind == 3:
            rem1 = R - used - 1               # level-1 income starts after 1 stay
            if rem <= 0 or rem1 <= 0:
                return None
            g = (v * rem1 * P["w_claim"] + v * rem * P["w_upgrade"]) * P["combo"]"""
assert old3 in s
s = s.replace(old3, new3)

# 3. mask by cell, not by candidate index, so one cell cannot be worked twice
old4 = """        idx = {}
        for k, (_, p, kind, v, need) in enumerate(cands):
            idx[p] = k"""
new4 = """        cellbit = {}
        for (_, p, kind, v, need) in cands:
            if p not in cellbit:
                cellbit[p] = len(cellbit)"""
assert old4 in s
s = s.replace(old4, new4)

old5 = """                for k, (_, p, kind, v, need) in enumerate(cands):
                    if (mask >> k) & 1:
                        continue"""
new5 = """                for (_, p, kind, v, need) in cands:
                    k = cellbit[p]
                    if (mask >> k) & 1:
                        continue"""
assert old5 in s
s = s.replace(old5, new5)

# 4. parameters
old6 = """    "w_raid_late": 1.00,       # raid weight at the final turn; interpolated by clock"""
new6 = """    "w_raid_late": 1.00,       # raid weight at the final turn; interpolated by clock
    "combo": 0.00,             # weight on claim-and-upgrade-in-one-visit plans
    "combo_pri": 1.00,         # its priority when trimming the candidate list"""
assert old6 in s
s = s.replace(old6, new6)

open(p, "w", encoding="utf-8").write(s)
print("applied combo patch to mybot.py")

t = "tune.py"
u = open(t, encoding="utf-8").read()
u = u.replace('    "w_raid_late":    (0.3, 3.0, False, 0.12),',
              '    "w_raid_late":    (0.3, 3.0, False, 0.12),\n'
              '    "combo":          (0.0, 1.6, False, 0.12),\n'
              '    "combo_pri":      (0.3, 2.0, False, 0.12),')
open(t, "w", encoding="utf-8").write(u)
print("tuner knows the new parameters")
