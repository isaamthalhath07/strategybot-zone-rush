"""Actual synthetic-output verifier tests; no GPU or known-control reruns."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from deadline_runner import runner,verify
from deadline_runner.test_runner import FakePhysics
from tests import reference_engine as engine


def fixture_registration(folder,count=2):
    source=folder/'toy.py'; source.write_text('CONFIG={}\ndef act(view): return "STAY"\n')
    entry=dict(path=str(source),sha256=runner.sha(source.read_bytes())); fixtures=[]
    for i in range(count):
        base=engine.make_map(canonical=True); seat=i%4
        fixtures.append(dict(id='SYNTHETIC-VERIFY-%d'%i,candidate=entry['sha256'],map_id=runner.sha(bytes(base)),base=base,
            token=seat+1,seat=seat,field='SYNTHETIC',opponents=[dict(id='R%d'%s,seat=s,family='planner',seed=1,genes={}) for s in range(4) if s!=seat]))
    return dict(candidates=[entry],sources={'planner':entry},fixtures=fixtures,guards={str(source):entry['sha256']},rules={'catch_requires_stay':True})


def reseal(path,value):
    body=runner.canonical(value)+b'\n'; path.write_bytes(body); path.with_suffix('.sha256').write_text(runner.sha(body)+'\n')


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=runner.ROOT/'deadline_runner'/'.cache'; parent.mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-VERIFY-',dir=parent); cls.folder=Path(cls.temp.name)
        cls.registration=fixture_registration(cls.folder); cls.original=cls.folder/'original'
        with patch.object(runner,'_physics',side_effect=FakePhysics):
            runner.run_fixtures(cls.registration,[f['id'] for f in cls.registration['fixtures']],cls.original,batch_size=2,workers=2,audit_workers=2)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def output(self,name):
        path=self.folder/name; shutil.copytree(self.original,path); return path

    def checked(self,path):
        # Only the explicit CPU physics test double's hardware assertion is
        # replaced. Every actual original/replay callback receipt is generated
        # by the real runner/pools and the exact six-field wire schema.
        with (patch.object(verify,'_cuda_metadata',return_value=None),
              patch.object(runner,'_actors',side_effect=AssertionError('Actor rerun')),
              patch.object(runner,'_physics',side_effect=AssertionError('GPU rerun')),
              patch.object(engine.Game,'step',side_effect=AssertionError('Physics rerun'))):
            return verify.verify_execution(self.registration,path)

    def test_actual_six_field_receipts_verify_read_only(self):
        result=self.checked(self.original)
        self.assertEqual(len(result['rows']),2); self.assertEqual(len(result['audits']),2)
        self.assertEqual(result['verification']['callback_or_physics_reruns'],0)

    def test_root_row_corruption_even_with_updated_root_hash_is_rejected(self):
        output=self.output('corrupt-row'); rows=verify.read_lines(output/'originals.jsonl')
        rows[0]['actions'][0][0]='EAST'
        (output/'originals.jsonl').write_bytes(b''.join(runner.canonical(r)+b'\n' for r in rows))
        summary=verify.read_sealed(output/'summary.json'); summary['originals_sha256']=runner.sha((output/'originals.jsonl').read_bytes()); reseal(output/'summary.json',summary)
        with self.assertRaises(ValueError): self.checked(output)

    def test_current_source_drift_is_rejected(self):
        pins=runner.source_pins(); pins['deadline_runner/runner.py']='0'*64
        with patch.object(runner,'source_pins',return_value=pins):
            with self.assertRaisesRegex(ValueError,'source pins changed'): self.checked(self.original)

    def test_rehashed_perturn_false_completion_is_rejected(self):
        output=self.output('corrupt-call'); path=output/'batch_00000'/'turns.jsonl'
        turns=verify.read_lines(path); turns[0]['actor_proofs'][0]['timing'][0]['completed']=False
        path.write_bytes(b''.join(runner.canonical(r)+b'\n' for r in turns))
        summary=verify.read_sealed(path.parent/'original_summary.json'); summary['turns_sha256']=runner.sha(path.read_bytes()); reseal(path.parent/'original_summary.json',summary)
        with self.assertRaisesRegex(ValueError,'receipt changed'): self.checked(output)

    def test_physics_metadata_exact_types_labels_rules_and_source_subclosure(self):
        pins=runner.source_pins()
        names={'training_gpu/batch_game.py','search_coach/gpu_batch.py','training_gpu/__init__.py',
               'search_coach/__init__.py','search_coach/belief.py','tests/reference_engine.py','local_cuda_matches/physics.py'}
        metadata=dict(format='local-cuda-match-physics/1',device='cuda:SCHEMA_TEST',cuda_kernel_executed=True,
            policy_backend='External exact CPU actors',batch_size=2,accepted_batch_steps=80,accepted_branch_turn_events=160,
            max_turns=80,setup_throwaway_transitions=3,setup_primary_match_credit=0,setup_completed_game_audit_credit=0,
            use_graph=True,rules=dict(frozen_stay_counts=False,claim_resets_progress=True,catch_requires_stay=True,
                lost_contest_is_stay=True,home_upgradable=True),source_sha256={name:pins[name] for name in names})
        verify._cuda_metadata(metadata,2,pins)
        variants=[]
        for key,value in [('format','wrong'),('policy_backend','GPU policy'),('accepted_batch_steps',80.0),
                          ('setup_primary_match_credit',False),('setup_throwaway_transitions',True)]:
            bad=copy.deepcopy(metadata); bad[key]=value; variants.append(bad)
        bad=copy.deepcopy(metadata); bad['rules']['catch_requires_stay']=1; variants.append(bad)
        bad=copy.deepcopy(metadata); del bad['source_sha256']['local_cuda_matches/physics.py']; variants.append(bad)
        bad=copy.deepcopy(metadata); bad['source_sha256']['local_cuda_matches/physics.py']='0'*64; variants.append(bad)
        for index,bad in enumerate(variants):
            with self.subTest(corruption=index),self.assertRaises(ValueError): verify._cuda_metadata(bad,2,pins)


if __name__=='__main__': unittest.main()
