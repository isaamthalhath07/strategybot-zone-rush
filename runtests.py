"""
Run every check, in order of how badly a failure would hurt.

There is no competition simulator and no trial run: whatever sits in the
repository at the deadline is played once by a server I cannot inspect. So these
are grouped by consequence, not by subject.

  correctness   the engine matches the rulebook, and the bot's reconstruction of
                the hidden state matches the engine. Everything else is measured
                through these, so if they are wrong, every other number is too.
  survival      the bot cannot crash, time out, return an illegal action, leak
                state between games, or degrade into 80 turns of STAY.
  strength      it still beats the field, and is not overfitted to it.

    python runtests.py           every suite
    python runtests.py fast      skip the two slow tournament suites
"""
import subprocess
import sys
import time

FAST = len(sys.argv) > 1 and sys.argv[1] == "fast"

SUITES = [
    ("correctness", "test_engine.py", [], False,
     "the engine against every worked example in the rulebook"),
    ("correctness", "test_gpuenv.py", ["cpu", "24"], False,
     "the batched tensor engine against the reference engine, all 5 rulesets"),
    ("correctness", "test_tracker.py", [], False,
     "hidden-state reconstruction against the engine's private state"),
    ("correctness", "test_planner.py", [], False,
     "completion income, legal defence, route progress and observed homes"),
    ("correctness", "test_merge_safeguards.py", [], False,
     "failed-home escape, arbitrary starting corners and reused-module resets"),
    ("correctness", "test_freshlab.py", [], False,
     "public opponent inference, fresh split isolation and final-turn payoffs"),
    ("correctness", "test_territorylab.py", [], False,
     "opening signals, spatial demand symmetry, public information and controls"),
    ("correctness", "test_determinism.py", ["60"], False,
     "the measurement harness itself: paired games must be reproducible"),
    ("survival", "test_guards.py", [], False,
     "progress-rule detection, the fallback policy, state reuse, odd inputs"),
    ("survival", "test_timing.py", [], False,
     "graceful degradation on hardware up to 100x slower"),
    ("survival", "test_robust.py", [], True,
     "ambiguous-rule flips, malformed state, seat symmetry, mirror matches"),
    ("survival", "test_amnesia.py", [], False,
     "what losing module state between turns would cost"),
    ("survival", "audit/test_input_contract.py", [], False,
     "the shipped public entry point: input immutability and legal output"),
    ("correctness", "test_visual_harness.py", [], False,
     "visual evidence replays exactly and matches submission source hashes"),
    ("strength", "audit.py", ["20"], False,
     "behavioural pathologies: pacing, shield-happiness, idle turns"),
    ("strength", "diag_seat.py", ["120", "mybot"], False,
     "seat bias in self-play, where symmetry fixes the answer at 1.50"),
    ("strength", "test_transfer.py", ["v7_params.json"], True,
     "held-out opponents never used in tuning"),
]

rows = []
t0 = time.time()
group = None
for grp, script, args, slow, what in SUITES:
    if FAST and slow:
        rows.append((grp, script, "skipped", 0.0))
        continue
    if group != grp:
        group = grp
        print("\n%s %s" % (grp.upper(), "-" * (68 - len(grp))))
    print("  %-20s %s" % (script, what))
    t1 = time.time()
    p = subprocess.run([sys.executable, "-u", script] + args,
                       capture_output=True, text=True)
    dt = time.time() - t1
    out = (p.stdout or "") + (p.stderr or "")
    tail = [ln for ln in out.strip().splitlines() if ln.strip()]
    verdict = "PASS" if p.returncode == 0 else "FAIL"
    # these two report findings rather than exiting non-zero
    # audit.py also profiles the opponents, two of which (ai_route pacing,
    # ai_marginal often frozen) are flagged on every run by design; only a flag
    # on the bot itself is worth a human look
    if script == "audit.py" and any(ln.startswith("flagged:") and "mybot" in ln
                                    for ln in out.splitlines()):
        verdict = "CHECK"
    if script == "diag_seat.py" and "SEAT BIAS" in out:
        verdict = "FAIL"
    rows.append((grp, script, verdict, dt))
    for ln in tail[-3:]:
        print("      | %s" % ln[:96])
    print("      -> %s  (%.0fs)" % (verdict, dt))

print("\n" + "=" * 72)
print("%-14s %-20s %8s %8s" % ("group", "suite", "result", "seconds"))
print("-" * 72)
for grp, script, verdict, dt in rows:
    print("%-14s %-20s %8s %8.0f" % (grp, script, verdict, dt))
bad = [r for r in rows if r[2] == "FAIL"]
print("-" * 72)
print("total %.0fs" % (time.time() - t0))
if bad:
    print("\n%d SUITE(S) FAILED: %s" % (len(bad), ", ".join(r[1] for r in bad)))
    sys.exit(1)
print("\nALL SUITES PASS")
