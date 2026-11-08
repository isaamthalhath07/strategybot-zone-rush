"""Publish all spatial-intent results, including unfavourable subgroups."""
import hashlib
import json
from pathlib import Path

from freshlab.evaluate import summary
from freshlab.report import describe
from territorylab.evaluate import hashes


def main():
    files = [Path("territorylab/results")/name for name in (
        "discovery.json", "development.json", "final.json",
        "economic_confirmation.json", "attribution.json")]
    data = [json.loads(p.read_text()) for p in files]
    for d in data:
        if d["sources"] != hashes():
            raise AssertionError("published sources differ from measured sources")
        for file, expected in d.get("extra_sources", {}).items():
            if hashlib.sha256(Path(file).read_bytes()).hexdigest() != expected:
                raise AssertionError("extra source changed")
    report = describe(files)
    for file, d in zip(files, data):
        if not any(r["task"]["scenario"] is not None for r in d["rows"]):
            continue
        variants = list(d["variants"])
        report += "\n## Nominal opening-role subgroups: %s\n\n" % file.name
        report += "These roles are test construction metadata, not guaranteed actual routes. "
        report += "Subgroup intervals are descriptive, without multiplicity adjustment.\n\n"
        report += "| Centre-opening roles | Tasks | Variant | Difference | 95% interval |\n|---|---:|---|---:|---|\n"
        for n in range(4):
            group = [r for r in d["rows"] if r["task"]["scenario"] == n]
            for v, r in summary(group, variants).items():
                if v != "baseline":
                    report += "| %d | %d | %s | %+.4f | [%+.4f, %+.4f] |\n" % (n, r["n"], v, r["difference"], *r["ci95"])
    games = sum(len(d["rows"])*len(d["variants"]) for d in data)
    calls = sum(r["calls"] for d in data for row in d["rows"] for r in row["results"].values())
    report += "\n%d comparison games; %d checked action calls. Baseline matches the unchanged v8 submission.\n" % (games, calls)
    contrast = data[-1]["history_minus_prior"]
    report += "\nHistory minus the static spatial prior (explanatory ablation): %+.4f, 95%% interval [%+.4f, %+.4f].\n" % (contrast["difference"], *contrast["ci95"])
    report += "\n**Decision: retain v8.** The original spatial final gain did not replicate in the separate economic-planner confirmation. History's additional value was not established.\n"
    Path("territorylab/RESULTS.md").write_text(report.rstrip()+"\n", encoding="utf-8", newline="\n")
    print("Games:", games, "Calls:", calls)
    print("Spatial final:", data[2]["summary"])
    print("Economic confirmation:", data[3]["summary"])


if __name__ == "__main__":
    main()
