"""Batched GPU physics/policies with sequential per-root observation-tree UCT."""
from collections import defaultdict
import ctypes
import time

import torch

from search_coach.belief import InconsistentObservation
from search_coach.gpu_batch import _pairwise_numerator, _public_adapter, _tensor_state, public_policy
from tests import reference_engine as ref
from .protocol import FORMAT, MODEL_VERSION, canonical, model_keys, prepare, sample_index, source_hashes
from .tree import Tree


def _sync(device):
    if str(device).startswith('cuda'):
        torch.cuda.synchronize()


def _bytes(tensor):
    # Copy ONLY this owned, contiguous public/action uint8 buffer. No NumPy or
    # pointer supplied by a job is used; its exact size is established here.
    if tensor.dtype != torch.uint8:
        raise ValueError('Only explicitly packed byte tensors can cross this boundary')
    cpu = tensor.detach().to('cpu').contiguous()
    return ctypes.string_at(cpu.data_ptr(), cpu.numel())


def packed_public(public, focal, *, powers=None):
    n, device = len(focal), focal.device
    rows = torch.arange(n, device=device)*4+focal
    board = public.board[rows]
    dynamic = (board[:, :, 0] | (board[:, :, 1] << 3) | (board[:, :, 2] << 6) | (board[:, :, 4] << 7)).to(torch.uint8)
    if powers is None:
        powers = torch.tensor([1, 2, 4, 8, 16, 32], device=device, dtype=torch.long)
    mask = (public.legal_actions[rows].long()*powers).sum(dim=1)
    last = (mask | (public.is_priority_token[rows].long() << 6)).to(torch.uint8)
    return torch.cat((dynamic, last.unsqueeze(1)), dim=1)


def _result(root, tree):
    return dict(root_id=root.root_id, history_sha256=root.history_sha256,
                recommended_action=ref.ACTIONS[tree.recommend()], simulations=root.options['simulations'],
                effective_horizon=root.horizon, terminal_reached=root.prefix_length+root.horizon == 80,
                cutoff_utility='exact_terminal_pairwise_numerator' if root.prefix_length+root.horizon == 80 else 'projected_income_pairwise_proxy',
                income_tail=min(root.options['income_tail'], 80-root.prefix_length-root.horizon),
                tree=tree.export(), cap_hits=tree.cap_hits, trace=tree.traces if root.options['trace'] else [],
                belief=root.belief_summary, raw_trace_retained=False,
                approximation=dict(beam_pruning=any(node.pruned for node in tree.nodes), node_cap=bool(tree.cap_hits),
                                   uniform_support_not_posterior=True, fixed_rival_model_not_true_controller=True),
                primary_match_credit=0, completed_game_audit_credit=0, certifies_optimality=False, deployed_policy_changed=False)


