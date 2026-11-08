# Historical comparison sources

`v8.py` preserves the exact root `bot.py` from commit `9df9497` (SHA-256
`cb30b5ae32f7e9013173adf7774c034482df3ce2592bfc2a7c3479a2dfa045e6`).
`engine_v8.py` preserves that experiment's exact `engine.py` (SHA-256
`9ddf7b3a6a674d6d25d4f7aa2a44a7e412f0833c758579ca35317c53ef584cdd`).
The active root export follows main's fusion policy; these files are frozen
comparators, not a new recommendation. `manifest.json` records original paths
and commit, and `.gitattributes` preserves their exact bytes on every platform.

The future and territory labs import `baselines.v8` explicitly. Freshlab keeps
its older experimental baseline in `freshlab/baseline.py`; its accepted v8 export
is verified against `baselines/v8.py`. The saved visual games are the historical
v8 recordings and replay through `baselines/engine_v8.py`.

Historical registrations, measured results, exported forward policy and release
verification reports retain their original paths and hashes. They describe the
source tree at measurement, not the current root export. Integration edits change
source hashes, so old final locks correctly reject new runs. Use an isolated
checkout at `9df9497` for the original final/confirmation/verification commands;
new policy revisions require new registrations and fresh comparison data.
