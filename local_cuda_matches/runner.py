"""Run original Python actors on local CUDA physics with two CPU observers.

Actors run on CPU and receive only immutable GPU-derived public views. CUDA
advances every physical turn; CPU referees observe and check, never supply actor
inputs. This local hybrid is not GPU policy inference or canonical admission.
"""
import copy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

from evolution import oversight
from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'local-cuda-physics-cpu-policy-matches/1'
BEHAVIOR = ('candidate','fixture','map_id','focal_seat','field','scores','focal_pw',
            'focal_score','opponent_ids','actions','faults')
STATE_FIELDS = ('base','owner','upg','home','pos','frozen','cd','prog','score','income','token')
ENGINE_LEGAL_ORDER = ('STAY','NORTH','SOUTH','WEST','EAST','SHIELD')
FROZEN = {
    'tests/reference_engine.py':'8f7b89995cad0f724fb8ac7c7bc8311a6fa9b3b722f2204097031ba2333726f4',
    'simulator/vendor_harness/referee.py':'f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337',
    'evolution/oversight.py':'02fbb41a16df510a33214207f6f3d0561b4865d75cb1a293ea614680df9000b6',
    'evolution/opponents.py':'b2b2c12cc3c27b209bd4af9089242f32c5128e17c411228e9bee4b692bf84c29',
    'training_gpu/__init__.py':'87dc9ae50c90732a585cda760c993217cd440e8bd2078fd9c867fb3bc5386d73',
    'training_gpu/batch_game.py':'4c314c10e733d9eea496a9973110639b95cb496b8ff9e7b9d49bc8459d8efb9f',
    'search_coach/gpu_batch.py':'1a15460f1ba38b31a701322683423d642f1e9d358a92a398238cac1683bbbc8b',
    'search_coach/__init__.py':'63563ec08cbca672ef264b2fa5678313820a8bf22b69e361279507d7f181df45',
    'search_coach/belief.py':'f4188a87e5f253685df98ba596af97601bd00b68a42ff397f4d244126aa8669c',
    'search_coach/beam.py':'33d8d138d1b2a290b4599a65122eb0dfc16d977277a19e4fb97cea7717c08925',
}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def _seal(path, value):
    """Exclusive durable publication inside an exclusively claimed new run."""
    path=Path(path); body=canonical(value)+b'\n'
    with path.open('xb') as handle:
        handle.write(body); handle.flush(); os.fsync(handle.fileno())
    with path.with_suffix('.sha256').open('xb') as handle:
        handle.write((sha(body)+'\n').encode('ascii')); handle.flush(); os.fsync(handle.fileno())


def source_pins():
    pins={}
    for name,expected in FROZEN.items():
        actual=sha((ROOT/name).read_bytes())
        if actual!=expected:
            raise ValueError('Frozen local CUDA dependency changed: '+name)
        pins[name]=actual
    for name in ('local_cuda_matches/__init__.py','local_cuda_matches/runner.py','local_cuda_matches/physics.py'):
        pins[name]=sha((ROOT/name).read_bytes())
    return dict(sorted(pins.items()))


