"""Preserve the original cohort while replacing unused helper allocation.

No actor, game, CUDA kernel, outcome analysis or primary admission runs here.
The user explicitly cancelled sharing. The same canonical study binding keeps
the old helper controller from issuing a second set of original fixtures.
"""
from pathlib import Path
import hashlib

from confirmation_campaign import architectures
from distributed_campaign import auth, protocol as transport, qualification
from primary_campaign import core

ROOT = Path(__file__).resolve().parents[1]
REGISTRATION_SHA256 = 'b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9'
FORMAT = 'zone-rush-owner-local-cuda-study/1'
REGISTRATION_PATH = ROOT / '.cache/confirmation/architectures_v2_001/registration.json'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def admitted_study(registration_path, registry_path):
    path = Path(registration_path).resolve()
    if path != REGISTRATION_PATH.resolve():
        raise ValueError('Copied registrations cannot create another canonical study binding')
    if sha(path.read_bytes()) != REGISTRATION_SHA256:
        raise ValueError('Only the exact preregistered four-arm study is authorized')
    registration = core.read_sealed(path)
    architectures.validate(registration)
    registry = auth.load_registry(registry_path)
    witness, gold = qualification.read_control_gold(path, registry)
    if len(gold) != 8 or set(gold) != set(registration['runtime_qualification_task_ids']):
        raise ValueError('Exactly eight canonical original reference rows required')
    if registration['planned_games'] != 32768:
        raise ValueError('Frozen study coverage changed')
    return registration, registry, witness, gold


def fixture_partition(registration, gold):
    identities = [fixture['id'] for fixture in registration['fixtures']]
    if len(identities) != 32768 or len(set(identities)) != len(identities):
        raise ValueError('Duplicate or incomplete frozen fixture schedule')
    if len(gold) != 8 or set(gold) != set(registration['runtime_qualification_task_ids']):
        raise ValueError('Canonical gold coverage changed')
    pending = [identity for identity in identities if identity not in gold]
    if len(pending) != 32760 or set(pending) & set(gold):
        raise ValueError('New CUDA originals overlap consumed reference originals')
    return pending


def binding_payload(registration_path, registry_path, output):
    if Path(registration_path).resolve() != REGISTRATION_PATH.resolve():
        raise ValueError('Only the original canonical study registration path is allowed')
    output = Path(output).resolve()
    allowed = (ROOT / '.cache/local_cuda').resolve()
    if not output.is_relative_to(allowed) or output == allowed:
        raise ValueError('Local study output must have its own ignored local-CUDA directory')
    return dict(
        format=FORMAT, source_registration_path=str(Path(registration_path).resolve()),
        source_registration_sha256=REGISTRATION_SHA256,
        canonical_output=str(output), registry_path=str(Path(registry_path).resolve()),
        role='extra_control_assignment', execution_mode='owner_local_cuda_physics_exact_cpu_python_actors',
        helpers=[], user_cancelled_shared_compute=True,
        rule='One canonical original cohort; import8 consumed originals once and execute32760 remaining originals locally.',
        primary_games_accepted=0, bmcts_audits=0, promotion_allowed=False)


def reserve(registration_path, registry_path, output):
    """Reserve the SAME binding/OS lease as the retired helper coordinator.

    A valid local binding intentionally differs from the old helper payload, so
    the unchanged helper coordinator refuses to issue original jobs afterward.
    Never replace an existing different binding, even with a valid owner key.
    """
    registration_path = Path(registration_path).resolve()
    registration, registry, witness, gold = admitted_study(registration_path, registry_path)
    pending = fixture_partition(registration, gold)
    expected = binding_payload(registration_path, registry_path, output)
    canonical = registration_path.parent / 'distributed_control_v2'
    with transport.ResultLease(canonical):
        binding = canonical / 'binding.json'
        if binding.exists():
            existing = auth.verify_owner(registry, 'distributed-control-study-binding/v2', core.read_sealed(binding))
            if existing != expected:
                raise ValueError('Study already reserved elsewhere; preserve the original binding and reconcile it')
        else:
            core.seal(binding, auth.sign_owner(registry, 'distributed-control-study-binding/v2', expected))
    return dict(binding=expected, pending_fixture_ids=pending,
                canonical_gold_originals=8, new_local_cuda_originals=32760,
                fixture_id_list_sha256=sha(core.canonical(pending)),
                gold_witness_sha256=sha((registration_path.parent/'runtime_gold_v2/gold_witness.json').read_bytes()),
                primary_games_accepted=0, bmcts_audits=0, promotion_allowed=False)
