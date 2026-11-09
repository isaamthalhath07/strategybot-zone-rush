"""Version1 bounded wrapper for a FUTURE exclusive-owner handoff.

Default execution is read-only planning. Existing source and old stage evidence
are never edited. The operator must observe the old owner terminate; the wrapper
also refuses a handoff naming a still-running OS process.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import sys
import time
import uuid

from campaign_monitor import audit
from evolution.genomes import digest
from primary_campaign import core, run

ROOT = core.ROOT
FROZEN = {
    'bot.py': 'e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5',
    'evolution/runner.py': 'bae5c92c51efa83eaef90db0ede9940be72201d2bb78e9d0527e3f6139d7503b',
    'primary_campaign/core.py': '6d0de2dae757a4db821bddbb6bad1978bd6f6ac4d612ac60946b2ff01412d6fa',
    'primary_campaign/run.py': 'bcaeeba986b4cdfd663be0a34bd507a93ee45db3f24ee4c80c8b60a4b1b7e98b',
}
INTERPRETER_SHA256 = '4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a'


class CoordinatorBusy(ValueError):
    pass


def canonical_campaign(path):
    return os.path.normcase(str(Path(path).resolve()))


class CoordinatorLease:
    """OS-held lock; the persistent file/PID itself never grants ownership."""
    def __init__(self, campaign):
        identity = digest(canonical_campaign(campaign).encode('utf8'))
        self.path = ROOT/'.cache/campaign_monitor/locks'/(identity+'.lock')
        self.descriptor = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b'\0')
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as error:
            os.close(descriptor)
            raise CoordinatorBusy('Another coordinator holds the OS campaign lease') from error
        self.descriptor = descriptor
        return self

    def __exit__(self, *args):
        if self.descriptor is not None:
            os.close(self.descriptor)  # OS releases ownership, including on process death.
            self.descriptor = None
        # Never unlink: deleting a lock file permits a second inode/owner race.


def process_running(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError('A valid previous-owner OS PID is required')
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError as error:
            raise ValueError('Cannot establish previous-owner process state') from error
        return True
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only.
    if not handle:
        if ctypes.get_last_error() == 87:  # Invalid PID: no such process.
            return False
        raise ValueError('Cannot establish previous-owner process state')
    try:
        result = kernel.WaitForSingleObject(handle, 0)
        if result == 0:
            return False
        if result == 258:
            return True
        raise ValueError('Previous-owner process state could not be read')
    finally:
        kernel.CloseHandle(handle)


def provenance():
    pins = {str((ROOT/path).resolve()): expected for path, expected in FROZEN.items()}
    for path in (Path(__file__), ROOT/'campaign_monitor/audit.py'):
        pins[str(path.resolve())] = digest(path.read_bytes())
    actual_exe = digest(Path(sys.executable).read_bytes())
    if (platform.python_implementation() != 'CPython' or platform.python_version() != '3.12.10'
            or actual_exe != INTERPRETER_SHA256):
        raise ValueError('Guarded driver v1 requires its reviewed CPython runtime; review a new version before migration')
    value = dict(source_pins=pins, interpreter=dict(implementation=platform.python_implementation(),
                 version=platform.python_version(), full_version=sys.version,
                 executable=str(Path(sys.executable).resolve()), executable_sha256=actual_exe))
    check_provenance(value)
    return value


def check_provenance(value):
    for path, expected in value['source_pins'].items():
        if digest(Path(path).read_bytes()) != expected:
            raise ValueError('Guarded continuation source drift')
    if (digest(Path(sys.executable).read_bytes()) != value['interpreter']['executable_sha256']
            or sys.version != value['interpreter']['full_version']):
        raise ValueError('Guarded continuation interpreter drift')


def requested_registration(campaign, index, allow_missing=False):
    manifest, catalog = core.load_catalog(campaign)
    if type(index) is not int or not 0 <= index < manifest['training_generations']:
        raise ValueError('Requested index exceeds scheduled training')
    path = Path(campaign)/('train_%03d' % index)/'registration.json'
    if not path.exists():
        if allow_missing:
            return None
        raise ValueError('Requested stage has no sealed registration')
    registration = core.read_sealed(path)
    audit.metadata_identity(registration, index, manifest, 'requested registration')
    core.validate_registration(registration, manifest, catalog)
    size = manifest['shape']['maps_per_generation']
    expected = {board['id'] for board in catalog if board['phase'] == 'train'
                and index*size <= board['phase_index'] < (index+1)*size}
    if {fixture['map_id'] for fixture in registration['fixtures']} != expected:
        raise ValueError('Requested stage differs from its exact catalog slice')
    return registration


def verify_handoff(path, campaign, campaign_id):
    if path is None:
        raise ValueError('Execution requires an explicit terminal-owner handoff receipt')
    body = Path(path).read_bytes()
    value = core.oversight.strict_loads(body)
    if (value.get('format') != 'zone-rush-controller-handoff/1'
            or canonical_campaign(value.get('campaign_directory', '')) != canonical_campaign(campaign)
            or value.get('campaign_id') != campaign_id or value.get('observed_terminal') is not True
            or type(value.get('observed_exit_code')) is not int):
        raise ValueError('Malformed or foreign owner handoff receipt')
    if process_running(value.get('previous_owner_pid')):
        raise CoordinatorBusy('Previous campaign owner is still running; no takeover is allowed')
    return dict(path=str(Path(path).resolve()), sha256=digest(body), receipt=value)


def boundary(report, start, stop):
    admitted = {stage['generation'] for stage in report['stages'] if stage.get('accepted_primary_games', 0) > 0}
    if not set(range(start)) <= admitted:
        raise ValueError('All stages before the requested start must already be independently admitted')
    for stage in report['stages']:
        index = stage['generation']
        if stage['status'] != 'preparation_incomplete' and index >= stop and not stage.get('accepted_primary_games'):
            raise ValueError('An unadmitted prepared stage lies outside the requested bounded range')


def continue_bounded(campaign, start, stop, workers=6, execute=False, handoff=None):
    campaign = Path(campaign).resolve()
    pins = provenance()
    manifest, _ = core.load_catalog(campaign)
    if (type(start) is not int or type(stop) is not int or not 0 <= start < stop <= manifest['training_generations']
            or type(workers) is not int or not 1 <= workers <= 24 or manifest['profile'] != 'full_primary'):
        raise ValueError('Explicit full-profile bounded range and valid worker count required')
    # Index/copy corruption must fail BEFORE any original executor/auditor call.
    preflight = audit.inspect(campaign)
    boundary(preflight, start, stop)
    requested_registration(campaign, start, allow_missing=True)
    plan = dict(format='zone-rush-guarded-training-driver/1', campaign_directory=str(campaign),
                campaign_id=manifest['campaign_id'], start_index=start, stop_before=stop, workers=workers,
                execute=execute, provenance=pins, existing_snapshot=preflight,
                promoted=False, heldout_execution=False)
    if not execute:
        return dict(plan, status='read_only_plan', campaign_files_modified=False)
    handoff_record = verify_handoff(handoff, campaign, manifest['campaign_id'])
    with CoordinatorLease(campaign):
        check_provenance(pins)
        locked_snapshot = audit.inspect(campaign)
        boundary(locked_snapshot, start, stop)
        # Close the check/lock interval against the explicitly named old owner.
        verify_handoff(handoff, campaign, manifest['campaign_id'])
        ledger = ROOT/'.cache/campaign_monitor/controllers'/uuid.uuid4().hex
        core.seal(ledger/'registration.json', dict(plan, handoff=handoff_record))
        admitted = []
        try:
            for index in range(start, stop):
                check_provenance(pins)
                requested_registration(campaign, index, allow_missing=True)
                core.prepare_generation(campaign, index)  # Original frozen preparation/gates.
                requested_registration(campaign, index)
                check_provenance(pins)
                run.execute_generation(campaign, index, workers)
                requested_registration(campaign, index)
                summary = core.read_sealed(campaign/('train_%03d' % index)/'summary.json')
                audit.metadata_identity(summary, index, manifest, 'requested summary')
                run.audit_generation(campaign, index, workers)
                check_provenance(pins)
                after = audit.inspect(campaign)
                exact = next(stage for stage in after['stages'] if stage['generation'] == index)
                if exact.get('accepted_primary_games') != manifest['shape']['maps_per_generation']*200:
                    raise ValueError('Requested stage lacks its exact independent admission')
                admitted.append(index)
                core.seal(ledger/('stage_%03d.json' % index), dict(generation=index, snapshot=after,
                          source_pins=pins, controller_primary_credit=0, promoted=False))
            result = dict(plan, status='bounded_range_complete', stages_verified=admitted,
                          handoff=handoff_record, controller_ledger=str(ledger), controller_primary_credit=0)
            core.seal(ledger/'result.json', result)
            return result
        except BaseException as error:
            core.seal(ledger/'failure.json', dict(error_type=type(error).__name__, reason=str(error),
                      stages_verified=admitted, promoted=False, controller_primary_credit=0))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--start-index', type=int, required=True)
    parser.add_argument('--stop-before', type=int, required=True)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--handoff', type=Path)
    args = parser.parse_args()
    result = continue_bounded(args.directory, args.start_index, args.stop_before, args.workers, args.execute, args.handoff)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
