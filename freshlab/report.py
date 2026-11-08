"""Summarise recorded experiments; never modify policies from final outcomes."""
import argparse
import json
from pathlib import Path

from freshlab.evaluate import summary


def describe(files):
    lines = ["# Recorded fresh-opponent experiments", "",
             "PW means mean opponents outscored per game (ties count half), maximum 3.",
             "Intervals describe independent paired game tasks. Discovery comparisons",
             "are exploratory and have no multiple-comparison adjustment.", ""]
    for file in files:
        d = json.loads(file.read_text(encoding="utf-8"))
        lines += ["## " + file.name, "", "Split: **%s**, seed **%s**." % (d["split"], d["seed"]), "",
                  "| Variant | PW/3 | Mean score | Difference | 95% interval |",
                  "|---|---:|---:|---:|---|"]
        for name, r in d["summary"].items():
            lines.append("| %s | %.4f | %.0f | %+.4f | [%+.4f, %+.4f] |" %
                         (name, r["pw"], r["score"], r["difference"], *r["ci95"]))
        styles = {s["seed"] for r in d["rows"] for s in r["task"]["specs"]}
        lines += ["", "%d tasks, %d distinct opponent parameter draws. " % (len(d["rows"]), len(styles)) +
                  "Every variant played the same maps, seats, token starts and draws.", ""]
        if d["split"] in ("final", "supplementary_final"):
            variants = list(d["variants"])
            chosen = [v for v in variants if v != "baseline"][0]
            r = d["summary"][chosen]
            lines += ["**Pre-registered final decision:** " +
                      ("aggregate gain supported by the interval; inspect robustness before promotion."
                       if r["ci95"][0] > 0 else
                       "no established gain; retain the existing submission."), "",
                      "### Final map subgroups (descriptive only)", "",
                      "| Map | Tasks | Difference | 95% interval |", "|---|---:|---:|---|"]
            for kind in sorted({r["task"]["map_kind"] for r in d["rows"]}):
                group = [r for r in d["rows"] if r["task"]["map_kind"] == kind]
                a = summary(group, variants)[chosen]
                lines.append("| %s | %d | %+.4f | [%+.4f, %+.4f] |" %
                             (kind, a["n"], a["difference"], *a["ci95"]))
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.write_text(describe(args.files).rstrip() + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
