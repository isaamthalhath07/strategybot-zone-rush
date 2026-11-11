"""Evaluate every legal root action on paired joint worlds, then public e8.

This is a new offline search architecture. It changes both future own control
and root allocation relative to the frozen information-tree teacher. It accepts
no actual controller, private state, seed, current rival action or future tape.
"""
import copy
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import platform
import time

from intent_search import mcts
from opponent_prediction.intent_filter import HYPOTHESES, public
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'public-e8-root-evaluation/1'
INCUMBENT = 'e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5'
ACTOR_LEGAL_ORDER = ('STAY','NORTH','SOUTH','WEST','EAST','SHIELD')
TIE_RULE = 'Highest exact numerator sum; exact ties prefer reconstructed baseline action, then engine.ACTIONS order.'
INACTIVE_OPTIONS = ('beam_width','exploration','max_nodes','trace')


def sha(body):
    return hashlib.sha256(body).hexdigest()


def source_pins():
    pins = mcts.source_pins()
    for name in ('bot.py','aligned_search/__init__.py','aligned_search/evaluator.py'):
        pins[name] = sha((ROOT/name).read_bytes())
    if pins['bot.py'] != INCUMBENT:
        raise ValueError('QUARANTINED: exact immutable e8 source required')
    return dict(sorted(pins.items()))


def prepare(raw):
    """Reuse the complete frozen joint inference and conservative work caps."""
    if (type(raw) is not dict or set(raw) != {'schema','kind','root_id','initial_observation','transitions','search'}
            or raw['kind'] != FORMAT):
        raise ValueError('Only the strict public-e8-root-evaluation/1 wire is accepted')
    copied = copy.deepcopy(raw)
    copied['kind'] = mcts.FORMAT
    root = mcts.prepare(copied)
    legal_count = len(root.observation.legal_actions)
    if root.options['simulations'] % legal_count or root.options['simulations']//legal_count < 2:
        raise ValueError('Simulations must give at least two complete paired worlds per legal root action')
    normalized = dict(schema=1,kind=FORMAT,root_id=root.root_id,
        initial_observation=public(raw['initial_observation']).serializable(),
        transitions=[dict(own_action=row['own_action'],observation=public(row['observation']).serializable())
                     for row in raw['transitions']],search=dict(root.options))
    return root,normalized


@dataclass(frozen=True, slots=True)
class PublicCell:
    occupant: int
    owner: int
    is_upgraded: bool
    is_home: bool
    is_frozen: bool
    base_points: int


@dataclass(frozen=True, slots=True)
class PolicyView:
    board: tuple
    bot_id: int
    is_priority_token: bool
    legal_actions: tuple


def policy_view(value):
    observation = PublicObservation.from_view(value)
    legal = tuple(action for action in ACTOR_LEGAL_ORDER if action in observation.legal_actions)
    return PolicyView(tuple(tuple(PublicCell(*cell) for cell in observation.cells[r*8:(r+1)*8]) for r in range(8)),
                      observation.bot_id,observation.is_priority_token,legal)


def _data(value):
    """Lossless tagged data encoding; reject functions or mutable hidden objects."""
    kind = type(value)
    if value is None or kind in (str,bool,int):
        return [kind.__name__,value]
    if kind is float:
        if not math.isfinite(value):
            raise ValueError('Nonfinite public policy memory')
        return ['float',value]
    if kind is dict:
        rows = [(_data(key),_data(item)) for key,item in value.items()]
        rows.sort(key=lambda row:mcts.canonical(row[0]))
        return ['dict',rows]
    if kind in (list,tuple,set,frozenset):
        rows = [_data(item) for item in value]
        if kind in (set,frozenset):
            rows.sort(key=mcts.canonical)
        return [kind.__name__,rows]
    raise ValueError('Only data-only public _history memory may be cloned')


def memory_fingerprint(memory):
    return sha(mcts.canonical(_data(memory)))


def _snapshot(namespace):
    memory = namespace.get('_history')
    if type(memory) is not dict:
        raise ValueError('e8 public memory dictionary missing')
    memory_fingerprint(memory)
    return copy.deepcopy(memory)


def new_policy(memory=None):
    """Fresh function globals every time; only verified data dictionaries clone."""
    body = (ROOT/'bot.py').read_bytes()
    if sha(body) != INCUMBENT:
        raise ValueError('QUARANTINED: e8 policy source changed')
    namespace = {'__name__':'_fresh_public_e8_rollout','__file__':str(ROOT/'bot.py')}
    exec(compile(body,str(ROOT/'bot.py'),'exec'),namespace)
    if memory is not None:
        if type(memory) is not dict:
            raise ValueError('Only a data-only memory dictionary may initialize e8')
        memory_fingerprint(memory)
        namespace['_history'] = copy.deepcopy(memory)
    return namespace