def _registration(registration, fixture_ids):
    if type(registration) is not dict or not {'guards','candidates','sources','fixtures'}<=set(registration):
        raise ValueError('A complete guarded source registration is required')
    if (type(fixture_ids) not in (list,tuple) or not fixture_ids or any(type(i) is not str for i in fixture_ids)
            or len(fixture_ids)!=len(set(fixture_ids))):
        raise ValueError('A nonempty unique ordered fixture-ID list is required')
    if type(registration['guards']) is not dict or not registration['guards']:
        raise ValueError('Registration source guards cannot be absent or empty')
    oversight.check(all(type(path) is str and type(digest) is str and sha(Path(path).read_bytes())==digest
                        for path,digest in registration['guards'].items()),'Registration source guard changed')
    if registration.get('rules',{'catch_requires_stay':True}) != {'catch_requires_stay':True}:
        raise ValueError('Only the frozen canonical catch-requires-STAY rules are supported')
    candidates={c['sha256']:c for c in registration['candidates']}
    fixtures={f['id']:f for f in registration['fixtures']}
    if len(candidates)!=len(registration['candidates']) or len(fixtures)!=len(registration['fixtures']):
        raise ValueError('Duplicate registered candidate or fixture identity')
    if not set(fixture_ids)<=set(fixtures):
        raise ValueError('Unknown requested fixture ID')
    for entry in list(candidates.values())+list(registration['sources'].values()):
        if (type(entry) is not dict or type(entry.get('path')) is not str or type(entry.get('sha256')) is not str
                or sha(Path(entry['path']).read_bytes())!=entry['sha256']):
            raise ValueError('Exact candidate/source bytes changed')
    selected=[]
    for identity in fixture_ids:
        fixture=fixtures[identity]
        if (fixture['candidate'] not in candidates or type(fixture['seat']) is not int or fixture['seat'] not in range(4)
                or type(fixture['token']) is not int or fixture['token'] not in range(1,5)
                or len(fixture['base'])!=64 or any(type(v) is not int or v not in (1,2,3) for v in fixture['base'])
                or fixture['map_id']!=sha(bytes(fixture['base']))
                or len(fixture['opponents'])!=3
                or {s['seat'] for s in fixture['opponents']}!=set(range(4))-{fixture['seat']}
                or len({s['id'] for s in fixture['opponents']})!=3):
            raise ValueError('Invalid exact fixture/candidate/map/opponent assignment')
        selected.append(copy.deepcopy(fixture))
    # Preserve only selected fixtures. The controller separately pins the full
    # original registration; a batch snapshot is never labelled as those bytes.
    provenance=registration.get('local_cuda_source_schedule')
    if provenance is None:
        provenance=dict(snapshot_scope='selected fixtures only; not the complete original registration bytes',
            original_fixture_count=len(registration['fixtures']),
            ordered_original_fixture_ids_sha256=sha(canonical([f['id'] for f in registration['fixtures']])))
    elif (type(provenance) is not dict or type(provenance.get('original_fixture_count')) is not int
            or provenance['original_fixture_count']<len(registration['fixtures'])
            or type(provenance.get('ordered_original_fixture_ids_sha256')) is not str
            or len(provenance['ordered_original_fixture_ids_sha256'])!=64):
        raise ValueError('Invalid original-schedule snapshot provenance')
    snapshot={key:copy.deepcopy(value) for key,value in registration.items() if key!='fixtures'}
    snapshot.update(fixtures=selected,local_cuda_source_schedule=copy.deepcopy(provenance))
    return snapshot,selected,copy.deepcopy(candidates)


@dataclass(frozen=True,slots=True)
class PublicCell:
    occupant: int
    owner: int
    is_upgraded: bool
    is_home: bool
    is_frozen: bool
    base_points: int


@dataclass(frozen=True,slots=True)
class ActorView:
    board: tuple
    bot_id: int
    is_priority_token: bool
    legal_actions: tuple


def _actor_view(board, legal, token, seat):
    """No observer state, CPU referee, source spec or actual RNG is accepted."""
    if len(board)!=64 or len(legal)!=6 or any(type(v) is not bool for v in legal):
        raise ValueError('Invalid GPU public board/legal mask')
    cells=[]
    for c in board:
        if (len(c)!=6 or type(c[0]) is not int or c[0] not in range(5) or type(c[1]) is not int or c[1] not in range(5)
                or type(c[5]) is not int or c[5] not in (1,2,3)
                or any(type(c[j]) not in (bool,int) or c[j] not in (0,1) for j in (2,3,4))):
            raise ValueError('Extra or invalid GPU public cell fields')
        cells.append(PublicCell(c[0],c[1],bool(c[2]),bool(c[3]),bool(c[4]),c[5]))
    if sorted(c.occupant for c in cells if c.occupant)!=[1,2,3,4] or type(token) is not int or token not in range(1,5):
        raise ValueError('GPU public occupant/priority contract changed')
    actions=tuple(a for a in ENGINE_LEGAL_ORDER if legal[engine.ACTIONS.index(a)])
    if not actions:
        raise ValueError('GPU supplied empty own legal set')
    return ActorView(tuple(tuple(cells[r*8:(r+1)*8]) for r in range(8)),seat+1,token==seat+1,actions)


