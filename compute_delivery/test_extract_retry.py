"""Deterministic source-activation fault controls; no workers or actors run."""
import os
from pathlib import Path
import zipfile
import unittest

from compute_delivery import runner,test_runner as mechanics


class ExtractionRetryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = mechanics.RunnerMechanicsTests('test_worker_count_and_context_are_persistent_across_cpu_changes')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root,self.config,self.bundle,_ = self.fixture.fixture()
        self.staging = self.root/'.extract-retry-unit'
        self.staging.mkdir()
        with zipfile.ZipFile(self.root/'worker_payload.zip') as archive:
            for item in archive.infolist():
                target = self.staging/item.filename
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.read(item.filename))
        self.worker = self.root/'worker'

    @staticmethod
    def error(number):
        value = PermissionError('SYNTHETIC Windows activation failure')
        value.winerror = number
        return value

    def promote(self,rename,sleep,platform_name='nt'):
        return runner._promote_staging(self.root,self.staging,self.worker,self.bundle,self.config,
                        platform_name=platform_name,rename=rename,sleep=sleep)

    def test_injected_first_failure_then_simulated_success_has_exact_bounded_control_flow(self):
        calls,delays = [],[]
        def simulated_native(source,destination):
            calls.append((source,destination))
            if len(calls)==1:
                raise self.error(5)
            # Simulates native acknowledgement only; independent tests below
            # use actual os.rename and verify the resulting complete directory.
        self.promote(simulated_native,delays.append)
        self.assertEqual(len(calls),2)
        self.assertEqual(delays,[runner.WINDOWS_RENAME_DELAYS[0]])
        self.assertTrue(self.staging.is_dir())
        self.assertFalse(self.worker.exists())

    def test_permanent_failure_preserves_every_staged_byte_and_stops_at_exact_limit(self):
        original = {path.relative_to(self.staging):path.read_bytes() for path in self.staging.rglob('*') if path.is_file()}
        calls,delays = [],[]
        def failure(source,destination):
            calls.append(1)
            raise self.error(32)
        with self.assertRaises(OSError):self.promote(failure,delays.append)
        self.assertEqual(len(calls),len(runner.WINDOWS_RENAME_DELAYS)+1)
        self.assertEqual(delays,list(runner.WINDOWS_RENAME_DELAYS))
        self.assertFalse(self.worker.exists())
        self.assertEqual(original,{path.relative_to(self.staging):path.read_bytes() for path in self.staging.rglob('*') if path.is_file()})

    def test_windows_errors_are_not_retried_under_a_non_windows_policy(self):
        calls,delays = [],[]
        def failure(source,destination):
            calls.append(1)
            raise self.error(5)
        with self.assertRaises(OSError):self.promote(failure,delays.append,platform_name='posix')
        self.assertEqual(calls,[1]);self.assertEqual(delays,[])

    def test_destination_present_initially_never_reaches_native_rename(self):
        self.worker.mkdir()
        sentinel = self.worker/'sentinel.txt';sentinel.write_bytes(b'UNRELATED EXISTING DESTINATION')
        def forbidden(*args):raise AssertionError('Existing directory must not reach rename')
        with self.assertRaises(ValueError):self.promote(forbidden,forbidden)
        self.assertEqual(sentinel.read_bytes(),b'UNRELATED EXISTING DESTINATION')
        self.assertTrue(self.staging.exists())

    def test_destination_appearing_inside_failed_native_call_is_preserved_without_retry(self):
        calls,delays = [],[]
        def race(source,destination):
            calls.append(1)
            self.worker.mkdir()
            (self.worker/'sentinel.txt').write_bytes(b'RACING DESTINATION')
            raise self.error(5)
        with self.assertRaises(ValueError):self.promote(race,delays.append)
        self.assertEqual(calls,[1]);self.assertEqual(delays,[])
        self.assertEqual((self.worker/'sentinel.txt').read_bytes(),b'RACING DESTINATION')
        self.assertTrue(self.staging.is_dir())

    def test_auxiliary_bytes_are_rechecked_before_retry(self):
        calls = []
        def blocked(source,destination):
            calls.append(1);raise self.error(33)
        def tamper(delay):
            (self.staging/'RUN_INSTRUCTIONS.txt').write_bytes(b'UNREGISTERED INSTRUCTION REPLACEMENT')
        with self.assertRaises(ValueError):self.promote(blocked,tamper)
        self.assertEqual(calls,[1]);self.assertFalse(self.worker.exists())
        self.assertTrue(self.staging.is_dir())

    def test_staging_path_outside_its_delivery_is_rejected_before_rename(self):
        outside = self.fixture.base/'.extract-outside-delivery';outside.mkdir()
        def forbidden(*args):raise AssertionError('Outside stage must not reach rename')
        with self.assertRaises(ValueError):
            runner._promote_staging(self.root,outside,self.worker,self.bundle,self.config,
                                   platform_name='nt',rename=forbidden,sleep=forbidden)
        self.assertFalse(self.worker.exists())

    def test_destination_hardlink_cannot_modify_an_unrelated_sentinel(self):
        sentinel = self.fixture.base/'sentinel.txt';sentinel.write_bytes(b'UNCHANGED SENTINEL')
        try:os.link(sentinel,self.worker)
        except OSError:self.skipTest('Native hard-link control requires normal local filesystem permissions')
        def forbidden(*args):raise AssertionError('Linked destination must not reach rename')
        with self.assertRaises(ValueError):self.promote(forbidden,forbidden)
        self.assertEqual(sentinel.read_bytes(),b'UNCHANGED SENTINEL')
        self.assertTrue(self.staging.exists())

    def test_source_hardlink_appearing_during_retry_is_rejected(self):
        reference = self.fixture.base/'reference.py'
        source = self.staging/'distributed_campaign/worker.py'
        reference.write_bytes(source.read_bytes())
        probe = self.fixture.base/'hardlink-probe'
        try:os.link(reference,probe)
        except OSError:self.skipTest('Native hard-link control requires normal local filesystem permissions')
        probe.unlink()
        calls=[]
        def blocked(origin,destination):
            calls.append(1);raise self.error(5)
        def link(delay):
            source.unlink();os.link(reference,source)
        with self.assertRaises(ValueError):self.promote(blocked,link)
        self.assertEqual(calls,[1]);self.assertFalse(self.worker.exists())
        self.assertTrue(self.staging.exists())


if __name__=='__main__':unittest.main()
