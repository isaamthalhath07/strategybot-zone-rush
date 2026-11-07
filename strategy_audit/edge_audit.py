"""
Paired, instrumented audit of the SHIPPED bot.py.

Every variant plays the identical list of (map, seat, opponents, token) tasks with
bot.py's two wall-clock guards pinned (throttle off, huge budget), so play is
deterministic and variants are compared game-for-game -- the method measure.py
uses. The bot is bot.py itself, not mybot.py: this audits what will be submitted.

    python strategy_audit/edge_audit.py <games> <tier> <variant> [<variant> ...]

tiers     any tier in field.py (realistic, peer, strangers, ...), plus
          outsiders   the eight designs in strategy_audit/outsiders.py
          unknown     outsiders + strangers mixed (nothing tuned against)
          nonshield   three copies of `greedy`, the repo's never-shield bot
          solo:NAME   three copies of one opponent
variants  `base`, or fixes/overrides joined with `+`:
          nol1        do not burn a shield on a level-1 cell (finding B2)
          home        ignore rivals standing on my home (finding B3)
          free        last-turn shield only for a real, worthwhile threat (B4)
          offby1      count income from the turn a take completes (B6)
          KEY:VALUE   any PARAMS override, e.g. q_weight:1.5
          @FILE.json  a whole parameter file, e.g. @v8_params.json
          e.g.  base nol1 nol1+home+free q_weight:1.5

Which bot is audited is set by the environment variable AUDIT_BOT:
          bot         (default) the shipped bot.py
          mybot       the development source, so parameter files can be compared
          PATH.py     any bot file, e.g. an old version pulled out of git:
                      git show 961e729:bot.py > /tmp/bot_v7.py
                      AUDIT_BOT=/tmp/bot_v7.py python strategy_audit/edge_audit.py ...

Results are written to strategy_audit/results/ under a name that starts with the
label of the bot that produced them (see bot_label), so a run of one version can
never overwrite another version's evidence.

AUDIT_SEED (default 7) draws a different task list -- fresh maps, seats,
lineups and tokens -- for a confirmation run. A non-default seed is part of the
result file name, so a confirmation never overwrites the draw it confirms.
"""
import hashlib
import importlib
import importlib.util
import json
import math
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
_CWD = os.getcwd()
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
os.chdir(REPO)                    # field.py loads pro_params_v1.json relative to cwd


