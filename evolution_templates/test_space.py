import ast
import copy
import math
import unittest

from .space import TemplateSpace,literal_sites,replace_literals


class AuthorTemplateTests(unittest.TestCase):
    def test_default_exports_are_identical_originals_with_the_same_direct_entry_points(self):
        for family,active in (('original-blocker','BlockerBot'),('original-feint','FeintBot')):
            with self.subTest(family=family):
                space=TemplateSpace(family)
                body=space.export(space.defaults)
                self.assertEqual(body,space.path.read_bytes())
                self.assertEqual(space.inspect_export(body),space.defaults)
                tree=ast.parse(body)
                entry=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='act')
                constructors=[n for n in ast.walk(entry) if isinstance(n,ast.Call)
                              and isinstance(n.func,ast.Name) and n.func.id in ('BlockerBot','FeintBot','RacerBot')]
                self.assertEqual([n.func.id for n in constructors],[active])
                self.assertIsInstance(entry.body[-1],ast.Return)
                self.assertEqual(entry.body[-1].value.func.attr,'act')

    def test_byte_spans_preserve_unicode_prefixes_crlf_and_comment_numbers(self):
        body=("# exact header\r\nclass _Core:\r\n    'é'; ALPHA = 0.34  # unchanged0.34\r\n"
              "    KEEP = 0.8  # compass🧭\r\n").encode('utf-8')
        sites=literal_sites(body,{'_Core.ALPHA','_Core.KEEP'})
        expected=body.replace(b'ALPHA = 0.34',b'ALPHA = 0.7').replace(b'KEEP = 0.8',b'KEEP = 0.9')
        changed=replace_literals(body,sites,{'_Core.ALPHA':0.7,'_Core.KEEP':0.9})
        self.assertEqual(changed,expected)
        self.assertEqual(changed.count(b'\r\n'),body.count(b'\r\n'))
        self.assertIn('é'.encode(),changed)
        self.assertIn('🧭'.encode(),changed)
        ast.parse(changed)

    def test_seeded_bounded_mutations_remain_distinct_standalone_exports(self):
        for family in ('original-blocker','original-feint'):
            space=TemplateSpace(family);parent=space.defaults;original=copy.deepcopy(parent)
            for seed in range(50):
                child=space.mutate(parent,seed)
                self.assertEqual(child,space.mutate(parent,seed))
                self.assertTrue(1<=sum(child[k]!=parent[k] for k in child)<=3)
                body=space.export(child)
                self.assertEqual(space.inspect_export(body),child)
                compile(body,'<standalone-numeric-variant>','exec')
            self.assertEqual(parent,original)
            self.assertNotEqual(space.mutate(parent,17,scale=1e-20),parent)

    def test_grouped_crossover_copies_parent_values_without_cross_family_genes(self):
        for family in ('original-blocker','original-feint'):
            space=TemplateSpace(family);first=space.defaults;second=space.mutate(first,91)
            for seed in range(10):
                child=space.crossover(first,second,seed)
                self.assertEqual(child,space.crossover(first,second,seed))
                self.assertTrue(all(child[k] in (first[k],second[k]) for k in child))
                self.assertEqual(space.inspect_export(space.export(child)),child)
        with self.assertRaises(ValueError):
            TemplateSpace('original-blocker').crossover(TemplateSpace('original-blocker').defaults,
                                                       TemplateSpace('original-feint').defaults,1)

    def test_metadata_and_invalid_values_cannot_create_qualification_or_unbounded_genes(self):
        space=TemplateSpace('original-blocker')
        for bad in (True,float('nan'),float('inf'),10**1000,'0.4',None):
            with self.subTest(value_type=type(bad).__name__):
                genes=space.defaults;genes['_Core.ALPHA']=bad
                with self.assertRaises(ValueError):space.export(genes)
        for seed in (True,-1,2**128,1.5):
            with self.assertRaises(ValueError):space.mutate(space.defaults,seed)
        for scale in (False,0,-1,float('nan'),.251):
            with self.assertRaises(ValueError):space.mutate(space.defaults,3,scale=scale)
        description=space.description()
        self.assertFalse(description['runtime_qualified'])
        self.assertFalse(description['playing_strength_tested'])
        self.assertEqual(description['primary_credit'],0)
        self.assertEqual(description['bmcts_audits'],0)


if __name__=='__main__':
    unittest.main()
