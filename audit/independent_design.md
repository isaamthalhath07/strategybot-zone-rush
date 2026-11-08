# Fixed independent challenge policies

`independent_bot.py` adds `IndependentFarmer(seed=0)` and `IndependentRaider(seed=0)`. Each instance is callable with the documented public `state`, and a fresh instance should be created for every game. This file imports only `collections.deque` and `random`; the policy has no reference to `engine`, `mybot`, `botlib`, any submission file, or another policy's private data.

Frozen source SHA256 before any submission matchup: `93a046a0f4347290b46658d8be2c0e9c38ac5fa22dbb61063cf7d4ce4513005c`.

These are deliberately unfamiliar, untuned policies. They were authored from the audited rule economics after the rules/interface review, without running against the final submission or using incumbent matchup outcomes to select constants. They are additional architectural diversity, not a statistically representative sample of external teams or a blinded independent research exercise. Their first submission matchups should remain held out from final parameter selection.

## Architecture

The policy enumerates economically useful jobs: take a neutral cell, upgrade own land, or raid a rival. Each job has observed travel distance, remaining stay work, recurring income value for the remaining scoring turns, and the official one-time raid bonus. Public-history shield estimates add expected delay to risky raids. The top fourteen jobs enter a fixed two-job schedule calculation, including same-cell claim then upgrade. The chosen first action is recomputed every turn with mild target inertia.

Breadth-first paths avoid initially occupied cells. Immediate contested-cell risks use known cyclic token order and ownership priority. Homes are read from the board; geometry never assumes seat-to-corner assignment. The input is copied into local observations and never modified.

Each policy remembers its own turn count, prior board, per-bot partial work, public freeze events, coarse shield readiness, and empirical commitment/escape frequencies. Freeze attribution is a simple heuristic rather than a hidden-state solver. Defensive shielding compares expected immediate ownership loss with the one-action shield expense and two-action backfire cost.

## Pros and cons

| Policy | Strengths | Weaknesses |
|---|---|---|
| Efficient farmer | Prices action tempo and clusters; avoids expensive ready-owner raids; exploits safe upgrades and neutral income; real path occupancy; fixed small runtime | Can cede valuable contested land; two jobs miss long routes; static rival occupancy can overstate future detours; fractional expected delays simplify strategic risk |
| Adaptive raider | Captures full level-1 raid bonus; values part of denial; uses observed shield cooldowns; sometimes leaves a likely shield to induce backfire; shields urgent own losses | Coarse freeze attribution can misread readiness; optimistic enemy assumptions can overcommit; baiting gives up a work turn; denial may help third parties more than itself |
| Both | Different architecture and fixed constants; stdlib and public inputs only; homes excluded from rival targets; official income/bonus arithmetic | Share one policy family and cannot substitute for external competition bots; approximate retention, two-job average rate, and empirical probabilities are not equilibrium proofs |

## Verification

`python -X utf8 audit/test_independent_smoke.py` passed 2,560 decisions across eight complete games containing only these independent policies. Maps included all-1, all-3, and six generated mirrored maps; token starts varied. Assertions covered legal actions, unchanged board and legal actions, no exceptions, home ownership, and the real 200ms/first-turn-2s limits. Worst observed call in the final smoke run was 20.697ms on this machine.

The smoke test imports the local engine outside the policy to supply public views. It never imports or plays against the submitted bot. No parameters were changed in response to win rates or scores. One planning correction was made before freezing: revisiting the present cell after moving away cannot reuse discarded partial progress.
