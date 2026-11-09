"""Persistent, shard-affine local CPU actors receiving public views only.

Each shard owns one spawn ProcessPoolExecutor with exactly one persistent
worker. A shared multiworker queue cannot guarantee per-game process affinity.
No CUDA, transport, credentials, registry or observer-state module is imported.
"""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import copy
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import threading
import time

from evolution import oversight

ROOT=Path(__file__).resolve().parents[1]
ACTIONS=('NORTH','EAST','SOUTH','WEST','STAY','SHIELD')
LEGAL_ORDER=('STAY','NORTH','SOUTH','WEST','EAST','SHIELD')
FORMAT='persistent-local-public-actor-pool/1'
_LANES={}
_BATCH=None
_FAILED=False
_ENTRIES=[]
_PINS={}
FROZEN={'evolution/oversight.py':'02fbb41a16df510a33214207f6f3d0561b4865d75cb1a293ea614680df9000b6',
        'evolution/opponents.py':'b2b2c12cc3c27b209bd4af9089242f32c5128e17c411228e9bee4b692bf84c29'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(body): return hashlib.sha256(body).hexdigest()


def source_pins():
    result={name:sha((ROOT/name).read_bytes()) for name in FROZEN}
    if any(result[name]!=expected for name,expected in FROZEN.items()): raise ValueError('Frozen exact actor loader changed')
    for name in ('local_policy_pool/__init__.py','local_policy_pool/pool.py'):
        result[name]=sha((ROOT/name).read_bytes())
    return result


class PoolExecutionError(RuntimeError):
    def __init__(self,evidence):
        self.evidence=copy.deepcopy(evidence)
        super().__init__('Local actor chunk failed; partial attempts retained and batch cannot be retried')


@dataclass(frozen=True,slots=True)
class Cell:
    occupant:int
    owner:int
    is_upgraded:bool
    is_home:bool
    is_frozen:bool
    base_points:int


@dataclass(frozen=True,slots=True)
class View:
    board:tuple
    bot_id:int
    is_priority_token:bool
    legal_actions:tuple


def wire_view(raw,seat):
    if type(raw) is not dict or set(raw)!={'board','bot_id','is_priority_token','legal_actions'}:
        raise ValueError('Exactly four serialized public view fields required')
    if raw['bot_id']!=seat+1 or type(raw['bot_id']) is not int or type(raw['is_priority_token']) is not bool:
        raise ValueError('Public seat/priority type mismatch')
    board=raw['board']
    if type(board) not in (list,tuple) or len(board)!=8 or any(len(row)!=8 for row in board):
        raise ValueError('Public board must be8x8')
    flattened=[]
    for row in board:
        for c in row:
            if (type(c) not in (list,tuple) or len(c)!=6 or type(c[0]) is not int or c[0] not in range(5)
                    or type(c[1]) is not int or c[1] not in range(5) or type(c[5]) is not int or c[5] not in (1,2,3)
                    or any(type(c[i]) is not bool for i in (2,3,4))):
                raise ValueError('Invalid/extra public cell field')
            flattened.append(list(c))
    if sorted(c[0] for c in flattened if c[0])!=[1,2,3,4]:
        raise ValueError('Each public seat must occupy one cell')
    legal=raw['legal_actions']
    if (type(legal) not in (list,tuple) or 'STAY' not in legal or any(type(a) is not str or a not in ACTIONS for a in legal)
            or len(set(legal))!=len(legal) or list(legal)!=[a for a in LEGAL_ORDER if a in legal]):
        raise ValueError('Exact admitted engine legal-action ordering required')
    return dict(board=[flattened[r*8:(r+1)*8] for r in range(8)],bot_id=seat+1,
                is_priority_token=raw['is_priority_token'],legal_actions=list(legal))


def immutable(raw):
    return View(tuple(tuple(Cell(*cell) for cell in row) for row in raw['board']),
                raw['bot_id'],raw['is_priority_token'],tuple(raw['legal_actions']))


def _entry(entry):
    if type(entry) is not dict or type(entry.get('path')) is not str or type(entry.get('sha256')) is not str:
        raise ValueError('Exact actor source entry required')
    result=dict(path=str(Path(entry['path']).resolve()),sha256=entry['sha256'])
    if sha(Path(result['path']).read_bytes())!=result['sha256']:
        raise ValueError('Actor source bytes changed')
    return result


def _source_check():
    if source_pins()!=_PINS: raise ValueError('Pool runtime source changed during batch')
    for entry in _ENTRIES: _entry(entry)


def _projection(namespace,seat):
    if namespace is None: return None
    if namespace.get('_input_failures',0) or namespace.get('_policy_failures',0):
        raise ValueError('Actor fallback flag')
    memory=namespace.get('_history',{}).get(seat+1,{})
    if 'cooldown_possible' not in memory: return None
    if memory.get('inference_failures',0): raise ValueError('Actor public inference fallback')
    # These are the actor's inferred public-memory values, never observer truth.
    result=dict(progress=memory['progress'],scores=list(memory['scores']),
        cooldown_possible={str(i):sorted(memory['cooldown_possible'][i]) for i in range(1,5)},
        inference_failures=memory.get('inference_failures',0))
    canonical(result)
    return result


def _dispatch(command):
    """Only this fixed trusted function is submitted; commands are plain JSON."""
    global _LANES,_BATCH,_FAILED,_ENTRIES,_PINS
    operation=command.get('operation'); active=dict(lane_id=None,seat=None); seat_proofs=[]; actions=[]; proofs=[]; joint=[]
    try:
        if operation=='initialize':
            if set(command)!={'operation','batch','lanes','sources'}: raise ValueError('Unknown setup field')
            if _LANES: raise ValueError('Explicit reset required before a fresh batch')
            _PINS=source_pins()
            _BATCH=command['batch']; _FAILED=False; _ENTRIES=list(command['sources'].values())
            for lane in command['lanes']:
                _ENTRIES.append(lane['candidate']); active['lane_id']=lane['lane_id']
                actors,namespaces=oversight.make_actors(lane['candidate'],lane['fixture'],command['sources'])
                _LANES[lane['lane_id']]=dict(actors=actors,namespaces=namespaces,next_turn=1,attempts=[0]*4,returned=[0]*4,completed=[0]*4)
            _source_check()
            return dict(ok=True,operation=operation,batch=_BATCH,lanes=list(_LANES),pid=os.getpid(),attempts=0,source_sha256=_PINS)
        if operation=='reset':
            if set(command)!={'operation'}: raise ValueError('Unknown reset field')
            report={key:dict(attempts=list(lane['attempts']),returned=list(lane['returned']),completed=list(lane['completed']),next_turn=lane['next_turn']) for key,lane in _LANES.items()}
            _LANES={}; _BATCH=None; _ENTRIES=[]; _PINS={}; failed=_FAILED; _FAILED=False
            return dict(ok=True,operation=operation,lanes=report,failed_batch=failed,pid=os.getpid())
        if operation!='decide' or set(command)!={'operation','batch','turn','lanes'}:
            raise ValueError('Unknown trusted pool operation/field')
        if _FAILED or command['batch']!=_BATCH or [r['lane_id'] for r in command['lanes']]!=list(_LANES):
            raise ValueError('Failed/foreign/reordered shard; reset required')
        turn=command['turn']
        if type(turn) is not int or not 1<=turn<=80 or any(lane['next_turn']!=turn for lane in _LANES.values()):
            raise ValueError('Repeated/skipped/terminal policy turn')
        # Validate and freeze EVERY same-preturn seat snapshot before callbacks.
        frozen={}
        for row in command['lanes']:
            if set(row)!={'lane_id','views'} or len(row['views'])!=4: raise ValueError('Four public seats required')
            raw=[wire_view(v,s) for s,v in enumerate(row['views'])]
            if any(v['board']!=raw[0]['board'] for v in raw) or sum(v['is_priority_token'] for v in raw)!=1:
                raise ValueError('Four simultaneous public boards/priority flags disagree')
            frozen[row['lane_id']]=[immutable(v) for v in raw]
        if turn in (1,80): _source_check()
        for row in command['lanes']:
            key=row['lane_id']; lane=_LANES[key]; joint=[]; seat_proofs=[]
            for seat,view in enumerate(frozen[key]):
                active.update(lane_id=key,seat=seat); signature=oversight.signature(view)
                proof=dict(seat=seat,attempted=True,returned=False,completed=False,input_unchanged=None,fallback=None)
                seat_proofs.append(proof); lane['attempts'][seat]+=1
                began=time.perf_counter()
                try:
                    action=lane['actors'][seat](view)
                    proof['returned']=True; lane['returned'][seat]+=1
                finally:
                    elapsed=time.perf_counter()-began
                    proof['callback_ms']=elapsed*1000 if math.isfinite(elapsed) and elapsed>=0 else None
                if proof['callback_ms'] is None or elapsed>(2 if turn==1 else .2): raise ValueError('Actor deadline/nonfinite duration')
                proof['input_unchanged']=oversight.signature(view)==signature
                if not proof['input_unchanged']: raise ValueError('Actor input mutation')
                proof['legal_action']=type(action) is str and action in view.legal_actions
                if not proof['legal_action']: raise ValueError('Illegal actor action')
                namespace=lane['namespaces'][seat]
                memory=namespace.get('_history',{}).get(seat+1,{}) if namespace is not None else {}
                proof['fallback']=bool(namespace is not None and (namespace.get('_input_failures',0) or namespace.get('_policy_failures',0)
                    or ('cooldown_possible' in memory and memory.get('inference_failures',0))))
                projection=_projection(lane['namespaces'][seat],seat)
                proof.update(completed=True,input_unchanged=True,fallback=False,public_memory_projection=projection)
                lane['completed'][seat]+=1; joint.append(action)
            lane['next_turn']+=1; actions.append(joint)
            proofs.append(dict(lane_id=key,seats=seat_proofs,attempts_total=list(lane['attempts']),
                               returned_total=list(lane['returned']),completed_total=list(lane['completed'])))
        if turn==80: _source_check()
        return dict(ok=True,operation=operation,batch=_BATCH,turn=turn,lane_ids=list(_LANES),actions=actions,proofs=proofs,pid=os.getpid())
    except BaseException as error:
        _FAILED=True
        return dict(ok=False,operation=operation,batch=_BATCH,active=active,pid=os.getpid(),
            error=dict(type=type(error).__name__,message=str(error)[:1024]),active_seat_proofs=seat_proofs,
            completed_lane_actions=actions,completed_lane_proofs=proofs,active_completed_actions=joint,
            lane_counters={key:dict(attempts=list(lane['attempts']),returned=list(lane['returned']),
                                   completed=list(lane['completed']),next_turn=lane['next_turn']) for key,lane in _LANES.items()})


class ActorPool:
    """Dedicated persistent spawn workers; no speculative calls or retries."""
    def __init__(self,max_workers=4,evidence_directory=None):
        if type(max_workers) is not int or not 1<=max_workers<=8: raise ValueError('Use one through eight LOCAL CPU workers')
        self.max_workers=max_workers; self._executors=[]; self._shards=[]; self._batch=None; self._turn=1
        self._failed=False; self._closed=False; self._history=[]; self._lock=threading.RLock(); self._generation=0
        self._directory=Path(evidence_directory).resolve() if evidence_directory is not None else None
        if self._directory is not None: self._directory.mkdir(parents=True,exist_ok=False)

    @property
    def evidence(self): return copy.deepcopy(self._history)

    def _record(self,event):
        canonical(event); self._history.append(copy.deepcopy(event))
        if self._directory is not None:
            with (self._directory/'events.jsonl').open('ab') as handle:
                handle.write(canonical(event)+b'\n'); handle.flush(); os.fsync(handle.fileno())

    def _collect(self,commands):
        futures=[executor.submit(_dispatch,command) for executor,command in zip(self._executors,commands)]
        responses=[]
        for future in futures:
            try: responses.append(future.result())
            except BaseException as error:
                responses.append(dict(ok=False,error=dict(type=type(error).__name__,message=str(error)[:1024]),
                                      process_or_transport_failure=True,attempt_counts_unknown=True))
        return responses

    def initialize_batch(self,registrationSubset,fixture_ids):
        with self._lock:
            if self._closed or self._failed or self._batch is not None: raise ValueError('Close/reset state forbids initialization')
            if type(registrationSubset) is not dict or not {'guards','candidates','sources','fixtures'}<=set(registrationSubset):
                raise ValueError('Guarded exact actor registration subset required')
            if type(fixture_ids) not in (list,tuple) or not fixture_ids or any(type(i) is not str for i in fixture_ids) or len(set(fixture_ids))!=len(fixture_ids):
                raise ValueError('Unique nonempty ordered lane IDs required')
            if type(registrationSubset['guards']) is not dict or not registrationSubset['guards']:
                raise ValueError('Nonempty exact source guards required')
            pins=source_pins()
            for path,digest in registrationSubset['guards'].items():
                if sha(Path(path).read_bytes())!=digest: raise ValueError('Registration source guard changed')
            candidates={c['sha256']:_entry(c) for c in registrationSubset['candidates']}
            fixtures={f['id']:f for f in registrationSubset['fixtures']}
            if len(fixtures)!=len(registrationSubset['fixtures']) or len(candidates)!=len(registrationSubset['candidates']) or not set(fixture_ids)<=set(fixtures):
                raise ValueError('Unknown/duplicate registered lane or candidate')
            sources={name:_entry(entry) for name,entry in registrationSubset['sources'].items()}
            lanes=[]
            for key in fixture_ids:
                fixture=fixtures[key]; seat=fixture['seat']
                if type(seat) is not int or seat not in range(4) or fixture['candidate'] not in candidates: raise ValueError('Bad focal assignment')
                specs=[]
                for raw in fixture['opponents']:
                    allowed={'id','seat','family','seed','genes','epsilon','commitment','pair_parameter_id'}
                    if not set(raw)<=allowed: raise ValueError('Undeclared actor spec/credential field')
                    if 'pair_parameter_id' in raw:
                        provenance=raw['pair_parameter_id']
                        if (type(provenance) is not str or len(provenance)!=64
                                or any(c not in '0123456789abcdef' for c in provenance)):
                            raise ValueError('pair_parameter_id must be lowercase64-hex provenance')
                    # Frozen actor constructors never consume study pairing
                    # provenance. Validate it on the host, then omit it from
                    # every worker setup message and actor constructor spec.
                    specs.append({name:copy.deepcopy(value) for name,value in raw.items() if name!='pair_parameter_id'})
                if len(specs)!=3 or {s['seat'] for s in specs}!=set(range(4))-{seat}: raise ValueError('Three distinct rival seats required')
                lanes.append(dict(lane_id=key,candidate=candidates[fixture['candidate']],fixture=dict(id=key,seat=seat,opponents=specs)))
            # Only exact actor/source specs cross process boundaries. Registration
            # headers, guards, maps, observer truth and credentials do not.
            self._generation+=1; self._batch=sha(canonical([self._generation,lanes,sources])); self._ids=list(fixture_ids)
            workers=min(self.max_workers,len(lanes))
            if not self._executors:
                self._executors=[ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn')) for _ in range(workers)]
            self._shards=[lanes[i::len(self._executors)] for i in range(len(self._executors))]
            commands=[dict(operation='initialize',batch=self._batch,lanes=shard,sources=sources) for shard in self._shards]
            responses=self._collect(commands); event=dict(operation='initialize',batch=self._batch,lane_ids=self._ids,responses=responses,admission_credit=0)
            event['source_sha256']=pins
            self._record(event); self._failed=any(not r['ok'] or r.get('source_sha256')!=pins for r in responses); self._turn=1
            if self._failed: raise PoolExecutionError(event)
            return copy.deepcopy(event)

    def decide_turn(self,publicviews):
        with self._lock:
            if self._closed or self._failed or self._batch is None: raise ValueError('Pool inactive/failed; explicit reset required')
            if (type(publicviews) is not dict or set(publicviews)!={'turn','lanes'}
                    or type(publicviews['turn']) is not int or publicviews['turn']!=self._turn or self._turn>80):
                raise ValueError('Exact next nonterminal turn required')
            rows=publicviews['lanes']
            if (type(rows) is not list or any(type(r) is not dict or set(r)!={'lane_id','views'} or type(r['views']) not in (list,tuple) or len(r['views'])!=4 for r in rows)
                    or [r['lane_id'] for r in rows]!=self._ids):
                raise ValueError('Exact ordered lane IDs and four public seats required')
            # Whole-batch public validation precedes every worker callback.
            normalized={r['lane_id']:[wire_view(v,s) for s,v in enumerate(r['views'])] for r in rows}
            for views in normalized.values():
                if any(v['board']!=views[0]['board'] for v in views) or sum(v['is_priority_token'] for v in views)!=1:
                    raise ValueError('Non-simultaneous public observations')
            commands=[dict(operation='decide',batch=self._batch,turn=self._turn,
                lanes=[dict(lane_id=lane['lane_id'],views=normalized[lane['lane_id']]) for lane in shard]) for shard in self._shards]
            responses=self._collect(commands); event=dict(operation='decide',batch=self._batch,turn=self._turn,responses=responses,admission_credit=0)
            self._record(event)
            if any(not r['ok'] for r in responses):
                self._failed=True; raise PoolExecutionError(event)
            indexed={key:(actions,proof) for r in responses for key,actions,proof in zip(r['lane_ids'],r['actions'],r['proofs'])}
            result=dict(turn=self._turn,lane_ids=list(self._ids),actions=[indexed[k][0] for k in self._ids],
                proofs=[indexed[k][1] for k in self._ids],worker_chunks=responses,admission_credit=0)
            self._turn+=1; return result

    def reset(self):
        with self._lock:
            if self._closed: raise ValueError('Pool is closed')
            responses=self._collect([dict(operation='reset') for _ in self._executors]) if self._executors else []
            event=dict(operation='reset',batch=self._batch,responses=responses,admission_credit=0); self._record(event)
            self._batch=None; self._shards=[]; self._failed=False; self._turn=1
            if any(not r['ok'] for r in responses): self._failed=True; raise PoolExecutionError(event)
            return copy.deepcopy(event)

    def close(self):
        with self._lock:
            if self._closed: return self.evidence
            try: self.reset()
            finally:
                for executor in self._executors: executor.shutdown(wait=True,cancel_futures=True)
                self._closed=True
            return self.evidence

    def __enter__(self): return self
    def __exit__(self,*_): self.close()
