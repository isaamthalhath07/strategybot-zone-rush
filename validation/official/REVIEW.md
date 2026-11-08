# Audit of the explicit STAY-only Shield clarification

The latest user-supplied answer is unambiguous: movement resolves first; Shield
catches only rivals whose effective action is STAY on the shielder's land. A
successful move escapes even if its destination belongs to the same shielder.
A blocked or lost-contest move becomes STAY and is catchable. A rival using a
valid Shield is not taking STAY and therefore is not a victim of another Shield.

Caught on turn 10 means forced STAY on turns 11 and 12, with movement available
again on turn 13. Shield on turn 10 means no Shield on 11–14, with the earliest
next use on 15. Empty catches backfire on the shielder, with the same two future
frozen turns. Backfire does not erase the four-turn Shield cooldown.

This explicitly replaces the earlier user interpretation implemented by release
`fc00af81...`. The earlier presence-rule campaigns remain valid measurements of
that particular local model, but do not establish strength under this clarified
rule. Their records, fixture flags, source hashes and results must not be rewritten.

## Existing referee and timing

The pinned vendored referee already implements this exact interpretation when
`catch_requires_stay=True`. It first resolves effective moves, including blocked
and lost-contest moves becoming STAY. It then checks STAY eligibility at the
resolved position, applies shields/freezes before work, resets caught progress,
and assigns two future frozen turns. A new Shield cooldown is set to four after
that turn and ages during the following turns. No referee source edit is needed.

Other physical rules are unaffected by the supplied answer: already-frozen
rivals remain ineligible; frozen STAY does not accrue work; Shield protects all
owned holdings; capture bonuses and completion-turn income are unchanged.

`rule_examples.json` records four directed external referee probes at turn 10:
move within A's land, productive STAY on A's land, a blocked move despite its
blocker moving away, and simultaneous Shields while B occupies A's land.
All pass, including the earliest-next-Shield turn-15 timeline. These are offline
observer tests, not private inputs to playing policies.

## Strong legacy candidates and known limitations

| Source | Assessment under the clarified rule |
|---|---|
| `tester_bots/transfer_previous.py`, SHA `fe03b8164ed3...` | Strong repaired STAY-only baseline. Its shield solver enumerates every feasible explanation, excludes movers/workers/players losing a holding as shielders, excludes shielding rivals from victims and retains ambiguous cooldown sets. Its same-owner-cell feint and any-successful-move escape assumptions are valid again. It lacks the new public-format and failed-job wrapper. |
| Frozen repaired research policy, SHA `1a718fd8b514...` | Same corrected tracker family with different frozen economic coefficients. A necessary strength control; old presence-rule rankings do not decide this comparison. |
| Original transfer, SHA `5457b5fdf4ca...` | Strong historical pricing control. Same-owner-land feint is now valid, but older progress reconstruction, attribution and continuation shortcomings remain. Do not confuse a useful economic prior with exact hidden-state inference. |
| Main fusion, SHA `720e5a3daf7b...` | STAY-only victim check is compatible, and its interface/cold-start/stuck-job safeguards remain useful. Its tracker picks the highest-plausibility Shield explanation rather than keeping all feasible possibilities, so it is a performance comparator, not a correctness oracle. |
| Current guarded presence release, SHA `fc00af81fdf7...` | Useful robustness scaffold, but its presence catch solver, territorial-retention labels and requirement to leave the owner's entire territory are wrong for the clarified rule. It must be corrected or retained only as a historical/control policy. |
| Latest shared shaunak/visual export, SHA `f7b40080a522...`, and original PR10 goal-forecast v9 | Goal forecasting remains an empirical hypothesis. Previously identified all-home clock/reset or disabled-clock-guard defects are independent of Shield eligibility. Rule clarification alone does not repair them. |
| Apex and other exact-policy predictors | Any embedded hypothetical referee must use STAY-only eligibility consistently. Matching a public source is not a hidden-state leak, but copy-sensitive identity assumptions and finite confirmation fields remain strategic limitations. |

The old fusion's warm fallback does not automatically confer its interface
robustness or its empirical strength on another policy. Conversely, adding a
normalization wrapper to a repaired economic policy should be checked for
canonical action equivalence and directly benchmarked rather than credited with
an assumed new playing-strength gain.

## Independent legacy-baseline oracle

`legacy_baseline_oracle.json` records a bounded independent check of the exact
`fe03b816...` export under `catch_requires_stay=True`: six actual self-play games
and six random public-history observer sequences, for 3,840 callbacks. Every
callback was legal and left its public input unchanged; own clock, score and
progress were exact, and every actual player cooldown remained in the retained
public belief set. Worst diagnostic callback was approximately 2.2 ms.

In random-history observer checks, only the external test chooses the recorded
joint actions. Each policy callback still receives only the four public fields;
afterward its observer remembers its own action, never an opponent's requested
or future action. Private counters are used only by external assertions. These
checks establish bookkeeping and contract compatibility, not tournament strength.

## Inference and decision requirements

1. Unchanged position alone does not prove STAY: a valid Shield also stays in
   place. Candidate shield sets must exclude their own members from victims.
   Two rivals shielding on one another's land can both backfire; a newly frozen
   rival standing on our land is not automatically evidence that we caught it.
2. Use pre-capture ownership when attributing the previous turn, and resolved
   positions/effective actions. A visible capture or completed upgrade proves
   work rather than Shield; losing any holding disproves an active Shield.
