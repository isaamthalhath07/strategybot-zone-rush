# Ranking of every bot in the repository's history

`RANKING.md` is the report; `full_ranking.csv` is the same table for all 595 bots.

## Reproduce

Run from this folder. Everything is rebuilt from Git history, so the working files
(a 12 MB corpus of bot sources and about 35 MB of per-game results) are not committed.

```bash
python3 build_corpus.py     # every distinct act(state) source in every commit and archive
python3 prep.py             # static scan and the multi-file bots
python3 make_cands.py       # candidate list
python3 labels.py           # provenance from the repo's registries
python3 arch.py             # architecture clusters
python3 tourney.py          # 35,616 games, about 80 minutes on 4 cores
python3 report.py           # rank.json, full_ranking.csv, console report
python3 write_md.py         # RANKING.md
```

Notes:

- `prep.py` writes `static.json` (imports and call sites per source) and rebuilds the
  bots that need sibling files from their own commit under `multi/`.
- `runner.py` plays games on `simulator/vendor_harness/referee.py` with one worker
  process per seat and the repository's timing limits (2,000 ms first call, 200 ms
  after). It is the same boundary `tools/benchmark.py` uses.
- `S1.json` to `S4.json` are the per-stage standings, `pooled.json` the finals with
  seed-only clones merged, `clones.json` the proof that eight finalist files are
  Racer or Blocker with one seat reseeded.
