"""Run stdlib-only portable checks; real worker games require explicit smoke."""
import argparse
from contextlib import redirect_stdout,redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SAFE_TESTS=('tests.test_portable_release','tests.test_rules','tests.test_simulator_catalog',
    'tests.test_simulator_server.ProtocolTests','tests.test_simulator_history',
    'tests.test_simulator_guards','tests.test_simulator_views')


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',default='validation/check_latest.json')
    args=parser.parse_args(); sys.path.insert(0,str(ROOT))
    if sys.version_info[:2]!=(3,12): raise SystemExit('Use Python3.12 for this validated release.')
    destination=(ROOT/args.output).resolve()
    if not destination.is_relative_to(ROOT/'validation'): raise ValueError('Check output must stay in validation/')
    destination.parent.mkdir(parents=True,exist_ok=True)
    text=io.StringIO(); began=time.perf_counter()
    with redirect_stdout(text),redirect_stderr(text):
        suite=unittest.defaultTestLoader.loadTestsFromNames(SAFE_TESTS)
        result=unittest.TextTestRunner(stream=text,verbosity=1).run(suite)
    report=dict(format='portable-release-contract-validation/1',passed=result.wasSuccessful(),tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),wall_seconds=time.perf_counter()-began,
        python=sys.version,ordinary_worker_games=0,primary_games=0,scope='Rules, catalog, history, UI protocol and one opening contract per source; no strength evidence.',log=text.getvalue())
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(text.getvalue(),end=''); print('Saved validation:',destination.relative_to(ROOT))
    return 0 if report['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
