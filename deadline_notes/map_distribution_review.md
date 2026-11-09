# Map-distribution robustness of the completed architecture study

**Blocker's observed lead is not confined to rich-home or uniform stress
maps.** On the65 declared centre-biased maps B−e8 is+0.104808 and B−Feint
is+0.064663 pairwise points. On the37 noisy-centre maps the differences are
+0.118877 and+0.045186. Removing both stress families leaves102 maps and
differences+0.109911/+0.057598. These are exploratory subgroup results, not a
new selection rule or a registered proof of performance under the official
random-map frequency distribution.

There is a material distribution mismatch despite legal equivalent physics.
The study's generator is a categorical Gaussian/stress mixture; the vendor
random generator has a shared sampled slope/noise model and homes at most2.
The word "centre-biased" does not make those distributions identical. The
correct conclusion includes both the robustness above and this remaining gap.

## Inputs and checks

This analysis reads only the complete root-authorized32768-case study, its
fixed map metadata and generator source. No new map/game, callback, physics,
GPU action, key, registry access, source change, policy recommendation or
heldout consumption was performed. No unapproved TRAIN generation was read.

- [Completed report](../.cache/local_cuda/architecture_v2_001/report.json):
  SHA256 `6a76e981432d13638a873ba4b45db6c3259707a45a8d26b6b8b0bf5ece915147`.
- [Registration](../.cache/confirmation/architectures_v2_001/registration.json):
  SHA256 `b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9`.
- [All completed rows](../.cache/local_cuda/architecture_v2_001/games.jsonl):
  SHA256 `b9301d2ad5389504d2e14186b6bc6a6a62f73eea287ca8f05ec4d807d299e2ae`,
  matching the admitted report's provenance.
- [Mixture generator](../evolution/maps.py):
  SHA256 `e0c9328d89aff7ab23caa9a9fa6b672fc4074f66f57dd69678d1a121d5d679ef`.
- [Vendor/reference generator](../simulator/vendor_harness/referee.py):
  SHA256 `f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337`.

Every one of the32768 row identities was matched once to its fixed fixture,
candidate, map, focal seat and opponent field. Declared map family and map bytes
were checked against the128 registered maps. Pairwise points were independently
recomputed from all final scores, and the four reconstructed total numerators
matched the completed report. This is arithmetic on admitted outcomes, not
another game/actor/physics admission or independent owner-MAC verification.

For group g with n maps, each arm has64n matches. If T[a,m] sums twice the
pairwise points over those64 games, the mean is
`sum_m T[a,m]/(128n)`. Thus map families retain identical field/seat/token
weighting. They are not opponent fields: each map family includes all four
opponent fields and all sixteen seat/token crossings.

## All declared families and all four policy means

| Declared map family | Maps | Games/arm | e8 |50d| Original B | Original Feint |
|---|---:|---:|---:|---:|---:|---:|
| centre-biased |65|4,160|2.256250|2.257692|2.361058|2.296394|
| noisy-centre |37|2,368|2.239654|2.236275|2.358530|2.313345|
| rich-home-stress |13|832|2.308293|2.307091|2.340144|2.345553|
| uniform-stress |13|832|2.245192|2.241587|2.326923|2.242788|
| Both centre families, exploratory combined |102|6,528|2.250230|2.249923|2.360141|2.302543|

The source's60%/20%/10%/10% weights are **proposal weights**, not a guarantee
that every accepted finite bank has exactly those proportions. This bank has
65/37/13/13 maps, or50.78%/28.91%/10.16%/10.16%. Fixed seeds, content/orbit
exclusions and rejection/deduplication can change accepted frequencies. The
registered overall result weights the actual128 maps equally; this review
does not replace it with nominal-mixture or guessed official-frequency weights.

Rich-home maps do not generate B's advantage over Feint: their point contrast
is slightly negative. Uniform stress helps B relative to Feint, but B also
leads in each centre family and in their combined102-map subset. This rules
out the simple descriptive explanation that the entire observed B lead comes
only from the two named stress categories. It does not establish a counterfactual
official-distribution mean.

## Exploratory whole-map intervals

These are new post-study descriptive diagnostics requested after complete
admission. Each row resamples whole maps **within that group**, preserving all
four fields/seat/token cells and arm pairing. There are20000 NumPy default_rng
draws, shared for the two contrasts within each group; percentile indices are
499/19499 without interpolation. There is no multiplicity adjustment across
these overlapping subgroups/contrasts. These are neither the study's registered
six-comparison intervals nor simultaneous opponent-field inference.

| Group | B−e8 | Exploratory95% | B−Feint | Exploratory95% |
|---|---:|---|---:|---|
| centre-biased,65maps |+0.104808|[0.060457,0.151202]|+0.064663|[0.036178,0.093510]|
| noisy-centre,37maps |+0.118877|[0.044764,0.189823]|+0.045186|[0.016470,0.075591]|
| rich-home-stress,13maps |+0.031851|[−0.058894,0.106370]|−0.005409|[−0.052284,0.039063]|
| uniform-stress,13maps |+0.081731|[−0.013221,0.182091]|+0.084135|[0.045673,0.123798]|
| Both centre families,102maps |+0.109911|[0.071232,0.149740]|+0.057598|[0.036688,0.079427]|

