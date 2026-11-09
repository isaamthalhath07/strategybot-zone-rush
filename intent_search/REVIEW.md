# Independent review and current limits

The separate information-set reviewer added eight tests without changing the
author's frozen runtime or archive. The checks independently replay 96 sampled
transitions in both referees, reconstruct public policy draws and tree backups,
verify that latent types share nodes when public histories match, and exercise
terminal ranks, source quarantine and exclusive CLI publication. The original
ten tests and these eight checks cover implementation mechanics, not strength.

The root also read the complete search implementation. The chosen focal action
is absent from rival policy inputs. The rollout policy is keyed by public
history rather than the sampled private explanation. Joint physical/type weights
are sampled together; separate marginals do not replace their correlations.
Gumbel sampling uses finite binary64 arithmetic and 52-bit uniforms. Extremely
small modeled probabilities do not have ideal real-number sampling behavior.

## Capacity is not a proof of universal coverage

Under the current canonical rules and complete public history, the board fixes
positions, ownership, upgrades and income. Public income and capture events fix
scores. Freeze booleans across turns determine the remaining freeze time because
already-frozen players cannot be caught again. Accepted own actions and public
events determine own cooldown and progress. The priority token is resolved by
the third complete public view.

A loose bound after token resolution leaves three rival cooldowns in 0..4 and
three rival progress counters in 0..2: at most 5^3 × 3^3 = 3,375 physical
explanations. A deliberately loose early bound allowing three token hypotheses
is 10,125. These multiply by 64 persistent joint type assignments, giving 216,000
and 648,000 physical/type pairs. The early bound does not assert that all its
combinations are reachable.

The prototype's 1,024-state / 65,536-pair limits therefore are not proven to cover
every valid history. No reachable counterexample exceeding those caps has been
claimed, and the 16-history prediction pilot had no cap failure. Exceeding a cap
rejects the whole input without pruning. A future complete two-million-game
BMCTS audit needs a reviewed capacity policy and actual complete coverage;
these tests cannot grant that claim. The bound also needs revision if persistent
goals, routes or controller memories are added to the latent model.

## Bounded latency evidence

A root-local probe of one canonical opening used 96 simulations, horizon six
and all six actions. Three external wall times were 0.40614, 0.40234 and
0.44630 seconds; the median was 0.40614. Every repetition checked 576 simulated
turns in both referees and produced the same complete tree fingerprint. Timing
includes public inference, sampling, source checks and simulation; Python import
startup is excluded. Other local work can affect these measurements.

That measured configuration exceeds the 200 ms regular-call budget in this
opening probe. It does not prove that every configuration is too slow, that
late-game latency is the same, or that an online policy is ready. This remains
an offline prototype. A causal usefulness experiment and fresh full-match policy
confirmation must precede any strength or promotion claim.
