# Fresh confirmation of the defensive variant

The same unpromoted variant, source SHA
`50d82d7ac58162e9cf651136afcedac5586db9a060f153854b00875f13efef37`,
led training stages 2 and 3 on different maps and rival instances. Its advantage
over the incumbent was approximately 0.0282 and 0.0249 standardized pairwise
points. Those unpaired training results are a discovery signal.

This package preregisters a fresh paired test: **128 maps × four rival fields ×
16 seat/token crossings × two policies = 16,384 complete matches**. Every map
and its rotations are excluded from the entire 10,000-map primary catalog and
the historical controls available at registration. Both arms use matched rival
parameters and separate fresh controller instances. These are extra controls;
they never increase the two-million-game primary count.

The variant changes five defensive configuration values. It preserves all
non-CONFIG source logic. The source policies and complete planned schedule are
in `evidence/preregistered_defense_50d.zip`, with fingerprints and planned counts
in `evidence/preregistration.json`. **No confirmation matches have been executed
by this preparation package.** Remote execution/import and final analysis still
need integration with the distributed worker.

The declared proposal gate is a positive overall 99% map-cluster bootstrap lower
bound and a 95% lower bound above -0.03 in each field. These are descriptive
bootstrap criteria, not a universal or familywise correctness guarantee. Passing
them does not automatically replace the production file; independent review,
fresh strength evidence and deployment/runtime checks remain required.

Five schedule-corruption tests pass. Their small positive fixture explicitly
mocks prior admission and executes no games. The real 128-map registration was
prepared only after validating the two actual discovery-stage admissions.

```powershell
python -m unittest confirmation_campaign.test_prepare -v
python -m confirmation_campaign.prepare --campaign .cache/primary/campaign_v1_20261109 --output .cache/confirmation/new-defensive-test
```

Preserve the existing preregistration. A failed outcome must not trigger silent
map replacement or an unreported rerun with a more favorable test set.
