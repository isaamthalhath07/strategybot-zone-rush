"""Frozen-code causal ablation; raw-score pairings and unchanged peer opponents."""
import hashlib
import importlib.util
import inspect
import json
import multiprocessing as mp
from pathlib import Path
import random

import engine
import field
import measure

ROOT = Path(__file__).resolve().parent
KINDS = ("base", "workgain", "priority", "income", "progress", "defence", "frame", "idle")
_MODULES = {}


def module(kind):
    if kind not in _MODULES:
        path = ROOT / "audit" / ("ablation_%s.py" % kind)
        spec = importlib.util.spec_from_file_location("audit_ablation_" + kind, path)
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        _MODULES[kind] = loaded
    return _MODULES[kind]


def replace_once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new)


def prepare():
    baseline_path = ROOT / "audit" / "baseline_mybot.py"
    source = baseline_path.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("ablation_original", baseline_path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    hashes = {}
    for kind in KINDS:
        changed = source
        if kind in ("workgain", "income"):
            changed = replace_once(changed, "rem = R - used - need", "rem = R - used - need + 1")
            changed = replace_once(changed, "rem1 = R - used - 1", "rem1 = R - used")
        if kind in ("priority", "income"):
            changed = replace_once(changed, "pri = v * (R - d - need) / float(d + need)",
                                   "pri = v * (R - d - need + 1) / float(d + need)")
        if kind == "progress":
            changed = replace_once(changed, "                    nu = used + travel + need",
                "                    work_need = need\n"
                "                    if p == me and used > 0 and tr.prog[seat - 1]:\n"
                "                        work_need = (4 if kind == 3 else 3 if kind == 1\n"
                "                                     or (kind == 2 and upg[p]) else 1)\n"
                "                    nu = used + travel + work_need")
            changed = replace_once(changed,
                "self._work_gain(p, kind, v, need, used + travel, owner, upg,",
                "self._work_gain(p, kind, v, work_need, used + travel, owner, upg,")
        if kind == "defence":
            changed = replace_once(changed,
                "if o and o != seat and owner[p] == seat and not frz[p]:",
                "if (o and o != seat and owner[p] == seat and not frz[p]\n"
                "                    and not tr.home_of[p]):")
            changed = replace_once(changed, "            return R <= 1", "            return False")
            changed = replace_once(changed, "lost = v * lvl * (R - 1)", "lost = v * lvl * R")
            changed = replace_once(changed, "their_gain = (8.0 * v * lvl + v * (R - 1))",
                                   "their_gain = (8.0 * v * lvl + v * R)")
            original = inspect.getsource(baseline.Agent._threat)
            updated = replace_once(original, "        tr = self.tr\n",
                                   "        tr = self.tr\n        if tr.home_of[p]:\n            return 0.0\n")
            changed = replace_once(changed, original, updated)
        if kind == "frame":
            frame = ("    def _home_frame(self, seat):\n"
                     "        home = self.tr.homes[seat - 1]\n"
                     "        return CANON[CORNERS.index(home) + 1] if home in CORNERS else CANON[seat]\n\n")
            marker = "    def _candidates("
            changed = replace_once(changed, marker, frame + marker)
            assert changed.count("can = CANON[seat]") == 2
            changed = changed.replace("can = CANON[seat]", "can = self._home_frame(seat)")
        if kind == "idle":
            changed = replace_once(changed, "target, tv = None, -1e18",
                                   "target, tv = None, (0.0 if owner[me] in (0, seat) else -1e18)")
            changed = replace_once(changed,
                "        self.plan_target = target\n        if target == me:",
                "        self.plan_target = target\n        if target is None:\n            return 'STAY'\n        if target == me:")
        path = ROOT / "audit" / ("ablation_%s.py" % kind)
        if path.exists() and path.read_text(encoding="utf-8") != changed:
            raise RuntimeError("Refusing to overwrite different frozen source: %s" % path)
        if not path.exists():
            path.write_text(changed, encoding="utf-8")
        hashes[kind] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def tasks(n, seed):
    rnd = random.Random(seed)
    names = field.tier("peer")
    out = []
    for i in range(n):
        out.append((rnd.randrange(1 << 30), i % 4,
                    [rnd.choice(names) for _ in range(3)],
                    ((i // 4) + (i % 4)) % 4 + 1))
    return out


def opponent(name, seed):
    baseline = module("base")
    with open(ROOT / "snapshots.json") as src:
        snapshots = json.load(src)
    if name in snapshots:
        params = dict(baseline.PARAMS)
        params.update(snapshots[name])
        params.update(throttle=0, budget_ms=10000.0)
        return baseline.Agent(seed=seed, params=params)
    return field.opponent(name)(seed)


def play(job):
    kind, params, task = job
    loaded = module(kind)
    map_seed, seat, names, token = task
    params = dict(params, throttle=0, budget_ms=10000.0)
    agent = loaded.Agent(seed=map_seed & 0xffff, params=params)
    bots, j = [], 0
    for i in range(4):
        if i == seat:
            bots.append(agent)
        else:
            bots.append(opponent(names[j], map_seed * 4 + i))
            j += 1
    game = engine.Game(base=engine.make_map(seed=map_seed), start_token=token)
    while not game.over():
        views, actions = game.views(), []
        for i, bot in enumerate(bots):
            if i == seat:
                action = bot.decide(views[i])
                bot.last_action = action
            else:
                action = bot(views[i])
            assert action in views[i].legal_actions
            actions.append(action)
        game.step(actions)
    score = game.score
    wins = sum(1.0 if score[seat] > score[i] else 0.5 if score[seat] == score[i] else 0.0
               for i in range(4) if i != seat)
    place = 1 + sum(score[i] > score[seat] for i in range(4) if i != seat)
    return kind, (wins, score[seat], place, score[:])


def main():
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 920771
    workers = min(4, int(sys.argv[3])) if len(sys.argv) > 3 else 4
    hashes = prepare()
    params = dict(module("base").PARAMS)
    params.update(json.load(open(ROOT / "v7_params.json")))
    selected = tasks(n, seed)
    result = {kind: [] for kind in KINDS}
    jobs = [(kind, params, task) for task in selected for kind in KINDS]
    print("Frozen-source peer ablation: %d pairs x %d variants, %d workers" %
          (n, len(KINDS), workers), flush=True)
    with mp.Pool(workers) as pool:
        for i, (kind, row) in enumerate(pool.imap(play, jobs, chunksize=2), 1):
            result[kind].append(row)
            if i % 160 == 0:
                print("Completed %d/%d games" % (i, len(jobs)), flush=True)
    measure.report([(k, params) for k in KINDS], result,
                   label="frozen peer ablation seed=%d" % seed)
    output = ROOT / ("audit_ablation_peer_%d_%d.json" % (seed, n))
    output.write_text(json.dumps({"seed": seed, "tasks": selected,
                                 "hashes": hashes, "params": params,
                                 "results": result}, indent=2), encoding="utf-8")
    print("Saved", output, flush=True)


if __name__ == "__main__":
    main()