Seeds are the first8 SHA256 bytes interpreted big-endian from compact JSON
`["map-distribution-exploratory/v1",202611091740,group_name]`. Exact group seeds:
centre-biased4337635640637624921; noisy-centre17482308013536991055;
rich-home-stress4410723685839052580; uniform-stress17805858719502342979;
centre-families-combined9337723391986508681. NumPy version2.5.4 was used.
Small13-map groups have broad unstable tails. Positive exploratory endpoints
are supporting diagnostics, not an additional registered superiority claim.

## What the official-generator mismatch means

Both generators mirror a4×4 quadrant into an8×8 board with point values1..3.
The custom-map parser and referee accept such legal mirrored maps, including
home value3. The referee's physics, Shield/work order, occupancy/contests,
income/capture accounting and deadlines do not change with the generator.
Consequently the completed evidence is valid play on its declared legal maps;
it is not invalid physics or hidden-information use.

But the map probability laws differ:

- The mixture draws each quadrant value from family-dependent categorical
  weights around `1.1+1.8(r+c)/6`, with width0.65 for centre-biased and1.05 for
  noisy/rich-home, uniform weights for uniform stress, and a forced home3 for
  rich-home stress.
- Vendor `random_map(seed)` draws one common slope in[0.33,0.58], one common
  noise amplitude in[0.25,0.75], then rounds/clips
  `3−(6−r−c)·slope+uniform(−noise,noise)` and caps homes at2. The shared slope
  and amplitude induce different spatial dependence as well as different
  marginals. A centre-looking board is not automatically a typical vendor draw.

There are23 registered home3 maps,17.97% of the bank:2 centre-biased,3
noisy-centre,13 rich-home and5 uniform. Those home values are absent from the
vendor generator. Removing every home3 map leaves105 maps, all four policy
means as follows:

| Subset | e8 |50d| B | Feint | B−e8 | B−Feint |
|---|---:|---:|---:|---:|---:|---:|
| Homes≤2,105maps |2.247991|2.247545|2.365104|2.308705|+0.117113|+0.056399|

Exploratory95% intervals are[0.081548,0.154018] and[0.036235,0.076563],
respectively, with seed5886486151910937255. Home value≤2 is necessary but not
sufficient for vendor-like maps. Filtering it cannot correct the full joint
distribution or supply appropriate importance weights.

## Additional metadata-only support screen

To check that merely deleting home3 is not disguising other differences, a
further **exploratory compatibility screen** uses only the board and source
generator bounds, without scores. This is a continuous-parameter/noise support
calculation; it does not demonstrate a particular finite PRNG seed, a density
or an official frequency for any retained map.

Let d=6−r−c in the independent quadrant. With noise allowed to approach0.75,
positive-measure feasibility requires a common slope s in(0.33,0.58):

- value1 with d>0 requires `s>0.75/d`; value1 at d=0 is infeasible;
- value2 with d>0 requires `s<2.25/d`;
- value3 with d>0 requires `s<1.25/d`.

Intersect those bounds across the sixteen cells. A nonempty open interval
allows a noise amplitude below0.75 and per-cell noise intervals of positive
length in the idealized continuous model. Boundary/finite-PRNG details are not
used to assert that every compatible board is actually attained by a seed.

Only46 maps pass this screen:40 of65 centre-biased,6 of37 noisy-centre and
none of the26 named stress maps. Thus even the centre labels cannot be equated
with the vendor distribution. On the46 compatible maps, the point means remain:

| Subset | e8 |50d| B | Feint | B−e8 | B−Feint |
|---|---:|---:|---:|---:|---:|---:|
| Continuous-support-compatible,46maps |2.278363|2.279721|2.366848|2.311141|+0.088485|+0.055707|

Exploratory95% intervals are[0.036855,0.144192] and[0.025815,0.084749],
seed10036996361889488811. This strengthens the descriptive finding that B's
advantage is not solely a consequence of extreme maps. It still does not
estimate the vendor law: compatible maps can have very different probabilities,
and outcome-based selection/importance reweighting was not performed. The
screen and all additional intervals are explicitly outside the registered
primary inference family.

## Consequence and remaining uncertainty

The registered original-B reference choice remains supported under the declared
study distribution, and its lead persists in both centre families. Do not
erase that evidence by calling all non-vendor-generator play invalid. Equally,
do not describe a custom legal stress mixture as an exact sample of the official
random frequency law. Equal physics supports legality, not distributional
representativeness. Unknown tournament map/opponent mixtures can still change
relative strength, even for a well-measured source.

A literal claim about that vendor random law would require a separate,
prospectively fixed, previously unconsumed panel from that generator, with
matched responding rivals and the same validity checks. This observation is
not permission to replace current reserved maps, tune on heldout outcomes or
change the frozen selection/promotion rules. The existing registered results
and these exploratory robustness checks must retain distinct labels. This
review creates no matches, callback/physics work, BMCTS audits or promotion.