def _physics(base_maps, tokens, device, use_graph):
    from .physics import CudaPhysics
    return CudaPhysics(base_maps,tokens,device=device,use_graph=use_graph)


def runtime_info():
    return dict(implementation=platform.python_implementation(),python_version=platform.python_version(),
        full_python_version=sys.version,executable=sys.executable,platform=platform.platform(),
        actor_backend='CPython CPU original Python actors',cuda_used_by_policy=False)


def _safe_evidence(value):
    """Keep a failed clock/metadata value diagnostic without masking its error."""
    if type(value) is float and not math.isfinite(value):
        return {'nonfinite_repr':repr(value)}
    if type(value) is dict:
        return {str(k):_safe_evidence(v) for k,v in value.items()}
    if type(value) in (list,tuple):
        return [_safe_evidence(v) for v in value]
    if value is None or type(value) in (str,int,float,bool):
        return value
    return {'unserializable_type':type(value).__name__}


def _snapshots(physics, timings):
    started=time.perf_counter(); public=physics.public_snapshot(); timings['gpu_public_download_wall_s']+=time.perf_counter()-started
    started=time.perf_counter(); state=physics.state_snapshot(); timings['gpu_state_download_wall_s']+=time.perf_counter()-started
    if type(public) is not dict or set(public)!={'board','legal','tokens'}:
        raise ValueError('GPU public snapshot contains an extra/private field')
    if not set(STATE_FIELDS+('turn',))<=set(state) or type(state['turn']) is not int:
        raise ValueError('Incomplete GPU observer state/true clock')
    return public,state


def _compare(public,state,refs,shadows,proofs,state_hashes,public_hashes):
    lanes=len(refs)
    if any(len(public[k])!=lanes for k in ('board','legal','tokens')) or any(len(state[k])!=lanes for k in STATE_FIELDS):
        raise ValueError('GPU snapshot lane count mismatch')
    for lane,(reference,shadow) in enumerate(zip(refs,shadows)):
        if state['turn']!=reference.turn or state['turn']!=shadow.turn:
            raise ValueError('GPU/CPU observer true clock disagreement')
        for ref in (reference,shadow):
            for name in STATE_FIELDS:
                expected=ref.income() if name=='income' and callable(ref.income) else getattr(ref,name)
                if state[name][lane]!=expected:
                    raise ValueError('GPU/two-referee state disagreement: lane%d %s'%(lane,name))
        if public['tokens'][lane]!=state['token'][lane] or len(public['legal'][lane])!=4:
            raise ValueError('GPU public token/legal seat mismatch')
        occupancy=[0]*64; frozen=[False]*64
        for seat,position in enumerate(state['pos'][lane]):
            occupancy[position]=seat+1; frozen[position]=bool(state['frozen'][lane][seat])
        expected_board=[[occupancy[c],state['owner'][lane][c],bool(state['upg'][lane][c]),
                         bool(state['home'][lane][c]),frozen[c],state['base'][lane][c]] for c in range(64)]
        if public['board'][lane]!=expected_board:
            raise ValueError('GPU public board disagrees with checked GPU observer state')
        for seat,mask in enumerate(public['legal'][lane]):
            if len(mask)!=6 or any(type(v) is not bool for v in mask):
                raise ValueError('GPU public legal mask shape/type mismatch')
            legal={engine.ACTIONS[a] for a,v in enumerate(mask) if v}
            if legal!=set(reference.legal(seat)) or legal!=set(shadow.legal(seat)):
                raise ValueError('GPU/two-referee legal disagreement')
        state_hashes[lane].update(canonical(dict(turn=state['turn'],**{name:state[name][lane] for name in STATE_FIELDS})))
        public_hashes[lane].update(canonical(dict(board=public['board'][lane],legal=public['legal'][lane],token=public['tokens'][lane])))
        proofs[lane]['gpu_reference_state_comparisons']+=1
        proofs[lane]['gpu_official_state_comparisons']+=1