3. Keep all public-consistent explanations and conservative cooldown bounds.
   Ambiguity is real information loss, not a reason to invent a certain safe
   raid window. Own known action and legal Shield availability constrain the set.
4. Learn actual STAY probability rather than territorial residence. Movements
   between two cells of one owner must no longer count as Shield exposure.
   Already-frozen forced actions are not voluntary opponent commitment labels.
5. An escape plan needs a successful move, not departure from the owner's land.
   Occupied-at-start destinations and lost contests become STAY. Public geometry
   can rule out an occupied destination; unknown simultaneous rival intentions
   still leave contest risk. Do not call a merely intended move a guaranteed escape.
6. Preserve progress resets after capture, movement, Shield and freezes, plus
   all-home clock continuity and new-game reset detection. Those fixes survive
   the eligibility reversal and should not be discarded in a blind rollback.

## Measurement and historical-evidence requirements

- The old benchmark hard-asserted `catch_requires_stay=False`. New campaigns must
  register `True` explicitly, use new output paths and check the actual complete
  rules in every result. Do not silently run a new label on the old referee flags.
- Preserve old False results/registrations, including their original tool hash.
  If the benchmark implementation changes, keep the old tool snapshot for the
  historical integrity check rather than changing an old registration to match.
  Historical tests must check old chosen-source hashes against the archived old
  source, not assume that today's root `bot.py` is still `fc00af81...`.
- Screen all credible old and new policies on common fixtures under the clarified
  model. Balance every corner and priority-token combination for serious selection.
  Freeze finalists before fresh confirmation, cluster uncertainty by actual board
  content and report small inconclusive gaps honestly. Old False scores cannot be
  pooled into a True ranking or treated as proof of a gain from the rule correction.
- Preserve old game recordings with their own rule flags and source fingerprints.
  Fresh games and UI descriptions must identify the new rule. Existing live
  presence-rule matches must not be advanced, reset or relabeled as official tests.

The proposed corrected bot and simulator should be promoted only after their
own directed rule, public-history, legality/immutability, real-worker/timing and
fresh comparison checks pass. A finite leader is not a proof of universal optimality.


## Independent integration review before final publication

The corrected source reviewed here has SHA-256 `dd26262ba90b7beeab57455bebabffb06f3d3dc32e7525fc59064428ca9252f4`. Its victim solver now
requires unchanged position/effective STAY and excludes valid shielders as
victims; any-successful-move escapes and the same-land feint are restored. Own
cooldown availability distinguishes raw offered actions from actions the policy
itself considers safe, so an unfiltered legal list does not invite repeated
on-cooldown requests. Cold starts retain genuine uncertainty rather than assuming
that an offered Shield necessarily proves cooldown zero. These use public input
and remembered own actions only.

The backend health response now returns the active game's public rule definition
under the same lock as its identity. It exposes no private counter, score or
pending action. The AI-view game envelope still contains only identity/turn/over
and the four-field public observation. The UI keeps rule metadata outside that
observation and keys its cache by game ID; a historical presence-rule cache does
not describe a newly created STAY-only match. Standard-state rules override the
new-game default, and first-load AI view can obtain the restored game's public
rule version from health. Existing histories retain their own explicit flags.

Historical evidence checks now use the original archived presence policy and
original benchmark-source snapshot. This correctly removes the old assumption
that root `bot.py` and the benchmark must remain byte-identical across releases.
No old False registration or match outcome is relabeled as True evidence.

One bounded noncanonical fallback limitation was found and reported separately:
if a legal, known-recharged own Shield request is externally replaced by STAY,
the next no-freeze observation disproves the forced Shield hypothesis. The
reviewed source increments `inference_failures` but its conservative fallback
keeps own cooldown only at four, excluding the actual zero. It skips Shield
opportunities rather than returning an illegal action. This was not observed in
the timely registered campaigns. A repair should retain the aged prior cooldown
alongside four when the public model is inconsistent, and carry new source
provenance/verification; alternatively, the source's server-action-substitution
claim must be narrowed. This edge is distinct from the correct canonical
STAY-only victim/timing semantics.


### Resolution of the bounded own-cast recovery finding

A separate resilient candidate was created without mutating the frozen parent:
SHA-256 `e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5`.
Independent direct probes pass for four cases: no-freeze substitution, visible
own upgrade substitution, loss of an owned holding plus an actual rival catch,
and a genuinely accepted own backfire. The first two retain actual own cooldown
zero and reconcile productive progress; the catch case retains own zero/rival
four and infers effective STAY; a physically consistent accepted backfire still
has certain own cooldown four. `resilient_independent_probes.json` records these.

The solver first tries its canonical accepted-action model, retries without
forcing the own cast only when public physics contradict that model, and commits
legal-list convention learning only after the cast explanation survives. Proven
rejections reconcile effective STAY before progress bookkeeping. No hidden
acceptance acknowledgement or oracle enters the policy.

The separate `unacknowledged_substitution_ambiguity.json` is an exact two-world
counterexample: all four public fields can agree while true own/rival cooldowns
are [4,0] or [0,4]. That indistinguishable external-failure case remains an
information limit, not a newly invented certainty. The candidate documents the
accepted/on-time-action assumption explicitly. Its new hash and canonical
behavior-equivalence/fresh comparisons must be recorded before publication.

No remaining canonical rule, public-input privacy, historical-evidence or UI
rule-cache blocker was found in this independent integration review.
