"""Generic contract tests copied into a portable release; no full policy game."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest

from simulator import server
from tests import reference_engine as engine

ROOT=Path(__file__).resolve().parents[1]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module; spec.loader.exec_module(module); return module


def signature(view):
    return (view.bot_id,view.is_priority_token,tuple(view.legal_actions),
        tuple((c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points) for row in view.board for c in row))


class PortableContractTests(unittest.TestCase):
    def test_exact_payload_fingerprints_and_no_external_policy_imports(self):
        manifest=json.loads((ROOT/'package_manifest.json').read_bytes())
        for name,digest in manifest['files'].items():
            path=(ROOT/name).resolve(); self.assertTrue(path.is_relative_to(ROOT)); self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest,name)
        release=json.loads((ROOT/'release_manifest.json').read_bytes())
        for name in ['bot.py']+[t['path'] for t in release['tester_bots']]:
            body=(ROOT/name).read_bytes(); self.assertTrue(server.standalone(body),name)
            tree=ast.parse(body); imports=set()
            for node in ast.walk(tree):
                if isinstance(node,ast.Import): imports.update(a.name.split('.')[0] for a in node.names)
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse(node.level); imports.add(node.module.split('.')[0])
            self.assertFalse(imports-set(sys.stdlib_module_names),name)
        self.assertEqual(release['bot_sha256'],manifest['selected_source_sha256'])

    def test_catalog_selects_only_pinned_local_sources_and_bundled_harness(self):
        catalog=server.Catalog(); self.assertFalse(catalog.warnings)
        manifest=json.loads((ROOT/'release_manifest.json').read_bytes())
        self.assertEqual(catalog.recommended_id,manifest['bot_sha256'][:20])
        self.assertEqual({entry['path'] for entry in catalog.entries.values()},{'bot.py',*(t['path'] for t in manifest['tester_bots'])})
        _match,_referee,_sources,provenance=server.bootstrap()
        for name,digest in provenance['files'].items():
            self.assertEqual(hashlib.sha256((server.VENDOR/name).read_bytes()).hexdigest(),digest)
        self.assertIs(server.NEW_GAME_RULES['catch_requires_stay'],True)

    def test_one_public_opening_per_policy_is_legal_unchanged_and_on_time(self):
        release=json.loads((ROOT/'release_manifest.json').read_bytes())
        names=['bot.py']+[t['path'] for t in release['tester_bots']]
        for index,name in enumerate(names):
            with self.subTest(policy=name):
                module=load(ROOT/name,'portable_contract_%d'%index); game=engine.Game(rules={'catch_requires_stay':True})
                view=game.views()[0]; before=signature(view); started=time.perf_counter(); action=module.act(view); elapsed=time.perf_counter()-started
                self.assertIs(type(action),str); self.assertIn(action,view.legal_actions); self.assertLessEqual(elapsed,2)
                self.assertEqual(signature(view),before)
                self.assertFalse(getattr(module,'_input_failures',0)); self.assertFalse(getattr(module,'_policy_failures',0))
                # This is an opening contract check, not a completed game or a
                # tracker-specific assumption about the selected architecture.


if __name__=='__main__': unittest.main()
