"""Run one bounded offline search from a strictly public JSON prefix."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from .mcts import recommend, strict_loads


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists() or args.input.resolve()==output:
        parser.error('Use a fresh output file distinct from the input')
    if args.input.stat().st_size>2*1024*1024:
        parser.error('Public prefix exceeds the explicit two-MiB input bound')
    result=recommend(strict_loads(args.input.read_bytes()))
    output.parent.mkdir(parents=True,exist_ok=True)
    pending=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',newline='\n',dir=output.parent,
                                         prefix='.intent-search-unpublished-',delete=False) as handle:
            pending=Path(handle.name)
            handle.write(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
            handle.flush();os.fsync(handle.fileno())
        if os.name=='nt':os.rename(pending,output)
        else:os.link(pending,output);pending.unlink()
        pending=None
        print(json.dumps(dict(output=str(output),recommended_action=result['recommended_action'],
                              counterfactual_turns=result['counterfactual_dual_referee_turns'],primary_match_credit=0,
                              full_bmcts_audit_credit=0,playing_strength_tested=False)),flush=True)
    finally:
        if pending is not None:pending.unlink(missing_ok=True)


if __name__=='__main__':main()
