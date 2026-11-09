"""Bounded CPU information-history search under a frozen joint intent model."""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import platform
import random
import time

from gpu_tree_coach.protocol import canonical, pack, legal_actions, strict_loads
from gpu_tree_coach.tree import Tree
from opponent_prediction.intent_filter import IntentFilter as FrozenIntentFilter
from opponent_prediction.intent_filter import HYPOTHESES, policy, public, logsum
from search_coach.belief import PublicObservation
from simulator.vendor_harness.referee import Referee
from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'joint-intent-public-history-mcts/1'
MODEL_VERSION = 'persistent-four-hypothesis-gumbel-information-tree-v1'
DEFAULTS = dict(seed=0, simulations=32, horizon=5, beam_width=6, exploration=1.4,
                max_nodes=256, income_tail=12, max_states=1024, max_particles=65536,
                max_joint_intents=200000, max_joint_sampling_terms=4194304, trace=False)
FROZEN = {
    'opponent_prediction/intent_filter.py':'43a1276f29f0669f1e1bbce0379ad02805d471c174172019f0db1e517302c3b9',
    'gpu_tree_coach/tree.py':'4da642282ebfabf1431c219bd106772a5900c4f9e04adf9f0ea8c3ee79349b46',
    'gpu_tree_coach/protocol.py':'c07a60eb53f535ad02e21aa1c83ecc2bc5b455659a767c04518b604d73b98883',
    'search_coach/belief.py':'f4188a87e5f253685df98ba596af97601bd00b68a42ff397f4d244126aa8669c',
    'evolution/maps.py':'e0c9328d89aff7ab23caa9a9fa6b672fc4074f66f57dd69678d1a121d5d679ef',
    'tests/reference_engine.py':'8f7b89995cad0f724fb8ac7c7bc8311a6fa9b3b722f2204097031ba2333726f4',
    'simulator/vendor_harness/referee.py':'f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337',
}


def source_pins():
    for name, expected in FROZEN.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise ValueError('QUARANTINED: a frozen intent/tree/referee source changed')
    names = list(FROZEN)+[p.relative_to(ROOT).as_posix() for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')]
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)}


@dataclass(frozen=True, slots=True)
class Prepared:
    root_id: str
    history_sha256: str
    packed: bytes
    observation: PublicObservation
    base: tuple
    home: tuple
    focal: int
    rivals: tuple
    prefix_length: int
    horizon: int
    options: dict
    states: tuple
    types: tuple
    joint: tuple
    posterior_summary: dict


def joint_entries(keys, types, weights):
    """Preserve every positive-mass (physical state, joint type) log weight."""
    if set(keys) != set(weights) or len(types) != 64:
        raise ValueError('The complete persistent joint posterior is required')
    entries = []
    for state_index,key in enumerate(keys):
        row = weights[key]
        if len(row) != len(types):
            raise ValueError('Joint posterior type dimension changed')
        for type_index,value in enumerate(row):
            if type(value) not in (float,int) or math.isnan(value) or value == math.inf:
                raise ValueError('Invalid joint log weight')
            if value != -math.inf:
                entries.append((state_index,type_index,float(value)))
    if not entries or abs(logsum(value for _,_,value in entries)) > 1e-8:
        raise ValueError('The joint log posterior must be normalized without marginal factorization')
    return tuple(entries)


