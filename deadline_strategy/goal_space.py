"""Prospective persistent public goal scores on the exact f5 Blocker structure.

This is an unqualified standalone-source builder. It runs no actors or matches,
changes no initial panel, and has no evidence-admission or promotion authority.
"""
import ast
from pathlib import Path

from evolution_templates.space import literal_sites, sha
from .space import PublicMemoryTemplateSpace
from . import space as memory_space

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'zone-rush-exact-persistent-goal-blocker-family/1'
FAMILY = 'persistent-goal-public-memory-blocker'
STRATEGY_FAMILY = 'blocker'
PARENT_TEMPLATE_SHA256 = memory_space.TEMPLATE_SHA256
TEMPLATE_SHA256 = '441596f94a1c2793e8f9c4b02c380160b4fa9985cc0cf50457bbbdfdbc73d514'
MEMORY_ADAPTER_SHA256 = '5949c9c4eaf46dbca6ba42c078f4faa4bb9bc3ef73e71dee49b8def02ab3795e'

OLD_OBSERVE_END = b'        self.prev = (own, upg, pos, frz)\n'
NEW_OBSERVE_END = OLD_OBSERVE_END+b'        self._update_goal_mass()\n'

GOAL_METHODS = '''    def _update_goal_mass(self):
        # Heuristic goal scores, not an identified controller/goal posterior.
        # This runs exactly once per public observation, even when we freeze.
        memory = getattr(self, "_persistent_goal_mass", None)
        if memory is None:
            memory = {}
            self._persistent_goal_mass = memory
        own, upg, home, base, occ = self.own, self.upg, self.home, self.base, self.occ
        for r in self.riv:
            pr = self.pos[r]
            q = [0.0] * 64
            for g in range(64):
                o = own[g]
                if o == 0:
                    v = float(base[g])
                elif o == r:
                    if upg[g]:
                        continue
                    v = 0.6 * base[g]
                elif home[g]:
                    continue
                elif upg[g]:
                    v = 0.6 * base[g]
                else:
                    v = 2.5 * base[g]
                if occ[g] and occ[g] != r:
                    v *= 0.3
                q[g] = v / (_MD[pr][g] + 1.0)
            total = sum(q)
            if total <= 0.0:
                # No attractive target: keep a public normalized stay sentinel.
                q[pr] = 1.0
                total = 1.0
            q = [value / total for value in q]
            previous = memory.get(r)
            surviving = (sum(previous[g] for g in range(64) if q[g] > 0.0)
                         if previous is not None else 0.0)
            if surviving <= 0.0:
                prior = q
            else:
                prior = [previous[g] / surviving if q[g] > 0.0 else 0.0
                         for g in range(64)]
            history = self.hist[r]
            moved = (len(history) >= 2 and history[-2] != pr
                     and not self.frz[r] and not self.pfrz.get(r, False))
            values = [0.0] * 64
            for g in range(64):
                if q[g] <= 0.0:
                    continue
                # exp(log(4) * improvement), using the identical base-4 form.
                # Lack of displacement may be a blocked intention: L=1 then.
                likelihood = (4.0 ** (_MD[history[-2]][g] - _MD[pr][g])
                              if moved else 1.0)
                values[g] = likelihood * (0.8 * prior[g] + 0.2 * q[g])
            norm = sum(values)
            if norm <= 0.0:
                raise ValueError("Persistent public goal score normalization failed")
            memory[r] = tuple(value / norm for value in values)

    def _forecast(self):
        # Read-only derivation: repeated planner calls cannot count evidence twice.
        self.post = {}
        self.goal = {}
        self.stepp = {}
        for r in self.riv:
            pr = self.pos[r]
            post = self._persistent_goal_mass[r]
            self.post[r] = post
            self.goal[r] = max(range(64), key=lambda g: post[g])
            sp = {}
            if not self.frz[r]:
                for g in range(64):
                    mass = post[g]
                    if mass < 0.003 or g == pr:
                        continue
                    red = [q for q in _RED[pr][g] if not self.occ[q]]
                    if not red:
                        continue
                    share = mass / len(red)
                    for q in red:
                        sp[q] = sp.get(q, 0.0) + share
            self.stepp[r] = sp

'''.encode('utf8')


