"""Small CPU-only synthetic benchmark protocol; actual512 is root-only."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_runner import benchmark,runner,verify
from deadline_runner.test_runner import FakePhysics
from deadline_runner.test_verify import fixture_registration
from tests import reference_engine as engine


class BenchmarkTests(unittest.TestCase):
    def test_fixed_replication_mapping_is_balanced_and_fresh(self):
        original,controls,_=benchmark._load_known()
        replicas,mapping=benchmark._replicas(original,controls)
        self.assertEqual(len(replicas['fixtures']),512); self.assertEqual(len(set(m['lane_id'] for m in mapping)),512)
        self.assertEqual([m['source_fixture_id'] for m in mapping],[r['fixture'] for _ in range(64) for r in controls])
        self.assertFalse(set(m['lane_id'] for m in mapping)&{r['fixture'] for r in controls})
        self.assertEqual(len(original['fixtures']),8)

    def test_synthetic_pipeline_benchmark_and_read_only_verifier(self):
        parent=runner.ROOT/'deadline_runner'/'.cache'; parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-BENCHMARK-',dir=parent) as temporary:
            folder=Path(temporary); reg=fixture_registration(folder); controls=[]
            for fixture in reg['fixtures']:
                game=engine.Game(base=fixture['base'],start_token=fixture['token']); tape=[['STAY']*4 for _ in range(80)]
                for joint in tape: game.step(joint)
                controls.append(dict(candidate=fixture['candidate'],fixture=fixture['id'],map_id=fixture['map_id'],focal_seat=fixture['seat'],field=fixture['field'],
                    scores=game.score,focal_pw=1.5,focal_score=game.score[fixture['seat']],opponent_ids=[s['id'] for s in fixture['opponents']],actions=tape,faults=[]))
            with (patch.multiple(benchmark,CONTROLS=2,REPETITIONS=2,PIPELINE_GAMES=4,BATCH_SIZE=2),
                  patch.object(benchmark,'_load_known',return_value=(reg,controls,{'SYNTHETIC_ONLY':'a'*64})),
                  patch.object(runner,'_physics',side_effect=FakePhysics),patch.object(verify,'_cuda_metadata',return_value=None)):
                output=folder/'output'; result=benchmark.run(output)
                self.assertEqual(result['measurements'][0]['games'],4)
                self.assertEqual(set(result['measurements'][0]),{'games','wall_seconds','full_actor_audits','both_referees'})
                with (patch.object(runner,'_actors',side_effect=AssertionError('Actor rerun')),
                      patch.object(runner,'_physics',side_effect=AssertionError('GPU rerun')),
                      patch.object(engine.Game,'step',side_effect=AssertionError('Physics rerun'))):
                    self.assertEqual(benchmark.verify_complete(output),result)
                pins=benchmark.source_pins(); pins['deadline_runner/benchmark.py']='0'*64
                with patch.object(benchmark,'source_pins',return_value=pins):
                    with self.assertRaisesRegex(ValueError,'source/input'): benchmark.verify_complete(output)
                self.assertEqual(result['primary_games'],0); self.assertEqual(result['study_games'],0)


if __name__=='__main__': unittest.main()
