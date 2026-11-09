"""Independent scalar information-tree implementation and reference physics."""
import math
import time

from search_coach.gpu_batch import scalar_public_policy, _trusted_public_views
from search_coach.belief import InconsistentObservation
from tests import reference_engine as ref
from .protocol import FORMAT, MODEL_VERSION, model_keys, prepare, sample_index


def _encode(observation):
    # Independent implementation of the exact dynamic-cell encoding.
    data = bytearray(65)
    for index, cell in enumerate(observation.cells):
        data[index] = cell[0]+8*cell[1]+64*int(cell[2])+128*int(cell[4])
    data[64] = sum(2**i for i, name in enumerate(ref.ACTIONS) if name in observation.legal_actions)
    if observation.is_priority_token:
        data[64] += 64
    return bytes(data)


def _new(parent, action, observation):
    return dict(parent=parent, action=action, observation=observation,
                legal=[a for a in range(6) if (observation[64] % 64)//(2**a) % 2],
                visits=0, total=0, count=[0]*6, value=[0]*6, children={}, active=None, pruned=[])


def _select(node, options):
    low = [a for a in node['legal'] if node['count'][a] < 2]
    if low:
        minimum = min(node['count'][a] for a in low)
        return min(a for a in low if node['count'][a] == minimum)
    if node['active'] is None:
        ordered = sorted(node['legal'], key=lambda a: (-node['value'][a]/node['count'][a], a))
        node['active'] = ordered[:options['beam_width']]
        node['pruned'] = [a for a in node['legal'] if a not in node['active']]
    best_action, best_score = None, float('-inf')
    for action in sorted(node['active']):
        score = (node['value'][action]/(6*node['count'][action])
                 + options['exploration']*math.sqrt(math.log(node['visits']+1)/node['count'][action]))
        if score > best_score:
            best_action, best_score = action, score
    return best_action


def _export(nodes):
    return [dict(id=i, parent=n['parent'], action=n['action'], observation=n['observation'].hex(),
                 legal=n['legal'], visits=n['visits'], value_sum=n['total'], counts=n['count'], values=n['value'],
                 active=n['active'] or [], pruned=n['pruned'],
                 children=[dict(action=action, observation=observation.hex(), node=child)
                           for (action, observation), child in sorted(n['children'].items())]) for i, n in enumerate(nodes)]


def _finish(root, nodes, cap_hits, traces):
    first = nodes[0]
    action = min(first['legal'])
    for candidate in first['legal']:
        left, right = first['value'][candidate]*first['count'][action], first['value'][action]*first['count'][candidate]
        if left > right or (left == right and (first['count'][candidate], -candidate) > (first['count'][action], -action)):
            action = candidate
    return dict(root_id=root.root_id, history_sha256=root.history_sha256, recommended_action=ref.ACTIONS[action],
                simulations=root.options['simulations'], effective_horizon=root.horizon,
                terminal_reached=root.prefix_length+root.horizon == 80,
                cutoff_utility='exact_terminal_pairwise_numerator' if root.prefix_length+root.horizon == 80 else 'projected_income_pairwise_proxy',
                income_tail=min(root.options['income_tail'], 80-root.prefix_length-root.horizon),
                tree=_export(nodes), cap_hits=cap_hits, trace=traces if root.options['trace'] else [],
                belief=root.belief_summary, raw_trace_retained=False,
                approximation=dict(beam_pruning=any(n['pruned'] for n in nodes), node_cap=bool(cap_hits),
                                   uniform_support_not_posterior=True, fixed_rival_model_not_true_controller=True),
                primary_match_credit=0, completed_game_audit_credit=0, certifies_optimality=False,
                deployed_policy_changed=False)


def run_prepared(root):
    nodes = [_new(-1, -1, root.packed)]
    cap_hits, traces = 0, []
    for simulation in range(root.options['simulations']):
        particle = sample_index(root, simulation)
        game = root.states[particle].clone()
        keys = model_keys(root, simulation)
        current = 0
        visited, edges = [0], []
        rollout = False
        trace = dict(simulation=simulation, inferred_support_index=particle, steps=[])
        for depth in range(root.horizon):
            # No hidden state or rival action is an argument to node selection.
            requested = None if rollout else _select(nodes[current], root.options)
            views = _trusted_public_views(game.views())
            before = _encode(views[root.focal])
            joint = [scalar_public_policy(view, keys[seat], root.prefix_length+depth) for seat, view in enumerate(views)]
            mode = 'rollout' if rollout else 'tree'
            selected_node = None if rollout else current
            if requested is not None:
                if ref.ACTIONS[requested] not in views[root.focal].legal_actions:
                    raise AssertionError('Reference tree chose a publicly illegal action')
                joint[root.focal] = requested
                edges.append((current, requested))
            game.step([ref.ACTIONS[a] for a in joint])
            after = _encode(_trusted_public_views(game.views())[root.focal])
            if not rollout:
                key = (requested, after)
                child = nodes[current]['children'].get(key)
                if child is None:
                    if len(nodes) >= root.options['max_nodes']:
                        cap_hits += 1
                    else:
                        child = len(nodes)
                        nodes[current]['children'][key] = child
                        nodes.append(_new(current, requested, after))
                    rollout = True
                if child is not None:
                    current = child
                    visited.append(child)
            if root.options['trace']:
                trace['steps'].append(dict(depth=depth, node=selected_node, mode=mode, before=before.hex(),
                                           action=joint[root.focal], joint=joint, observation=after.hex()))
        remaining = max(0, 80-root.prefix_length-root.horizon)
        tail = min(root.options['income_tail'], remaining)
        projected = [game.score[s]+tail*game.income[s] for s in range(4)]
        own = projected[root.focal]
        value = sum(2 if own > score else 1 if own == score else 0 for s, score in enumerate(projected) if s != root.focal)
        for node_id in visited:
            nodes[node_id]['visits'] += 1
            nodes[node_id]['total'] += value
        for node_id, action in edges:
            nodes[node_id]['count'][action] += 1
            nodes[node_id]['value'][action] += value
        if root.options['trace']:
            trace['value'] = value
            traces.append(trace)
    return _finish(root, nodes, cap_hits, traces)


def search_many(raw_roots):
    start = time.perf_counter()
    output, ids, unsupported = [], set(), []
    for raw in raw_roots:
        root_id = raw.get('root_id') if type(raw) is dict else None
        if type(root_id) is str and root_id in ids:
            raise ValueError('Root IDs must be unique')
        try:
            root = prepare(raw)
        except InconsistentObservation as error:
            ids.add(root_id)
            unsupported.append(dict(root_id=root_id, reason=str(error), recommended_action=None,
                                    primary_match_credit=0, completed_game_audit_credit=0))
            continue
        ids.add(root.root_id)
        output.append(run_prepared(root))
    return dict(format=FORMAT, model_version=MODEL_VERSION, backend='scalar_reference', roots=output,
                elapsed_s=time.perf_counter()-start, unsupported=unsupported, primary_match_credit=0,
                completed_game_audit_credit=0, full_bmcts_audit_credit=0)