def _load_bot(which):
    if which.endswith(".py"):
        path = which if os.path.isabs(which) else os.path.join(_CWD, which)
        spec = importlib.util.spec_from_file_location("audited_bot", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return importlib.import_module(which)


bot = _load_bot(os.environ.get("AUDIT_BOT", "bot"))

# Result files are named after the bot that produced them. bot.py is rewritten
# whenever a version ships, so a name built only from the command line let a v8
# run silently overwrite the committed v7 evidence. The label is taken from the
# file's content (line endings normalised), so it is the same however the file
# was obtained -- checked out, or pulled from git history into /tmp. Versions
# that differ only in comments map to the same label.
KNOWN_BOTS = {
    "f4a4449efe2fa82d22154af3217588b4d41ab506": "v7",    # bot.py at 961e729
    "fe5c2b1dc9197d8aaa0c00fe94b2d74618d5074d": "v8",    # first v8 build
    "38728a78bfef2a607da31b88e7f0ff2e218c41ec": "v8",    # same, doc path fixed
    "abc3ec9e6ca9f9eaf14427980a09891c09e7d931": "v9",    # v8 + opponent forecast
    "e678a727d75faaa2be3a388aae5923408e79ff8c": "mybot",  # source behind v8
    "b4d9e70ddbfd1a259016c634266dde4e46701e3c": "mybot",  # same, doc path fixed
}


def bot_label(mod=None):
    """v7, v8 or mybot for a known file; otherwise bot-<hash> / mybot-<hash>,
    so an edited bot never writes over results of the one it replaced."""
    mod = mod or bot
    with open(mod.__file__, "rb") as f:
        digest = hashlib.sha1(f.read().replace(b"\r\n", b"\n")).hexdigest()
    if digest in KNOWN_BOTS:
        return KNOWN_BOTS[digest]
    stem = "mybot" if os.path.basename(mod.__file__) == "mybot.py" else "bot"
    return "%s-%s" % (stem, digest[:8])


def _slug(x):
    return (str(x).replace(":", "-").replace("+", "_").replace("@", "")
            .replace(".json", "").replace("/", "-"))


def result_path(probe, *parts, **kw):
    """strategy_audit/results/<bot label>_<probe>_<parts...><ext>.

    Long names keep a readable prefix and end in a hash of the full name instead
    of being cut short, since two runs whose names share a prefix would
    otherwise collide."""
    ext = kw.get("ext", ".txt")
    name = "_".join([bot_label(), probe] + [_slug(p) for p in parts if p != ""])
    if len(name) > 120:
        name = name[:100] + "-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    rdir = os.path.join(HERE, "results")
    if not os.path.isdir(rdir):
        os.makedirs(rdir)
    return os.path.join(rdir, name + ext)


class _Tee(object):
    """Mirror a probe's console output into its results file.

    Written to <path>.partial (gitignored) and renamed into place only when the
    probe exits normally, so an interrupted or still-running probe can never
    leave an empty or half-written file that looks like a result."""

    def __init__(self, path):
        self.out = sys.stdout
        self.path = path
        self.f = open(path + ".partial", "w", encoding="utf-8")

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush()
        self.f.flush()

    def finish(self):
        self.f.close()
        os.replace(self.path + ".partial", self.path)


def tee_to(path):
    import atexit
    t = _Tee(path)
    sys.stdout = t
    pid = os.getpid()

    def _done():
        if os.getpid() == pid:          # never from a forked worker
            sys.stdout = t.out
            t.finish()
    atexit.register(_done)
    return path


import engine  # noqa: E402
import field as fieldmod  # noqa: E402
import measure  # noqa: E402
import outsiders  # noqa: E402

fieldmod.TIERS.setdefault("outsiders", sorted(outsiders.REGISTRY))
fieldmod.TIERS.setdefault("unknown", sorted(outsiders.REGISTRY) + fieldmod.TIERS["strangers"])
fieldmod.TIERS.setdefault("nonshield", ["greedy"])


def make_opponent(name, seed):
    c = outsiders.REGISTRY.get(name)
    if c is not None:
        return c(seed)
    return measure._make(name, seed)


def stay_completion_gain(tr, owner, upg, base, home_of, seat, me):
    """What STAY on the final turn is worth to me (completes a take/upgrade)."""
    o = owner[me]
    v = base[me]
    prog = tr.prog[seat - 1]
    if o == 0:
        return v
    if o == seat:
        return v if (not upg[me] and prog >= 2) else 0
    if home_of[me]:
        return 0
    if upg[me]:
        return (16 * v + v) if prog >= 2 else 0
    return 8 * v + v


class Inst(bot.Agent):
    """bot.Agent with logging, and the candidate fixes behind switches."""

    def __init__(self, seed=0, params=None, fixes=()):
        bot.Agent.__init__(self, seed=seed, params=params)
        self.fixes = set(fixes)
        self.log = {"shields": [], "idle": 0, "idle_late": 0, "moves": 0,
                    "turns90": 0, "reversals": 0, "last_dir": None}

    def decide(self, view):
        a = bot.Agent.decide(self, view)
        lg = self.log
        if a in ("NORTH", "SOUTH", "EAST", "WEST"):
            lg["moves"] += 1
            if lg["last_dir"] is not None and lg["last_dir"] != a:
                lg["turns90"] += 1
                if {lg["last_dir"], a} in ({"NORTH", "SOUTH"}, {"EAST", "WEST"}):
                    lg["reversals"] += 1
            lg["last_dir"] = a
        return a

    def _idle(self, *a, **k):
        self.log["idle"] += 1
        if bot.MAX_TURNS - self.tr.turn + 1 > 3:
            self.log["idle_late"] += 1
        return bot.Agent._idle(self, *a, **k)

    def _work_gain(self, p, kind, v, need, used, *rest):
        if "offby1" in self.fixes:
            used = used - 1              # rem and rem1 are the only uses of `used`
        return bot.Agent._work_gain(self, p, kind, v, need, used, *rest)

    def _intruders(self, owner, occ, frz, seat, upg):
        tr = self.tr
        out = []
        for p in range(bot.NC):
            o = occ[p]
            if o and o != seat and owner[p] == seat and not frz[p]:
                j = o - 1
                need = (3 if upg[p] else 1) - tr.prog[j]
                out.append((p, j, bool(tr.home_of[p]), need <= 1, bool(upg[p])))
        return out

    def _should_shield(self, owner, upg, occ, frz, base, seat, R, kappa, care):
        P = self.P
        tr = self.tr
        ints = self._intruders(owner, occ, frz, seat, upg)
        me = tr.pos[seat - 1]
        alt = stay_completion_gain(tr, owner, upg, base, tr.home_of, seat, me)
        hide = set()
        if "home" in self.fixes:
            hide.update(p for p, _j, h, _i, _u in ints if h)
        if "nol1" in self.fixes and R > P["free_shield_turns"]:
            hide.update(p for p, _j, h, _i, u in ints if not u and not h)
        if hide:
            occ = [0 if p in hide else occ[p] for p in range(bot.NC)]
        if "free" in self.fixes and R <= P["free_shield_turns"]:
            save = 0.0
            for p, j, is_home, imm, up in ints:
                if is_home or not imm:
                    continue
                lvl = 2 if up else 1
                save += base[p] * lvl + (8 * base[p] * lvl + base[p]) * care[j]
            res = save > 0 and save >= alt
        else:
            res = bot.Agent._should_shield(self, owner, upg, occ, frz, base,
                                           seat, R, kappa, care)
        if res:
            self.log["shields"].append({"turn": tr.turn, "R": R, "alt": alt,
                                        "ints": ints})
        return res


def parse_variant(spec):
    params = {"throttle": 0, "budget_ms": 10000.0}
    fixes = []
    for part in spec.split("+"):
        if part == "base":
            continue
        if part.startswith("@"):
            with open(os.path.join(REPO, part[1:])) as f:
                params.update(json.load(f))
            params["throttle"] = 0           # a file must not undo the pinning
            params["budget_ms"] = 10000.0
            continue
        if ":" in part:
            k, v = part.split(":", 1)
            if k not in bot.PARAMS:
                raise SystemExit("unknown param %r" % k)
            params[k] = float(v)
        else:
            if part not in ("nol1", "home", "free", "offby1"):
                raise SystemExit("unknown fix %r" % part)
            fixes.append(part)
    return params, fixes


def play(spec, task):
    params, fixes = parse_variant(spec)
    map_seed, myseat, opps, token = task
    base = engine.make_map(seed=map_seed)
    bots, names = [], []
    k = 0
    me = None
    for i in range(4):
        if i == myseat:
            me = Inst(seed=map_seed & 0xffff, params=params, fixes=fixes)
            bots.append(me)
            names.append(None)
        else:
            bots.append(make_opponent(opps[k], map_seed * 4 + i))
            names.append(opps[k])
            k += 1
    g = engine.Game(base=base, start_token=token)
    pending = []
    l1_shields = l1_lost = backfires = raids = raids_early = cells_lost = 0
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            acts.append(a if a in vs[i].legal_actions else "STAY")
        t_now = g.turn
        nsh = len(me.log["shields"])
        own_before = g.owner[:]
        fr_before = g.frozen[myseat]
        g.step(acts)
        if acts[myseat] == "SHIELD" and fr_before == 0 and g.frozen[myseat] == 2:
            backfires += 1
        for p in range(engine.NC):
            if g.owner[p] == myseat + 1 and own_before[p] not in (0, myseat + 1):
                raids += 1
                raids_early += t_now <= 40
            if own_before[p] == myseat + 1 and g.owner[p] != myseat + 1:
                cells_lost += 1
        if acts[myseat] == "SHIELD" and nsh:
            rec = me.log["shields"][-1]
            if rec["turn"] == t_now and rec["R"] > 1:
                for p, j, h, imm, up in rec["ints"]:
                    if imm and not h and not up:
                        l1_shields += 1
                        pending.append((p, j, t_now))
        still = []
        for (p, j, t0) in pending:
            if g.owner[p] == j + 1:
                l1_lost += 1
            elif g.turn - t0 <= 6:
                still.append((p, j, t0))
        pending = still
    pl = g.places()
    pw, vs_opp = 0.0, []
    for j in range(4):
        if j == myseat:
            continue
        r = 1.0 if pl[myseat] < pl[j] else (0.5 if pl[myseat] == pl[j] else 0.0)
        pw += r
        vs_opp.append((names[j], r))
    lg = me.log
    sh = lg["shields"]
    last = [s for s in sh if s["R"] == 1]
    return {
        "pw": pw, "score": g.score[myseat], "vs": vs_opp,
        "opp_scores": [g.score[j] for j in range(4) if j != myseat],
        "shields": len(sh), "last_shields": len(last),
        "last_no_imminent": sum(1 for s in last
                                if not any(i and not h for _p, _j, h, i, _u in s["ints"])),
        "home_shields": sum(1 for s in sh if s["ints"]
                            and all(h for _p, _j, h, _i, _u in s["ints"])),
        "l1_shields": l1_shields, "l1_lost_anyway": l1_lost,
        "backfires": backfires, "raids": raids, "raids_early": raids_early,
        "cells_lost": cells_lost, "idle": lg["idle"], "idle_late": lg["idle_late"],
        "moves": lg["moves"], "turns90": lg["turns90"], "reversals": lg["reversals"],
    }


def _worker(arg):
    spec, tasks = arg
    return [play(spec, t) for t in tasks]


KEYS = ["shields", "last_shields", "last_no_imminent", "home_shields", "l1_shields",
        "l1_lost_anyway", "backfires", "raids", "raids_early", "cells_lost",
        "idle", "idle_late", "moves", "turns90", "reversals"]


def tasks_for(games, tier, seed=7):
    if tier.startswith("solo:"):
        name = tier[5:]
        fieldmod.TIERS[tier] = [name]
    return measure.make_tasks(games, tier, seed=seed)


SEED = int(os.environ.get("AUDIT_SEED", "7"))


def run(games, tier, specs, procs=None, seed=None):
    tasks = tasks_for(games, tier, SEED if seed is None else seed)
    pool = mp.Pool(procs or min(4, mp.cpu_count()))
    jobs, own = [], []
    for si, s in enumerate(specs):
        for i in range(0, len(tasks), 5):
            jobs.append((s, tasks[i:i + 5]))
            own.append(si)
    res = pool.map(_worker, jobs, chunksize=1)
    pool.close()
    pool.join()
    out = [[] for _ in specs]
    for o, r in zip(own, res):
        out[o].extend(r)
    return out


def paired(a, b, key):
    n = len(a)
    d = [b[i][key] - a[i][key] for i in range(n)]
    md = sum(d) / n
    se = math.sqrt(sum((x - md) ** 2 for x in d) / (n - 1) / n) if n > 1 else 0.0
    return md, se, sum(1 for x in d if x != 0)


def report(tier, specs, out):
    ref = out[0]
    n = len(ref)
    lines = ["[%s] %d paired games, reference = %s%s"
             % (tier, n, specs[0], "" if SEED == 7 else ", task seed %d" % SEED)]
    for si, s in enumerate(specs):
        b = out[si]
        pw = sum(x["pw"] for x in b) / n
        sc = sum(x["score"] for x in b) / n
        line = "%-24s PW %.4f  score %7.1f" % (s, pw, sc)
        if si:
            md, se, ch = paired(ref, b, "pw")
            ms, ses, _ = paired(ref, b, "score")
            line += ("  dPW %+.4f +/- %.4f (z %+.2f)  dScore %+.2f +/- %.2f (z %+.2f)"
                     "  games changed %d"
                     % (md, se, md / se if se else 0.0, ms, ses, ms / ses if ses else 0.0, ch))
        lines.append(line)
        tot = dict((k, sum(x[k] for x in b)) for k in KEYS)
        lines.append("    per game: " + ", ".join("%s=%.2f" % (k, tot[k] / float(n))
                                                  for k in KEYS))
    # pairwise win rate of the reference against each opponent design
    per = {}
    for x in ref:
        for nm, r in x["vs"]:
            per.setdefault(nm, []).append(r)
    if len(per) > 1:
        lines.append("    %s pairwise win rate vs each opponent:" % specs[0])
        for nm in sorted(per, key=lambda k: sum(per[k]) / len(per[k])):
            v = per[nm]
            lines.append("      %-14s %.3f  (n=%d)" % (nm, sum(v) / len(v), len(v)))
    return "\n".join(lines)


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    games = int(sys.argv[1])
    tier = sys.argv[2]
    specs = sys.argv[3:]
    for s in specs:
        parse_variant(s)                     # fail fast on a typo
    out = run(games, tier, specs)
    txt = report(tier, specs, out)
    print(txt)
    extra = [] if SEED == 7 else ["seed%d" % SEED]
    path = result_path("edge", tier, games, *(extra + list(specs)))
    with open(path + ".partial", "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    os.replace(path + ".partial", path)
    print("-> %s" % os.path.relpath(path, REPO))


if __name__ == "__main__":
    main()
