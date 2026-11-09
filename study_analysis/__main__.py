"""Generate only a complete owner-authenticated frozen-study report."""
import argparse
import json
from pathlib import Path

from distributed_campaign import protocol as p
from primary_campaign import core
from .report import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.with_suffix('.sha256').exists():
        parser.error('Use a fresh report output path')
    result = analyze(args.registration, args.registry)
    core.seal(output, result)
    print(json.dumps(dict(output=str(output), sha256=p.sha(output.read_bytes()),
                          accepted_games=result['coverage']['unique_games'], comparisons=len(result['comparisons']),
                          new_games_executed=0, primary_match_credit=0, promoted=False)), flush=True)


if __name__ == '__main__':
    main()
