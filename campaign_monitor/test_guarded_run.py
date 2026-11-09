"""Future-controller ownership/index gates; never executes campaign games."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from campaign_monitor import guarded_run as driver
from primary_campaign import core


class GuardedDriverTests(unittest.TestCase):
    def setUp(self):
        parent = core.ROOT/'.cache/campaign_monitor'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='guarded-test-', dir=parent)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(parent.resolve()))

    def tearDown(self):
        self.temp.cleanup()

    def test_two_processes_cannot_hold_lease_and_persistent_file_is_not_ownership(self):
        code = """import sys
from campaign_monitor.guarded_run import CoordinatorLease, CoordinatorBusy
try:
    with CoordinatorLease(sys.argv[1]):
        print('ACQUIRED')
except CoordinatorBusy:
    print('BUSY')
    sys.exit(7)
"""
        command = [sys.executable, '-c', code, str(self.directory)]
        kwargs = dict(cwd=core.ROOT, capture_output=True, text=True, timeout=20,
                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        with driver.CoordinatorLease(self.directory) as lease:
            blocked = subprocess.run(command, **kwargs)
            self.assertEqual(blocked.returncode, 7, blocked.stderr)
            self.assertEqual(blocked.stdout.strip(), 'BUSY')
            lock_path = lease.path
        self.assertTrue(lock_path.exists())
        released = subprocess.run(command, **kwargs)
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertEqual(released.stdout.strip(), 'ACQUIRED')

    def test_live_previous_owner_cannot_be_blessed_by_a_terminal_flag(self):
        path = self.directory/'handoff.json'
        value = dict(format='zone-rush-controller-handoff/1', campaign_directory=str(self.directory),
                     campaign_id='test', observed_terminal=True, observed_exit_code=0,
                     previous_owner_pid=os.getpid())
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(driver.CoordinatorBusy, 'still running'):
            driver.verify_handoff(path, self.directory, 'test')
        with self.assertRaises(ValueError):
            driver.verify_handoff(None, self.directory, 'test')

    def test_exited_process_handoff_is_explicit_and_foreign_campaign_rejected(self):
        process = subprocess.run([sys.executable, '-c', 'import os; print(os.getpid())'],
                                 capture_output=True, text=True, check=True,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=10)
        previous = int(process.stdout.strip())
        self.assertFalse(driver.process_running(previous))
        value = dict(format='zone-rush-controller-handoff/1', campaign_directory=str(self.directory),
                     campaign_id='test', observed_terminal=True, observed_exit_code=0,
                     previous_owner_pid=previous)
        path = self.directory/'handoff.json'
        path.write_text(json.dumps(value))
        result = driver.verify_handoff(path, self.directory, 'test')
        self.assertEqual(result['receipt']['previous_owner_pid'], previous)
        with self.assertRaises(ValueError):
            driver.verify_handoff(path, self.directory, 'foreign')

    def test_source_drift_detected_without_editing_a_frozen_source(self):
        source = self.directory/'reviewed.py'
        source.write_text('reviewed = True\n')
        pins = driver.provenance()
        pins['source_pins'][str(source)] = core.digest(source.read_bytes())
        driver.check_provenance(pins)
        source.write_text('reviewed = False\n')
        with self.assertRaisesRegex(ValueError, 'source drift'):
            driver.check_provenance(pins)

    def test_copied_real_stage_is_rejected_before_original_executor_or_auditor(self):
        original = core.ROOT/'.cache/primary/campaign_v1_20261109'
        if not (original/'train_000/registration.json').exists():
            self.skipTest('Local real campaign evidence unavailable in clean checkout')
        for name in ('manifest.json', 'manifest.sha256', 'catalog.json', 'catalog.sha256'):
            (self.directory/name).write_bytes((original/name).read_bytes())
        fake = self.directory/'train_001'
        fake.mkdir()
        for name in ('registration.json', 'registration.sha256'):
            (fake/name).write_bytes((original/'train_000'/name).read_bytes())
        with mock.patch.object(driver.run, 'execute_generation', side_effect=AssertionError('Executor must not run')) as execute, \
                mock.patch.object(driver.run, 'audit_generation', side_effect=AssertionError('Auditor must not run')) as auditor:
            with self.assertRaisesRegex(ValueError, 'directory index'):
                driver.continue_bounded(self.directory, 1, 2, execute=True)
            execute.assert_not_called()
            auditor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