def _group(roots, device, use_cuda_graph=False):
    """One simulation per root per iteration; no root has stale UCT updates."""
    n = len(roots)
    horizon, simulations = roots[0].horizon, roots[0].options['simulations']
    if any(root.horizon != horizon or root.options['simulations'] != simulations for root in roots):
        raise ValueError('Group by effective horizon and simulation budget')
    _sync(device)
    setup_start = time.perf_counter()
    offsets, bank_states = [], []
    for root in roots:
        offsets.append(len(bank_states))
        bank_states.extend(root.states)
    # Transfer the inferred correlated support once, then gather starts on-device.
    bank = _tensor_state(bank_states, device)
    batch = _tensor_state([root.states[0] for root in roots], device)
    focal = torch.tensor([root.focal for root in roots], device=device, dtype=torch.long)
    row = torch.arange(n, device=device)
    public_steps = torch.tensor([root.prefix_length for root in roots], device=device, dtype=torch.long)
    tail = torch.tensor([min(root.options['income_tail'], 80-root.prefix_length-horizon) for root in roots],
                        device=device, dtype=torch.long)
    graph = None
    if use_cuda_graph:
        from .graph import PublicStepGraph
        graph = PublicStepGraph(batch, focal, public_steps)
    _sync(device)
    setup_s = time.perf_counter()-setup_start
    start = time.perf_counter()
    trees = [Tree(root) for root in roots]
    transferred = 0
    for simulation in range(simulations):
        indices = [sample_index(root, simulation) for root in roots]
        selected = torch.tensor([offset+index for offset, index in zip(offsets, indices)], device=device, dtype=torch.long)
        for field in ('owner', 'upg', 'pos', 'frozen', 'cd', 'prog', 'score', 'income', 'token'):
            getattr(batch, field).copy_(getattr(bank, field).index_select(0, selected))
        batch.turn = 1  # Local physics step clock, NEVER the true horizon clock.
        keys = torch.tensor([model_keys(root, simulation) for root in roots], device=device, dtype=torch.long).reshape(-1)
        if graph is not None:
            graph.set_keys(keys)
        current, rollout = [0]*n, [False]*n
        visited, edges = [[0] for _ in roots], [[] for _ in roots]
        before = [root.packed for root in roots]
        traces = [dict(simulation=simulation, inferred_support_index=index, steps=[]) for index in indices]
        for depth in range(horizon):
            # Selection precedes rival-model computation and receives no game.
            requested = [None if rollout[i] else trees[i].select(current[i]) for i in range(n)]
            if graph is None:
                public = _public_adapter(batch)
                # Every model receives the SAME pre-turn public board. The focal
                # requested action is not a feature or key in any rival model.
                steps = (public_steps+depth).unsqueeze(1).expand(n, 4).reshape(-1)
                actions = public_policy(public, keys, steps).reshape(n, 4)
                override = torch.tensor([action is not None for action in requested], device=device)
                wanted = torch.tensor([0 if action is None else action for action in requested], device=device, dtype=torch.long)
                actions[row, focal] = torch.where(override, wanted, actions[row, focal])
                if not bool(public.legal_actions.reshape(n, 4, 6)[row, focal, actions[row, focal]].all().item()):
                    raise AssertionError('Tree/default policy selected a publicly illegal action')
            else:
                actions, packed = graph.step(requested, depth)
            # Capture only4 action bytes when diagnostics ask for traces.
            joint_raw = _bytes(actions.to(torch.uint8)) if any(root.options['trace'] for root in roots) else None
            if graph is None:
                batch.step(actions)
                packed = packed_public(_public_adapter(batch), focal)
            raw = _bytes(packed)
            transferred += len(raw)+(len(joint_raw) if joint_raw is not None else 0)
            for i, root in enumerate(roots):
                observation = raw[i*65:(i+1)*65]
                selected_node, mode = (None, 'rollout') if rollout[i] else (current[i], 'tree')
                if not rollout[i]:
                    edges[i].append((current[i], requested[i]))
                    child, new = trees[i].observe(current[i], requested[i], observation)
                    if child is not None:
                        current[i] = child
                        visited[i].append(child)
                    if new:
                        rollout[i] = True
                if root.options['trace']:
                    joint = list(joint_raw[i*4:(i+1)*4])
                    traces[i]['steps'].append(dict(depth=depth, node=selected_node, mode=mode, before=before[i].hex(),
                                                   action=joint[root.focal], joint=joint, observation=observation.hex()))
                before[i] = observation
        # True remaining time is public-prefix-derived, not batch.turn/over().
        values = _pairwise_numerator(batch.score+tail.unsqueeze(1)*batch.income, focal).to('cpu').tolist()
        for i, value in enumerate(values):
            trees[i].backup(visited[i], edges[i], int(value))
            if roots[i].options['trace']:
                traces[i]['value'] = int(value)
                trees[i].traces.append(traces[i])
        # All backup calls complete before the next simulation for these roots.
    _sync(device)
    search_s = time.perf_counter()-start
    output = [_result(root, tree) for root, tree in zip(roots, trees)]
    return output, dict(tensor_bank_setup_s=setup_s, search_with_cpu_tree_and_transfers_s=search_s,
                        packed_public_and_trace_bytes_to_host=transferred, inferred_support_states=len(bank_states),
                        roots=n, effective_horizon=horizon, simulations_per_root=simulations, cuda_graph=use_cuda_graph)


