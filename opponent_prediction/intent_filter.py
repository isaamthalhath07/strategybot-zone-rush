"""Enumerate joint intended actions and persistent model/physical explanations.

Weights are a posterior conditional on the declared model, not a recovered real
rival identity or a calibrated tournament prior. Private referee states occur
only as hypotheses reconstructed from public observations. No actual state,
controller, rival seed or future tape is accepted. Limits reject transactionally;
there is no silent pruning, state repair or new campaign/game credit.
"""
from collections import defaultdict
import itertools
import math

from evolution.maps import valid as valid_map
from search_coach.belief import PublicBelief, PublicObservation, matches, state_key
from tests import reference_engine as engine


HYPOTHESES = ('economic', 'raider', 'feinter', 'wanderer')
MODES = ('uniform', 'mixture', 'persistent')
EPSILON = .15
NEG_INF = float('-inf')


class InferenceBudgetExceeded(ValueError):
    pass


def public(value):
    if type(value) is not dict:
        raise ValueError('Input must be a serialized four-field public observation')
    board = value.get('board')
    fields = {'occupant','owner','is_upgraded','is_home','is_frozen','base_points'}
    if (type(board) is not list or len(board) != 8
            or any(type(row) is not list or len(row) != 8 for row in board)):
        raise ValueError('Serialized board must have eight rows of eight public cells')
    for row in board:
        for cell in row:
            if not ((type(cell) is list and len(cell) == 6)
                    or (type(cell) is dict and set(cell) == fields)):
                raise ValueError('Serialized cells must contain exactly the six public fields')
    if (type(value.get('legal_actions')) is not list
            or any(type(action) is not str for action in value['legal_actions'])):
        raise ValueError('Serialized legal actions must be a list of action names')
    observation = PublicObservation.from_view(value)
    if not valid_map([cell[5] for cell in observation.cells]):
        raise ValueError('The public map must have mirrored integer values1..3')
    return observation


def logadd(a, b):
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    high, low = (a, b) if a >= b else (b, a)
    return high + math.log1p(math.exp(low-high))


def logsum(values):
    result = NEG_INF
    for value in values:
        result = logadd(result, value)
    return result


