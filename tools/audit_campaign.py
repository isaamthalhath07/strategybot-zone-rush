"""Create fresh registered panels and freeze finalists without fitting bots."""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"validation/branch_audit"
CORPUS = ROOT/"consolidation_candidates/branch_audit"
sys.path.insert(0,str(ROOT/"simulator/vendor_harness"))
from referee import mirror


FAMILIES = {
    "contracts": ("district_rate","time_discount","turn_budget","local_pairs"),
    "contracts_extra": ("district_rate","time_discount","turn_budget","local_pairs"),
    "screen": ("district_rate","time_discount","turn_budget","local_pairs"),
    "development": ("return_schedule","capture_deadline","sector_bids","sampling_portfolio"),
    "final": ("boundary_cluster","periodic_switch","cooldown_feint","chase_income"),
}
MAIN_SHA = "e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5"
RESEARCH_SHA = "6f2ac1487cd0a66793db3f2fab01f621d9c945a4f71a78cc92d176ef1de321f4"
FUSION_SHA = "720e5a3daf7b848e8a25038c20bda47e8fb0433495aaa7bdbff9b285b8ba5a2d"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def known_boards():
    boards = set()
    def visit(value):
        if isinstance(value,dict):
            b = value.get("base")
            if isinstance(b,list) and len(b)==64 and all(type(v)==int and 1<=v<=3 for v in b):
                boards.add(tuple(b))
            for v in value.values():
                visit(v)
        elif isinstance(value,list):
            for v in value:
                visit(v)
    for path in (ROOT/"validation").rglob("*.json"):
        visit(json.loads(path.read_text(encoding="utf8")))
    return boards


def board(rng,family):
    q = []
    for r in range(4):
        row = []
        for c in range(4):
            if family == "gradient":
                x = 1+(r+c)*rng.uniform(0.25,0.45)+rng.uniform(-0.5,0.5)
            elif family == "noise":
                x = rng.choice((1,2,3))
            elif family == "edge":
                x = 3-min(r,c)*0.7+rng.uniform(-0.65,0.65)
            elif family == "highhome":
                x = 1.5+0.25*(r+c)+rng.uniform(-0.6,0.6)
            elif family == "pockets":
                x = rng.choice((1,1,2,3,3))
            else:
                x = (3 if r==2 or c==2 else 1)+rng.uniform(-0.7,0.7)
            row.append(max(1,min(3,int(round(x)))))
        q.append(row)
    if family == "highhome":
        q[0][0] = 3
    return mirror(q)


def novel(stage,group,slot,field,rng):
    families = FAMILIES[stage]
    pool = families[:2] if field=="novel_economy" else families[2:]
    config = dict(seed=rng.randrange(2**31),family=rng.choice(pool),
                  claim=rng.uniform(0.85,1.25),upgrade=rng.uniform(1.05,1.65),
                  raid=rng.uniform(0.35,0.85),stick=rng.uniform(1.08,1.35),
                  power=rng.uniform(0.85,1.15),shield=rng.uniform(0.65,0.95),
                  period=rng.randrange(8,18),phase=rng.randrange(2))
    template = (ROOT/"tools/audit_opponent.py").read_text(encoding="utf8")
    start,end = template.index("CONFIG = "),template.index("\nNEIGH =")
    source = (template[:start]+"CONFIG = "+repr(config)+template[end:]).encode()
    ast.parse(source)
    sha = digest(source)
    target = CORPUS/(sha+".py")
    target.write_bytes(source)
    return dict(name="novel_"+sha[:12],path=str(target.relative_to(ROOT)).replace("\\","/"),
                sha256=sha,role="fresh-opponent",configuration=config,
                generation=dict(stage=stage,map_group=group,field=field,slot=slot))


def select_candidates(stage,inventory):
    policies = inventory["policies"]
    if stage=="contracts":
        return [p["name"] for p in policies]
    if stage=="contracts_extra":
        return [p["name"] for p in policies if p.get('build_inputs')]
    contract = json.loads((OUT/"contracts_results.json.summary.json").read_text())
    qualified = {name for name,s in contract["summary"].items() if s["focal_faults"]==0}
    extra = OUT/'contracts_extra_results.json.summary.json'
    if extra.exists():
        qualified.update(name for name,s in json.loads(extra.read_text())['summary'].items() if s['focal_faults']==0)
    if stage=="screen":
        return [p["name"] for p in policies if p["name"] in qualified]
    prior = "screen" if stage=="development" else "development"
    data = json.loads((OUT/(prior+"_results.json.summary.json")).read_text())
    ranked = [name for name,s in data["summary"].items() if s["focal_faults"]==0 and name in qualified]
    champion = next(p["name"] for p in policies if p["sha256"]==MAIN_SHA)
    chosen = set(ranked[:8 if stage=="development" else 4])
    chosen.add(champion)
    if stage=="development":
        # A coarse screen cannot safely discard every branch's distinct root.
        chosen.update(p["name"] for p in policies if p["name"] in qualified and any(
            a.get("path")=="bot.py" and a.get("ref","").startswith("refs/remotes/origin/") for a in p["aliases"]))
        for field in ("league","novel_economy","novel_dynamic"):
            winner = max(ranked,key=lambda name:data["summary"][name]["fields"].get(field,-1))
            chosen.add(winner)
    return sorted(chosen)


