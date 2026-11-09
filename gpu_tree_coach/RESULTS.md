# Bounded prototype result

Four execution paths produced the same recommendations, full observation trees, visit counts and integer value sums: independent scalar, CPU tensor, eager CUDA, and CUDA Graph. Fourteen tests passed, including full action/observation/value traces on the adversarial panel, hidden-distinct real worlds with identical public prefixes, observation branching, real terminal timing, simultaneous rival actions, reordered/chunked jobs, support loss, node caps, memory limits and late-error receipt quarantine. The graph regression additionally matched **every dynamic hidden physics field** against eager CUDA for 15 consecutive replays. These are implementation checks, not playing-strength evidence.

The working environment was Python 3.12.10, PyTorch 2.11.0+cu128, RTX 5070 Ti Laptop, with one CPU tensor thread. Three repetitions were run per workload, after warmup. Each root used 24 simulations, horizon 5 and at most 64 nodes. All workloads use the canonical map, opening/three early STAY prefixes, declared diagnostic seeds and simple integer rival models. Public inference, tensor setup, CPU tree work, synchronous public-byte transfers, source checks and graph capture are included in the external wall time. Reference searches are timed separately. Other work on the laptop may affect measurements; these are local bounded results, not controlled hardware-performance guarantees.

## Final CUDA Graph benchmark

Median external wall times, seconds:

| Independent roots | Scalar reference | CPU tensor | CUDA Graph | CPU tensor / CUDA Graph | Fastest measured path |
| ---: | ---: | ---: | ---: | ---: | --- |
|1|0.0267|0.5068|0.3791|1.34×|Scalar|
|8|0.2118|0.6520|0.4069|1.60×|Scalar|
|64|2.5591|1.1524|0.8801|1.31×|CUDA Graph|
|256|7.7547|2.8906|2.6152|1.11×|CUDA Graph|

The GPU graph was about 14 times slower than scalar for one root, and about 1.9 times slower for eight roots. CUDA becomes useful here when there are enough independent roots to batch. This is throughput over a batch, not a claim that a single search meets the bot's 200 ms budget.

The last 256-root graph repetition breaks down as 1.7665 s public preparation, 0.1265 s support setup/warmup/graph capture, and 0.6717 s sequential search including CPU trees and public transfers. These component values describe that last repetition; they are not component medians and must not be combined with the table's median as if they were the same sample. Public inference now dominates that measured batch. Exactly 1,996,800 public bytes returned to CPU during its 120 simulated steps; no 384-scalar board serialization is used per node.

The default benchmark throughput calls do **not** rerun scalar verification internally. Every repetition is nevertheless compared exactly to the complete scalar tree outside its timed call. The scalar column is the separately measured cost of an independent full reference search, including its public preparation; enabling `--verify-reference` adds a reference search and comparison for each root and materially reduces throughput. The tests exercise that in-call verification. Optional traces were enabled in parity tests and disabled for benchmark timings.

## Preserved unsuccessful eager result

Before graph capture, eager CUDA lost to CPU tensor for every measured size:

| Independent roots | Scalar reference | CPU tensor | Eager CUDA |
| ---: | ---: | ---: | ---: |
|1|0.0205|0.3757|1.4813|
|8|0.2404|0.5809|2.1398|
|64|1.3338|0.6715|1.7781|
|256|4.4775|1.7193|3.3957|

Keep this negative result. These runs occurred at a different time, so the two tables cannot establish a clean graph/eager speedup ratio. Within each table the implementations are interleaved and repeated, and all complete-tree digests agree. The graph and eager tables also have identical per-case complete-tree digests. Capturing one frozen step reduced launch overhead without changing the model, draws, UCT, utility or returned tree.

## Evidence and limits

- [Initial eager measurements](evidence/warm_benchmark_001.json), SHA-256 `62ea471c0b91efdc405a6c3e6c5420c7a32d49712fe4e95f7395fd9b83fa3097`.
- [Initial exact runtime source archive](evidence/eager_001_sources.zip), SHA-256 `eec240eda1ba6067506f65a32857a7520966502bcb59cbe54006b39aa3664fa8`.
- [Final graph measurements](evidence/warm_graph_002.json), SHA-256 `969d83c3dd93a936dc099b6bc2c305ccaaa00ab7cdbfafb2c522bf7baea6c5c5`.
- The final frozen source manifest and source archive are stored beside these files. The manifest also records the successful test command and unchanged reused-source fingerprints.

No actual primary match, completed-game audit, full BMCTS audit or improved playing result is credited. The old small CPU-tree usefulness panel found no improvements; this implementation does not reverse that finding. Uncalibrated rival models, uniform support sampling, a projected-income cutoff, fixed beam pruning and finite samples remain strategic limitations. Speed/parity alone justify no promotion, no architecture winner and no large distributed GPU run. The deployed bot, frozen four-arm architecture study and primary-campaign assurances remain unchanged.