def prepare(raw):
    if type(raw) is not dict or set(raw) != {'schema','kind','root_id','initial_observation','transitions','search'}:
        raise ValueError('Only schema/kind/root_id/full public prefix/search are accepted')
    if type(raw['schema']) is not int or raw['schema'] != 1 or raw['kind'] != FORMAT:
        raise ValueError('Unsupported public search schema')
    if type(raw['root_id']) is not str or not 1 <= len(raw['root_id']) <= 128:
        raise ValueError('A bounded public root label is required')
    if type(raw['search']) is not dict or not set(raw['search']) <= set(DEFAULTS):
        raise ValueError('Unknown search option; private/controller/future inputs are forbidden')
    options = dict(DEFAULTS,**raw['search'])
    bounds = dict(seed=(0,2**63-1),simulations=(2,512),horizon=(1,8),beam_width=(1,6),max_nodes=(1,8192),
                  income_tail=(0,80),max_states=(1,1024),max_particles=(64,65536),max_joint_intents=(1,200000),
                  max_joint_sampling_terms=(1,4194304))
    for name,(low,high) in bounds.items():
        if type(options[name]) is not int or not low <= options[name] <= high:
            raise ValueError('A bounded integer option is required: '+name)
    if (type(options['exploration']) not in (int,float) or not math.isfinite(options['exploration'])
            or not 0 <= options['exploration'] <= 8 or type(options['trace']) is not bool):
        raise ValueError('Finite bounded exploration and Boolean trace are required')
    transitions = raw['transitions']
    if type(transitions) is not list or len(transitions) > 79:
        raise ValueError('A complete nonterminal public prefix needs 0 through 79 transitions')
    first = public(raw['initial_observation'])
    belief = FrozenIntentFilter(first.serializable(),mode='persistent',
        **{name:options[name] for name in ('max_states','max_particles','max_joint_intents')})
    normalized = []
    for item in transitions:
        if type(item) is not dict or set(item) != {'own_action','observation'} or type(item['own_action']) is not str:
            raise ValueError('A transition contains only accepted own action and next public observation')
        observation = public(item['observation'])
        belief.advance(item['own_action'],observation.serializable())
        normalized.append(dict(own_action=item['own_action'],observation=observation.serializable()))
    observation = belief.observation
    packed = pack(observation)
    if options['simulations'] < 2*len(legal_actions(packed)):
        raise ValueError('All legal root actions require at least two simulations')
    keys = tuple(sorted(belief.states))
    states = tuple(belief.states[key] for key in keys)
    joint = joint_entries(keys,belief.types,belief.weights)
    if len(joint)*options['simulations'] > options['max_joint_sampling_terms']:
        raise ValueError('Declared complete joint-sampling work budget exceeded; no support is silently pruned')
    base,home = tuple(states[0].base),tuple(states[0].home)
    if any(tuple(g.base) != base or tuple(g.home) != home or g.turn != len(transitions)+1
           or pack(PublicObservation.from_view(g.views()[belief.focal])) != packed for g in states):
        raise ValueError('Reconstructed states disagree with the immutable public descriptor or true clock')
    history_sha = hashlib.sha256(canonical(dict(initial_observation=first.serializable(),transitions=normalized))).hexdigest()
    summary = dict(physical_states=len(states),joint_type_assignments=64,positive_joint_pairs=len(joint),
                   joint_log_normalizer=logsum(value for _,_,value in joint),
                   joint_posterior_sha256=hashlib.sha256(canonical(joint)).hexdigest(),
                   model_log_evidence=belief.log_evidence,type_marginals=belief.type_marginals(),
                   uniform_support_sampling=False,marginal_factorization=False,inference_pruning=False,
                   raw_prefix_retained=False,actual_private_state_accepted=False)
    return Prepared(raw['root_id'],history_sha,packed,observation,base,home,belief.focal,belief.rivals,len(transitions),
                    min(options['horizon'],80-len(transitions)),options,states,belief.types,joint,summary)


def _seed(history_sha, seed, domain, *indices):
    return int.from_bytes(hashlib.sha256(canonical([MODEL_VERSION,history_sha,seed,domain,*indices])).digest(),'big')


def draw_joint(root, simulation):
    # Log-space Gumbel-max considers every finite joint entry and avoids
    # exponentiating tiny posterior probabilities to zero. Finite52-bit RNG
    # resolution is still a numerical limitation, not exact real arithmetic.
    rng = random.Random(_seed(root.history_sha256,root.options['seed'],'joint-posterior',simulation))
    best,chosen = -math.inf,None
    for state,type_index,weight in root.joint:
        u = (rng.getrandbits(52)+1)/(2**52+1)
        score = weight-math.log(-math.log(u))
        if score > best:
            best,chosen = score,(state,type_index)
    return chosen


