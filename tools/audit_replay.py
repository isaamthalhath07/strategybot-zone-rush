"""Verify final trajectories with the independently implemented test engine."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.reference_engine import Game


def main():
    path = ROOT/'validation/branch_audit/final_results.json.gz'
    data = json.loads(gzip.decompress(path.read_bytes()))
    spec = data['registration']['spec']
    fixtures = {f['id']:f for f in spec['fixtures']}
    selected = {}
    for row in data['games']:
        key = (row['candidate'],row['map_group'],row['field'])
        selected.setdefault(key,row)
        if not row['complete'] or len(row['actions'])!=80:
            raise AssertionError('incomplete strength game')
        if sum(row['pw'])!=6:
            raise AssertionError('pairwise conservation')
    turns = 0
    for row in selected.values():
        fixture = fixtures[row['fixture']]
        game = Game(base=fixture['base'],rules=spec['rules'],start_token=fixture['token'])
        for actions in row['actions']:
            for seat,a in enumerate(actions):
                if a not in game.legal(seat):
                    raise AssertionError(('illegal used action',row['candidate'],row['fixture'],game.turn,seat,a))
            game.step(actions)
            turns += 1
        if game.score!=row['scores']:
            raise AssertionError(('score disagreement',row['candidate'],row['fixture'],game.score,row['scores']))
    report = dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  independent_engine_sha256=hashlib.sha256((ROOT/'tests/reference_engine.py').read_bytes()).hexdigest(),
                  final_rows_checked=len(data['games']),sampled_full_replays=len(selected),replayed_turns=turns,
                  sampling='First fixture per finalist, board and opponent field. All rows checked for full 80-turn completion and pairwise score conservation.',
                  exact=True)
    target = ROOT/'validation/branch_audit/independent_replay.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf8',newline='\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
