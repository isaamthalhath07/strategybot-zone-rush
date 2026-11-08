# Retained tester bots

Every file is a standalone public-input opponent, pinned in the release manifest.
These provide different challenges; they are not interchangeable champions.

| File | Why retain it |
|---|---|
| `transfer_previous.py` | Closest final comparator: 1.8516 mean opponents outscored across384 games. |
| `transfer_original.py` | Strong original economic control: 1.7474 in final confirmation. |
| `fusion.py` | Previous main export and robust economic/fallback architecture: 1.5247 in final confirmation. |
| `apex.py` | Exact-copy counter-policy specialist: 1.7500 in balanced development. Useful for testing predictable policies; identity and old-rule model assumptions limit generalization. |
| `racer.py` | PR10's direct income/capture race: 1.5781 in balanced development. |
| `blocker.py` | PR10's obstruction/denial strategy: 1.6667 in initialscreen,1.4141 in balanced development. |

These measurements use different fields where indicated; do not rank across
rounds by pooling their numbers. All retained files had zero worker faults in
their recorded comparisons. Some preserve historical internal rule assumptions,
which makes them useful controls; the actual simulator always enforces the
clarified post-movement Shield rule. No deliberately broken bot is retained.
Original source commits and hashes are in `release_manifest.json` and the
validation source registry. No tester reads the other players' pending actions.