def _uniform(history_sha,seed,domain,*indices):
    return (_seed(history_sha,seed,domain,*indices) >> (256-53))/2**53


def _categorical(view,hypothesis,u):
    probabilities = policy(view,hypothesis)
    if (len(probabilities) != 6 or abs(math.fsum(probabilities)-1) > 1e-12
            or any(not math.isfinite(p) or p < 0 or (engine.ACTIONS[i] not in view.legal_actions and p != 0)
                   for i,p in enumerate(probabilities))):
        raise ValueError('QUARANTINED: hypothetical policy violated the public legal distribution')
    cumulative,last = 0.0,None
    for index,probability in enumerate(probabilities):
        if probability:
            last = index
        cumulative += probability
        if u < cumulative:
            return index
    return last  # Binary64 summation residue; never an illegal/zero-mass action.


def rival_actions(views,assignment,rivals,history_sha,seed,simulation,depth):
    # No chosen focal action, actual controller, game object or future tape is
    # accepted. Every actor uses its own immutable pre-turn public observation.
    return {seat:_categorical(views[seat],HYPOTHESES[assignment[i]],
                _uniform(history_sha,seed,'hypothetical-rival',simulation,depth,seat)) for i,seat in enumerate(rivals)}


def focal_rollout(view,public_history_sha,seed,depth):
    # Same public history => same policy draw across every latent particle.
    return _categorical(view,'economic',_uniform(public_history_sha,seed,'public-focal-rollout',depth))


def shadow_of(game):
    shadow = Referee(list(game.base),rules=dict(game.rules),start_token=game.token,max_turns=80)
    for name in ('owner','upg','home','pos','frozen','cd','prog','score'):
        setattr(shadow,name,list(getattr(game,name)))
    shadow.turn = game.turn
    return shadow


def equal_referees(game,shadow):
    for name in ('base','owner','upg','home','pos','frozen','cd','prog','score','turn','token'):
        if getattr(game,name) != getattr(shadow,name):
            raise ValueError('QUARANTINED: independent referee disagreement in '+name)
    if game.income != shadow.income() or any(set(game.legal(i)) != set(shadow.legal(i)) for i in range(4)):
        raise ValueError('QUARANTINED: independent referee income/legal disagreement')


def utility(game,focal,remaining,income_tail):
    tail = min(income_tail,remaining)
    scores = [game.score[i]+tail*game.income[i] for i in range(4)]
    return sum(2 if scores[focal]>x else 1 if scores[focal]==x else 0 for i,x in enumerate(scores) if i != focal)


