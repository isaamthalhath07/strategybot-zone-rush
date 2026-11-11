"""Whitelisted numeric changes; every other template byte remains immutable.

This module exports standalone source. It executes no actor, game, selection,
qualification, admission or heldout evaluation and makes no strength claim.
"""
import ast
import hashlib
import math
from pathlib import Path
import random
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'zone-rush-exact-class-numeric-family/1'
TEMPLATES = {
    'original-blocker': ('tester_bots/blocker.py',
        '1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5'),
    'original-feint': ('confirmation_campaign/evidence/architectures_v2/feint_original.py',
        'f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94'),
}
COMMON_BOUNDS = {
    '_Core.ALPHA': (0.0,1.0),
    '_Core.RHO0': (0.01,0.99),
    '_Core.STAY0': (0.01,0.99),
    '_Core.PROT': (0.0,1.2),
    '_Core.KEEP': (0.0,1.0),
    '_Core.CLAIM_THR': (0.0,1.0),
    '_Core.SHW': (0.0,2.0),
    '_Core.AGG0': (0.01,0.99),
    '_Core.CONF': (0.0,1.0),
}
GROUPS = (
    ('_Core.ALPHA','_Core.PROT','_Core.CLAIM_THR','BlockerBot.LEADER_BUMP','BlockerBot.DENY'),
    ('_Core.RHO0','_Core.STAY0','_Core.AGG0','_Core.HOP_RISK','FeintBot.HOP_RISK'),
    ('_Core.KEEP','_Core.SHW','_Core.CONF'),
)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def _numeric(value):
    if type(value) not in (int,float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _seed(seed):
    if type(seed) is not int or not 0 <= seed < 2**128:
        raise ValueError('A nonnegative bounded integer operator seed is required')
    return random.Random(seed)


def literal_sites(body, keys):
    """Return exact UTF-8 byte spans for directly class-qualified assignments.

    Python AST columns count UTF-8 bytes. Use byte offsets, never character
    slicing or ast.unparse, so comments and CRLF bytes survive a replacement.
    """
    if type(body) is not bytes:
        raise ValueError('Standalone source must be exact bytes')
    try:
        tree = ast.parse(body)
    except (SyntaxError,ValueError,UnicodeError) as error:
        raise ValueError('Invalid standalone source') from error
    offsets, total = [], 0
    for line in body.splitlines(keepends=True):
        offsets.append(total)
        total += len(line)
    sites, classes = {}, set()
    for cls in tree.body:
        if not isinstance(cls,ast.ClassDef):
            continue
        if cls.name in classes:
            raise ValueError('Duplicate top-level class')
        classes.add(cls.name)
        for assignment in cls.body:
            if (not isinstance(assignment,ast.Assign) or len(assignment.targets) != 1
                    or not isinstance(assignment.targets[0],ast.Name)):
                continue
            key = cls.name+'.'+assignment.targets[0].id
            if key not in keys:
                continue
            if key in sites:
                raise ValueError('Duplicate class-qualified numeric assignment')
            try:
                value = ast.literal_eval(assignment.value)
            except (ValueError,TypeError,RecursionError) as error:
                raise ValueError('Only a finite numeric literal is mutable') from error
            if not _numeric(value):
                raise ValueError('Mutable values must be finite numeric literals, never Boolean')
            node = assignment.value
            begin = offsets[node.lineno-1]+node.col_offset
            end = offsets[node.end_lineno-1]+node.end_col_offset
            sites[key] = (begin,end,value)
    if set(sites) != set(keys):
        raise ValueError('Missing or renamed class-qualified numeric assignment')
    return sites


def replace_literals(body, sites, genes):
    result = body
    for key,(begin,end,prior) in sorted(sites.items(),key=lambda item:item[1][0],reverse=True):
        if genes[key] != prior:
            replacement = repr(float(genes[key])).encode('ascii')
            result = result[:begin]+replacement+result[end:]
    return result


class TemplateSpace:
    def __init__(self,family):
        if type(family) is not str or family not in TEMPLATES:
            raise ValueError('Only the two fixed original source families are supported')
        self.family = family
        relative,self.template_sha256 = TEMPLATES[family]
        self.path = ROOT/relative
        self._body = self.path.read_bytes()
        if sha(self._body) != self.template_sha256:
            raise ValueError('QUARANTINED: exact original template bytes changed')
        bounds = dict(COMMON_BOUNDS)
        if family == 'original-blocker':
            bounds.update({'_Core.HOP_RISK':(0.01,0.99),
                                'BlockerBot.LEADER_BUMP':(0.0,0.2),
                                'BlockerBot.DENY':(0.0,1.0)})
        else:
            bounds['FeintBot.HOP_RISK'] = (0.01,0.99)
        self._bounds = MappingProxyType(bounds)
        self._sites = MappingProxyType(literal_sites(self._body,self._bounds))
        self._defaults = MappingProxyType({key:site[2] for key,site in self._sites.items()})
        self.validate(self.defaults)

    @property
    def bounds(self):
        return dict(self._bounds)

    @property
    def defaults(self):
        return dict(self._defaults)

    def _guard(self):
        relative,expected = TEMPLATES[self.family]
        if (self.path != ROOT/relative or self.template_sha256 != expected
                or sha(self._body) != expected or sha(self.path.read_bytes()) != expected):
            raise ValueError('QUARANTINED: original template identity or bytes changed')

    def validate(self,genes):
        if type(genes) is not dict or set(genes) != set(self.bounds):
            raise ValueError('Exact class-qualified gene set required; no correctness or cost switches')
        for key,value in genes.items():
            low,high = self.bounds[key]
            if not _numeric(value) or not low <= value <= high:
                raise ValueError('Invalid finite bounded numeric gene: '+key)
        return dict(genes)

    def export(self,genes):
        self._guard()
        self.validate(genes)
        body = replace_literals(self._body,self._sites,genes)
        # A syntax failure cannot become a deployed fallback candidate.
        ast.parse(body)
        return body

    def inspect_export(self,body):
        self._guard()
        if type(body) is not bytes or len(body) > len(self._body)+2048:
            raise ValueError('Expected bounded standalone source bytes')
        sites = literal_sites(body,self.bounds)
        genes = self.validate({key:site[2] for key,site in sites.items()})
        if body != self.export(genes):
            raise ValueError('Candidate changed bytes outside exact canonical numeric replacements')
        return genes

    def mutate(self,parent,seed,scale=0.06,max_changes=3):
        self._guard()
        child = self.validate(parent)
        if not _numeric(scale) or not 0 < scale <= 0.25 or type(max_changes) is not int or not 1 <= max_changes <= 3:
            raise ValueError('Bounded positive mutation scale and one through three gene changes required')
        rng = _seed(seed)
        keys = rng.sample(sorted(child),rng.randint(1,max_changes))
        for key in keys:
            low,high = self.bounds[key]
            child[key] = round(min(high,max(low,parent[key]+rng.gauss(0,scale*(high-low)))),6)
        if child == parent:
            # Ensure a declared mutation has an actual bounded numeric change,
            # even at tiny scales or after a clamp at a boundary.
            key = keys[0]
            low,high = self.bounds[key]
            step = max(0.000001,round((high-low)*0.001,6))
            child[key] = round(min(high,parent[key]+step) if parent[key]+step <= high
                               else max(low,parent[key]-step),6)
        self.validate(child)
        if child == parent:
            raise ValueError('Mutation did not create a distinct bounded genotype')
        return child

    def crossover(self,first,second,seed):
        self._guard()
        self.validate(first); self.validate(second)
        rng,child = _seed(seed),{}
        for group in GROUPS:
            parent = first if rng.random() < 0.5 else second
            child.update({key:parent[key] for key in group if key in self.bounds})
        self.validate(child)
        return child

    def description(self):
        self._guard()
        return dict(format=FORMAT,family=self.family,template_sha256=self.template_sha256,
                    defaults=dict(self.defaults),bounds={key:list(value) for key,value in self.bounds.items()},
                    mutation='one to three finite class-qualified numeric literals; stdlib seeded Gaussian, six decimals',
                    fixed='All other bytes, cost budgets, rules, architecture switches, entry point and focal RNG initialization',
                    runtime_qualified=False,playing_strength_tested=False,primary_credit=0,bmcts_audits=0)