def _sync(namespace, focal_id, accepted):
    if type(accepted) is not str or accepted not in engine.ACTIONS:
        raise ValueError('A documented accepted own action is required')
    memory = namespace.get('_history',{}).get(focal_id)
    if type(memory) is not dict or 'last' not in memory:
        raise ValueError('Original e8 proposal must run before accepted-action synchronization')
    memory['last'] = accepted


def _signature(view):
    if (set(view.__slots__) != {'board','bot_id','is_priority_token','legal_actions'}
            or any(set(cell.__slots__) != {'occupant','owner','is_upgraded','is_home','is_frozen','base_points'}
                   for row in view.board for cell in row)):
        raise ValueError('Extra public actor fields')
    return (view.bot_id,view.is_priority_token,view.legal_actions,
        tuple((cell.occupant,cell.owner,cell.is_upgraded,cell.is_home,cell.is_frozen,cell.base_points)
              for row in view.board for cell in row))


def _call(namespace, observation, history_sha, registry, counters, category):
    """Actor call takes only a four-field view; auditor hashes remain outside."""
    supplied = policy_view(observation)
    before = _signature(supplied)
    memory_before = memory_fingerprint(_snapshot(namespace))
    started = time.perf_counter()
    proposal = namespace['act'](supplied)
    elapsed = time.perf_counter()-started
    counters[category] += 1
    counters['policy_callback_total_s'] += elapsed
    counters['policy_callback_max_s'] = max(counters['policy_callback_max_s'],elapsed)
    if _signature(supplied) != before:
        raise ValueError('QUARANTINED: public e8 input mutation')
    if type(proposal) is not str or proposal not in supplied.legal_actions:
        raise ValueError('QUARANTINED: illegal e8 proposal')
    if namespace.get('_input_failures',0) or namespace.get('_policy_failures',0):
        raise ValueError('QUARANTINED: e8 fallback')
    memory = namespace.get('_history',{}).get(supplied.bot_id,{})
    if memory.get('inference_failures',0):
        raise ValueError('QUARANTINED: e8 inference fallback')
    after = memory_fingerprint(_snapshot(namespace))
    witness = (sha(mcts.canonical(before)),memory_before,proposal,after)
    if history_sha in registry:
        if registry[history_sha] != witness:
            raise ValueError('QUARANTINED: equal public own histories changed policy proposal/memory')
        counters['public_history_invariance_checks'] += 1
    else:
        registry[history_sha] = witness
    return proposal,dict(memory_before_sha256=memory_before,memory_after_proposal_sha256=after,
                         actor_legal_actions=list(supplied.legal_actions))


def _counters():
    return dict(prefix_policy_callbacks=0,root_probe_callbacks=0,simulation_policy_callbacks=0,
                fresh_policy_namespaces=0,public_history_invariance_checks=0,
                public_score_oracles=0,public_memory_oracles=0,dual_referee_turns=0,
                root_original_proposals=0,root_accepted_action_synchronizations=0,
                policy_callback_total_s=0.0,policy_callback_max_s=0.0)


def _public_scores(previous,current,scores):
    result = list(scores)
    income = [0]*4
    for index,cell in enumerate(current.cells):
        owner,base = cell[1],cell[5]
        if owner:
            income[owner-1] += base*(1+int(cell[2]))
        if previous is not None:
            old = previous.cells[index]
            if old[1] and owner and old[1] != owner:
                result[owner-1] += 8*base*(1+int(old[2]))
    return [score+rate for score,rate in zip(result,income)] if previous is not None else result


def prefill(job,registry=None,counters=None):
    """Public-history replay only; no referee, controller spec or latent input."""
    registry = {} if registry is None else registry
    counters = _counters() if counters is None else counters
    namespace = new_policy()
    counters['fresh_policy_namespaces'] += 1
    opening = public(job['initial_observation'])
    transitions = job['transitions']
    observations = [opening]+[public(row['observation']) for row in transitions]
    normalized_transitions = [dict(own_action=row['own_action'],observation=observation.serializable())
                              for row,observation in zip(transitions,observations[1:])]
    previous,scores,trace = None,[0]*4,[]
    before_root,root_memory,baseline = None,None,None
    for index,observation in enumerate(observations):
        scores = _public_scores(previous,observation,scores)
        root = index == len(transitions)
        if root:
            before_root = _snapshot(namespace)
        history_sha = sha(mcts.canonical(dict(initial_observation=opening.serializable(),
                                             transitions=normalized_transitions[:index])))
        category = 'root_probe_callbacks' if root else 'prefix_policy_callbacks'
        proposal,witness = _call(namespace,observation,history_sha,registry,counters,category)
        memory = namespace['_history'][observation.bot_id]
        if memory['scores'][1:] != scores:
            raise ValueError('QUARANTINED: public-prefix score memory mismatch')
        counters['public_score_oracles'] += 1
        accepted = None if root else transitions[index]['own_action']
        if accepted is not None:
            if accepted not in observation.legal_actions:
                raise ValueError('Illegal accepted prefix action')
            _sync(namespace,observation.bot_id,accepted)
        else:
            baseline,root_memory = proposal,_snapshot(namespace)
            counters['root_original_proposals'] += 1
        trace.append(dict(turn=index+1,observation=observation.serializable(),history_sha256=history_sha,
            proposal=proposal,accepted_action=accepted,**witness,
            memory_after_accepted_sha256=memory_fingerprint(_snapshot(namespace))))
        previous = observation
    return dict(before_root_memory=before_root,root_memory=root_memory,baseline_action=baseline,
                trace=trace,counters=counters,root_history_sha256=trace[-1]['history_sha256'])


