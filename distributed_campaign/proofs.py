"""Proof validation without inventing legacy oracles for other architectures."""
import ast
from functools import lru_cache
from pathlib import Path

from distributed_campaign import protocol as p
from evolution import oversight


def legacy_tracker(path, expected_sha):
    body = Path(path).read_bytes()
    if p.sha(body) != expected_sha:
        raise ValueError('Actor source changed during oracle schema inspection')
    return _legacy_body(body)


@lru_cache(maxsize=256)
def _legacy_body(body):
    tree = ast.parse(body)
    names = {target.id for node in tree.body if isinstance(node,ast.Assign)
             for target in node.targets if isinstance(target,ast.Name)}
    return '_history' in names and any(isinstance(node,ast.FunctionDef) and node.name == '_infer_shields' for node in tree.body)


def expected_oracles(candidate, fixture, sources):
    count = int(legacy_tracker(candidate['path'], candidate['sha256']))
    for spec in fixture['opponents']:
        if spec['family'] in ('planner','research','racer','blocker'):
            source = sources[spec['family']]
            count += int(legacy_tracker(source['path'],source['sha256']))
    return 80*count


def validate(proof, row, candidate, fixture, sources):
    if (proof['fixture'] != row['fixture'] or proof['candidate'] != row['candidate']
            or proof['row_sha256'] != p.sha(p.canonical(row))
            or proof['proof_kind'] != 'dual_referee_fresh_actor_regeneration'
            or proof['all_actors_regenerated'] is not True
            or proof['referee_sha256'] != oversight.REFEREE_SHA or proof['engine_sha256'] != oversight.ENGINE_SHA
            or proof['oversight_sha256'] != p.sha(Path(oversight.__file__).read_bytes())
            or type(proof['callbacks_regenerated']) is not int or proof['callbacks_regenerated'] != 320
            or type(proof['public_memory_oracles']) is not int
            or proof['public_memory_oracles'] != expected_oracles(candidate,fixture,sources)):
        raise ValueError('Full-actor proof has incomplete/foreign/incorrect source-specific coverage')
