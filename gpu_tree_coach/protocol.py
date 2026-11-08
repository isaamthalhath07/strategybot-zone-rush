"""Strict public-prefix inputs and compact public information-set descriptors."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from evolution.maps import valid as valid_map
from search_coach.belief import PublicBelief, PublicObservation
from tests import reference_engine as ref

M = 2147483647
FORMAT = 'public-observation-tree-mcts/1'
MODEL_VERSION = 'frozen-public-integer-policy/domain-separated-tree-v1'
PUBLIC_FIELDS = {'board', 'bot_id', 'is_priority_token', 'legal_actions'}
CELL_FIELDS = {'occupant', 'owner', 'is_upgraded', 'is_home', 'is_frozen', 'base_points'}
DEFAULTS = dict(seed=0, horizon=5, simulations=24, beam_width=6, exploration=1.4,
                support_cap=512, max_nodes=256, income_tail=12, trace=False)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def strict_loads(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate input key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite input')))


def _view(value):
    if type(value) is not dict or set(value) != PUBLIC_FIELDS:
        raise ValueError('Only the four serialized public observation fields are accepted')
    board = value['board']
    if type(board) is not list or len(board) != 8 or any(type(row) is not list or len(row) != 8 for row in board):
        raise ValueError('An eight by eight public board is required')
    if type(value['legal_actions']) is not list or any(type(a) is not str for a in value['legal_actions']):
        raise ValueError('Serialized public legal actions must be a list of names')
    for row in board:
        for cell in row:
            if not ((type(cell) is list and len(cell) == 6) or (type(cell) is dict and set(cell) == CELL_FIELDS)):
                raise ValueError('Cells must expose exactly the six public fields')
    observation = PublicObservation.from_view(value)
    if not valid_map([cell[5] for cell in observation.cells]):
        raise ValueError('Map must have mirrored integer values1..3')
    return observation


def pack(observation):
    result = bytes(cell[0] | (cell[1] << 3) | (int(cell[2]) << 6) | (int(cell[4]) << 7)
                   for cell in observation.cells)
    mask = sum(1 << index for index, name in enumerate(ref.ACTIONS) if name in observation.legal_actions)
    return result + bytes([mask | (int(observation.is_priority_token) << 6)])


def legal_actions(packed):
    if type(packed) is not bytes or len(packed) != 65 or packed[64] & 128:
        raise ValueError('Invalid packed public observation')
    result = tuple(action for action in range(6) if packed[64] & (1 << action))
    if not result:
        raise ValueError('A public node must have a legal action')
    return result


@dataclass(frozen=True, slots=True)
class PreparedRoot:
    root_id: str
    history_sha256: str
    input_sha256: str
    observation: PublicObservation
    packed: bytes
    states: tuple
    base: bytes
    home: bytes
    focal: int
    prefix_length: int
    horizon: int
    options: dict
    belief_summary: dict


def prepare(raw):
    if type(raw) is not dict or set(raw) != {'schema', 'kind', 'root_id', 'initial_observation', 'transitions', 'search'}:
        raise ValueError('Raw roots accept only schema/kind/root_id/public prefix/search')
    if type(raw['schema']) is not int or raw['schema'] != 1 or raw['kind'] != FORMAT:
        raise ValueError('Unsupported public-tree root schema')
    if type(raw['root_id']) is not str or not 1 <= len(raw['root_id']) <= 128:
        raise ValueError('A root identifier of1..128 characters is required')
    if type(raw['search']) is not dict or not set(raw['search']) <= set(DEFAULTS):
        raise ValueError('Unknown search option')
    options = {**DEFAULTS, **raw['search']}
    for key, low, high in (('seed', 0, M-1), ('horizon', 1, 12), ('simulations', 2, 4096),
                           ('beam_width', 1, 6), ('support_cap', 1, 1024), ('max_nodes', 1, 65536), ('income_tail', 0, 80)):
        if type(options[key]) is not int or not low <= options[key] <= high:
            raise ValueError('Bounded integer search option required: '+key)
    if type(options['exploration']) not in (float, int) or not math.isfinite(options['exploration']) or not 0 <= options['exploration'] <= 8:
        raise ValueError('Finite exploration constant0..8 required')
    if type(options['trace']) is not bool:
        raise ValueError('Trace must be Boolean')
    transitions = raw['transitions']
    if type(transitions) is not list or len(transitions) >= 80:
        raise ValueError('Complete nonterminal prefix needs0..79 transitions')
    initial = _view(raw['initial_observation'])
    belief = PublicBelief(initial.serializable(), cap=options['support_cap'])
    for transition in transitions:
        if type(transition) is not dict or set(transition) != {'own_action', 'observation'} or type(transition['own_action']) is not str:
            raise ValueError('Transitions contain only accepted own action and next public observation')
        observation = _view(transition['observation'])
        belief.advance(transition['own_action'], observation.serializable())
    observation = belief.observation
    current = pack(observation)
    if options['simulations'] < 2*len(legal_actions(current)):
        raise ValueError('Budget must visit every legal root action at least twice')
    base = bytes(cell[5] for cell in observation.cells)
    home = bytes(int(cell[3]) for cell in observation.cells)
    states = tuple(belief._states)
    home_owners = tuple(states[0].home)
    if any(bytes(state.base) != base or bytes(bool(v) for v in state.home) != home or tuple(state.home) != home_owners
           or pack(PublicObservation.from_view(state.views()[belief.focal])) != current for state in states):
        raise ValueError('Inferred states disagree with the immutable public root descriptor')
    # Do not retain the duplicated raw trace after its correlated support is inferred.
    summary = belief.summary()
    return PreparedRoot(raw['root_id'], belief.history_sha256, hashlib.sha256(canonical(raw)).hexdigest(),
                        observation, current, states, base, home, belief.focal, len(transitions),
                        min(options['horizon'], 80-len(transitions)), dict(options), summary)


def draw(root, simulation, domain, seat=0):
    # root_id, job order, packet hashes and actual opponent data are absent.
    body = canonical([MODEL_VERSION, root.history_sha256, root.options['seed'], domain, simulation, seat])
    return int.from_bytes(hashlib.sha256(body).digest()[:16], 'big')


def sample_index(root, simulation):
    return draw(root, simulation, 'correlated-support') % len(root.states)


def model_keys(root, simulation):
    return tuple(draw(root, -1 if seat == root.focal else simulation,
                      'focal-public-rollout' if seat == root.focal else 'hypothetical-rival', seat) % M
                 for seat in range(4))


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    names = ('gpu_tree_coach/protocol.py', 'gpu_tree_coach/tree.py', 'gpu_tree_coach/scalar.py', 'gpu_tree_coach/tensor.py',
             'gpu_tree_coach/graph.py',
             'search_coach/belief.py', 'search_coach/gpu_batch.py', 'training_gpu/batch_game.py', 'tests/reference_engine.py')
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
