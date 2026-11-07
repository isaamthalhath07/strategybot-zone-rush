"""Summarise all versions, failures, final outcomes and subgroup uncertainty."""
import hashlib
import json
from pathlib import Path

from freshlab.evaluate import summary


def main():
    names = ("discovery.json","corrected_discovery.json","development.json","final.json","native_confirmation.json")
    lines = ["# Forward-planning experiments", "",
             "PW is opponents outscored per game, ties half, maximum 3. It is not actual competition Elo.",
             "Discovery intervals are exploratory. Final aggregate intervals concern the registered synthetic distributions.", ""]
    games,calls = 0,0
    for name in names:
        path = Path("futurelab/results")/name
        d = json.loads(path.read_text())
        for filename,expected in d["sources"].items():
            if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
                raise AssertionError("measured source differs: "+filename)
        variants = list(d["variants"])
        lines += ["## "+name,"", "Split: %s; seed: %d; actual clock budgets: %s." % (d["split"],d["seed"],d["native"]), "",
                  "| Variant | PW/3 | Mean score | Difference | 95% interval |",
                  "|---|---:|---:|---:|---|"]
        for v,r in d["summary"].items():
            lines.append("| %s | %.4f | %.0f | %+.4f | [%+.4f, %+.4f] |" % (v,r["pw"],r["score"],r["difference"],*r["ci95"]))
        lines.append("")
        games += len(d["rows"])*len(variants)
        calls += sum(r["calls"] for row in d["rows"] for r in row["results"].values())
        if name in ("final.json","native_confirmation.json"):
            for axis,label in (("map_kind","Map"),("seat","Seat (zero-based in data)")):
                lines += ["### "+label+" subgroups (descriptive, not multiplicity-adjusted)","",
                          "| Group | Tasks | Difference | 95% interval |","|---|---:|---:|---|"]
                for group in sorted({row["task"][axis] for row in d["rows"]}):
                    rows = [row for row in d["rows"] if row["task"][axis] == group]
                    r = summary(rows,variants)["one_job"]
                    lines.append("| %s | %d | %+.4f | [%+.4f, %+.4f] |" % (group,r["n"],r["difference"],*r["ci95"]))
                lines.append("")
    prediction = json.loads(Path("futurelab/results/prediction.json").read_text())
    lines += ["## Ownership prediction (separate from policy improvement)","",
              "56 fixed-baseline games; five-class Brier loss, lower is better. Forecasts see only current public history.","",
              "| Turns ahead | Persistence | Raw futures | 50% persistence shrinkage |","|---|---:|---:|---:|"]
    for h,group in prediction["summary"].items():
        lines.append("| %s | %.4f | %.4f | %.4f |" % (h,group["persistence"]["brier"],group["raw"]["brier"],group["shrunk"]["brier"]))
    lines += ["", "%d comparison games; %d checked action calls. Prediction and correctness games are additional." % (games,calls), "",
              "All original failures are retained. Source hashes refer to this frozen code; future revisions must not reuse consumed final sets as tuning data.", ""]
    Path("futurelab/RESULTS.md").write_text("\n".join(lines),encoding="utf-8",newline="\n")
    print("Recorded comparison games:",games,"checked calls:",calls)


if __name__ == "__main__":
    main()
