# Reserved development and final evaluation

This package implements the two reserved evaluation phases without changing the
running primary/evolution code. **No live development or final games were run
during implementation.** Targeted tests are not campaign completion evidence.

Development can start only after every scheduled training audit passes. The
shortlist is fixed in advance: exactly the eight policies registered in the final
scheduled training generation, in that order, including the incumbent. There is
no manual SHA selection or ranking of incomparable training generations.

The full development phase uses 1,000 catalog maps × 200 games, split into ten
100-map blocks. Each shortlisted policy plays 25,000 games. After all ten blocks
are independently accepted, the program selects one policy using the predeclared
64-cell pairwise metric, then mean score, then source hash. Arithmetic for the
ranking is exact rational; displayed floats do not decide ties.

The selected policy is frozen before any final game. It plays all 200,000 final
games, in ten blocks, without further policy changes or automatic deployment.
All actors must be freshly regenerated in two referees before a block is accepted.
Mechanics profiles always credit zero primary games.

## Owner commands

Run from the repository root. Replace the campaign path only with its original
immutable local campaign directory. Each execute/audit command is bounded to one
block. Do not invoke admission on an unfinished training campaign expecting it
to use the latest completed generation—it intentionally refuses.

```powershell
python -m campaign_holdout.run admit-development --campaign .cache/primary/campaign_v1_20261109
python -m campaign_holdout.run prepare --campaign .cache/primary/campaign_v1_20261109 --phase development --block 0
python -m campaign_holdout.run execute --campaign .cache/primary/campaign_v1_20261109 --phase development --block 0 --workers 6
python -m campaign_holdout.run audit --campaign .cache/primary/campaign_v1_20261109 --phase development --block 0 --workers 6
```

Repeat execute/audit for blocks 1–9. The previous block must be accepted first.
Then:

```powershell
python -m campaign_holdout.run admit-final --campaign .cache/primary/campaign_v1_20261109
python -m campaign_holdout.run prepare --campaign .cache/primary/campaign_v1_20261109 --phase final --block 0
```

Execute and audit final blocks the same way. Accepted counts come only from the
authenticated completed-block audit, never from a registration, partial log,
summary, sample replay, mock fixture or numerical rollout.

## Local authority and recovery

Admission deeply verifies every scheduled training stage once. It then creates a
fresh owner-only 32-byte HMAC key under the campaign's ignored local cache. This
key authenticates raw artifact bindings, the immutable shortlist, exact source
versions and later audit checkpoints. Every resume verifies signatures and
re-hashes bound raw files, rather than trusting lengths or modification times.

The authority is the trusted local evaluator, not independent third-party
attestation. Never bundle, log, copy to workers or commit `.authority/`, any key,
or the owner's cache. Worker processes receive no key; fresh actor checks run in
spawned processes and only the owner signs returned proofs.

Missing/replaced keys or invalid gate signatures stop execution. Explicit
`admit-development --recover-gate` repeats deep training validation and reproduces
the same frozen shortlist before writing a new key/gate. It preserves prior gate
artifacts. Audit proofs whose keys are lost require fresh regeneration under the
new authority; old flags are not silently blessed. Final admission similarly
requires all development evidence and the same immutable selection. Code or
policy changes after evaluation begins require a separately reviewed protocol,
not casual cache recovery.

Authority paths reject symlinks, Windows junctions and other reparse points before
key creation or ACL modification. Windows keys use a protected DACL with only the
current owner's full-control ACE; POSIX keys require owner identity and private
permissions. The empty file is restricted before random key bytes are written.

An OS-held stage lock prevents two evaluators from owning a block simultaneously.
The kernel releases the lock after a crash, so the persistent lock file does not
require an unsafe manual deletion. Incomplete append tails are preserved before
retry; complete corruption is rejected. Existing accepted evidence is never
rewritten on normal completed resume.

## Validation scope

The targeted suites cover missing/forged/copied training approvals, raw tampering
despite unchanged size/mtime, rehashed/unsigned approvals, missing/replaced keys,
explicit recovery, policy/phase/opponent substitutions, early final execution,
selection freeze, completed resume, exact metric ordering, full-size assignment
counts, actual public-input game/replay contracts, real Windows private-key ACLs,
junction rejection and OS-lock crash recovery.

```powershell
python -m unittest campaign_holdout.test_holdout campaign_holdout.test_gate_security campaign_holdout.test_schedule -v
```

Some positive admission/selection tests explicitly mock expensive training or
development acceptance and use disposable mechanics fixtures. They certify
control flow, never that those mock games occurred. The 400,000 scheduled-phase
assignment check constructs schedules only and mocks rival creation to isolate
the counting mathematics. No 800-game heldout integration or live full-phase
evaluation has been performed yet; independent code review remains required
before such execution. See [the design](DESIGN.md) for the trust and counting
boundaries.
