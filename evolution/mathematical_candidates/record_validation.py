"""Record the actual focused test result without altering any bot source."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    paths = [ROOT/"bot.py", ROOT/"evolution/mathematical_probes.py",
             HERE/"build_arrival.py", HERE/"arrival_lifetime.py",
             HERE/"arrival_lifetime_depth2.py", HERE/"baseline_depth2.py",
             HERE/"test_arrival.py", HERE/"test_mathematics.py", Path(__file__)]
    guards = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        "evolution.mathematical_candidates.test_arrival", "evolution.mathematical_candidates.test_mathematics"])
    output = io.StringIO()
    start = time.perf_counter()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    for relative, expected in guards.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != expected:
            raise ValueError("A focused-validation source changed")
    captured = output.getvalue()
    match = re.search(r"worst ([\d.]+)ms", captured)
    report = dict(format="zone-rush-mathematical-contract-validation/1",
                  python=platform.python_version(), tests=result.testsRun, success=result.wasSuccessful(),
                  failures=len(result.failures), errors=len(result.errors), elapsed_s=time.perf_counter()-start,
                  source_sha256=guards, closed_loop_contract_games=32, focal_callbacks=2560,
                  worst_focal_ms=float(match.group(1)) if match else None,
                  claimed_strength_games=0, production_changed=False,
                  caveat="Contract and counterexample tests only; strength is evaluated separately by the root agent.")
    (HERE/"focused_tests.txt").write_text(captured, encoding="utf8", newline="\n")
    (HERE/"focused_validation.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(report, indent=2))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
