"""Independent exact-byte template checks and short synthetic public mechanics.

No GPU, actual study result, qualification or playing-strength game is used.
"""
import ast
import builtins
import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import reference_engine as ref
from . import space as model


ROOT=Path(__file__).resolve().parents[1]
TEMPLATES={
    'original-blocker':('tester_bots/blocker.py','1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5'),
    'original-feint':('confirmation_campaign/evidence/architectures_v2/feint_original.py','f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94')}
COMMON={'_Core.ALPHA','_Core.RHO0','_Core.STAY0','_Core.PROT','_Core.KEEP',
        '_Core.CLAIM_THR','_Core.SHW','_Core.AGG0','_Core.CONF'}


def independent_sites(body):
    """Locate every direct class literal without using the production parser."""
    lines=body.splitlines(keepends=True)
    starts=[sum(map(len,lines[:index])) for index in range(len(lines))]
    result={}
    for cls in ast.parse(body).body:
        if not isinstance(cls,ast.ClassDef): continue
        for node in cls.body:
            if (isinstance(node,ast.Assign) and len(node.targets)==1
                    and isinstance(node.targets[0],ast.Name)):
                key=cls.name+'.'+node.targets[0].id
                result[key]=(starts[node.value.lineno-1]+node.value.col_offset,
                             starts[node.value.end_lineno-1]+node.value.end_col_offset)
    return result


def mask_mutable(body,keys):
    result=body
    for key,(begin,end) in sorted(independent_sites(body).items(),key=lambda item:item[1][0],reverse=True):
        if key in keys: result=result[:begin]+('<'+key+'>').encode()+result[end:]
    return result


