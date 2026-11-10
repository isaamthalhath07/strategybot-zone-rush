"""Group sources into architecture clusters by their set of top-level/class-level definition names."""
import ast, json, os, hashlib, collections, sys
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import names as N
CANDS = N.CANDS
def sig(path):
    tree = ast.parse(open(path, "rb").read())
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, ast.FunctionDef): out.add(n.name + "." + m.name)
    return frozenset(out)
sigs = {cid: sig(c["path"]) for cid, c in CANDS.items()}
# greedy clustering by Jaccard >= 0.8 against cluster representative
clusters = []
for cid in sorted(sigs, key=lambda c: -len(sigs[c])):
    s = sigs[cid]
    for cl in clusters:
        r = cl["rep"]; inter = len(s & r); uni = len(s | r)
        if uni and inter / uni >= 0.8: cl["members"].append(cid); break
    else: clusters.append(dict(rep=s, members=[cid]))
arch = {}
for i, cl in enumerate(sorted(clusters, key=lambda c: -len(c["members"]))):
    for m in cl["members"]: arch[m] = i
json.dump(arch, open(SP + "/arch.json", "w"))
if __name__ == "__main__":
    print(len(clusters), "clusters")
    for i, cl in enumerate(sorted(clusters, key=lambda c: -len(c["members"]))[:30]):
        fam = collections.Counter(N.family(m) for m in cl["members"])
        known = [N.name(m) for m in cl["members"] if m in N.TESTER or m in N.ROOT][:5]
        ex = [N.name(m) for m in cl["members"][:3]]
        sizes = sorted(CANDS[m]["size"] for m in cl["members"])
        print(i, len(cl["members"]), dict(fam), "sizes %d-%d" % (sizes[0], sizes[-1]), "| known:", known, "| e.g.", ex, "| defs:", sorted(cl["rep"])[:6])