def _oracle(namespace,seat,state,lane,proof):
    if namespace is None:
        return
    if namespace.get('_input_failures',0) or namespace.get('_policy_failures',0):
        raise ValueError('Actor used input/policy fallback')
    memory=namespace.get('_history',{}).get(seat+1,{})
    if 'cooldown_possible' not in memory:
        return
    if (memory.get('inference_failures',0) or memory['progress']!=state['prog'][lane][seat]
            or memory['scores'][1:]!=state['score'][lane]
            or any(state['cd'][lane][i] not in memory['cooldown_possible'][i+1] for i in range(4))):
        raise ValueError('Supported legacy public-history oracle lost GPU/referee-consistent truth')
    proof['public_memory_oracles']+=1
    proof['oracle_calls_by_seat'][seat]+=1


def run_fixtures(registration,fixture_ids,output_directory,device='cuda',use_graph=True,primary_credit=0):
    """Return complete BEHAVIOR-compatible rows; never award admission credit."""
    started=time.perf_counter(); output=Path(output_directory).resolve()
    if output.exists():
        raise ValueError('Fresh output required; preserve partial/completed evidence and never resume automatically')
    if type(primary_credit) is not int or primary_credit!=0:
        raise ValueError('Local runner cannot award primary/admission credit')
    if type(device) is not str or not (device=='cuda' or device.startswith('cuda:')) or type(use_graph) is not bool:
        raise ValueError('Explicit local CUDA device and Boolean graph option required; no CPU fallback')
    if platform.python_implementation()!='CPython':
        raise ValueError('This exact original Python actor runner requires CPython')
    pins=source_pins(); registration,fixtures,candidates=_registration(registration,fixture_ids)
    output.mkdir(parents=True,exist_ok=False); (output/'.execution_claim').mkdir(exist_ok=False)
    _seal(output/'registration.json',registration)
    _seal(output/'execution_started.json',dict(format=FORMAT,fixture_ids=list(fixture_ids),
        registration_snapshot_sha256=sha((output/'registration.json').read_bytes()),source_sha256=pins,
        source_schedule=registration['local_cuda_source_schedule'],cpu_runtime=runtime_info(),
        actor_backend='CPython CPU original Python actors',physics_backend='local CUDA',
        primary_games=0,canonical_local_admission='pending separate review',completed_per_game_bmcts_audits=0))
    active=dict(turn=1,lane=None,seat=None,phase='setup'); pending=None; physics=None
    tapes=[[] for _ in fixtures]; faults=[[] for _ in fixtures]
    timing=[[dict(calls=0,first_ms=0.0,regular_max_ms=0.0,max_ms=0.0,total_ms=0.0) for _ in range(4)] for _ in fixtures]
    proofs=[dict(callbacks_regenerated=0,public_memory_oracles=0,oracle_calls_by_seat=[0]*4,
                 gpu_reference_state_comparisons=0,gpu_official_state_comparisons=0,physical_turns=0) for _ in fixtures]
    totals=dict(actor_setup_s=0.0,actor_callbacks_s=0.0,actor_view_construction_s=0.0,
        gpu_setup_wall_s=0.0,gpu_step_wall_s=0.0,gpu_public_download_wall_s=0.0,
        gpu_state_download_wall_s=0.0,referee_step_and_checks_s=0.0)
    state_hashes=[hashlib.sha256() for _ in fixtures]; public_hashes=[hashlib.sha256() for _ in fixtures]
    try:
        moment=time.perf_counter(); physics=_physics([f['base'] for f in fixtures],[f['token'] for f in fixtures],device,use_graph)
        totals['gpu_setup_wall_s']=time.perf_counter()-moment
        refs=[engine.Game(base=f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
        shadows=[oversight.referee.Referee(f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
        moment=time.perf_counter(); actors=[]; namespaces=[]
        for f in fixtures:
            lane_actors,lane_namespaces=oversight.make_actors(candidates[f['candidate']],f,registration['sources'])
            if len(lane_actors)!=4 or len(lane_namespaces)!=4:
                raise ValueError('Fresh per-lane actor factory returned incomplete seats')
            actors.append(lane_actors); namespaces.append(lane_namespaces)
        totals['actor_setup_s']=time.perf_counter()-moment
        public,state=_snapshots(physics,totals); moment=time.perf_counter()
        _compare(public,state,refs,shadows,proofs,state_hashes,public_hashes)
        totals['referee_step_and_checks_s']+=time.perf_counter()-moment
        with (output/'turns.jsonl').open('xb') as stream:
            for turn in range(1,81):
                active.update(turn=turn,lane=None,seat=None,phase='actors')
                if state['turn']!=turn:
                    raise ValueError('GPU true clock skipped/repeated an actor turn')
                moment=time.perf_counter()
                # ALL immutable public snapshots exist before the first call.
                views=[[_actor_view(public['board'][lane],public['legal'][lane][seat],public['tokens'][lane],seat)
                        for seat in range(4)] for lane in range(len(fixtures))]
                totals['actor_view_construction_s']+=time.perf_counter()-moment
                pending=[]
                for lane in range(len(fixtures)):
                    joint=[]; pending.append(joint)
                    for seat,view in enumerate(views[lane]):
                        active.update(lane=lane,seat=seat); before=oversight.signature(view); call_start=time.perf_counter()
                        try:
                            action=actors[lane][seat](view)
                        finally:
                            elapsed=time.perf_counter()-call_start
                            rec=timing[lane][seat]; rec['calls']+=1
                            if math.isfinite(elapsed) and elapsed>=0:
                                totals['actor_callbacks_s']+=elapsed; rec['total_ms']+=elapsed*1000
                                rec['max_ms']=max(rec['max_ms'],elapsed*1000)
                                rec['first_ms']=elapsed*1000 if turn==1 else rec['first_ms']
                                if turn!=1: rec['regular_max_ms']=max(rec['regular_max_ms'],elapsed*1000)
                            else:
                                active['invalid_callback_elapsed_repr']=repr(elapsed)
                            proofs[lane]['callbacks_regenerated']+=1
                        if not math.isfinite(elapsed) or elapsed<0 or elapsed>(2 if turn==1 else .2):
                            raise ValueError('Actor callback missed finite first/regular deadline')
                        if oversight.signature(view)!=before:
                            raise ValueError('Actor mutated its immutable four-field public input')
                        if (type(action) is not str or action not in view.legal_actions
                                or action not in refs[lane].legal(seat) or action not in shadows[lane].legal(seat)):
                            raise ValueError('Actor decision illegal in GPU public view or a CPU observer')
                        _oracle(namespaces[lane][seat],seat,state,lane,proofs[lane]); joint.append(action)
                active.update(lane=None,seat=None,phase='cuda_step'); codes=[[engine.ACTIONS.index(a) for a in joint] for joint in pending]
                moment=time.perf_counter(); physics.step(codes); totals['gpu_step_wall_s']+=time.perf_counter()-moment
                public,state=_snapshots(physics,totals); active['phase']='referee_step_and_compare'; moment=time.perf_counter()
                for lane,joint in enumerate(pending): refs[lane].step(joint); shadows[lane].step(joint)
                _compare(public,state,refs,shadows,proofs,state_hashes,public_hashes)
                totals['referee_step_and_checks_s']+=time.perf_counter()-moment
                for lane,joint in enumerate(pending): tapes[lane].append(list(joint)); proofs[lane]['physical_turns']+=1
                stream.write(canonical(dict(turn=turn,actions=pending,
                    gpu_state_chain_sha256=[h.hexdigest() for h in state_hashes],
                    gpu_public_chain_sha256=[h.hexdigest() for h in public_hashes],
                    per_lane_completed_physical_turns=[p['physical_turns'] for p in proofs]))+b'\n')
                stream.flush(); os.fsync(stream.fileno()); pending=None
        active['phase']='final_source_and_coverage_checks'
        if source_pins()!=pins:
            raise ValueError('Local CUDA runtime source changed during matches')
        _registration(registration,fixture_ids)  # exact actor/source/guard bytes again
        if state['turn']!=81 or not all(r.over() and s.over() for r,s in zip(refs,shadows)):
            raise ValueError('A lane is not truly terminal after eighty turns')
        rows=[]
        for lane,f in enumerate(fixtures):
            proof=proofs[lane]
            if (proof['callbacks_regenerated']!=320 or proof['physical_turns']!=80
                    or proof['gpu_reference_state_comparisons']!=81 or proof['gpu_official_state_comparisons']!=81
                    or any(t['calls']!=80 for t in timing[lane]) or len(tapes[lane])!=80):
                raise ValueError('Measured full-game actor/physics/observer coverage is incomplete')
            scores=list(state['score'][lane]); seat=f['seat']
            points=sum(1 if scores[seat]>v else .5 if scores[seat]==v else 0 for i,v in enumerate(scores) if i!=seat)
            rows.append(dict(candidate=f['candidate'],fixture=f['id'],map_id=f['map_id'],focal_seat=seat,
                field=f['field'],scores=scores,focal_pw=points,focal_score=scores[seat],
                opponent_ids=[s['id'] for s in f['opponents']],actions=tapes[lane],faults=[],timing=timing[lane],
                elapsed_s=time.perf_counter()-started,public_memory_oracles=proof['public_memory_oracles'],
                proof=dict(proof,gpu_state_chain_sha256=state_hashes[lane].hexdigest(),
                    gpu_public_chain_sha256=public_hashes[lane].hexdigest(),all_inputs_gpu_public_only=True,
                    source_closure_sha256=sha(canonical(pins)),registration_snapshot_sha256=sha((output/'registration.json').read_bytes()),
                    cpu_referees_observers_only=True,actor_backend='CPython CPU',physics_backend='local CUDA',
                    primary_games=0,canonical_local_admission='pending',completed_per_game_bmcts_audits=0)))
        with (output/'games.jsonl').open('xb') as handle:
            for row in rows: handle.write(canonical(row)+b'\n')
            handle.flush(); os.fsync(handle.fileno())
        _seal(output/'summary.json',dict(format=FORMAT,complete_games=len(rows),primary_games=0,
            canonical_local_admission='pending separate canonical acceptance',completed_per_game_bmcts_audits=0,
            callbacks=sum(p['callbacks_regenerated'] for p in proofs),gpu_physical_turns=sum(p['physical_turns'] for p in proofs),
            gpu_reference_state_comparisons=sum(p['gpu_reference_state_comparisons'] for p in proofs),
            gpu_official_state_comparisons=sum(p['gpu_official_state_comparisons'] for p in proofs),
            games_sha256=sha((output/'games.jsonl').read_bytes()),turns_sha256=sha((output/'turns.jsonl').read_bytes()),
            source_sha256=pins,source_schedule=registration['local_cuda_source_schedule'],cpu_runtime=runtime_info(),
            physics_metadata=copy.deepcopy(physics.metadata),physics_timings=copy.deepcopy(physics.timings),
            runner_wall_seconds=totals,wall_before_final_summary_write_s=time.perf_counter()-started,
            limits=['Original Python actors run on CPU; CUDA advances official physical transitions.',
                    'CPU referees observe and check every opening/turn/terminal state; they never supply actor inputs.',
                    'Synchronized wall timings include transfers and observer costs; no GPU-policy or200ms CUDA-actor qualification claim.',
                    'No primary/study admission, new BMCTS audit or promotion credit is awarded by this runner.']))
        return rows
    except BaseException as error:
        if active['lane'] is not None:
            faults[active['lane']].append(dict(turn=active['turn'],seat=active['seat'],exception_type=type(error).__name__))
        partial=dict(active=active,accepted_actions=tapes,pending_actions=pending,timing=timing,proofs=proofs,faults=faults,
                     state_chain_sha256=[h.hexdigest() for h in state_hashes],runner_wall_seconds=totals)
        error.local_cuda_partial=partial
        try:
            metadata=copy.deepcopy(physics.metadata) if physics is not None else None
        except BaseException as metadata_error:
            metadata={'metadata_failure_type':type(metadata_error).__name__}
        try:
            _seal(output/'error.json',_safe_evidence(dict(format=FORMAT,exception_type=type(error).__name__,message=str(error),partial=partial,
                physics_metadata=metadata,primary_games=0,canonical_local_admission='not admitted: failed whole batch',
                completed_per_game_bmcts_audits=0,status='preserve_all_partial_evidence_no_automatic_resume_or_replacement')))
        except BaseException as publication_error:
            # A second interruption or I/O failure must never replace the
            # original callback/physics exception. Retain in-memory evidence.
            error.local_cuda_evidence_publication_failure=type(publication_error).__name__
        raise