def prepare(stage):
    target = OUT/(stage+"_spec.json")
    if target.exists():
        raise ValueError("a registered panel is immutable")
    inventory = json.loads((OUT/"inventory.json").read_text())
    extension = OUT/'inventory_extension.json'
    if extension.exists() and stage!='contracts':
        inventory['policies'].extend(json.loads(extension.read_text())['policies'])
    candidates = select_candidates(stage,inventory)
    sources = {p["name"]:p for p in inventory["policies"]}
    by_sha = {p["sha256"]:p["name"] for p in inventory["policies"]}
    league = [by_sha[s] for s in (MAIN_SHA,RESEARCH_SHA,FUSION_SHA)]
    rng = random.Random("all-branch-frozen-audit:%s:20261108" % stage)
    blocked = known_boards()
    original_forbidden = len(blocked)
    count = {"contracts":4,"contracts_extra":4,"screen":2,"development":6,"final":24}[stage]
    kinds = ("gradient","noise","edge","highhome","pockets","corridors")
    fixtures = []
    for group in range(count):
        family = kinds[group % len(kinds)]
        for _ in range(10000):
            base = board(rng,family)
            if tuple(base) not in blocked:
                break
        else:
            raise ValueError("could not create an unused board")
        blocked.add(tuple(base))
        lineups = {"league":league}
        for field in ("novel_economy","novel_dynamic"):
            generated = [novel(stage,group,slot,field,rng) for slot in range(3)]
            for source in generated:
                sources[source["name"]] = source
            lineups[field] = [s["name"] for s in generated]
        if stage.startswith("contracts"):
            crossings = [(group % 4,1+group % 4,"novel_economy")]
        elif stage=="screen":
            crossings = [(seat,token,("league","novel_economy","novel_dynamic")[(seat+token+group)%3])
                         for seat in range(4) for token in range(1,5)]
        elif stage=="development":
            crossings = [(seat,token,("league","novel_economy","novel_dynamic")[group % 3])
                         for seat in range(4) for token in range(1,5)]
        else:
            crossings = [(seat,token,field) for field in lineups for seat in range(4) for token in range(1,5)]
        for seat,token,field in crossings:
            fixtures.append(dict(id=len(fixtures),map_group=group,map_family=family,base=base,
                                 seat=seat,token=token,field=field,opponents=lineups[field]))
    required = set(candidates) | {n for f in fixtures for n in f["opponents"]}
    manifest = json.loads((ROOT/"release_manifest.json").read_text())
    spec = dict(id="all_branches_"+stage,stage=stage,diagnostic=stage.startswith("contracts"),
                candidates=candidates,sources=[sources[n] for n in sorted(required)],fixtures=fixtures,
                rules=manifest["rules"],forbidden_board_contents=original_forbidden,
                candidate_selection="Frozen source snapshots. Screen retains all passing distinct remote branch roots for development. Final takes the leading four development means plus the incumbent; no strategic coefficients fitted.",
                inference="Only final paired intervals are confirmatory. Each final map crosses all seats/tokens and all three fields. Promotion needs zero contract/worker faults, a positive paired map-clustered interval against the incumbent with Bonferroni adjustment across final challengers, a positive ordinary 95% novel-only interval, and a nonnegative mean change in each novel field. Otherwise retain the incumbent and report uncertainty. The final is consumed once; no strategic changes may be fitted to it.",
                challenger_scope="Per-map generated opponents are reset for every game and identical across candidate pairs. Each stage reserves different decision rules. Parameters are drawn without checking how they perform against any focal candidate.")
    target.write_text(json.dumps(spec,indent=2),encoding="utf8",newline="\n")
    print(json.dumps(dict(stage=stage,candidates=len(candidates),fixtures=len(fixtures),games=len(candidates)*len(fixtures),
                         maps=count,prior_board_contents=original_forbidden,source_files=len(required)),indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage",choices=FAMILIES)
    args = parser.parse_args()
    prepare(args.stage)


if __name__=="__main__":
    main()
