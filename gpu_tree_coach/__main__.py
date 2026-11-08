"""Bounded JSONL input/output runner. A mismatch prevents result publication."""
import argparse
import json
import os
from pathlib import Path
import tempfile

import torch

from .protocol import strict_loads
from .tensor import search_many


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--roots-per-chunk', type=int, default=256)
    parser.add_argument('--support-budget', type=int, default=4096)
    parser.add_argument('--node-budget', type=int, default=65536)
    parser.add_argument('--total-root-budget', type=int, default=16384)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--verify-reference', action='store_true')
    parser.add_argument('--cuda-graph', action='store_true')
    args = parser.parse_args()
    if args.threads < 1 or args.output.exists() or args.input.resolve() == args.output.resolve():
        parser.error('Use positive threads and a fresh distinct output file')
    torch.set_num_threads(args.threads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def roots():
        with args.input.open('r', encoding='utf8') as stream:
            while True:
                # A full79-turn public prefix is comfortably below2MiB.
                line = stream.readline(2*1024*1024+1)
                if not line:
                    return
                if len(line) > 2*1024*1024 or not line.strip():
                    raise ValueError('Oversize or empty input line')
                yield strict_loads(line)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', newline='\n',
                                         dir=args.output.parent, prefix='.tree-unpublished-', delete=False) as output:
            temp_path = Path(output.name)
            def emit(row):
                output.write(json.dumps(dict(kind='root_result', result=row), separators=(',', ':'), allow_nan=False)+'\n')
            report = search_many(roots(), device=args.device, max_roots=args.roots_per_chunk,
                                 max_support_states=args.support_budget, max_tree_nodes=args.node_budget,
                                 max_input_roots=args.total_root_budget, verify_reference=args.verify_reference,
                                 result_sink=emit, use_cuda_graph=args.cuda_graph)
            output.write(json.dumps(dict(kind='summary', result=report), separators=(',', ':'), allow_nan=False)+'\n')
            output.flush(); os.fsync(output.fileno())
        # Windows rename is atomic and fails if the destination exists. On
        # POSIX, a no-replace hard link gives the same publication contract.
        if os.name == 'nt':
            os.rename(temp_path, args.output)
        else:
            os.link(temp_path, args.output)
            temp_path.unlink()
        temp_path = None
        print(json.dumps(dict(output=str(args.output.resolve()), supported=report['supported_roots'],
                              unsupported=report['unsupported_roots'], elapsed_s=report['elapsed_s'],
                              exact_reference_verified=report['exact_reference_verified'])))
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
