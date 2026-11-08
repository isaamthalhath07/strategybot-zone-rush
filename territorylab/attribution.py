"""Separate history learning from the static spatial prior, without tuning.

This is an explanatory ablation on fresh seeds, not another promotion test.
Opponent algorithms come from the economic confirmation, never a training set.
"""
import hashlib
import json
import multiprocessing as mp
from pathlib import Path

from freshlab.evaluate import summary
from territorylab import confirm, evaluate, policy
from territorylab.model import RegionModel


class PriorModel(RegionModel):
    def demand(self, board, positions, homes, seat, history=True):
        counts = self.n
        self.n = [0]*4
        try:
            return super().demand(board, positions, homes, seat, history)
        finally:
            self.n = counts


class ControlledAgent(policy.SpatialAgent):
    def __init__(self, seed=0, params=None, feature=None):
        super().__init__(seed, params, feature)
        if self.feature.get("prior_only"):
            self.regions = PriorModel()


VARIANT = {"strength": 0.35, "history": True, "prior_only": True}


def initialize():
    evaluate.opponents.SpatialOpponent = confirm.EconomicOpponent
    evaluate.policy.SpatialAgent = ControlledAgent
    evaluate.policy.VARIANTS["prior_only"] = VARIANT


def main():
    out = Path("territorylab/results/attribution.json")
    if out.exists():
        raise SystemExit("preserve ablation outcomes")
    sources = evaluate.hashes()
    extra = {p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
             for p in ("territorylab/confirm.py", "territorylab/attribution.py")}
    variants = ["baseline", "territory", "prior_only"]
    rows = []
    with mp.Pool(8, initializer=initialize) as pool:
        for row in pool.imap(evaluate.job, [(t, variants) for t in confirm.tasks(448, 829781)], chunksize=1):
            rows.append(row)
            if len(rows) % 64 == 0:
                print("%d/448" % len(rows), flush=True)
    if sources != evaluate.hashes() or any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in extra.items()):
        raise AssertionError("ablation source changed")
    report = summary(rows, variants)
    # Re-express the existing observations relative to the static spatial prior.
    differences = [dict(task=row["task"], results={"baseline":row["results"]["prior_only"],
                                                 "territory":row["results"]["territory"]}) for row in rows]
    contrast = summary(differences, ["baseline", "territory"])["territory"]
    definitions = dict(policy.VARIANTS)
    definitions["prior_only"] = VARIANT
    payload = dict(split="attribution", seed=829781, sources=sources, extra_sources=extra,
                   variants={v:definitions[v] for v in variants}, summary=report,
                   history_minus_prior=contrast, rows=rows,
                   caveat="Explanatory ablation, no policy selection or change. Same region field/strength, with learned beliefs removed in prior_only. Fresh economic-opponent parameters, shared bookkeeping.")
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    print("History minus spatial prior:", json.dumps(contrast))


if __name__ == "__main__":
    main()
