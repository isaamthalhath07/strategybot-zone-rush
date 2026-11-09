"""Author checks; no completed policy/worker games or research outcomes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

from deadline_release import packager as p


BOT = b"# exact selected source\r\ndef act(state):\r\n    return 'STAY'\r\n"
TESTER = b"def act(state):\n    return state.legal_actions[0]\n"


class PackagerTests(unittest.TestCase):
    def setUp(self):
        temporary=p.HERE/'.t'; temporary.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='p',dir=temporary)
        self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        self.bot=self.root/'chosen.py'; self.bot.write_bytes(BOT)
        self.tester=self.root/'control.py'; self.tester.write_bytes(TESTER)
        self.entries=[dict(path=str(self.tester),sha256=p.sha(TESTER),label='Known reference')]

    def build(self,**kwargs):
        return p.build_release(self.bot,p.sha(BOT),self.entries,self.root/'release',validate=False,**kwargs)

    def test_exact_sources_runtime_provenance_and_only_sealed_zip_payload(self):
        manifest=self.build(); output=self.root/'release'
        self.assertEqual((output/'bot.py').read_bytes(),BOT)
        self.assertEqual((output/'tester_bots/control.py').read_bytes(),TESTER)
        self.assertEqual(manifest['selection_status'],'reference_only')
        self.assertEqual(manifest['validation'],dict(status='not_run',ordinary_worker_games=0,primary_games=0))
        for name in p.RUNTIME: self.assertEqual((output/name).read_bytes(),(p.ROOT/name).read_bytes())
        (output/'simulator/history').mkdir(); (output/'simulator/history/private_local_play.jsonl').write_text('local')
        archive=self.root/'release.zip'; receipt=p.make_zip(output,archive)
        with zipfile.ZipFile(archive) as stream:
            self.assertEqual(stream.read('bot.py'),BOT)
            self.assertNotIn('simulator/history/private_local_play.jsonl',stream.namelist())
            self.assertFalse(any('.git/' in n or '__pycache__' in n for n in stream.namelist()))
        self.assertEqual(receipt['sha256'],p.sha(archive.read_bytes()))
        with self.assertRaises(FileExistsError): self.build()
        with self.assertRaises(FileExistsError): p.make_zip(output,archive)

    def test_hash_external_dependency_duplicates_and_path_guards_precede_output(self):
        for body in (b'import numpy\ndef act(s): return "STAY"\n',b'from . import x\ndef act(s): return "STAY"\n',b'async def act(s): return "STAY"\n'):
            self.bot.write_bytes(body)
            with self.assertRaises(ValueError): p.build_release(self.bot,p.sha(body),[],self.root/'release',validate=False)
        self.bot.write_bytes(BOT)
        with self.assertRaises(ValueError): p.build_release(self.bot,'0'*64,[],self.root/'release',validate=False)
        for entries in ([self.entries[0],self.entries[0]],
                [dict(path=self.bot,sha256=p.sha(BOT),label='duplicate')],
                [dict(self.entries[0],filename='../escape.py')],
                [dict(self.entries[0],credentials='private')]):
            with self.assertRaises(ValueError): p.build_release(self.bot,p.sha(BOT),entries,self.root/'release',validate=False)
        self.assertFalse((self.root/'release').exists())

    def test_final_decision_requires_same_source_validation_and_explicit_public_evidence(self):
        final=dict(status='final_selection',selected_source_sha256=p.sha(BOT))
        with self.assertRaises(ValueError): self.build(decision_manifest=final)
        with self.assertRaises(ValueError): self.build(decision_manifest=dict(final,selected_source_sha256='0'*64))
        evidence=self.root/'public.json'; evidence.write_text(json.dumps({'owner_key':'never_ship'}))
        with self.assertRaises(ValueError): self.build(evidence_entries=[dict(path=evidence,sha256=p.sha(evidence.read_bytes()))])
        self.assertFalse((self.root/'release').exists())
        evidence.write_text(json.dumps({'scope':'reference packaging only','games':0}))
        m=self.build(evidence_entries=[dict(path=evidence,sha256=p.sha(evidence.read_bytes()),label='Public declaration')])
        self.assertEqual(m['public_evidence'][0]['sha256'],p.sha(evidence.read_bytes()))
        self.assertNotIn(str(self.root),json.dumps(m))

    def test_readonly_verifier_rejects_payload_corruption_and_rehashed_catalog_disagreement(self):
        self.build(); output=self.root/'release'; before=(output/'package_manifest.json').read_bytes()
        p.verify_release(output); self.assertEqual((output/'package_manifest.json').read_bytes(),before)
        (output/'bot.py').write_bytes(BOT+b'# corruption')
        with self.assertRaisesRegex(ValueError,'fingerprint'): p.verify_release(output)
        (output/'bot.py').write_bytes(BOT)
        release=json.loads((output/'release_manifest.json').read_bytes()); release['bot_sha256']='0'*64
        (output/'release_manifest.json').write_bytes(p.encoded(release))
        manifest=json.loads(before); manifest['files']['release_manifest.json']=p.sha(p.encoded(release)); p._seal(output,manifest)
        with self.assertRaisesRegex(ValueError,'disagreement'): p.verify_release(output)

    def test_interruption_preserves_failure_and_reraises_same_object(self):
        fault=KeyboardInterrupt('synthetic interruption')
        with mock.patch.object(p.subprocess,'run',side_effect=fault):
            with self.assertRaises(KeyboardInterrupt) as caught:
                p.build_release(self.bot,p.sha(BOT),[],self.root/'release',validate=True)
        self.assertIs(caught.exception,fault)
        error=json.loads((self.root/'release/packaging_error.json').read_bytes())
        self.assertEqual(error['exception_type'],'KeyboardInterrupt'); self.assertEqual(error['primary_games'],0)
        with self.assertRaisesRegex(ValueError,'preserved build failure'): p.verify_release(self.root/'release')

    def test_end_guard_detects_changed_selected_input_without_changing_packaged_body(self):
        original=p.source_pins
        def drift():
            result=original(); self.bot.write_bytes(BOT+b'# late input change'); return result
        with mock.patch.object(p,'source_pins',side_effect=drift):
            with self.assertRaisesRegex(ValueError,'Input changed'):
                self.build()
        self.assertEqual((self.root/'release/bot.py').read_bytes(),BOT)
        self.assertTrue((self.root/'release/packaging_error.json').exists())

    def test_reference_e8_portable_validation_runs_isolated_without_site_packages(self):
        # One opening per source only. This neither plays a policy game nor
        # declares the reference the final selection.
        selected=p.ROOT/'bot.py'; expected='e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5'
        self.assertEqual(p.sha(selected.read_bytes()),expected)
        try:
            manifest=p.build_release(selected,expected,self.entries,self.root/'release',validate=True,
                selection_note='Reference e8 portability check, not the final selection.')
        except ValueError:
            self.fail((self.root/'release/validation/build_validation.log').read_text(encoding='utf8'))
        self.assertEqual(manifest['validation']['status'],'passed')
        report=json.loads((self.root/'release/validation/build_validation.json').read_bytes())
        self.assertGreaterEqual(report['tests'],40); self.assertEqual(report['ordinary_worker_games'],0)
        self.assertEqual((self.root/'release/bot.py').read_bytes(),selected.read_bytes())

    def test_archived_single_reference_smoke_is_verified_without_callbacks_or_subprocesses(self):
        archive=p.HERE/'evidence/reference_e8.zip'
        self.assertEqual(p.sha(archive.read_bytes()),'adb3119397cf6cf2098bd65666cc8ced6188ff8f73f33211da02ba4f8126b6b1')
        output=self.root/'recorded'; output.mkdir()
        with zipfile.ZipFile(archive) as stream:
            for name in stream.namelist():
                p.relative(name); path=output/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(stream.read(name))
        with mock.patch.object(p.subprocess,'run',side_effect=AssertionError('Offline verification must not execute a game')):
            manifest=p.verify_release(output)
        self.assertEqual(manifest['smoke']['ordinary_worker_games'],1)
        self.assertEqual(manifest['smoke']['primary_games'],0)
        original=(output/'validation/smoke_result.json').read_bytes()
        for key,value in (('actual_ai_callbacks',239),('fresh_replay_callbacks',239),('turns',79),('faults',1),('supported_memory_oracle_checks',240.0)):
            report=json.loads(original); report['games'][0][key]=value
            body=p.encoded(report); (output/'validation/smoke_result.json').write_bytes(body)
            modified=json.loads(p.encoded(manifest)); modified['files']['validation/smoke_result.json']=p.sha(body); p._seal(output,modified)
            with self.assertRaises(ValueError): p.verify_release(output)
        (output/'validation/smoke_result.json').write_bytes(original); p._seal(output,manifest)
        report=json.loads(original); report['package_manifest_sha256']='0'*64
        body=p.encoded(report); (output/'validation/smoke_result.json').write_bytes(body)
        modified=json.loads(p.encoded(manifest)); modified['files']['validation/smoke_result.json']=p.sha(body); p._seal(output,modified)
        with self.assertRaisesRegex(ValueError,'source, completion'): p.verify_release(output)


if __name__=='__main__': unittest.main()
