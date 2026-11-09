# Public-history opponent prediction

`intent_filter.py` is an offline reference model for better search inputs. It
accepts the opening public observation, accepted own actions and subsequent
public observations. It accepts no actual referee, rival controller, real seed,
private counter or future-action tape. Serialized cells must contain exactly the
six public properties. Hypothetical rivals receive their own public views of
reconstructed possible states, including their own legal-action list.

The model maintains joint weights over hidden physical explanations and four
persistent hypothetical rival styles: economic, raider, feinter and wanderer.
Three rivals yield 64 joint style assignments per physical state. These are
heuristic hypotheses with a fixed epsilon mixture, not identified real opponents
or calibrated probabilities that tournament rivals belong to those classes.

Every legal intended rival action contributes probability through simultaneous
physics. A stationary rival may have tried a blocked move. That move has STAY
effects but its probability must be added, rather than discarded or relabelled
as an observed STAY. Shield/backfire evidence can couple rivals, so the complete
joint posterior is retained instead of multiplying separate style marginals.
Weights remain in log space. Physics is computed once per physical state and
joint intention, independently of the 64 style assignments.

Three modes separate two questions: uniform legal intentions are the baseline;
a fresh mixture each turn tests the structural policies; persistent styles test
whether public history helps identify behavior. All three condition on the
same observations. The own action enters transition physics, never the rival
policy probability calculation.

Limits reject the entire update transactionally. No state is silently pruned,
patched or replaced. An unsupported history is a failed experiment, not a
completed prediction or a reason to omit an unfavorable case. Floating point
weights and the assumed policy class limit the interpretation even when all
modeled explanations are enumerated.

Twenty-two tests pass, including independent hand-computed Bayes cases,
blocked-action mass, full first-observation normalization, joint Shield/style
correlations, hidden-world indistinguishability, nested-input rejection and
budget rollback. The pilot tests use synthetic fixtures and explicitly mocked
expensive admission; they execute no campaign actors or matches.

```powershell
python -m unittest opponent_prediction.test_intent_filter opponent_prediction.test_independent opponent_prediction.test_pilot -v
```

`pilot.py` prepares a deterministic, balanced 16-history experiment from the
already accepted 100,000 TRAIN matches. It verifies the published source receipts
and raw fingerprints and replays selected transcripts in both referees. Each
history measures 79 observed successor views; its final physical turn is also
replayed, without inventing a turn81 bot observation. Full catalog metadata is
read to validate TRAIN assignment. Reserved games and outcomes are not consumed.

The full protocol is sealed before evaluating any selected likelihood. It fixes
all three comparisons, exact source versions, failure behavior, equal field
weights and a shared within-field map bootstrap. Intervals and public-context
subsets are descriptive. The data were already used for primary training, so
this is neither fresh policy confirmation nor a playing-strength test.

The first fixed pilot completed all 16 histories and 1,264 public prediction
steps, with no pruning, unsupported history, dropped case or inference-limit
failure. Mean log loss was 4.50946 for uniform intentions, 2.83763 for the per-turn
mixture and 2.43887 for persistent styles. The persistent model's loss was
14.05% lower than the per-turn mixture; every field improved in this sample.
The paired difference was -0.39876, with a descriptive within-field bootstrap
interval of [-0.44858, -0.34455]. This is a prediction result on consumed TRAIN
data, not a win-rate improvement, calibration proof or simultaneous confidence
claim. An independent implementation reproduced the means and bootstrap draws.
Exact results, the preregistration published before execution, and the independent
review are under `evidence/intent_001/`.

Prediction quality alone cannot establish stronger search decisions. Any later
search integration must retain public information boundaries and be checked
against responding counterfactual rivals, then validated in fresh complete
matches. This module changes no deployed bot, frozen four-arm study or existing
GPU worker. It adds zero primary matches and zero completed-game BMCTS audits.
