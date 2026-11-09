# Independent continuation review

The frozen helpers regenerate actual actors rather than replaying future rival
actions. `oversight.make_actors` executes pinned source in fresh namespaces and
freshly instantiates each rival. This is necessary: `deepcopy` of a Python
function retains its original global namespace and RNG.

All four proposals must be computed from separately isolated copies of the same
preturn public board before the focal proposal is replaced. A focal intervention
must therefore leave the other three actions on its own turn unchanged; rivals
can react from the following observation onward.

The frozen focal bot writes planner intent (`prior_target`, sometimes
`last_bait`) while proposing an action. Synchronizing only `_history[seat]['last']`
repairs accepted-action inference but retains those intent updates. This is a
declared one-step hybrid diagnostic, not the unchanged focal policy or a newly
trained stronger bot. Reassigning the already proposed action should be a no-op;
admission must prove full trace, terminal score, and pairwise equality for that
explicit baseline branch on every accepted source case.

The old coaching helper returns literal 320/80 coverage totals. Those totals
cannot alone establish callback coverage. New evidence must count each of the
four callbacks on all 80 turns, count both-referee state comparisons, check
legality/deadlines/input isolation/fallbacks and each supported public-memory
oracle after the callback, then verify terminal scores and pairwise results.

The new `experiment.py` implements those measured counters. Independent test
spies observed four actual 80-call controller histories, all 80 physical steps,
and 81 successful two-referee comparisons including the opening. The synthetic
explicit baseline reproduces the entire independent original tape. A forced
move changes a rival's next-turn response and terminal outcome while leaving
that rival's simultaneous root decision unchanged. Poisoning every post-root
recorded action does not change that responding continuation.

Review caught and corrected an important compatibility issue: constructing
actor views through the teacher's public serializer canonicalized legal-action
order. Seeded, order-sensitive rivals then failed original-tape reproduction.
The immutable actor adapter now preserves the source view's legal-action order.

Only serialized four-field public observations and the focal player's accepted
past actions may enter the teacher. Real actor identities, source specs, RNG,
private referee counters and future source actions remain observer-only.

The accompanying tests use synthetic public controllers and short public
inference witnesses. They grant zero primary matches, zero completed-game or
BMCTS audit credit, no playing-strength evidence and no promotion. No 16-case
study, heldout run or source-stage outcome is asserted by this review.

Validation: `python -m unittest intent_trials.test_continuation -v` passed all
10 tests. They also exercise first/regular deadlines, illegal actions, immutable
view isolation, fallback rejection and every supported score/progress/cooldown
oracle failure. A synthetic `KeyboardInterrupt` is re-raised unchanged with the
partial branch trace and measured callback/referee coverage attached. Actual
selected-source-case baseline equivalence remains a
mandatory execution assertion; it has not been claimed from synthetic tests.