def _memory_oracle(namespace,game,focal,counters):
    # Hypothetical referee truth is auditor-only AFTER the strict public call.
    memory = namespace.get('_history',{}).get(focal+1,{})
    if (not memory or memory.get('inference_failures',0) or memory['progress'] != game.prog[focal]
            or memory['scores'][1:] != game.score
            or any(game.cd[seat] not in memory['cooldown_possible'][seat+1] for seat in range(4))):
        raise ValueError('QUARANTINED: hypothetical public e8 memory oracle mismatch')
    counters['public_memory_oracles'] += 1


def _evaluate(root,prefix,registry,counters):
    legal = tuple(action for action in engine.ACTIONS if action in root.observation.legal_actions)
    pairs = root.options['simulations']//len(legal)
    totals = {action:0 for action in legal}
    trace = []
    for pair_index in range(pairs):
        state_index,type_index = mcts.draw_joint(root,pair_index)
        assignment = root.types[type_index]
        pair = dict(pair_index=pair_index,inferred_state_index=state_index,joint_type_index=type_index,
                    hypothetical_types=[HYPOTHESES[value] for value in assignment],branches=[])
        for root_action in legal:
            game = root.states[state_index].clone()
            shadow = mcts.shadow_of(game)
            mcts.equal_referees(game,shadow)
            namespace = new_policy(prefix['before_root_memory'])
            counters['fresh_policy_namespaces'] += 1
            history_sha,steps = root.history_sha256,[]
            for depth in range(root.horizon):
                # Snapshot all simultaneous public views before any proposal.
                views = tuple(PublicObservation.from_view(view) for view in game.views())
                own = views[root.focal]
                before = own.serializable()
                proposal,witness = _call(namespace,own,history_sha,registry,counters,'simulation_policy_callbacks')
                _memory_oracle(namespace,game,root.focal,counters)
                if depth == 0:
                    counters['root_original_proposals'] += 1
                    if (proposal != prefix['baseline_action']
                            or memory_fingerprint(_snapshot(namespace)) != memory_fingerprint(prefix['root_memory'])):
                        raise ValueError('QUARANTINED: original root proposal/memory changed across paired worlds')
                rivals = mcts.rival_actions(views,assignment,root.rivals,root.history_sha256,
                                           root.options['seed'],pair_index,depth)
                accepted = root_action if depth == 0 else proposal
                _sync(namespace,root.focal+1,accepted)
                if depth == 0:
                    counters['root_accepted_action_synchronizations'] += 1
                joint = [accepted if seat == root.focal else engine.ACTIONS[rivals[seat]] for seat in range(4)]
                if any(action not in views[seat].legal_actions or action not in shadow.legal(seat)
                       for seat,action in enumerate(joint)):
                    raise ValueError('QUARANTINED: illegal paired simulated intention')
                effective = game.step(joint)
                shadow.step(joint)
                mcts.equal_referees(game,shadow)
                counters['dual_referee_turns'] += 1
                terminal = root.prefix_length+depth+1 == 80
                # No terminal actor/public observation at turn81 is fabricated.
                after = None if terminal else PublicObservation.from_view(game.views()[root.focal])
                after_history = None if after is None else sha(mcts.canonical([history_sha,accepted,mcts.pack(after).hex()]))
                steps.append(dict(depth=depth,turn=root.prefix_length+depth+1,proposal=proposal,
                    accepted_action=accepted,own_action=accepted,effective_own_action=effective[root.focal],
                    before=before,after=None if after is None else after.serializable(),
                    before_history_sha256=history_sha,after_history_sha256=after_history,
                    joint_actions=joint,terminal=terminal,**witness,
                    policy_memory_sha256=memory_fingerprint(_snapshot(namespace))))
                history_sha = after_history
            value = mcts.utility(game,root.focal,80-root.prefix_length-root.horizon,root.options['income_tail'])
            totals[root_action] += value
            pair['branches'].append(dict(root_action=root_action,steps=steps,value_numerator=value,
                final_scores=list(game.score),final_income=list(game.income),
                final_policy_memory_sha256=memory_fingerprint(_snapshot(namespace))))
        trace.append(pair)
    expected = root.options['simulations']*root.horizon
    if (counters['dual_referee_turns'] != expected or counters['simulation_policy_callbacks'] != expected
            or counters['public_memory_oracles'] != expected
            or counters['root_accepted_action_synchronizations'] != root.options['simulations']
            or len(trace) != pairs or any(len(pair['branches']) != len(legal) for pair in trace)):
        raise ValueError('QUARANTINED: incomplete paired action/world/turn coverage')
    best = max(totals.values())
    tied = [action for action in legal if totals[action] == best]
    baseline = prefix['baseline_action']
    chosen = baseline if baseline in tied else tied[0]
    terminal = root.prefix_length+root.horizon == 80
    return dict(recommended_action=chosen,baseline_action=baseline,tie_rule=TIE_RULE,
        root_estimates={action:dict(visits=pairs,paired_worlds=pairs,value_numerator_sum=totals[action],
                       empirical_pairwise_points=totals[action]/(2*pairs)) for action in legal},
        pair_count=pairs,simulations=root.options['simulations'],effective_horizon=root.horizon,
        legal_root_actions=list(legal),true_terminal_reached=terminal,
        income_tail=min(root.options['income_tail'],80-root.prefix_length-root.horizon),
        cutoff_utility='exact_terminal_pairwise_numerator' if terminal else 'projected_income_pairwise_proxy',
        trace=trace,public_prefill_trace=prefix['trace'],counters=counters,
        counterfactual_dual_referee_turns=expected,
        coverage=dict(paired_worlds=pairs,actions_per_world=len(legal),complete_trajectories=root.options['simulations'],
                      expected_dual_referee_turns=expected,actual_dual_referee_turns=counters['dual_referee_turns']),
        all_sampled_turns_dual_referee_checked=True,terminal_turn81_view_fabricated=False,
        node_cap_hits=0,future_tree_control=False,posterior_pruning=False,
        inactive_inherited_options=list(INACTIVE_OPTIONS),audit_trace_always_retained=True)


