"""Where does the score gap come from in the pairings the focal bot loses?
  python3 lab/gap.py cand [--field strong|mid|weak] [--maps 60] [--seed 41]
Every seat is profiled in every game. For each rival that finishes ahead of the focal
bot, the difference (rival minus focal) is accumulated per profile key, so the table
shows what the bots that beat us do differently in exactly the games where they do.
A second table lists which opponents beat us most often.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, diag, arena, suite2
import multiprocessing as mp

SHOW = ["score", "income_early", "income_mid", "income_late", "raid_bonus", "lost_bonus",
        "claims", "claim_value", "upgrades", "upgrade_value", "raids", "raids_L1", "raids_L2",
        "lost_cells", "lost_L1", "lost_L2", "shield", "catches", "backfires", "got_caught",
        "frozen_turns", "move", "move_failed", "idle_stay", "abandoned_progress",
        "claims_early", "upgrades_early", "claims_mid", "upgrades_mid", "claims_late",
        "upgrades_late", "raids_early", "raids_mid", "raids_late", "final_cells", "final_upgraded"]


def job(t):
    names = list(t["opponents"]); names.insert(t["seat"], t["cand"])
    r = sim.play(names, sim.make_map(t["family"], t["mapseed"]), token=t["token"], seed=t["seed"],
                 record=True)
    profs = [dict(diag.profile(r, s)) for s in range(4)]
    return t["seat"], names, profs, r["pw"][t["seat"]], t["family"]


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--field": "strong", "--maps": "60", "--seed": "41"}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    cand = args[0]
    field = suite2.groups()[opt["--field"]]
    fx = arena.fixtures(field, maps=int(opt["--maps"]), seed=int(opt["--seed"]), families=suite2.FAMS)
    tasks = [dict(f, cand=cand) for f in fx]
    lose = collections.Counter(); nlose = 0
    win = collections.Counter(); nwin = 0
    me_all = collections.Counter()
    by_pw = collections.defaultdict(lambda: [0, collections.Counter()])
    by_opp = collections.defaultdict(lambda: [0, 0.0, 0.0])
    by_fam = collections.defaultdict(lambda: [0, 0.0])
    games = 0; pwsum = 0.0
    margins = []
    with mp.Pool(4) as pool:
        for seat, names, profs, pw, fam in pool.imap_unordered(job, tasks, chunksize=4):
            games += 1; pwsum += pw
            by_fam[fam][0] += 1; by_fam[fam][1] += pw
            mine = profs[seat]
            me_all.update(mine)
            bucket = by_pw["bad (PW<=1)" if pw <= 1 else "mid" if pw < 3 else "first"]
            bucket[0] += 1; bucket[1].update(mine)
            for j in range(4):
                if j == seat:
                    continue
                d = profs[j]["score"] - mine["score"]
                row = by_opp[names[j]]
                row[0] += 1; row[1] += 1.0 if d < 0 else 0.5 if d == 0 else 0.0; row[2] += d
                margins.append(d)
                target, = (lose,) if d > 0 else (win,)
                if d > 0:
                    nlose += 1
                elif d < 0:
                    nwin += 1
                else:
                    continue
                for k in SHOW:
                    target[k] += profs[j].get(k, 0) - mine.get(k, 0)
    print("%s vs %s: %d games, PW %.3f, pairings lost %d won %d" % (cand, opt["--field"], games,
                                                                    pwsum / games, nlose, nwin))
    print("%-20s %10s %12s %12s" % ("key", "focal/game", "lost: r-me", "won: r-me"))
    for k in SHOW:
        print("%-20s %10.1f %12.1f %12.1f" % (k, me_all[k] / games, lose[k] / max(1, nlose),
                                             win[k] / max(1, nwin)))
    close = sum(1 for d in margins if 0 < d <= 60); far = sum(1 for d in margins if d > 60)
    print("lost by <=60: %d   lost by more: %d   won by <=60: %d" % (
        close, far, sum(1 for d in margins if -60 <= d < 0)))
    print("\nfocal bot's own numbers by result")
    order = [b for b in ("bad (PW<=1)", "mid", "first") if b in by_pw]
    print("%-20s" % "key" + "".join("%14s" % ("%s n=%d" % (b[:5], by_pw[b][0])) for b in order))
    for k in SHOW:
        print("%-20s" % k + "".join("%14.1f" % (by_pw[b][1][k] / by_pw[b][0]) for b in order))
    print("\nby map family")
    for fam, (n, s) in sorted(by_fam.items(), key=lambda kv: kv[1][1] / kv[1][0]):
        print("  %-10s n=%-4d PW=%.3f" % (fam, n, s / n))
    print("\nby opponent (share of pairings the focal bot wins; mean rival-minus-focal score)")
    for name, (n, s, d) in sorted(by_opp.items(), key=lambda kv: kv[1][1] / kv[1][0]):
        print("  %-34s n=%-4d win=%.2f  gap=%+.0f" % (name[-34:], n, s / n, d / n))
