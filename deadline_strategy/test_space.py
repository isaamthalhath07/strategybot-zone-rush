"""Source/operator and scripted public-memory checks; no strength games."""
import ast
import copy
import unittest
from unittest.mock import patch

from deadline_strategy import space
from evolution.oversight import referee, signature, state_equal
from evolution_templates.space import TemplateSpace, literal_sites
from strategy_candidates.test_public_memory import path
from tests import reference_engine as engine


def masked(body,keys):
    for key,(begin,end,_) in sorted(literal_sites(body,keys).items(),key=lambda item:item[1][0],reverse=True):
        body = body[:begin]+b'<NUMERIC_LOCUS>'+body[end:]
    return body


class PublicMemorySpaceTests(unittest.TestCase):
    def test_default_exact_published_f5_and_original_numeric_loci(self):
        candidate = space.PublicMemoryTemplateSpace()
        numeric = TemplateSpace('original-blocker')
        body = candidate.export(candidate.defaults)
        self.assertEqual(space.sha(body),space.TEMPLATE_SHA256)
        self.assertEqual(body,(space.ROOT/'strategy_candidates/blocker_public_memory.py').read_bytes())
        self.assertEqual(candidate.defaults,numeric.defaults)
        self.assertEqual(candidate.bounds,numeric.bounds)
        self.assertEqual(len(candidate.bounds),12)
        self.assertEqual(candidate.inspect_export(body),candidate.defaults)
        description = candidate.description()
        self.assertFalse(description['admission_authority'])
        self.assertFalse(description['playing_strength_tested'])
        self.assertEqual(description['primary_credit'],0)
        self.assertEqual(description['bmcts_audits'],0)

    def test_mutation_crossover_change_only_canonical_numeric_bytes(self):
        candidate = space.PublicMemoryTemplateSpace()
        default = candidate.export(candidate.defaults)
        parent = candidate.defaults
        children = []
        for seed in range(32):
            genes = candidate.mutate(parent,seed)
            self.assertEqual(genes,candidate.mutate(parent,seed))
            self.assertNotEqual(genes,parent)
            self.assertLessEqual(sum(genes[k]!=parent[k] for k in genes),3)
            body = candidate.export(genes)
            self.assertEqual(masked(default,candidate.bounds),masked(body,candidate.bounds))
            self.assertEqual(candidate.inspect_export(body),genes)
            ast.parse(body)
            children.append(genes)
        crossed = candidate.crossover(children[0],children[-1],902)
        self.assertEqual(crossed,candidate.crossover(children[0],children[-1],902))
        self.assertEqual(candidate.inspect_export(candidate.export(crossed)),crossed)
        # A structural choice must be made explicitly; original bytes are not f5 exports.
        with self.assertRaises(ValueError):
            candidate.inspect_export(TemplateSpace('original-blocker').export(parent))

    def test_fail_closed_on_semantic_source_numeric_spelling_and_guard_drift(self):
        candidate = space.PublicMemoryTemplateSpace()
        body = candidate.export(candidate.defaults)
        for changed in (body+b'\n',body.replace(b'player.act(state)',b'player(state)'),
                        body.replace(b'seed=seat * 7919',b'seed=seat * 7920'),
                        body.replace(b'RHO0 = 0.5',b'RHO0 = 0.50')):
            with self.assertRaises(ValueError): candidate.inspect_export(changed)
        for key,value in (('_Core.RHO0',True),('_Core.PROT',float('nan')),('_Core.KEEP',1.1)):
            genes = candidate.defaults;genes[key] = value
            with self.assertRaises(ValueError): candidate.export(genes)
        genes = candidate.defaults;genes['private_rival_seed'] = 3
        with self.assertRaises(ValueError): candidate.export(genes)
        changed = space.source_pins();changed['deadline_strategy/space.py'] = '0'*64
        with patch.object(space,'source_pins',return_value=changed):
            with self.assertRaises(ValueError): candidate.export(candidate.defaults)

    def test_scripted_blocked_stay_fix_survives_numeric_mutation_and_public_indistinguishability(self):
        candidate = space.PublicMemoryTemplateSpace()
        for genes in (candidate.defaults,candidate.mutate(candidate.defaults,917)):
            namespace = {'__name__':'_synthetic_memory_test'}
            exec(compile(candidate.export(genes),'<f5-synthetic>','exec'),namespace)
            blocked = engine.Game(rules={'catch_requires_stay':True})
            tracker = namespace['BlockerBot'](seed=7919)
            for joint in path(own_final='EAST'):
                tracker._observe(blocked.views()[0]);tracker.last = joint[0]
                self.assertTrue(all(a in blocked.legal(s) for s,a in enumerate(joint)))
                blocked.step(joint)
            tracker._observe(blocked.views()[0])
            self.assertEqual(blocked.pos[0],5)  # Occupied cell6 blocked the accepted EAST.
            self.assertEqual(blocked.prog[0],1)
            self.assertEqual(tracker.prog,1)
            self.assertTrue(tracker._can_shield(3,26))
            worlds = []
            # Same public history and accepted own actions; rival hidden Shield
            # attribution differs. These scripts isolate memory, not decisions.
            for actions in (path(own_final='WEST'),
                            path(own_final='WEST',defender_final='SHIELD',raider_final='STAY')):
                game = engine.Game(rules={'catch_requires_stay':True})
                shadow = referee.Referee(game.base,start_token=game.token,rules=game.rules)
                tracker = namespace['BlockerBot'](seed=7919)
                public = []
                for joint in actions:
                    view = game.views()[0];before = signature(view)
                    tracker._observe(copy.deepcopy(view));tracker.last = joint[0]
                    public.append((before,joint[0]))
                    self.assertEqual(signature(view),before)
                    self.assertEqual(tracker.prog,game.prog[0])
                    self.assertEqual([tracker.score[s] for s in range(1,5)],game.score)
                    self.assertTrue(all(a in game.legal(s) for s,a in enumerate(joint)))
                    game.step(joint);shadow.step(joint);state_equal(game,shadow)
                tracker._observe(game.views()[0]);public.append(signature(game.views()[0]))
                self.assertEqual(tracker.prog,game.prog[0])
                worlds.append((game,tracker,public))
            self.assertEqual(worlds[0][2],worlds[1][2])
            self.assertNotEqual(worlds[0][0].cd,worlds[1][0].cd)
            first,second = worlds[0][1],worlds[1][1]
            self.assertEqual(first.__dict__,second.__dict__ | {'rng':first.rng})
            self.assertEqual(first._decide(worlds[0][0].views()[0]),second._decide(worlds[1][0].views()[0]))


if __name__=='__main__': unittest.main()