def policy(observation, hypothesis):
    """A hypothetical actor sees only its own four public fields.

    This deliberately simple structural mixture is specified before measurement.
    It is not the actual Rival implementation or an inferred private RNG.
    """
    if not isinstance(observation, PublicObservation) or hypothesis not in HYPOTHESES:
        raise ValueError('A public observation and a declared hypothesis are required')
    legal = observation.legal_actions
    available = [engine.ACTIONS.index(action) for action in legal]
    if len(available) == 1:
        return tuple(1.0 if index == available[0] else 0.0 for index in range(6))
    cells, me = observation.cells, observation.bot_id
    position = observation.positions[me-1]
    row, col = divmod(position, 8)
    free = []
    for action, dr, dc in ((0,-1,0),(1,0,1),(2,1,0),(3,0,-1)):
        rr, cc = row+dr, col+dc
        if action in available and 0 <= rr < 8 and 0 <= cc < 8 and not cells[rr*8+cc][0]:
            free.append((action, rr*8+cc))
    result = [EPSILON/len(available) if index in available else 0.0 for index in range(6)]
    residual = 1-EPSILON

    def spread(actions, mass):
        for action in actions:
            result[action] += mass/len(actions)

    if hypothesis == 'wanderer':
        spread([a for a,_ in free]+[4,4], residual)
        return tuple(result)
    intruders = sum(owner == me and occupant not in (0,me) and not frozen
                    for occupant,owner,_,_,frozen,_ in cells)
    if intruders and 5 in available:
        result[5] += residual*.65
        residual *= .35
    _, owner, upgraded, home, _, _ = cells[position]
    if owner not in (0,me) and not home and hypothesis == 'feinter':
        hops = [a for a,p in free if cells[p][1] == owner]
        if hops:
            spread(hops, residual*.65)
            residual *= .35
    if owner == 0 or (owner not in (0,me) and not home):
        result[4] += residual
        return tuple(result)
    if owner == me and not upgraded:
        chance = .9 if hypothesis == 'economic' else .4
        result[4] += residual*chance
        residual *= 1-chance
    targets = []
    for p, (occupant, target_owner, upg, target_home, _, base) in enumerate(cells):
        if p == position or (target_home and target_owner != me) or occupant:
            continue
        distance = abs(row-p//8)+abs(col-p%8)
        if target_owner == me:
            value = 0.0 if upg else base*1.6
        elif target_owner == 0:
            value = base*2.1
        else:
            value = base*(3.4 if hypothesis == 'raider' else 1.1)*(.68 if upg else 1)
        targets.append((value/(distance+1), p))
    if not targets or not free:
        result[4] += residual
    else:
        best_value = max(value for value,_ in targets)
        goals = [p for value,p in targets if value == best_value]
        for goal in goals:
            distance = min(abs(p//8-goal//8)+abs(p%8-goal%8) for _,p in free)
            steps = [a for a,p in free if abs(p//8-goal//8)+abs(p%8-goal%8) == distance]
            spread(steps, residual/len(goals))
    if abs(sum(result)-1) > 1e-12 or any(p < 0 or not math.isfinite(p) for p in result):
        raise ValueError('Invalid hypothetical public policy distribution')
    return tuple(result)


class IntentFilter:
    """Joint persistent-type and canonical physical-state filtering.

    A physical state has a log-weight vector over joint rival type assignments.
    Physics is enumerated once per state, rather than once per assignment. Every
    compatible intended move contributes mass, even if it was blocked. Scores,
    cooldowns and progress are reconstructed hypotheses, never actual inputs.
    """
    def __init__(self, initial, *, mode='persistent', max_states=1024,
                 max_particles=65536, max_joint_intents=200000):
        if mode not in MODES:
            raise ValueError('Unknown inference mode')
        if any(type(v) is not int or v < 1 for v in (max_states,max_particles,max_joint_intents)):
            raise ValueError('Positive inference limits required')
        self.mode = mode
        self.observation = public(initial)
        belief = PublicBelief(self.observation.serializable(), cap=4)
        if not belief.exact_support:
            raise ValueError('Opening support was truncated')
        self.focal = belief.focal
        self.rivals = tuple(seat for seat in range(4) if seat != self.focal)
        self.types = tuple(itertools.product(range(4), repeat=3)) if mode == 'persistent' else ((-1,)*3,)
        self.max_states, self.max_particles, self.max_joint_intents = max_states,max_particles,max_joint_intents
        self.states = {state_key(game):game for game in belief._states}
        self._limits(len(self.states))
        prior = -math.log(len(self.states)*len(self.types))
        self.weights = {key:[prior]*len(self.types) for key in self.states}
        self.transitions = 0
        self.log_evidence = 0.0

    def _limits(self, states):
        if states > self.max_states or states*len(self.types) > self.max_particles:
            raise InferenceBudgetExceeded('Complete modeled explanation set exceeds explicit budget; no pruning performed')

    def _probabilities(self, game):
        output = []
        views = game.views()
        for seat in self.rivals:
            observation = PublicObservation.from_view(views[seat])
            if self.mode == 'uniform':
                available = {engine.ACTIONS.index(a) for a in observation.legal_actions}
                output.append([tuple(1/len(available) if a in available else 0.0 for a in range(6))])
            else:
                distributions = [policy(observation,name) for name in HYPOTHESES]
                output.append(distributions if self.mode == 'persistent' else
                              [tuple(sum(row[a] for row in distributions)/4 for a in range(6))])
        return output

    def advance(self, own_action, next_observation):
        if type(own_action) is not str or own_action not in self.observation.legal_actions:
            raise ValueError('Own accepted action must have been publicly legal')
        if self.transitions >= 80:
            raise ValueError('An80-turn game has no further transition')
        post = public(next_observation)
        if (post.bot_id != self.observation.bot_id
                or any(a[3] != b[3] or a[5] != b[5] for a,b in zip(post.cells,self.observation.cells))):
            raise ValueError('Public identity or immutable map/home descriptor changed')
        states, weights = {}, {}
        tried, compatible, aliases = 0, 0, 0
        for key, game in sorted(self.states.items()):
            probabilities = self._probabilities(game)
            options = []
            for seat in range(4):
                if seat == self.focal:
                    options.append((own_action,))
                elif post.positions[seat] != game.pos[seat]:
                    delta = post.positions[seat]-game.pos[seat]
                    move = next((a for a,d in engine.MOVES.items() if d == delta), None)
                    options.append((move,) if move in game.legal(seat) else ())
                else:
                    # Keep every legal intended move. Failed moves have STAY
                    # physics, but their probability mass must not disappear.
                    options.append(tuple(game.legal(seat)))
            kernels = {}
            for joint in itertools.product(*options):
                tried += 1
                if tried > self.max_joint_intents:
                    raise InferenceBudgetExceeded('Joint-intent budget exceeded before committing update')
                successor = game.clone()
                successor.step(joint)
                if not matches(successor,post):
                    continue
                compatible += 1
                newkey = state_key(successor)
                if newkey not in states:
                    states[newkey] = successor
                    self._limits(len(states))
                kernel = kernels.setdefault(newkey,[NEG_INF]*len(self.types))
                actions = [engine.ACTIONS.index(joint[seat]) for seat in self.rivals]
                for index, assignment in enumerate(self.types):
                    logs = []
                    for rival, action in enumerate(actions):
                        p = probabilities[rival][assignment[rival] if self.mode == 'persistent' else 0][action]
                        if p <= 0:
                            raise ValueError('Declared epsilon model lost a legal intention')
                        logs.append(math.log(p))
                    if kernel[index] != NEG_INF:
                        aliases += 1 if index == 0 else 0
                    kernel[index] = logadd(kernel[index],sum(logs))
            for newkey, kernel in kernels.items():
                total = weights.setdefault(newkey,[NEG_INF]*len(self.types))
                for index, likelihood in enumerate(kernel):
                    total[index] = logadd(total[index],self.weights[key][index]+likelihood)
        evidence = logsum(value for vector in weights.values() for value in vector)
        if not weights or not math.isfinite(evidence):
            raise ValueError('Public transition has no positive modeled explanation; state unchanged')
        if evidence > 1e-10:
            raise ValueError('Conditional public transition probability exceeded one')
        for vector in weights.values():
            for index in range(len(vector)):
                vector[index] -= evidence
        self.states, self.weights = states, weights
        self.observation = post
        self.transitions += 1
        self.log_evidence += evidence
        return dict(log_predictive_probability=evidence,physical_states=len(states),
                    joint_type_assignments=len(self.types),modeled_particles=len(states)*len(self.types),
                    legal_joint_intents_tested=tried,compatible_joint_intents=compatible,
                    compatible_alias_intents=aliases,pruning_performed=False,
                    hidden_actual_state_accepted=False)

    def type_marginals(self):
        if self.mode != 'persistent':
            return None
        result = [[0.0]*4 for _ in self.rivals]
        for vector in self.weights.values():
            for index, assignment in enumerate(self.types):
                probability = math.exp(vector[index])
                for rival, hypothesis in enumerate(assignment):
                    result[rival][hypothesis] += probability
        return {str(seat+1):dict(zip(HYPOTHESES,values)) for seat,values in zip(self.rivals,result)}

    def action_marginals(self):
        result = {seat:[0.0]*6 for seat in self.rivals}
        for key, game in self.states.items():
            probabilities = self._probabilities(game)
            for index, assignment in enumerate(self.types):
                mass = math.exp(self.weights[key][index])
                for rival, seat in enumerate(self.rivals):
                    row = probabilities[rival][assignment[rival] if self.mode == 'persistent' else 0]
                    for action,p in enumerate(row):
                        result[seat][action] += mass*p
        return {str(seat+1):dict(zip(engine.ACTIONS,values)) for seat,values in result.items()}
