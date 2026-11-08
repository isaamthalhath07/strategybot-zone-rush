"""Read-only planning checks. A valid schedule never certifies played games.

No actor, referee, campaign writer, network client or MAC authority is imported.
The continuation executor, source-family exporters and admission gate do not yet
exist. This module must not be used as evidence that a match was executed.
"""
from collections import Counter
import hashlib
import json


FIELDS = ('economic','independent','erratic','pressure')
PHASES = (('train',0,8000),('development',8000,9000),('final',9000,10000))
GOAL = 2_000_000
EPISODES = 200
BLOCK = 100
FORMAT = 'zone-rush-primary-migration-design-contract/0'
ORIGINAL_CATALOG_SHA256 = '311b51f5eef35402f88887bd18f54053fedf923cc17d3b8b13d6d1e2142f794f'
ANCHORS = {
    'e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5': ('e8-config',80),
    '50d82d7ac58162e9cf651136afcedac5586db9a060f153854b00875f13efef37': ('e8-config',80),
    '1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5': ('original-blocker',0),
    'f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94': ('original-feint',0),
}


def _integer(value,low,high):
    if type(value) is not int or not low <= value < high:
        raise ValueError('Invalid integer planning coordinate')
    return value


def _hash(value):
    if type(value) is not str or len(value)!=64 or any(character not in '0123456789abcdef' for character in value):
        raise ValueError('Expected exact lowercase SHA256')
    return value


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def _strict_json(body):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('Nonfinite JSON constant')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=reject)


def rotation_orbit(base):
    current,variants = list(base),[]
    for _ in range(4):
        variants.append(bytes(current))
        current = [current[(7-column)*8+row] for row in range(8) for column in range(8)]
    return min(variants).hex()


def validate_catalog_bytes(body,expected_sha256):
    """Validate unchanged catalog CONTENT only; not raw game/admission proofs."""
    if _hash(expected_sha256)!=ORIGINAL_CATALOG_SHA256 or _sha(body) != expected_sha256:
        raise ValueError('Original catalog bytes changed')
    catalog = _strict_json(body)
    if type(catalog) is not list or len(catalog)!=10000:
        raise ValueError('The existing exact ten-thousand-map catalog is required')
    ids,seeds,orbits = set(),set(),set()
    for index,board in enumerate(catalog):
        phase,start,_ = next(item for item in PHASES if item[1] <= index < item[2])
        base = board['base']
        if (type(board['map_index']) is not int or board['map_index']!=index
                or board['phase']!=phase or type(board['phase_index']) is not int
                or board['phase_index']!=index-start or type(base) is not list or len(base)!=64
                or any(type(value) is not int or value not in (1,2,3) for value in base)
                or any(base[row*8+column]!=base[row*8+7-column] or base[row*8+column]!=base[(7-row)*8+column]
                       for row in range(8) for column in range(8))):
            raise ValueError('Map content/index/phase differs from the original shape')
        identity = _sha(bytes(base))
        orbit = rotation_orbit(base)
        seed = _integer(board['seed'],0,1<<64)
        if (identity!=board['id'] or identity in ids or seed in seeds or orbit in orbits
                or board['rotation_orbit']!=orbit):
            raise ValueError('Duplicate, rotated, relabeled or changed catalog map')
        ids.add(identity)
        seeds.add(seed)
        orbits.add(orbit)
    return dict(format=FORMAT,catalog_maps=10000,train_maps=8000,development_maps=1000,final_maps=1000,
                scheduled_primary_slots=GOAL,certifies_executed_games=False,new_primary_credit=0)


def planned_budget(declared_legacy_stages):
    """Accounting for a declared prefix; deliberately NOT an admission check."""
    if type(declared_legacy_stages) not in (tuple,list):
        raise ValueError('Explicit ordered declared stage indices required')
    for index in declared_legacy_stages:
        _integer(index,0,80)
    if list(declared_legacy_stages)!=list(range(len(declared_legacy_stages))):
        raise ValueError('Legacy declaration is copied, gapped or reordered')
    stages = len(declared_legacy_stages)
    return dict(format=FORMAT,status='PROPOSED_ACCOUNTING_ONLY',declared_legacy_stages=stages,
                declared_legacy_slots=stages*20000,remaining_train_stages=80-stages,
                remaining_train_maps=8000-stages*100,remaining_train_slots=1_600_000-stages*20000,
                reserved_development_slots=200000,reserved_final_slots=200000,total_primary_slots=GOAL,
                certifies_executed_games=False,new_primary_credit=0)


