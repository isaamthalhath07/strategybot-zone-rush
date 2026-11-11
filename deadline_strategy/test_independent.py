"""Immutable public-input mechanics only; no policy strength or GPU games."""
import copy
import unittest

from deadline_runner.actors import freeze_lane
from deadline_strategy.space import PublicMemoryTemplateSpace,sha,TEMPLATE_SHA256
from evolution.oversight import referee,signature,state_equal
from strategy_candidates.test_public_memory import path
from tests import reference_engine as engine


def public(game,seat):
    board=[[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points]
        for row in game.board_view() for c in row]
    legal=[[action in game.legal(s) for action in engine.ACTIONS] for s in range(4)]
    return freeze_lane(board,legal,[game.token==s+1 for s in range(4)])[seat]


class IndependentMemoryTests(unittest.TestCase):
    def test_exact_structural_template_and_no_foreign_code_or_focal_seed_change(self):
        space=PublicMemoryTemplateSpace();body=space.export(space.defaults)
        self.assertEqual(sha(body),TEMPLATE_SHA256)
        self.assertEqual(len(space.defaults),12)
        for genes in (space.defaults,space.mutate(space.defaults,212),
                space.crossover(space.defaults,space.mutate(space.defaults,213),214)):
            candidate=space.export(genes)
            self.assertEqual(space.inspect_export(candidate),genes)
            self.assertEqual(candidate.count(b'player.act(state)'),1)
            self.assertEqual(candidate.count(b'seed=seat * 7919'),1)
            for changed in (candidate+b'\n# injected comment\n',
                    candidate.replace(b'seed=seat * 7919',b'seed=seat * 7920'),
                    candidate.replace(b'player.act(state)',b'"STAY"')):
                with self.assertRaises(ValueError): space.inspect_export(changed)

    def test_indistinguishable_private_worlds_stay_equal_with_shared_immutable_inputs(self):
        space=PublicMemoryTemplateSpace()
        for genes in (space.defaults,space.mutate(space.defaults,919)):
            namespace={'__name__':'_independent_public_only_memory'}
            exec(compile(space.export(genes),'<synthetic-f5>','exec'),namespace)
            worlds=[]
            for script in (path(own_final='WEST'),
                    path(own_final='WEST',defender_final='SHIELD',raider_final='STAY')):
                game=engine.Game(rules={'catch_requires_stay':True})
                shadow=referee.Referee(game.base,start_token=game.token,rules=game.rules)
                tracker=namespace['BlockerBot'](seed=7919)
                prefix=[]
                for joint in script:
                    view=public(game,0);before=signature(view)
                    tracker._observe(view)  # no game, shadow, types or RNG passed
                    tracker.last=joint[0]   # accepted own action, not a truth repair
                    prefix.append((before,joint[0]))
                    self.assertEqual(signature(view),before)
                    self.assertEqual(tracker.prog,game.prog[0])
                    self.assertEqual([tracker.score[s] for s in range(1,5)],game.score)
                    self.assertTrue(all(a in game.legal(s) for s,a in enumerate(joint)))
                    game.step(joint);shadow.step(joint);state_equal(game,shadow)
                view=public(game,0);tracker._observe(view);prefix.append(signature(view))
                worlds.append((game,tracker,prefix))
            self.assertEqual(worlds[0][2],worlds[1][2])
            self.assertNotEqual(worlds[0][0].cd,worlds[1][0].cd)
            left,right=worlds[0][1],worlds[1][1]
            self.assertEqual(left.__dict__,right.__dict__|{'rng':left.rng})
            self.assertEqual(left.rng.getstate(),right.rng.getstate())
            self.assertEqual(left._decide(public(worlds[0][0],0)),right._decide(public(worlds[1][0],0)))

    def test_blocked_accepted_move_is_work_under_immutable_views(self):
        space=PublicMemoryTemplateSpace();namespace={'__name__':'_independent_blocked_memory'}
        exec(compile(space.export(space.mutate(space.defaults,454)),
            '<synthetic-f5>','exec'),namespace)
        tracker=namespace['BlockerBot'](seed=7919);game=engine.Game()
        for joint in path(own_final='EAST'):
            tracker._observe(public(game,0));tracker.last=joint[0];game.step(joint)
        tracker._observe(public(game,0))
        self.assertEqual(game.pos[0],5)
        self.assertEqual(game.prog[0],1)
        self.assertEqual(tracker.prog,1)
        self.assertTrue(tracker._can_shield(3,26))


if __name__=='__main__': unittest.main()
