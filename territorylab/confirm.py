"""Unchanged spatial candidate against further, non-scripted economic planners.

Four newly authored scheduling objectives, no fit against either focal policy.
Register the candidate and this test's sources before producing outcomes.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import random
import time
from pathlib import Path

import maps
from botlib import first_step, man
from freshlab.population import ProceduralOpponent, specification
from freshlab.evaluate import summary
from territorylab import evaluate


FAMILIES = ("beam_sum", "renewal_route", "frontier_market", "reactive_allocator")


class EconomicOpponent(ProceduralOpponent):
    def __init__(self, spec):
        super().__init__(spec)
        self.finish_upgrade = None

    def choose(self, state):
        if len(state.legal_actions) == 1:
            return state.legal_actions[0]
        if self.shield(state):
            return "SHIELD"
        if (self.finish_upgrade == self.me and self.owner[self.me] == self.seat
                and not self.upg[self.me]):
            return "STAY"
        self.finish_upgrade = None
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        candidates = []
        for p, g, c, d, n in jobs:
            candidates.append((p, g, d, n, False))
            if self.owner[p] == 0 and d+4 <= self.R:
                extra = self.base[p]*(self.R-d-3)*self.spec["upgrade"]
                candidates.append((p, g+extra, d, 4, True))
        family = self.spec["family"]
        scores = {}
        for k, (p, g, d, n, combo) in enumerate(candidates):
            value = g/(d+n)
            if family == "renewal_route":
                # Amortise a visit across useful work remaining in its cluster.
                nearby = sum(self.base[q] for q in range(64)
                             if not self.owner[q] and man(p, q) <= 2)
                value *= 1+nearby/(20.0+d)
            elif family == "frontier_market":
                rival = min(man(p, q) for j, q in enumerate(self.pos)
                            if j != self.seat-1 and q is not None)
                value *= max(0.5, min(1.5, 1+0.08*(rival-d)))
            elif family == "reactive_allocator":
                # Actual rivals' positions and empty work, not a fixed compass
                # preference; the occupied region can change during a game.
                nearby = [q for q in range(64) if man(p, q) <= 2]
                empty = sum(self.base[q] for q in nearby if not self.owner[q])
                traffic = sum(man(p, q) <= 3 for j, q in enumerate(self.pos)
                              if j != self.seat-1 and q is not None)
                value *= (1+empty/15.0)/(1+0.30*traffic)
            scores[k] = value
        best = max(scores, key=scores.get)
        if family == "beam_sum":
            top = sorted(scores, key=scores.get, reverse=True)[:12]
            beam = [(0.0, self.me, 0, frozenset(), None)]
            best_value = -1.0
            for _ in range(3):
                nxt = []
                for val, pos, elapsed, visited, first in beam:
                    for k in top:
                        p, g, d, n, combo = candidates[k]
                        if p in visited:
                            continue
                        arrival = elapsed + man(pos, p)
                        finished = arrival+n
                        if finished > min(16, self.R):
                            continue
                        # Completion income adjustment, a coarse short-route
                        # model. It is not advertised as an exact game solver.
                        gain = g*max(0, self.R-finished+1)/max(1, self.R-d-n+1)
                        total = val+gain
                        f = k if first is None else first
                        nxt.append((total, p, finished, visited | {p}, f))
                        if total > best_value:
                            best_value, best = total, f
                if not nxt:
                    break
                beam = sorted(nxt, key=lambda x: x[0], reverse=True)[:8]
        p, g, d, n, combo = candidates[best]
        if combo:
            self.finish_upgrade = p
        self.target = p
        return "STAY" if p == self.me else first_step(self.me, p, self.closed) or "STAY"


def tasks(count, seed):
    rng = random.Random("territorial-economic-confirm:%d" % seed)
    kinds = ("standard", "noise", "flat", "edge", "richhome", "richcorner", "inverted")
    result = []
    for i in range(count):
        s = rng.randrange(2**31)
        specs = []
        for _ in range(3):
            spec = specification("train", rng.randrange(2**31))
            spec["family"] = rng.choice(FAMILIES)
            specs.append(spec)
        kind = kinds[i//16 % len(kinds)]
        result.append(dict(id=i, seat=i//4 % 4, token=1+i % 4,
                           map_seed=s, map_kind=kind, base=maps.make(s, kind),
                           scenario=None, specs=specs))
    return result


def initialize():
    evaluate.opponents.SpatialOpponent = EconomicOpponent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=896)
    ap.add_argument("--seed", type=int, default=729251)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=Path, default=Path("territorylab/results/economic_confirmation.json"))
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("preserve the completed confirmation")
    sources = evaluate.hashes()
    extra_sources = {"territorylab/confirm.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    registration = dict(candidate="territory", games=args.games, seed=args.seed,
                        sources=sources, extra_sources=extra_sources,
                        criterion="Same candidate as locked spatial final, no retraining. Require a positive lower endpoint of the aggregate paired interval before calling the improvement independently replicated. Zero contract failures required.")
    Path("territorylab/economic_registration.json").write_text(json.dumps(registration, indent=2), encoding="utf-8", newline="\n")
    variants = ["baseline", "territory"]
    rows = []
    start = time.perf_counter()
    with mp.Pool(args.workers, initializer=initialize) as pool:
        for row in pool.imap(evaluate.job, [(t, variants) for t in tasks(args.games, args.seed)], chunksize=1):
            rows.append(row)
            if len(rows) % 64 == 0:
                print("%d/%d %.1fs" % (len(rows), args.games, time.perf_counter()-start), flush=True)
    if evaluate.hashes() != sources or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != extra_sources["territorylab/confirm.py"]:
        raise AssertionError("sources changed; discard confirmation")
    report = summary(rows, variants)
    payload = dict(split="supplementary_final", seed=args.seed, sources=sources,
                   extra_sources=extra_sources, variants={v:evaluate.policy.VARIANTS[v] for v in variants},
                   summary=report, rows=rows, elapsed_seconds=time.perf_counter()-start,
                   caveat="Four further newly authored economic scheduling rules, no fixed spatial roles. Same public observation plumbing. Candidate unchanged from original final.")
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