def search_many(raw_roots, *, device='cpu', max_roots=256, max_support_states=4096,
                max_tree_nodes=65536, verify_reference=False, result_sink=None,
                max_retained_nodes=65536, max_retained_roots=1024, max_input_roots=16384, use_cuda_graph=False):
    """Stream bounded chunks; decisions never depend on chunk size or root IDs."""
    if any(type(value) is not int or value < 1 for value in (max_roots, max_support_states, max_tree_nodes,
                                                           max_retained_nodes, max_retained_roots, max_input_roots)):
        raise ValueError('Positive explicit memory budgets required')
    if result_sink is not None and not callable(result_sink):
        raise ValueError('A result sink must be callable')
    if type(verify_reference) is not bool or str(device) not in ('cpu', 'cuda', 'cuda:0'):
        raise ValueError('Choose CPU or CUDA and an explicit reference verification Boolean')
    if type(use_cuda_graph) is not bool or (use_cuda_graph and not str(device).startswith('cuda')):
        raise ValueError('CUDA Graph option requires a CUDA device')
    if str(device).startswith('cuda'):
        if not torch.cuda.is_available():
            raise ValueError('CUDA unavailable')
        torch.ones(1, device=device).sum().item()  # Real kernel before accepting work.
    guards = source_hashes()
    started = time.perf_counter()
    output, groups_report, unsupported, ids, chunk = [], [], [], set(), []
    prep_s, validation_s, support_count, node_budget = 0.0, 0.0, 0, 0
    completed, unsupported_count, retained_nodes = 0, 0, 0
    def flush():
        nonlocal chunk, support_count, node_budget, validation_s, completed, retained_nodes
        if not chunk:
            return
        groups = defaultdict(list)
        for root in chunk:
            groups[root.horizon, root.options['simulations']].append(root)
        results = {}
        for roots in groups.values():
            produced, report = _group(roots, device, use_cuda_graph)
            groups_report.append(report)
            results.update({value['root_id']: value for value in produced})
        for root in chunk:
            result = results[root.root_id]
            if verify_reference:
                from .scalar import run_prepared
                check_start = time.perf_counter()
                expected = run_prepared(root)
                if result != expected:
                    raise AssertionError('QUARANTINED: exact scalar/tensor tree, trace or recommendation disagreement')
                validation_s += time.perf_counter()-check_start
            if result_sink is not None:
                result_sink(result)
            else:
                retained_nodes += len(result['tree'])
                if retained_nodes > max_retained_nodes or len(output)+len(unsupported) >= max_retained_roots:
                    raise ValueError('Retained result budget exceeded; use a streaming result sink')
                output.append(result)
            completed += 1
        chunk, support_count, node_budget = [], 0, 0
    for raw in raw_roots:
        if len(ids) >= max_input_roots:
            raise ValueError('Explicit total input-root budget exceeded')
        root_id = raw.get('root_id') if type(raw) is dict else None
        if type(root_id) is str and root_id in ids:
            raise ValueError('Root IDs must be unique')
        prep_start = time.perf_counter()
        try:
            root = prepare(raw)
        except InconsistentObservation as error:
            if type(raw) is not dict:
                raise
            ids.add(root_id)
            failure = dict(root_id=raw.get('root_id'), reason=str(error), recommended_action=None,
                           primary_match_credit=0, completed_game_audit_credit=0)
            if result_sink is not None:
                result_sink(failure)
            else:
                if len(output)+len(unsupported) >= max_retained_roots:
                    raise ValueError('Retained result budget exceeded; use a streaming result sink')
                unsupported.append(failure)
            unsupported_count += 1
            prep_s += time.perf_counter()-prep_start
            continue
        prep_s += time.perf_counter()-prep_start
        ids.add(root.root_id)
        if len(root.states) > max_support_states or root.options['max_nodes'] > max_tree_nodes:
            raise ValueError('A single root exceeds explicit support/tree memory budget')
        if (len(chunk) >= max_roots or support_count+len(root.states) > max_support_states
                or node_budget+root.options['max_nodes'] > max_tree_nodes):
            flush()
        chunk.append(root)
        support_count += len(root.states)
        node_budget += root.options['max_nodes']
    flush()
    if guards != source_hashes():
        raise ValueError('QUARANTINED: a frozen physics/model or prototype source changed')
    return dict(format=FORMAT, model_version=MODEL_VERSION, backend=str(device), cuda_graph=use_cuda_graph, roots=output, unsupported=unsupported,
                source_sha256=guards, elapsed_s=time.perf_counter()-started, preparation_s=prep_s,
                independent_scalar_verification_s=validation_s, exact_reference_verified=verify_reference,
                supported_roots=completed, unsupported_roots=unsupported_count, results_streamed=result_sink is not None,
                batches=groups_report, primary_match_credit=0, completed_game_audit_credit=0, full_bmcts_audit_credit=0,
                caveat='Offline fixed-model information-tree prototype. Finite samples, support/beam/node caps and projected cutoff utility do not certify optimality or playing strength.')