def slot_schedule(map_index,episode):
    """Closed-form equivalent of the existing pair-occurrence schedule."""
    _integer(map_index,0,10000)
    _integer(episode,0,200)
    phase,start,_ = next(item for item in PHASES if item[1] <= map_index < item[2])
    block = (map_index-start)//100
    occurrence_start = (map_index//100)*100 if phase=='train' else start
    seat = episode%4
    token = (episode//4+seat+map_index)%4+1
    prior_maps = map_index-occurrence_start
    # Each completed board contributes12 or13 occurrences of a given pair.
    n = 12*prior_maps+2*(prior_maps//4)
    for prior in range(occurrence_start+4*(prior_maps//4),map_index):
        n += int((token-1-seat-prior)%4 < 2)
    residue = (token-1-seat-map_index)%4
    n += max(0,(episode//4+3-residue)//4)
    candidate = (n+4*seat+token-1)%8 if phase!='final' else 0
    field = FIELDS[(n//8+n%8+2*seat+token-1)%4]
    return dict(map_index=map_index,episode=episode,phase=phase,stage_index=map_index//100 if phase=='train' else block,
                seat=seat,token=token,candidate_slot=candidate,field=field,canonical_slot=200*map_index+episode)


def rival_seed(map_index,episode,rival_seat):
    schedule = slot_schedule(map_index,episode)
    _integer(rival_seat,0,4)
    if rival_seat==schedule['seat']:
        raise ValueError('A rival seed cannot be claimed as hidden focal initialization')
    return (1<<64)+4*schedule['canonical_slot']+rival_seat


def rival_identity(version_id,map_index,episode,rival_seat,spec_sha256):
    """Instance provenance only; no source or seed is passed in the actor View."""
    seed = rival_seed(map_index,episode,rival_seat)
    return _sha(_canonical(dict(protocol='primary-continuation/2',version=_hash(version_id),
                               map_index=map_index,episode=episode,seat=rival_seat,seed=seed,
                               full_registered_spec_sha256=_hash(spec_sha256))))


def seed_key(value):
    """Lossless SQLite BLOB key for old64-bit and prospective65-bit seeds."""
    return _integer(value,0,1<<65).to_bytes(9,'big')


def validate_schedule(descriptors,start_map,map_count,phase):
    """Validate planning descriptors; this function never consumes game rows."""
    _integer(start_map,0,10000)
    _integer(map_count,1,10001)
    if phase not in {item[0] for item in PHASES}:
        raise ValueError('Unknown declared phase')
    lower,upper = next((item[1],item[2]) for item in PHASES if item[0]==phase)
    if not lower<=start_map<start_map+map_count<=upper:
        raise ValueError('Schedule crosses a reserved phase boundary')
    seen,counts,cells,pairs = set(),Counter(),Counter(),Counter()
    for descriptor in descriptors:
        if type(descriptor) is not dict:
            raise ValueError('Plain planning descriptor required')
        expected = slot_schedule(descriptor['map_index'],descriptor['episode'])
        if set(descriptor)!=set(expected):
            raise ValueError('Unregistered planning fields')
        for key,value in expected.items():
            if type(descriptor.get(key)) is not type(value) or descriptor[key]!=value:
                raise ValueError('Changed candidate/seat/token/field/phase planning assignment')
        key = descriptor['map_index'],descriptor['episode']
        if key in seen or not start_map<=key[0]<start_map+map_count:
            raise ValueError('Duplicate or foreign catalog slot')
        seen.add(key)
        counts[descriptor['candidate_slot']] += 1
        pairs[descriptor['candidate_slot'],descriptor['seat'],descriptor['token']] += 1
        cells[descriptor['candidate_slot'],descriptor['seat'],descriptor['token'],descriptor['field']] += 1
    if len(seen)!=map_count*200:
        raise ValueError('Incomplete planning slot coverage')
    return dict(planning_slots_checked=len(seen),candidate_counts=dict(counts),
                candidate_pair_min=min(pairs.values()),candidate_pair_max=max(pairs.values()),
                observed_candidate_cells=len(cells),certifies_executed_games=False,new_primary_credit=0)


class SlotReservations:
    """In-memory conflict demonstration, not a persistent credit authority."""
    def __init__(self,catalog_sha256):
        self.catalog_sha256 = _hash(catalog_sha256)
        if self.catalog_sha256!=ORIGINAL_CATALOG_SHA256:
            raise ValueError('Another catalog cannot acquire this campaign slot budget')
        self._slots = {}

    def reserve(self,map_index,episode,version_id,task_id,row_sha256):
        slot = slot_schedule(map_index,episode)['canonical_slot']
        binding = tuple(_hash(value) for value in (version_id,task_id,row_sha256))
        if slot in self._slots:
            if self._slots[slot]!=binding:
                raise ValueError('A catalog slot cannot acquire another version/task/result credit')
            return False
        self._slots[slot] = binding
        return True


def classify_exact_reference(body):
    """Recognize four exact sources; do not infer mutation/runtime approval."""
    identity = _sha(body)
    if identity not in ANCHORS:
        raise ValueError('Unknown source requires reviewed exact-export family validation')
    family,oracles = ANCHORS[identity]
    return dict(source_sha256=identity,family=family,expected_focal_legacy_oracles_per_full_game=oracles,
                required_actor_callbacks_per_game=320,required_referees=2,
                qualifies_mutants=False,grants_runtime_approval=False,new_primary_credit=0)
