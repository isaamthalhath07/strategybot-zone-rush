"""Offline public-prefix Monte Carlo worker with verified CPU/CUDA execution.

This samples common open-loop plans, not full BMCTS. Synthetic trajectories
never count as primary campaign games. No deployed policy is modified.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import random
import time

import torch

from tests import reference_engine as ref
from training_gpu.batch_game import BatchGame
from .belief import PublicBelief, PublicObservation


ROOT = Path(__file__).resolve().parents[1]
M = 2147483647
NORTH, EAST, SOUTH, WEST, STAY, SHIELD = range(6)
FIELDS = ("base", "owner", "upg", "home", "pos", "frozen", "cd", "prog", "score", "income", "token")


def _pairwise_numerator(projected_scores, focal):
    """Official Round 1 pairwise points times two: win=2,tie=1,loss=0.

    The self-comparison contributes a tie and is subtracted. Terminal inputs
    are final scores; nonterminal projected inputs remain an explicit proxy.
    """
    rows = torch.arange(len(focal), device=focal.device)
    own = projected_scores[rows, focal].unsqueeze(1)
    return ((own > projected_scores).long() * 2 + (own == projected_scores).long()).sum(dim=1) - 1


@dataclass(frozen=True)
class PublicPolicyBatch:
    """One row per independent player view; no private referee reference.

    board[B,64,6]: occupant,owner,upgraded,home,frozen_boolean,base.
    legal_actions[B,6] is only that row's player's advertised legal mask.
    """
    board: torch.Tensor
    bot_id: torch.Tensor
    is_priority_token: torch.Tensor
    legal_actions: torch.Tensor


def _noise(key, step, action):
    x = (key * 48271 + (step + 1) * 69621 + (action + 1) * 19937 + 43051) % M
    return (x * x + 12345) % M  # maximum < 2**63: exact on CPU and CUDA


def public_policy(public, model_keys, step):
    """Row-local responding rival model; only public observations plus own RNG.

    Integer arithmetic and canonical argmax tie-breaking avoid floating-point
    decision drift across different GPUs. Families and draws are hypothetical
    rollout models, never actual opponent controller identities or seeds.
    """
    board, ids = public.board, public.bot_id
    rows = torch.arange(len(ids), device=ids.device)
    pos = (board[:, :, 0] == ids.unsqueeze(1)).long().argmax(dim=1)
    own = board[rows, pos]
    family = _noise(model_keys, 0, 7) % 4
    explore = (_noise(model_keys, step, 8) % 100) < 12
    scores = torch.full((len(ids), 6), -1000, dtype=torch.long, device=ids.device)
    for action, delta in enumerate((-8, 1, 8, -1)):
        target = (pos + delta).clamp(0, 63)
        cell = board[rows, target]
        owner, base = cell[:, 1], cell[:, 5]
        denominator = torch.where(cell[:, 2] != 0, 3, 1)
        raid = torch.where(family == 1, 400, 200) * base // denominator
        center = 14 - abs(2 * (target // 8) - 7) - abs(2 * (target % 8) - 7)
        value = torch.where(owner == 0, base * 300,
                            torch.where((owner != ids) & (cell[:, 3] == 0), raid, center))
        scores[:, action] = torch.where(cell[:, 0] == 0, value, -1000)
    work = (own[:, 1] == 0) | ((own[:, 1] == ids) & (own[:, 2] == 0))
    raid_here = (own[:, 1] != 0) & (own[:, 1] != ids) & (own[:, 3] == 0)
    scores[:, STAY] = torch.where(work | ((family == 1) & raid_here), 5000, -1000)
    intruder = ((board[:, :, 1] == ids.unsqueeze(1)) & (board[:, :, 0] > 0)
                & (board[:, :, 0] != ids.unsqueeze(1)) & (board[:, :, 4] == 0)).sum(dim=1)
    scores[:, SHIELD] = torch.where(intruder > 0, intruder * 450, -1000)
    scores[:, STAY] = torch.where(family == 3, 10000, scores[:, STAY])
    random_scores = torch.stack([_noise(model_keys, step, a) % 1000000 for a in range(6)], dim=1)
    scores = torch.where(((family == 2) | explore).unsqueeze(1), random_scores, scores)
    return torch.where(public.legal_actions, scores, -10**12).argmax(dim=1)


def scalar_public_policy(public, model_key, step):
    """Independent stdlib implementation used to audit tensor policy decisions."""
    position = public.positions[public.bot_id - 1]
    cell = public.cells[position]
    family = _noise(model_key, 0, 7) % 4
    explore = _noise(model_key, step, 8) % 100 < 12
    scores = [-1000] * 6
    for action, delta in enumerate((-8, 1, 8, -1)):
        target = max(0, min(63, position + delta))
        occupant, owner, upgraded, home, frozen, base = public.cells[target]
        center = 14 - abs(2 * (target // 8) - 7) - abs(2 * (target % 8) - 7)
        value = base * 300 if owner == 0 else (
            (400 if family == 1 else 200) * base // (3 if upgraded else 1)
            if owner != public.bot_id and not home else center)
        scores[action] = value if not occupant else -1000
    work = cell[1] == 0 or (cell[1] == public.bot_id and not cell[2])
    raid_here = cell[1] not in (0, public.bot_id) and not cell[3]
    scores[STAY] = 5000 if work or (family == 1 and raid_here) else -1000
    intruders = sum(c[1] == public.bot_id and c[0] not in (0, public.bot_id) and not c[4]
                    for c in public.cells)
    scores[SHIELD] = intruders * 450 if intruders else -1000
    if family == 3:
        scores[STAY] = 10000
    if family == 2 or explore:
        scores = [_noise(model_key, step, a) % 1000000 for a in range(6)]
    return max((i for i, a in enumerate(ref.ACTIONS) if a in public.legal_actions),
               key=lambda i: (scores[i], -i))


def _public_adapter(batch):
    """Trusted referee-to-observation boundary; private counters stay here."""
    n, dev = batch.n, batch.dev
    occupant = batch._occupancy()
    frozen = torch.zeros((n, 64), dtype=torch.long, device=dev)
    frozen.scatter_(1, batch.pos, (batch.frozen > 0).long())
    board = torch.stack((occupant, batch.owner, batch.upg.long(), (batch.home > 0).long(),
                         frozen, batch.base), dim=2)
    ids = torch.arange(1, 5, device=dev).expand(n, 4)
    return PublicPolicyBatch(board.unsqueeze(1).expand(n, 4, 64, 6).reshape(n * 4, 64, 6),
                             ids.reshape(-1), (batch.token.unsqueeze(1) == ids).reshape(-1),
                             batch.legal_mask().reshape(n * 4, 6))


def _sync(device):
    if str(device).startswith("cuda"):
        torch.cuda.synchronize()


def _exact_keys(data, expected, label):
    if not isinstance(data, dict) or set(data) != set(expected):
        raise ValueError(f"{label} must contain exactly {sorted(expected)}")


def _bounded(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f"{label} must be an integer in {lo}..{hi}")
    return value


def prepare_job(job):
    _exact_keys(job, ("schema", "kind", "job_id", "initial_observation", "transitions", "search"), "job")
    if job["schema"] != 1 or job["kind"] != "public_history_gpu_coach":
        raise ValueError("unsupported job schema/kind")
    if not isinstance(job["job_id"], str) or not 1 <= len(job["job_id"]) <= 128:
        raise ValueError("job_id must have 1..128 characters")
    config = job["search"]
    allowed = {"seed", "horizon", "plans_per_root", "rollouts_per_plan", "support_cap", "income_tail"}
    if not isinstance(config, dict) or not set(config) <= allowed:
        raise ValueError("unknown search option")
    config = {**dict(seed=0, horizon=3, plans_per_root=8, rollouts_per_plan=16,
                    support_cap=512, income_tail=12), **config}
    limits = {"seed": (0, M - 1), "horizon": (1, 6), "plans_per_root": (1, 32),
              "rollouts_per_plan": (1, 256), "support_cap": (1, 1024), "income_tail": (0, 80)}
    for name, (lo, hi) in limits.items():
        _bounded(config[name], lo, hi, name)
    transitions = job["transitions"]
    if not isinstance(transitions, list) or len(transitions) >= 80:
        raise ValueError("a complete nonterminal prefix of 0..79 transitions is required")
    belief = PublicBelief(job["initial_observation"], cap=config["support_cap"])
    for entry in transitions:
        _exact_keys(entry, ("own_action", "observation"), "transition")
        belief.advance(entry["own_action"], entry["observation"])
    horizon = min(config["horizon"], 80 - len(transitions))
    key = int(hashlib.sha256(f"{belief.history_sha256}:{config['seed']}".encode()).hexdigest()[:16], 16) % M
    rng = random.Random(key)
    indices = [rng.randrange(len(belief._states)) for _ in range(config["rollouts_per_plan"])]
    plans = []
    for root_action in belief.observation.legal_actions:
        root = ref.ACTIONS.index(root_action)
        count = min(config["plans_per_root"], 6 ** (horizon - 1))
        stay_rank = sum(STAY * 6 ** p for p in range(horizon - 1))
        tail_rng = random.Random(key + root * 1000003)
        choices = [i for i in range(6 ** (horizon - 1)) if i != stay_rank]
        ranks = [stay_rank] + tail_rng.sample(choices, count - 1)
        for rank in ranks:
            tail = []
            for _ in range(horizon - 1):
                tail.append(rank % 6)
                rank //= 6
            plans.append(tuple([root] + tail))
    return {"job_id": job["job_id"], "belief": belief, "config": config, "horizon": horizon,
            "key": key, "indices": indices, "plans": plans,
            "input_sha256": hashlib.sha256(json.dumps(job, sort_keys=True, separators=(",", ":"),
                                                       ensure_ascii=True).encode()).hexdigest(),
            "values": [[] for _ in plans], "audit_checks": 0}


def _tensor_state(games, device):
    batch = BatchGame([g.base for g in games], n=len(games), device=device)
    for field in FIELDS:
        old = getattr(batch, field)
        old.copy_(torch.tensor([getattr(g, field) for g in games], dtype=old.dtype, device=device))
    return batch


def _trusted_public_views(views):
    """Copy one referee-produced PUBLIC board for all four scalar players.

    These views were produced by the pinned reference implementation. Incoming
    job observations still receive full validation in PublicBelief. Avoiding
    four redundant validations here changes no policy inputs or decisions.
    """
    cells = tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in views[0].board for c in row)
    return [PublicObservation(cells, view.bot_id, view.is_priority_token,
                               tuple(a for a in ref.ACTIONS if a in view.legal_actions))
            for view in views]


def _verify(games, metadata, prepared, traces, final_state, values):
    """Replay every returned trajectory independently, including policy actions."""
    checked = 0
    for i, original in enumerate(games):
        job_index, plan_index, sample = metadata[i]
        job = prepared[job_index]
        focal = job["belief"].focal
        plan = job["plans"][plan_index]
        game = original.clone()
        model_key = (job["key"] + sample * 1013904223) % M
        for step, tensor_actions in enumerate(traces):
            views = _trusted_public_views(game.views())
            keys = [(model_key + seat * 43051) % M for seat in range(4)]
            actions = [scalar_public_policy(view, keys[seat], step) for seat, view in enumerate(views)]
            wanted = plan[step]
            actions[focal] = wanted if ref.ACTIONS[wanted] in views[focal].legal_actions else STAY
            if actions != tensor_actions[i]:
                raise AssertionError(f"public policy CPU/tensor mismatch trajectory {i}, step {step}")
            game.step([ref.ACTIONS[a] for a in actions])
            checked += 1
        for field in FIELDS:
            if getattr(game, field) != final_state[field][i]:
                raise AssertionError(f"independent CPU physics mismatch trajectory {i}, field {field}")
        tail = min(job["config"]["income_tail"], max(0, 81 - game.turn))
        projected = [game.score[s] + tail * game.income[s] for s in range(4)]
        expected = sum(2 if projected[focal] > projected[s] else
                       1 if projected[focal] == projected[s] else 0
                       for s in range(4) if s != focal)
        if expected != values[i]:
            raise AssertionError("independent CPU utility mismatch")
    return checked


def run_batch(jobs, *, device="cpu", max_trajectories=8192, verify_all=True):
    """Return root values only after optional independent stdlib replay succeeds.

    Verification is on by default. Turning it off is a throughput diagnostic,
    prominently marked unverified, and is unsuitable for accepting remote work.
    """
    _bounded(max_trajectories, 1, 8192, "max_trajectories")
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 64:
        raise ValueError("a batch must contain 1..64 jobs")
    if device not in ("cpu", "cuda"):
        raise ValueError("device must be cpu or cuda")
    started = time.perf_counter()
    torch.set_num_threads(1)
    if device == "cuda":
        if torch.ones(16, device=device).sum().item() != 16:
            raise RuntimeError("CUDA smoke kernel failed")
        torch.cuda.reset_peak_memory_stats()
    preparation = time.perf_counter()
    prepared = [prepare_job(job) for job in jobs]
    if len({j["job_id"] for j in prepared}) != len(prepared):
        raise ValueError("duplicate job IDs in batch")
    prefix_seconds = time.perf_counter() - preparation
    groups = {}
    for j, job in enumerate(prepared):
        for p in range(len(job["plans"])):
            for sample in range(len(job["indices"])):
                groups.setdefault(job["horizon"], []).append((j, p, sample))
    total = sum(len(rows) for rows in groups.values())
    if total > 65536:
        raise ValueError("batch exceeds 65,536 synthetic trajectories; split the jobs")
    durations = dict(prefix_reconstruction=prefix_seconds, tensor_setup_and_transfer=0.0,
                     public_policy_and_physics_with_trace_transfers=0.0, independent_cpu_replay=0.0)
    trace_hash = hashlib.sha256()
    chunks, turns_checked, game_turns = 0, 0, 0
    for horizon, group in sorted(groups.items()):
        for offset in range(0, len(group), max_trajectories):
            metadata = group[offset:offset + max_trajectories]
            chunk_start = time.perf_counter()
            games = [prepared[j]["belief"]._states[prepared[j]["indices"][sample]] for j, p, sample in metadata]
            batch = _tensor_state(games, device)
            n = len(games)
            rows = torch.arange(n, device=device)
            focal = torch.tensor([prepared[j]["belief"].focal for j, p, sample in metadata], device=device)
            plans = torch.tensor([prepared[j]["plans"][p] for j, p, sample in metadata], device=device)
            keys = torch.tensor([(prepared[j]["key"] + sample * 1013904223) % M for j, p, sample in metadata], device=device)
            keys = ((keys.unsqueeze(1) + torch.arange(4, device=device) * 43051) % M).reshape(-1)
            tails = torch.tensor([min(prepared[j]["config"]["income_tail"], max(0, 81 - game.turn - horizon))
                                  for (j, p, sample), game in zip(metadata, games)], device=device)
            _sync(device)
            durations["tensor_setup_and_transfer"] += time.perf_counter() - chunk_start
            kernel_start = time.perf_counter()
            traces = []
            for step in range(horizon):
                public = _public_adapter(batch)
                actions = public_policy(public, keys, step).reshape(n, 4)
                wanted = plans[:, step]
                own_legal = public.legal_actions.reshape(n, 4, 6)[rows, focal, wanted]
                actions[rows, focal] = torch.where(own_legal, wanted, STAY)
                # Trace transfer and synchronization are included in this timing.
                traces.append(actions.cpu().tolist())
                batch.step(actions)
            projected_scores = batch.score + tails.unsqueeze(1) * batch.income
            values = _pairwise_numerator(projected_scores, focal).cpu().tolist()
            final_state = {field: getattr(batch, field).cpu().tolist() for field in FIELDS}
            _sync(device)
            durations["public_policy_and_physics_with_trace_transfers"] += time.perf_counter() - kernel_start
            validation_start = time.perf_counter()
            if verify_all:
                turns_checked += _verify(games, metadata, prepared, traces, final_state, values)
            durations["independent_cpu_replay"] += time.perf_counter() - validation_start
            trace_hash.update(json.dumps([metadata, traces, values], separators=(",", ":")).encode())
            for (j, p, sample), value in zip(metadata, values):
                prepared[j]["values"][p].append(value)
            game_turns += n * horizon
            chunks += 1
    results = []
    for job in prepared:
        roots = {}
        for plan, values in zip(job["plans"], job["values"]):
            entry = {"sequence": [ref.ACTIONS[a] for a in plan], "value_numerator_sum": sum(values),
                     "value_denominator": 2 * len(values), "rollouts": len(values),
                     "mean_projected_pairwise_points": sum(values) / (2 * len(values))}
            roots.setdefault(plan[0], []).append(entry)
        estimates = []
        for root, entries in sorted(roots.items()):
            entries.sort(key=lambda entry: (-entry["value_numerator_sum"],
                         tuple(ref.ACTIONS.index(a) for a in entry["sequence"])))
            estimates.append({"action": ref.ACTIONS[root], "best_common_plan": entries[0], "plans": entries})
        estimates.sort(key=lambda entry: (-entry["best_common_plan"]["value_numerator_sum"],
                                          ref.ACTIONS.index(entry["action"])))
        if any(entry["action"] not in job["belief"].observation.legal_actions for entry in estimates):
            raise AssertionError("a diagnostic root action is not publicly legal")
        results.append({"job_id": job["job_id"], "recommended_action": estimates[0]["action"],
                        "input_sha256": job["input_sha256"],
                        "root_estimates": estimates, "belief": job["belief"].summary(),
                        "search": job["config"], "effective_horizon": job["horizon"],
                        "sampled_support_states": len(set(job["indices"]))})
    total_seconds = time.perf_counter() - started
    durations["total_end_to_end"] = total_seconds
    paths = (Path(__file__), Path(__file__).with_name("belief.py"), ROOT / "training_gpu/batch_game.py", Path(ref.__file__))
    return {"schema": 1, "kind": "public_history_gpu_coach_batch_result", "jobs": results,
            "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "device": device, "torch": torch.__version__, "torch_cuda": torch.version.cuda,
            "python": platform.python_version(), "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
            "timing_seconds": durations, "chunks": chunks, "synthetic_trajectories": total,
            "synthetic_game_turns": game_turns, "independent_cpu_verified": bool(verify_all),
            "independent_cpu_turn_checks": turns_checked, "trace_sha256": trace_hash.hexdigest(),
            "peak_torch_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
            "primary_campaign_games": 0, "full_bmcts": False, "deployed_policy_changed": False,
            "certifies_optimality": False, "uniform_support_not_calibrated_posterior": True,
            "per_particle_focal_optimization": False,
            "policy_model": "row-local public-only integer heuristic mixture v1",
            "objective": "Round 1 pairwise points: exact at terminal; projected scores plus bounded income tail otherwise",
            "limitations": ["sampled open-loop continuations, not an information-set tree",
                            "handwritten rival models and nonterminal projected-pairwise cutoff proxy",
                            "search runtime is offline, no 200ms deployment guarantee",
                            "CUDA trajectories are diagnostic rollouts, not full incumbent games"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--max-trajectories", type=int, default=8192)
    parser.add_argument("--skip-independent-verification", action="store_true")
    args = parser.parse_args()
    if args.input.stat().st_size > 128 * 1024 * 1024:
        parser.error("job JSON exceeds 128 MiB")
    payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
    if payload.get("kind") == "public_history_gpu_coach":
        jobs = [payload]
    else:
        _exact_keys(payload, ("schema", "kind", "jobs"), "batch")
        if payload["schema"] != 1 or payload["kind"] != "public_history_gpu_coach_batch":
            parser.error("unsupported batch schema/kind")
        jobs = payload["jobs"]
    result = run_batch(jobs, device=args.device, max_trajectories=args.max_trajectories,
                       verify_all=not args.skip_independent_verification)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"{result['synthetic_trajectories']} synthetic trajectories, "
          f"{result['independent_cpu_turn_checks']} independently checked turns; "
          f"{result['timing_seconds']['total_end_to_end']:.3f}s total; primary games: 0", flush=True)


if __name__ == "__main__":
    main()