def _method_span(body,classname,methodname):
    nodes = [node for cls in ast.parse(body).body
             if isinstance(cls,ast.ClassDef) and cls.name == classname
             for node in cls.body if isinstance(node,ast.FunctionDef) and node.name == methodname]
    if len(nodes) != 1:
        raise ValueError('Expected one exact structural method')
    lines = body.splitlines(keepends=True)
    node = nodes[0]
    begin = sum(map(len,lines[:node.lineno-1]))
    end = sum(map(len,lines[:node.end_lineno]))
    return begin,end


def _build(parent):
    if parent.count(OLD_OBSERVE_END) != 1:
        raise ValueError('Expected one exact public observation boundary')
    body = parent.replace(OLD_OBSERVE_END,NEW_OBSERVE_END,1)
    begin,end = _method_span(body,'_Core','_forecast')
    body = body[:begin]+GOAL_METHODS+body[end:]
    header = ('# Unpromoted fixed persistent-goal extension of public-memory Blocker.\n'
              '# Parent SHA256: '+PARENT_TEMPLATE_SHA256+'\n').encode('ascii')
    result = header+body
    ast.parse(result)
    return result


def source_pins():
    result = memory_space.source_pins()
    if result['deadline_strategy/space.py'] != MEMORY_ADAPTER_SHA256:
        raise ValueError('QUARANTINED: exact parent public-memory adapter changed')
    result['deadline_strategy/goal_space.py'] = sha(Path(__file__).read_bytes())
    return result


class PersistentGoalTemplateSpace:
    family = FAMILY
    strategy_family = STRATEGY_FAMILY
    template_sha256 = TEMPLATE_SHA256

    def __init__(self):
        self._pins = source_pins()
        self._parent = PublicMemoryTemplateSpace()
        self._body = _build(self._parent.export(self._parent.defaults))
        if sha(self._body) != TEMPLATE_SHA256:
            raise ValueError('QUARANTINED: fixed persistent-goal structural template changed')

    @property
    def defaults(self): return self._parent.defaults

    @property
    def bounds(self): return self._parent.bounds

    def _guard(self):
        if (source_pins() != self._pins or sha(self._body) != TEMPLATE_SHA256
                or self.family != FAMILY or self.strategy_family != STRATEGY_FAMILY
                or self.template_sha256 != TEMPLATE_SHA256):
            raise ValueError('QUARANTINED: persistent-goal identity or source closure changed')

    def validate(self,genes):
        self._guard()
        return self._parent.validate(genes)

    def export(self,genes):
        self._guard()
        return _build(self._parent.export(genes))

    def inspect_export(self,body):
        self._guard()
        if type(body) is not bytes or len(body) > len(self._body)+2048:
            raise ValueError('Bounded standalone persistent-goal source bytes required')
        sites = literal_sites(body,self.bounds)
        genes = self.validate({key:site[2] for key,site in sites.items()})
        if body != self.export(genes):
            raise ValueError('Source changed outside exact persistent-goal numeric replacements')
        return genes

    def mutate(self,parent,seed,scale=0.06,max_changes=3):
        self._guard()
        return self._parent.mutate(parent,seed,scale,max_changes)

    def crossover(self,first,second,seed):
        self._guard()
        return self._parent.crossover(first,second,seed)

    def description(self):
        self._guard()
        result = self._parent.description()
        result.update(format=FORMAT,family=FAMILY,strategy_family=STRATEGY_FAMILY,
            template_sha256=TEMPLATE_SHA256,parent_template_sha256=PARENT_TEMPLATE_SHA256,
            goal_update=dict(hazard=0.2,moved_factor_base=4.0,stationary_or_frozen_likelihood=1.0,
                timing='exactly once at end of each public observation',
                invalid_targets='condition prior on positive current public attractiveness; restart from it if empty',
                interpretation='heuristic normalized goal scores; not an identified Bayesian posterior'),
            structural_change='persistent public goal scores feeding existing conflict/route/sniping logic on fixed f5 mechanics',
            source_sha256=source_pins(),runtime_qualified=False,playing_strength_tested=False,
            initial_panel_included=False,requires_explicit_future_train_amendment=True,
            admission_authority=False,primary_credit=0,bmcts_audits=0,promotion_credit=0)
        return result
