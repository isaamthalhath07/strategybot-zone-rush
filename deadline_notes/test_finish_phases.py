"""Synthetic operator tests; no owner capability, real phase or actor call."""
import copy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

from . import finish_phases as operator

ROOT=Path(operator.__file__).resolve().parents[1]
TEMP=ROOT/'deadline_notes/.test-tmp'


def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


class FakeAuthority:
    def __init__(self): self.records={};self.reads=[]
    def read(self,scope,path):
        self.reads.append((scope,Path(path)))
        return copy.deepcopy(self.records[(scope,Path(path))])


class OperatorTests(unittest.TestCase):
    def setUp(self):
        TEMP.mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='finish-',dir=TEMP)
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.campaign=self.root/'campaign';self.campaign.mkdir()
        self.folder=self.root/'certificates';self.folder.mkdir();self.output=self.root/'operator'
        self.authority=FakeAuthority();self.calls=[];self.waits=[];self.guards=[]
        self.current=datetime(2026,11,9,8,10,tzinfo=timezone.utc)
        self.cutoff=datetime(2026,11,9,10,58,39,tzinfo=timezone.utc)
        self.measurement=dict(games=512,wall_seconds=100,full_actor_audits=512,both_referees=True)
        self.manifest=dict(timing_measurements=[self.measurement])
        self.cache=SimpleNamespace(folder=self.folder,_guard=lambda:self.guards.append(1))
        self.complete_dev=True
        self.error_on_dev=False
        self.controller=SimpleNamespace(now=lambda:self.current,_heldout_absent=lambda campaign:True,
            design=SimpleNamespace(canonical=canonical,sha=lambda b:hashlib.sha256(b).hexdigest()))
        self.budget=SimpleNamespace(may_start_generation=lambda *a,**k:False,FINAL_CUTOFF=self.cutoff)
        self.counter=0
        self.clock=SimpleNamespace(sleep=self.sleep,perf_counter=self.tick)
        self.add_stage(0);self.add_stage(1)

    def tick(self): self.counter+=1;return float(self.counter)

    def add_stage(self,index,accepted=True,certificate=True):
        name='train_%03d'%index;stage=self.campaign/name;stage.mkdir()
        if accepted:
            path=stage/'accepted.json';path.write_text('{}')
            self.authority.records['acceptance',path]=dict(measurement=self.measurement)
        if certificate:
            path=self.folder/(name+'.json');path.write_text('{}')
            self.authority.records['acceptance',path]=dict(stage=name)

    def sleep(self,seconds):
        self.waits.append(seconds)
        (self.folder/'development.json').write_text('{}')

    def phase(self,cache,action):
        self.assertIs(cache,self.cache);self.calls.append(action)
        if action=='development' and self.complete_dev: (self.folder/'development.json').write_text('{}')
        if action=='development' and self.error_on_dev: (self.folder/'advance_error.json').write_text('{}')
        return dict(action=action,selected='a'*64)

    def invoke_operator(self):
        with patch.object(operator,'controller',self.controller),patch.object(operator,'budget',self.budget),\
             patch.object(operator,'run_phase',side_effect=self.phase),patch.object(operator,'time',self.clock):
            return operator.finish(self.campaign,self.authority,self.manifest,self.cache,self.output)

    def test_import_does_not_load_authority_or_invoke_a_phase(self):
        events=[]
        def forbidden(*a,**k): events.append(1);raise AssertionError('No owner operation on import')
        campaign=ModuleType('deadline_campaign');campaign.budget=object();campaign.controller=SimpleNamespace(_context=forbidden)
        cache=ModuleType('deadline_finalization.cache');cache.IntegrityCache=forbidden;cache.run_phase=forbidden
        spec=importlib.util.spec_from_file_location('_synthetic_finish_import',operator.__file__)
        module=importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules',{'deadline_campaign':campaign,'deadline_finalization.cache':cache}):
            spec.loader.exec_module(module)
        self.assertEqual(events,[])

    def test_exact_order_results_and_ready_dev_certificate(self):
        result=self.invoke_operator()
        self.assertEqual(self.calls,['freeze','development','final']);self.assertEqual(self.waits,[])
        self.assertEqual(result['action'],'final')
        for action in self.calls:
            self.assertEqual((self.output/(action+'.json')).read_bytes(),canonical(dict(action=action,selected='a'*64))+b'\n')
        with self.assertRaises(FileExistsError): self.invoke_operator()
        self.assertEqual(len(self.calls),3)

    def test_waits_only_for_completed_dev_certificate_and_checks_guard(self):
        self.complete_dev=False;self.invoke_operator()
        self.assertEqual(self.calls,['freeze','development','final']);self.assertEqual(self.waits,[5]);self.assertEqual(self.guards,[1,1])

    def test_partial_missing_nonconsecutive_or_wrong_certificate_never_starts(self):
        # Each independent fixture is malformed before the first action.
        accepted=self.campaign/'train_001/accepted.json';old=accepted.read_bytes();accepted.unlink()
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,[])
        accepted.write_bytes(old);self.output.rmdir()
        stage=self.campaign/'train_001';stage.rename(self.campaign/'train_003')
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,[])
        (self.campaign/'train_003').rename(stage);self.output.rmdir()
        path=self.folder/'train_001.json';record=self.authority.records.pop(('acceptance',path))
        with self.assertRaises(KeyError): self.invoke_operator()
        self.assertEqual(self.calls,[])
        self.authority.records['acceptance',path]=dict(record,stage='train_002');self.output.rmdir()
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,[])

    def test_still_trainable_or_existing_heldout_blocks_all_actions(self):
        self.budget.may_start_generation=lambda *a,**k:True
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,[]);self.output.rmdir()
        self.budget.may_start_generation=lambda *a,**k:False
        self.controller._heldout_absent=lambda campaign:False
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,[])

    def test_each_phase_exception_is_same_object_stops_and_preserves_prior_results(self):
        for failed_index,action in enumerate(('freeze','development','final')):
            if self.output.exists():
                for path in self.output.iterdir(): path.unlink()
                self.output.rmdir()
            self.calls=[];fault=KeyboardInterrupt('Synthetic '+action)
            def fail(cache,phase):
                result=self.phase(cache,phase)
                if phase==action: raise fault
                return result
            with patch.object(operator,'controller',self.controller),patch.object(operator,'budget',self.budget),\
                 patch.object(operator,'run_phase',side_effect=fail),patch.object(operator,'time',self.clock):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    operator.finish(self.campaign,self.authority,self.manifest,self.cache,self.output)
            self.assertIs(caught.exception,fault)
            self.assertEqual(self.calls,list(('freeze','development','final')[:failed_index+1]))
            self.assertEqual(sorted(p.stem for p in self.output.iterdir()),sorted(('freeze','development','final')[:failed_index]))

    def test_guard_failure_and_final_cutoff_never_invoke_final(self):
        self.complete_dev=False;fault=ValueError('Synthetic source guard drift')
        checks=[]
        def guard():
            checks.append(1)
            if len(checks)==2: raise fault
        self.cache._guard=guard
        with self.assertRaises(ValueError) as caught: self.invoke_operator()
        self.assertIs(caught.exception,fault);self.assertEqual(self.calls,['freeze','development'])
        for path in self.output.iterdir(): path.unlink()
        self.output.rmdir();self.calls=[];self.cache._guard=lambda:None;self.current=self.cutoff
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,['freeze','development']);self.assertEqual(self.waits,[])

    def test_advancer_error_blocks_final_even_when_dev_certificate_coexists(self):
        self.error_on_dev=True
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,['freeze','development']);self.assertEqual(self.waits,[])
        self.assertFalse((self.output/'final.json').exists())

    def test_entry_advancer_error_or_source_guard_fault_creates_no_output_or_phase(self):
        path=self.folder/'advance_error.json';path.write_text('{}')
        with self.assertRaises(ValueError): self.invoke_operator()
        self.assertEqual(self.calls,[]);self.assertFalse(self.output.exists())
        path.unlink();fault=ValueError('Synthetic initial source drift')
        self.cache._guard=lambda:(_ for _ in ()).throw(fault)
        with self.assertRaises(ValueError) as caught: self.invoke_operator()
        self.assertIs(caught.exception,fault);self.assertEqual(self.calls,[]);self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