def recommend(raw):
    guards = source_pins()
    started = time.perf_counter()
    root,job = prepare(raw)
    inferred = time.perf_counter()
    registry,counters = {},_counters()
    prefix = prefill(job,registry,counters)
    prefilled = time.perf_counter()
    if prefix['root_history_sha256'] != root.history_sha256:
        raise ValueError('QUARANTINED: public prefill and joint inference prefix differ')
    result = _evaluate(root,prefix,registry,counters)
    if guards != source_pins():
        raise ValueError('QUARANTINED: aligned source changed during the job')
    result.update(format=FORMAT,root_id=root.root_id,history_sha256=root.history_sha256,
        model_version=mcts.MODEL_VERSION,posterior=root.posterior_summary,source_sha256=guards,
        public_root_descriptor=dict(focal_bot_id=root.focal+1,base=list(root.base),home=[bool(value) for value in root.home]),
        timing=dict(public_inference_s=inferred-started,public_policy_prefill_s=prefilled-inferred,
                    paired_evaluation_s=time.perf_counter()-prefilled,end_to_end_s=time.perf_counter()-started),
        runtime=dict(python=platform.python_version(),backend='CPU stdlib',policy_sha256=INCUMBENT),
        approximations=dict(finite_paired_world_samples=True,fixed_heuristic_type_family=True,
                            calibrated_real_opponents=False,binary64_gumbel_sampling_with_52_bit_uniforms=True,
                            posterior_factorization=False,tree_optimization=False),
        paired_sampling='One complete joint physical/type draw per pair; same pair_index/depth rival random keys across every root alternative. This is not the old adaptive96-world allocation or identical cross-architecture trajectories.',
        policy_semantics='Fresh exact-e8 globals per trajectory; data-only public prefix memory; original root proposal intent retained, accepted last synchronized, then e8 at every own future step. Legal sets use public reference-engine ordering.',
        comparison_scope='Changes continuation target, removes future UCT control, balances root allocation and shares paired worlds; not a one-factor causal ablation.',
        primary_match_credit=0,completed_game_audit_credit=0,full_bmcts_audit_credit=0,promoted=False,
        deployed_policy_changed=False,certifies_optimality=False,playing_strength_tested=False,
        caveat='Offline finite model-conditional paired-root estimates with a public e8 hybrid continuation. No fresh playing-strength, equilibrium, calibrated identity, online200ms qualification or completed-game/BMCTS credit.')
    return result