class IndependentTemplateTests(unittest.TestCase):
    def test_exact_default_bytes_and_active_class_qualified_12_10_gene_sets(self):
        for family,(relative,expected) in TEMPLATES.items():
            with self.subTest(family=family):
                space=model.TemplateSpace(family);body=(ROOT/relative).read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(),expected)
                self.assertEqual(space.export(space.defaults),body)
                self.assertEqual(space.inspect_export(body),space.defaults)
                keys=COMMON|({'_Core.HOP_RISK','BlockerBot.LEADER_BUMP','BlockerBot.DENY'}
                    if family=='original-blocker' else {'FeintBot.HOP_RISK'})
                self.assertEqual(set(space.defaults),keys);self.assertEqual(set(space.bounds),keys)
                self.assertEqual(len(keys),12 if family=='original-blocker' else 10)
                self.assertNotIn('_Core.CLAIM_BONUS_SHARE',keys)
                self.assertNotIn('BlockerBot.CLAIM_BONUS_SHARE',keys)
                self.assertNotIn('RacerBot.R_FIRST',keys)

    def test_only_active_literal_bytes_change_and_entrypoint_imports_remain_exact(self):
        for family,(relative,_) in TEMPLATES.items():
            space=model.TemplateSpace(family);body=(ROOT/relative).read_bytes()
            genes={key:(low+high)/2 for key,(low,high) in space.bounds.items()}
            child=space.export(genes)
            self.assertEqual(space.inspect_export(child),genes)
            self.assertEqual(mask_mutable(body,space.defaults),mask_mutable(child,space.defaults))
            self.assertEqual(child.count(b'\n'),body.count(b'\n'));self.assertNotIn(b'\r',child)
            old_tree,new_tree=ast.parse(body),ast.parse(child)
            imports=lambda tree:[ast.dump(n) for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
            self.assertEqual(imports(old_tree),imports(new_tree))
            self.assertEqual(imports(new_tree),[ast.dump(ast.parse('import random').body[0])])
            entry=lambda tree:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='act')
            self.assertEqual(ast.dump(entry(old_tree)),ast.dump(entry(new_tree)))
            self.assertIn(b'return player.act(state)',child)
            all_sites=independent_sites(child)
            if family=='original-blocker':
                begin,end=all_sites['FeintBot.HOP_RISK'];self.assertEqual(child[begin:end],b'0.3')
            else:
                begin,end=all_sites['_Core.HOP_RISK'];self.assertEqual(child[begin:end],b'0.45')

    def test_utf8_columns_comments_and_crlf_preserve_every_unselected_byte(self):
        body="# π\r\nclass _Core:\r\n    étiquette = '☃'; ALPHA = 0.34  # défense\r\n".encode('utf8')
        sites=model.literal_sites(body,{'_Core.ALPHA'})
        begin,end,prior=sites['_Core.ALPHA']
        self.assertEqual(body[begin:end],b'0.34');self.assertEqual(prior,.34)
        child=model.replace_literals(body,sites,{'_Core.ALPHA':.125})
        self.assertEqual(child,body.replace(b'0.34',b'0.125'))
        self.assertEqual(child.count(b'\r\n'),body.count(b'\r\n'))
        self.assertIn('étiquette'.encode(),child);self.assertIn('# défense'.encode(),child)

    def test_inactive_classes_flags_costs_seed_entrypoint_comments_and_line_endings_reject(self):
        for family,(relative,_) in TEMPLATES.items():
            space=model.TemplateSpace(family);body=(ROOT/relative).read_bytes()
            attacks=[body.replace(b'POOL = 22',b'POOL = 23'),body.replace(b'K1 = 8',b'K1 = 9'),
                body.replace(b'BAIT = False',b'BAIT = True'),body.replace(b'DYN = True',b'DYN = False'),
                body.replace(b'CLAIM_BONUS_SHARE = 1.0',b'CLAIM_BONUS_SHARE = 0.5'),
                body.replace(b'R_FIRST = 0.15',b'R_FIRST = 0.2'),
                body.replace(b'seed=seat * 7919',b'seed=seat * 7918'),
                body.replace(b'return player.act(state)',b'return player(state)'),
                body.replace(b'import random',b'import random\nimport os'),
                body.replace(b'for _p in range(64):',b'for _p in range(63):'),
                body+b'# harmless-looking comment\n',body.replace(b'\n',b'\r\n'),
                body.replace(b'# weight of damage', '# poids éthique de damage'.encode()),
                body+b'\nclass _Core:\n    ALPHA = 0.34\n',
                body.replace(b'    ALPHA = 0.34',b'    ALPHA = 0.34\n    ALPHA = 0.34')]
            inactive=b'HOP_RISK = 0.3' if family=='original-blocker' else b'HOP_RISK = 0.45'
            attacks.append(body.replace(inactive,b'HOP_RISK = 0.31'))
            for index,attack in enumerate(attacks):
                self.assertNotEqual(attack,body)
                with self.subTest(family=family,attack=index),self.assertRaises(ValueError): space.inspect_export(attack)

    def test_expressions_boolean_nonfinite_and_foreign_genes_fail_without_execution(self):
        original_import=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='SYNTHETIC_EVIL_NEVER_IMPORT': raise AssertionError('Candidate executed during inspection')
            return original_import(name,*args,**kwargs)
        for family,(relative,_) in TEMPLATES.items():
            space=model.TemplateSpace(family);body=(ROOT/relative).read_bytes()
            for literal in (b'True',b'None',b'1e309',b'0.1 + 0.24',b"float('nan')",
                            b"__import__('SYNTHETIC_EVIL_NEVER_IMPORT')",b'(lambda: 0.34)()'):
                candidate=body.replace(b'ALPHA = 0.34',b'ALPHA = '+literal)
                with self.subTest(family=family,literal=literal),patch.object(builtins,'__import__',side_effect=guarded),self.assertRaises(ValueError):
                    space.inspect_export(candidate)
            for value in (True,float('nan'),float('inf'),-float('inf'),10**1000,'0.34',lambda:None):
                genes=space.defaults;genes['_Core.ALPHA']=value
                with self.subTest(value=str(value)[:30]),self.assertRaises(ValueError): space.export(genes)
            for change in ('extra','deleted','wrong_class'):
                genes=space.defaults
                if change=='extra': genes['_Core.POOL']=22
                elif change=='deleted': genes.pop('_Core.ALPHA')
                else: genes['UnknownClass.ALPHA']=genes.pop('_Core.ALPHA')
                with self.assertRaises(ValueError): space.export(genes)
            foreign=model.TemplateSpace('original-feint' if family=='original-blocker' else 'original-blocker')
            with self.assertRaises(ValueError): space.export(foreign.defaults)
            with self.assertRaises(ValueError): space.crossover(space.defaults,foreign.defaults,7)
            with self.assertRaises(ValueError): space.inspect_export(foreign.export(foreign.defaults))

    def test_public_metadata_edits_cannot_relax_bounds_or_change_defaults(self):
        for family in TEMPLATES:
            space=model.TemplateSpace(family);original=space.defaults
            bounds=space.bounds;bounds['_Core.RHO0']=(0,100);bounds['_Core.POOL']=(1,64)
            defaults=space.defaults;defaults['_Core.RHO0']=50;defaults['_Core.POOL']=22
            self.assertEqual(space.defaults,original)
            self.assertNotIn('_Core.POOL',space.bounds)
            self.assertEqual(space.bounds['_Core.RHO0'],(.01,.99))
            illegal=space.defaults;illegal['_Core.RHO0']=50
            with self.assertRaises(ValueError): space.export(illegal)

    def test_every_source_operation_quarantines_changed_template_bytes(self):
        actual_read=Path.read_bytes
        for family,(relative,_) in TEMPLATES.items():
            path=ROOT/relative;space=model.TemplateSpace(family);body=actual_read(path)
            def changed(target):
                content=actual_read(target)
                return content+b'\n' if target==path else content
            with patch.object(Path,'read_bytes',changed):
                with self.assertRaises(ValueError): model.TemplateSpace(family)
                for operation in (lambda:space.export(space.defaults),lambda:space.inspect_export(body),
                                  lambda:space.mutate(space.defaults,8),lambda:space.crossover(space.defaults,space.defaults,8)):
                    with self.assertRaisesRegex(ValueError,'QUARANTINED'): operation()

    def test_seeded_mutation_crossover_bounds_and_change_limits(self):
        for family in TEMPLATES:
            space=model.TemplateSpace(family);parent=space.defaults
            for seed in range(12):
                child=space.mutate(parent,seed,scale=.06,max_changes=3)
                self.assertEqual(child,space.mutate(parent,seed,scale=.06,max_changes=3))
                self.assertTrue(1<=sum(child[key]!=parent[key] for key in parent)<=3)
                self.assertEqual(set(child),set(parent))
                self.assertTrue(all(low<=child[key]<=high for key,(low,high) in space.bounds.items()))
                self.assertEqual(space.inspect_export(space.export(child)),child)
                crossed=space.crossover(parent,child,seed)
                self.assertEqual(crossed,space.crossover(parent,child,seed))
                self.assertTrue(all(crossed[key] in (parent[key],child[key]) for key in parent))
            for kwargs in (dict(seed=True),dict(seed=-1),dict(seed=2**128),dict(seed=0,scale=0),
                           dict(seed=0,scale=float('nan')),dict(seed=0,max_changes=True),dict(seed=0,max_changes=4)):
                with self.assertRaises(ValueError): space.mutate(parent,**kwargs)

    def test_short_synthetic_direct_entrypoint_mutants_are_legal_without_catching_fallback(self):
        callbacks=0
        for family in TEMPLATES:
            space=model.TemplateSpace(family)
            for genes in (space.defaults,space.mutate(space.defaults,421,scale=.01,max_changes=1)):
                body=space.export(genes)
                namespace={'__name__':'SYNTHETIC_TEMPLATE_PREFIX_ONLY'}
                exec(compile(body,'SYNTHETIC_TEMPLATE_PREFIX_ONLY','exec'),namespace)
                def prohibited_fallback(*args): raise AssertionError('Broad __call__ fallback wrapper invoked')
                namespace['_Core'].__call__=prohibited_fallback
                decide=namespace['_Core']._decide
                def checked_decide(player,view,original=decide):
                    action=original(player,view)
                    self.assertIs(type(action),str);self.assertIn(action,view.legal_actions)
                    return action
                namespace['_Core']._decide=checked_decide
                game=ref.Game(rules={'catch_requires_stay':True})
                for _ in range(8):
                    supplied=copy.deepcopy(game.views()[0])
                    signature=lambda v:(v.bot_id,v.is_priority_token,tuple(v.legal_actions),
                        tuple((c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points) for row in v.board for c in row))
                    before=signature(supplied)
                    action=namespace['act'](supplied);callbacks+=1
                    self.assertIn(action,game.legal(0));self.assertEqual(signature(supplied),before)
                    game.step([action,'STAY','STAY','STAY'])
        self.assertEqual(callbacks,32)


if __name__=='__main__': unittest.main()
