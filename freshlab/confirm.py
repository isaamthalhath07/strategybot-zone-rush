"""Balanced supplementary confirmation on four further unseen algorithms.

Candidate is the already registered raid_calibration; no new selection here.
Every map has every one of the 16 seat/token combinations in each block.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import random
import time
from pathlib import Path

import maps
from freshlab import evaluate, population, unseen


def tasks(repeats, seed):
    rng = random.Random("balanced-extra:%d" % seed)
    result = []
    for repeat in range(repeats):
        for kind in ("standard", "noise", "flat", "edge", "richhome", "richcorner", "inverted", "standard"):
            for seat in range(4):
                for token in range(1, 5):
                    s = rng.randrange(2**31)
                    result.append(dict(id=len(result), seat=seat, token=token,
                                       map_kind=kind, base=maps.make(s, kind), map_seed=s,
                                       specs=[unseen.extra_spec(rng.randrange(2**31)) for _ in range(3)]))
    rng.shuffle(result)
    return result


def initialize():
    # The policy sees only the standard view. Replace only the factory used by
    # the observer harness, never a field the focal bot receives.
    evaluate.population.ProceduralOpponent = unseen.ExtraOpponent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=883917)
    ap.add_argument("--repeats", type=int, default=8)
    ap.add_argument("--out", type=Path, default=Path("freshlab/results/balanced_confirmation.json"))
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("do not overwrite a confirmation result")
    provenance = evaluate.hashes()
    extras = {f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
              for f in ("freshlab/unseen.py", "freshlab/confirm.py")}
    registration = dict(candidate="raid_calibration", final_seed=args.seed,
                        repeats=args.repeats, sources=provenance, extra_sources=extras,
                        note="The original final design confounded map kinds with seat/token pairs. The paired result remains valid for that schedule. This additional pre-registered check balances them and adds four unused algorithms; no candidate change.")
    Path("freshlab/balanced_registration.json").write_text(json.dumps(registration, indent=2), encoding="utf-8", newline="\n")
    params = json.loads(Path("v7_params.json").read_text())
    params.update(throttle=0, budget_ms=10000.0, first_turn_ms=0)
    variants = ["baseline", "raid_calibration"]
    batch = tasks(args.repeats, args.seed)
    rows = []
    start = time.perf_counter()
    with mp.Pool(args.workers, initializer=initialize) as pool:
        for row in pool.imap(evaluate.job, [(t, variants, params) for t in batch], chunksize=1):
            rows.append(row)
            if len(rows) % 128 == 0:
                print("%d/%d (%.1fs)" % (len(rows), len(batch), time.perf_counter()-start), flush=True)
    if evaluate.hashes() != provenance:
        raise AssertionError("policy sources changed")
    if {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in extras} != extras:
        raise AssertionError("confirmation sources changed")
    report = evaluate.summary(rows, variants)
    payload = dict(split="supplementary_final", seed=args.seed, sources=provenance,
                   extra_sources=extras, variants={v: evaluate.candidate.VARIANTS[v] for v in variants},
                   summary=report, rows=rows,
                   caveat="Four new algorithms with shared observation plumbing. Fixed already-registered candidate. Balanced map/seat/token blocks. Confirmatory task intervals; subgroup intervals descriptive.")
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
