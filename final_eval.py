"""Decide which version to ship, then characterise it."""
import json, random, sys
import arena, engine, holdout, mybot, rivals, zoo

def registry():
    reg = arena.Registry()
    for c in zoo.ZOO:   reg.add(c.name, (lambda k: (lambda s: k(s)))(c))
    for c in holdout.HOLDOUT: reg.add(c.name, (lambda k: (lambda s: k(s)))(c))
    for n in rivals.names(): reg.add(n, rivals.factory(n))
    return reg

reg = registry()
names = reg.names()
print("=== all-versions tournament: %d entrants, no focus bot ===" % len(names))
st = arena.tournament(reg, names, games=int(sys.argv[1]) if len(sys.argv)>1 else 1100, seed=99)
print(st.table(sort="pw"))

print("\n=== head-to-head among my own versions ===")
vers = [n for n in rivals.names() if n.startswith("v")]
print("     " + "".join("%10s" % v for v in vers))
for a in vers:
    row = "%-5s" % a
    for b in vers:
        if a == b: row += "%10s" % "-"
        else:
            s, c = st.h2h.get((a, b), [0.0, 0])
            row += "%10s" % ("%.0f%%" % (100*s/c) if c >= 8 else "-")
    print(row)

print("\n=== exploitability of each version (counter scores vs 3 copies; 1.50 = no edge) ===")
for v in vers:
    for ctr in ("nemesis1", "nemesis2"):
        s2 = arena.tournament(reg, [v, ctr], games=200, seed=7, focus=ctr, opponents=[v])
        g = max(1, s2.games[ctr])
        print("  %-4s attacked by %-9s -> %.2f/3" % (v, ctr, s2.pw[ctr]/g))