def _search(root):
    tree,transitions = Tree(root),0
    trace = []
    for simulation in range(root.options['simulations']):
        state_index,type_index = draw_joint(root,simulation)
        assignment = root.types[type_index]
        game = root.states[state_index].clone()
        shadow = shadow_of(game)
        equal_referees(game,shadow)
        current,rollout,history_sha = 0,False,root.history_sha256
        visited,edges,steps = [0],[],[]
        for depth in range(root.horizon):
            views = tuple(PublicObservation.from_view(v) for v in game.views())
            before = pack(views[root.focal])
            if not rollout and before != tree.nodes[current].observation:
                raise ValueError('QUARANTINED: selected information-history node has a different public observation')
            requested = None if rollout else tree.select(current)
            rivals = rival_actions(views,assignment,root.rivals,root.history_sha256,root.options['seed'],simulation,depth)
            focal = focal_rollout(views[root.focal],history_sha,root.options['seed'],depth) if requested is None else requested
            joint = [engine.ACTIONS[focal if i == root.focal else rivals[i]] for i in range(4)]
            if any(joint[i] not in views[i].legal_actions for i in range(4)):
                raise ValueError('QUARANTINED: simulated actor selected a publicly illegal action')
            node = None if rollout else current
            if not rollout:
                edges.append((current,focal))
            # Every intention was chosen from the same pre-turn observations.
            game.step(joint);shadow.step(joint)
            equal_referees(game,shadow);transitions += 1
            terminal = root.prefix_length+depth+1 == 80
            after = None if terminal else pack(PublicObservation.from_view(game.views()[root.focal]))
            if not rollout and not terminal:
                child,new = tree.observe(current,focal,after)
                if child is not None:
                    current=child;visited.append(child)
                if new:
                    rollout=True
            if root.options['trace']:
                steps.append(dict(depth=depth,node=node,mode='rollout' if node is None else 'tree',before=before.hex(),
                                  own_action=joint[root.focal],joint_actions=joint,
                                  observation=None if after is None else after.hex(),terminal=terminal))
            if after is not None:
                history_sha=hashlib.sha256(canonical([history_sha,joint[root.focal],after.hex()])).hexdigest()
        value=utility(game,root.focal,80-root.prefix_length-root.horizon,root.options['income_tail'])
        tree.backup(visited,edges,value)
        if root.options['trace']:
            trace.append(dict(simulation=simulation,inferred_state_index=state_index,joint_type_index=type_index,
                              hypothetical_types=[HYPOTHESES[t] for t in assignment],steps=steps,value=value,
                              final_scores=list(game.score),final_income=list(game.income)))
    terminal = root.prefix_length+root.horizon == 80
    first = tree.nodes[0]
    return dict(root_id=root.root_id,history_sha256=root.history_sha256,model_version=MODEL_VERSION,
        public_root_descriptor=dict(focal_bot_id=root.focal+1,base=list(root.base),home=[bool(v) for v in root.home]),
        recommended_action=engine.ACTIONS[tree.recommend()],simulations=root.options['simulations'],effective_horizon=root.horizon,
        true_terminal_reached=terminal,cutoff_utility='exact_terminal_pairwise_numerator' if terminal else 'projected_income_pairwise_proxy',
        income_tail=min(root.options['income_tail'],80-root.prefix_length-root.horizon),posterior=root.posterior_summary,
        root_estimates={engine.ACTIONS[a]:dict(visits=first.counts[a],value_numerator_sum=first.values[a],
            empirical_pairwise_points=first.values[a]/(2*first.counts[a])) for a in first.legal},
        tree=tree.export(),trace=trace,node_cap_hits=tree.cap_hits,
        approximations=dict(finite_MCTS_samples=True,fixed_heuristic_type_family=True,calibrated_real_opponents=False,
             fixed_beam_pruning=any(n.pruned for n in tree.nodes),node_cap_public_rollout=bool(tree.cap_hits),
             binary64_gumbel_sampling_with_52_bit_uniforms=True,posterior_factorization=False),
        counterfactual_dual_referee_turns=transitions,all_sampled_turns_dual_referee_checked=True,
        terminal_turn81_view_fabricated=False,primary_match_credit=0,completed_game_audit_credit=0,full_bmcts_audit_credit=0,
        deployed_policy_changed=False,certifies_optimality=False,playing_strength_tested=False)


def recommend(raw):
    guards=source_pins();started=time.perf_counter()
    root=prepare(raw);prepared=time.perf_counter()
    result=_search(root)
    if guards != source_pins():
        raise ValueError('QUARANTINED: search source changed during inference/search')
    result.update(source_sha256=guards,runtime=dict(python=platform.python_version(),backend='CPU stdlib'),
                  timing=dict(public_inference_s=prepared-started,search_and_dual_referee_s=time.perf_counter()-prepared,
                              end_to_end_s=time.perf_counter()-started),
                  caveat='Offline finite information-tree estimates under an inferred fixed-model posterior. Forecast improvement is not playing strength, calibrated identity, optimality, deployment readiness or completed-game/BMCTS audit credit.')
    return result
