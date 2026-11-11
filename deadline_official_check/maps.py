"""Freeze64 official-generator maps from metadata only; never call a policy."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

from primary_migration.contract import rotation_orbit,validate_catalog_bytes

ROOT=Path(__file__).resolve().parents[1]
FORMAT='deadline-official-generator-release-check-maps/1'
COUNT=64
GENERATOR='simulator/vendor_harness/referee.py'
GENERATOR_SHA256='f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337'
INPUTS={
    '.cache/primary/campaign_v1_20261109/catalog.json':'311b51f5eef35402f88887bd18f54053fedf923cc17d3b8b13d6d1e2142f794f',
    '.cache/confirmation/architectures_v2_001/registration.json':'b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9',
    'confirmation_campaign/evidence/architectures_v2/consumed_map_specs.zip':'b114f25deebe965aed3556e590afe9af87db1884116dc8c5908f93e946aed966',
    'validation/official/final_spec.json':'d0bd30cbc1cfcb20a69fe0964bf07c2beb3f1ec0263652eb5179832976f9657d',
    'validation/official/followup_spec.json':'3f61584f0fa5e51950ccba001e950062d379d37cb69d594c6b31fded8c887a29',
    'validation/official/screen_spec.json':'97f6a7c12f395e54b8e4e960c359a651a4fe7231992edce0e218b86762ad648f',
    'validation/official/selection_spec.json':'c504ade09918bfdc8c272a5678518f0e65ba29e09d0c9244e13c80c3db8ff466',
    'validation/official/ultimate_spec.json':'9c3ae48748f2c5bcfc3508aa0f08599fb29e3af2e63a48b75d4b66352c1c1208',
    'deadline_release/evidence/reference_e8.zip':'adb3119397cf6cf2098bd65666cc8ced6188ff8f73f33211da02ba4f8126b6b1',
}
SMOKE_SEED=2026110971


def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def sha(body): return hashlib.sha256(body).hexdigest()


def generator():
    path=ROOT/GENERATOR
    if sha(path.read_bytes())!=GENERATOR_SHA256: raise ValueError('Official generator source changed')
    spec=importlib.util.spec_from_file_location('_official_map_generator_only',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.random_map


def _boards(value):
    """Read only known metadata containers, never a result/games container."""
    if type(value) is list:
        for child in value: yield from _boards(child)
    elif type(value) is dict:
        if 'base' in value:
            base=value['base']
            if type(base) is not list or len(base)!=64 or any(type(v) is not int or v not in (1,2,3) for v in base):
                raise ValueError('Malformed exclusion map metadata')
            yield base
        for key in ('fixtures','maps','boards','registration','spec'):
            if key in value: yield from _boards(value[key])


def exclusions():
    excluded=set();records=[]
    for name,expected in INPUTS.items():
        path=ROOT/name;body=path.read_bytes()
        if sha(body)!=expected: raise ValueError('Pinned map exclusion input changed: '+name)
        if name.endswith('reference_e8.zip'):
            orbits={rotation_orbit(generator()(SMOKE_SEED))};members=[]
        elif name.endswith('.zip'):
            orbits=set();members=[]
            with zipfile.ZipFile(path) as archive:
                names=sorted(archive.namelist())
                if len(names)!=11 or any(not n.endswith('_spec.json') or not n.startswith('validation/branch_audit/') for n in names):
                    raise ValueError('Only the exact eleven metadata spec members are admissible')
                for member in names:
                    raw=archive.read(member);found={rotation_orbit(b) for b in _boards(json.loads(raw))}
                    if not found: raise ValueError('Empty public consumed map spec')
                    orbits.update(found);members.append(dict(path=member,sha256=sha(raw),map_orbits=len(found)))
        else:
            data=json.loads(body)
            if name.endswith('/catalog.json'): validate_catalog_bytes(body,expected)
            orbits={rotation_orbit(b) for b in _boards(data)};members=[]
            if name.endswith('/catalog.json') and len(orbits)!=10000: raise ValueError('Entire primary catalog must be excluded')
            if name.endswith('architectures_v2_001/registration.json') and len(orbits)!=128: raise ValueError('Entire quad128 panel must be excluded')
            if not orbits: raise ValueError('Empty map exclusion input')
        excluded.update(orbits)
        records.append(dict(path=name,sha256=expected,unique_rotation_orbits=len(orbits),members=members))
    return excluded,dict(inputs=records,unique_rotation_orbits=len(excluded),
        sorted_rotation_orbits_sha256=sha(canonical(sorted(excluded))),known_reference_smoke_seed=SMOKE_SEED)


def build(excluded,proof,random_map=None):
    """Deterministic rejection/deduplication, before any policy source is chosen."""
    random_map=generator() if random_map is None else random_map
    selected=[];used=set(excluded);ledger=[]
    for ordinal in range(1000000):
        seed=int.from_bytes(hashlib.sha256(canonical([FORMAT,'fresh-official-map',ordinal])).digest()[:8],'big')
        base=random_map(seed);orbit=rotation_orbit(base)
        accepted=orbit not in used
        ledger.append(dict(ordinal=ordinal,seed=seed,map_id=sha(bytes(base)),rotation_orbit=orbit,accepted=accepted))
        if accepted:
            index=len(selected);used.add(orbit)
            selected.append(dict(map_index=index,id=sha(bytes(base)),seed=seed,base=base,rotation_orbit=orbit,
                generator_ordinal=ordinal,family='official-vendor-random-map',phase='official-release-check'))
            if len(selected)==COUNT: break
    if len(selected)!=COUNT: raise ValueError('Fixed official map selection exhausted; no alternative generator')
    return dict(format=FORMAT,generator=dict(path=GENERATOR,sha256=GENERATOR_SHA256,
        slope=[.33,.58],noise=[.25,.75],home_points_at_most=2),maps=selected,selection_ledger=ledger,
        exclusions=proof,selection='First64 fresh distinct rotation orbits under fixed domain-hashed64bit seeds; no action/outcome/source input.',
        scope='Conditional on rejection of prior consumed/reserved and duplicate orbits; not an unconditional iid seed sample.',
        metadata_only=True,executed_games=0,primary_campaign_credit=0,bmcts_credit=0)


def freeze(path):
    path=Path(path);excluded,proof=exclusions();value=build(excluded,proof)
    value['created_utc']=datetime.now(timezone.utc).isoformat();body=canonical(value)+b'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream: stream.write(body)
    with path.with_suffix('.sha256').open('x',encoding='ascii') as stream: stream.write(sha(body)+'\n')
    return value


def validate(path):
    path=Path(path);body=path.read_bytes();value=json.loads(body)
    if body!=canonical(value)+b'\n' or path.with_suffix('.sha256').read_text().strip()!=sha(body):
        raise ValueError('Frozen official map artifact changed')
    timestamp=value.get('created_utc');parsed=datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None: raise ValueError('Explicit map-freeze UTC timestamp required')
    excluded,proof=exclusions();expected=build(excluded,proof);expected['created_utc']=timestamp
    if canonical(value)!=canonical(expected): raise ValueError('Official map plan semantic drift')
    return value
