"""Freeze historical class policies as standard-library single-file entries.

This adds deployment wrappers, never changes weights or fits to opponents.
Original module semantics are checked against the build on public observations.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import symtable
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'simulator/vendor_harness'))
from referee import Referee,mirror
from tools.audit_worker import Cell,Game

def public(game,seat):
    s = game.observation(seat)
    return Game([[Cell(*c) for c in row] for row in s['board']],s['bot_id'],s['is_priority_token'],list(s['legal_actions']))

COMMIT = '3e787a9828e83e864f99e2f3241ddf2e3df96e68'
PREFIX = {n:'_m%d_' % i for i,n in enumerate(('botlib','zoo','holdout','aifield','probot','independent','mybot','nnbot'))}

def read(path):
    return subprocess.check_output(['git','show',COMMIT+':'+path],cwd=ROOT)

class Flatten(ast.NodeTransformer):
    def __init__(self,source,filename,prefix):
        table = symtable.symtable(source,filename,'exec')
        self.names = {s.get_name():prefix+s.get_name() for s in table.get_symbols()
                      if s.is_assigned() or s.is_imported() or s.is_namespace()}
        self.modules = {}

    def visit_Import(self,node):
        kept = []
        for a in node.names:
            local = a.asname or a.name
            if a.name in PREFIX:
                self.modules[local] = PREFIX[a.name]
            else:
                kept.append(ast.alias(name=a.name,asname=self.names[local]))
        return ast.Import(names=kept) if kept else None

    def visit_ImportFrom(self,node):
        if node.module in PREFIX:
            for a in node.names:
                self.names[a.asname or a.name] = PREFIX[node.module]+a.name
            return None
        return ast.ImportFrom(module=node.module,names=[ast.alias(name=a.name,asname=self.names[a.asname or a.name]) for a in node.names],level=0)

    def visit_Attribute(self,node):
        if isinstance(node.value,ast.Name) and node.value.id in self.modules:
            return ast.copy_location(ast.Name(id=self.modules[node.value.id]+node.attr,ctx=node.ctx),node)
        return self.generic_visit(node)

    def visit_Name(self,node):
        if node.id in self.modules:
            raise ValueError('first-class module reference')
        return ast.copy_location(ast.Name(id=self.names.get(node.id,node.id),ctx=node.ctx),node)

    def visit_arg(self,node):
        node.arg = self.names.get(node.arg,node.arg)
        return node

    def visit_FunctionDef(self,node):
        node.name = self.names.get(node.name,node.name)
        return self.generic_visit(node)

    def visit_ClassDef(self,node):
        node.name = self.names.get(node.name,node.name)
        return self.generic_visit(node)

def main():
    out = ROOT/'validation/branch_audit/inventory_extension.json'
    if out.exists():
        raise ValueError('extension is immutable')
    paths = dict(botlib='botlib.py',zoo='zoo.py',holdout='holdout.py',aifield='aifield.py',probot='probot.py',independent='audit/independent_bot.py',mybot='mybot.py',nnbot='nnbot.py')
    raw = {n:read(p) for n,p in paths.items()}
    frozen = {}
    modules = {}
    for name,body in raw.items():
        tree = ast.parse(body)
        # The NN self-test imports Torch only for training-side validation.
        tree.body = [n for n in tree.body if not isinstance(n,ast.If) and not
                     (isinstance(n,ast.FunctionDef) and n.name=='_selftest')] if name=='nnbot' else tree.body
        source = ast.unparse(tree)
        module = types.ModuleType(name)
        module.__file__ = paths[name]
        sys.modules[name] = module
        exec(compile(source,paths[name],'exec'),module.__dict__)
        modules[name] = module
        flat = Flatten(source,paths[name],PREFIX[name]).visit(ast.parse(source))
        ast.fix_missing_locations(flat)
        frozen[name] = ast.unparse(flat)
    definitions = []
    for name,classes,deps in (
        ('zoo',('StayBot','RandomBot','GreedyValueBot','GreedyShieldBot','PacifistBot','SpineFarmerBot','RaiderBot','CamperBot','BaiterBot'),('botlib','zoo')),
        ('holdout',('TurtleBot','LeaderHunterBot','CentreRushBot','CooldownRaiderBot'),('botlib','zoo','holdout')),
        ('aifield',('MarginalBot','CheapRaiderBot','HomeFortBot','CentreLockBot','RouteBot','CooldownHawkBot','EloEndgameBot'),('botlib','aifield')),
        ('probot',('ProBot',),('botlib','probot')),
        ('independent',('IndependentFarmer','IndependentRaider'),('independent',)),
        ('nnbot',('NNAgent',),('mybot','nnbot'))):
        for cls in classes:
            definitions.append((name,cls,deps,{},'default'))
    definitions.append(('probot','ProBot',('botlib','probot'),{'params':json.loads(read('pro_params_v1.json'))},'frozen_v1'))
    weights = json.loads(read('nn_policy.json'))
    policies = []
    checks = []
    for name,cls,deps,options,label in definitions:
        if name=='nnbot':
            options = dict(weights=weights)
        source = '\n\n'.join(frozen[d] for d in deps)
        source += '\n_PLAYERS = {}\ndef act(state):\n    seat = state.bot_id\n    if seat not in _PLAYERS:\n        _PLAYERS[seat] = %s%s(seed=seat*7919, **%r)\n    return _PLAYERS[seat](state)\n' % (PREFIX[name],cls,options)
        body = source.encode()
        sha = hashlib.sha256(body).hexdigest()
        path = ROOT/'consolidation_candidates/branch_audit'/(sha+'.py')
        path.write_bytes(body)
        built = {}
        exec(compile(source,str(path),'exec'),built)
        originals = {s:getattr(modules[name],cls)(seed=s*7919,**options) for s in range(1,5)}
        game = Referee(mirror([[1,2,1,3],[2,3,2,1],[1,2,3,2],[3,1,2,3]]))
        calls = 0
        while not game.over():
            actions = []
            for seat in range(1,5):
                a = originals[seat](public(game,seat))
                b = built['act'](public(game,seat))
                if a!=b:
                    raise AssertionError((name,cls,label,seat,game.turn,a,b))
                actions.append(a)
                calls += 1
            game.step(actions)
        checks.append(dict(class_name=cls,variant=label,calls=calls,exact_actions=True))
        provenance = [dict(commit=COMMIT,path=paths[d],sha256=hashlib.sha256(raw[d]).hexdigest()) for d in deps]
        if name=='nnbot':
            provenance.append(dict(commit=COMMIT,path='nn_policy.json',sha256=hashlib.sha256(read('nn_policy.json')).hexdigest()))
        if label=='frozen_v1':
            provenance.append(dict(commit=COMMIT,path='pro_params_v1.json',sha256=hashlib.sha256(read('pro_params_v1.json')).hexdigest()))
        policies.append(dict(name='bot_'+sha[:12],sha256=sha,path=str(path.relative_to(ROOT)).replace('\\','/'),aliases=[dict(class_name=cls,module=paths[name],variant=label,commit=COMMIT)],registered_names=[cls+'_'+label],build_inputs=provenance))
    out.write_text(json.dumps(dict(policies=policies,build_equivalence=checks,scope='Class defaults, one previously frozen ProBot genotype, and embedded frozen PPO weights. No training or coefficient changes. Original-vs-build checks use 320 public callbacks per export.'),indent=2),encoding='utf8',newline='\n')
    print('Added %d class exports, %d exact-action equivalence callbacks' % (len(policies),sum(c['calls'] for c in checks)))

if __name__=='__main__':
    main()
