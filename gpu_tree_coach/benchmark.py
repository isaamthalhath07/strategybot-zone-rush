"""Small warm end-to-end benchmark; search simulations never count as games."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

import torch

from search_coach.belief import PublicObservation
from tests import reference_engine as ref
from . import scalar, tensor
from .protocol import FORMAT, MODEL_VERSION, canonical, source_hashes


def roots(count, simulations, horizon):
    result = []
    for i in range(count):
        focal = i % 4
        game = ref.Game(start_token=1+(i//4)%4)
        initial = PublicObservation.from_view(game.views()[focal]).serializable()
        transitions = []
        for _ in range(i%4):
            game.step(['STAY']*4)
            transitions.append(dict(own_action='STAY', observation=PublicObservation.from_view(game.views()[focal]).serializable()))
        result.append(dict(schema=1, kind=FORMAT, root_id='warm-benchmark-'+str(i),
                           initial_observation=initial, transitions=transitions,
                           search=dict(seed=710000+i, simulations=simulations, horizon=horizon,
                                       max_nodes=64, trace=False)))
    return result


def measured(call):
    started = time.perf_counter()
    report = call()
    return report, time.perf_counter()-started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts', default='1,8,64,256')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--simulations', type=int, default=24)
    parser.add_argument('--horizon', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cuda-graph', action='store_true')
    args = parser.parse_args()
    counts = [int(n) for n in args.counts.split(',')]
    if (not counts or any(not 1 <= n <= 512 for n in counts) or not 1 <= args.repeats <= 3
            or not 12 <= args.simulations <= 32 or not 1 <= args.horizon <= 5 or args.output.exists()):
        parser.error('Use fresh output and bounded counts1..512/repeats1..3/simulations12..32/horizon1..5')
    torch.set_num_threads(1)
    device = 'cuda'
    torch.ones(1, device=device).sum().item()
    # Warm both runtimes and verify an actual complete tree and trace first.
    warm = roots(1, 12, 2)
    warm[0]['search']['trace'] = True
    tensor.search_many(warm, device='cpu', verify_reference=True)
    tensor.search_many(warm, device='cuda', use_cuda_graph=args.cuda_graph, verify_reference=True)
    evidence = dict(schema=1, model_version=MODEL_VERSION, source_sha256=source_hashes(),
                    python=platform.python_version(), torch=torch.__version__, cuda=torch.version.cuda,
                    gpu=torch.cuda.get_device_name(), cpu_tensor_threads=1,
                    cuda_graph=args.cuda_graph, cuda_graph_capture_included_in_each_run=True,
                    repeats=args.repeats, simulations=args.simulations, horizon=args.horizon,
                    warm_complete_trace_parity=True, cases=[], primary_match_credit=0,
                    completed_game_audit_credit=0, full_bmcts_audit_credit=0,
                    caveat='Fixed integer models and synthetic public prefixes; timings are local bounded warm workloads, not playing strength or real primary-game throughput.')
    for count in counts:
        raw = roots(count, args.simulations, args.horizon)
        input_sha = hashlib.sha256(canonical(raw)).hexdigest()
        runs = dict(scalar_reference=[], cpu_tensor=[], cuda=[])
        reports = {}
        for _ in range(args.repeats):
            for name, call in [('scalar_reference', lambda: scalar.search_many(iter(raw))),
                               ('cpu_tensor', lambda: tensor.search_many(iter(raw), device='cpu', max_roots=512)),
                               ('cuda', lambda: tensor.search_many(iter(raw), device='cuda', max_roots=512,
                                                                  use_cuda_graph=args.cuda_graph))]:
                report, elapsed = measured(call)
                runs[name].append(elapsed)
                if 'expected' not in reports:
                    reports['expected'] = report['roots']
                if report['roots'] != reports['expected']:
                    raise AssertionError('QUARANTINED: benchmark exact full tree disagreement')
                reports[name] = report
        medians = {name: statistics.median(values) for name, values in runs.items()}
        trees_sha = hashlib.sha256(canonical(reports['expected'])).hexdigest()
        entry = dict(roots=count, public_input_sha256=input_sha, complete_tree_sha256=trees_sha,
                     all_repetitions_exactly_equal=True, wall_s=runs, median_wall_s=medians,
                     cuda_speedup_over_cpu_tensor=medians['cpu_tensor']/medians['cuda'],
                     cuda_speedup_over_scalar=medians['scalar_reference']/medians['cuda'],
                     cuda_search_simulations_per_s=count*args.simulations/medians['cuda'],
                     cuda_end_to_end_preparation_s=reports['cuda']['preparation_s'],
                     cuda_groups=reports['cuda']['batches'], cpu_tensor_groups=reports['cpu_tensor']['batches'])
        evidence['cases'].append(entry)
        print(json.dumps(dict(roots=count, median_wall_s=medians,
                              cuda_speedup_over_cpu_tensor=entry['cuda_speedup_over_cpu_tensor'])), flush=True)
    if evidence['source_sha256'] != source_hashes():
        raise ValueError('QUARANTINED: source mutation during benchmark')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as output:
        output.write(json.dumps(evidence, sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    main()
