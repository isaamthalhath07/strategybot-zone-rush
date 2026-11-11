"""Compact public views and persistent shard-affine exact local CPU actors.

Namedtuple cells/views and builtin tuple/scalar leaves are immutable. Only the
minimal exact actor constructors enter workers at setup; decisions receive one
public board per lane. This is trusted qualified-code execution, not a hostile
operating-system sandbox or an admission authority. No CUDA is imported.
"""
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor,TimeoutError
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

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'deadline-compact-local-actor-pool/1'
ACTIONS = ('NORTH','EAST','SOUTH','WEST','STAY','SHIELD')
LEGAL_ORDER = ('STAY','NORTH','SOUTH','WEST','EAST','SHIELD')
SOURCE_FAMILIES = frozenset(('planner','research','racer','blocker'))
RIVAL_FAMILIES = frozenset(('wanderer','farmer','raider','interceptor','feinter','mixed'))
ENTRY_FIELDS = frozenset(('path','sha256','name','genes','lineage','source_path','archive_source',
                         'source_kind','implementation_family','family','genotype_sha256','slot','kind'))
FROZEN = {'evolution/oversight.py':'02fbb41a16df510a33214207f6f3d0561b4865d75cb1a293ea614680df9000b6',
          'evolution/opponents.py':'b2b2c12cc3c27b209bd4af9089242f32c5128e17c411228e9bee4b692bf84c29'}
Cell = namedtuple('Cell','occupant owner is_upgraded is_home is_frozen base_points')
View = namedtuple('View','board bot_id is_priority_token legal_actions')
Cell6,View4 = Cell,View
_LANES = {}
_BATCH = None
_FAILED = False
_PINS = {}
_ENTRIES = ()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def sha(body):
    return hashlib.sha256(body).hexdigest()


def require(condition,message):
    if not condition:
        raise ValueError(message)


def _hex(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def _name(value):
    return type(value) is str and 0<len(value)<=128


def source_pins():
    result = {name:sha((ROOT/name).read_bytes()) for name in FROZEN}
    require(all(result[name]==value for name,value in FROZEN.items()),'Frozen exact actor loader changed')
    for name in ('deadline_runner/__init__.py','deadline_runner/actors.py'):
        result[name] = sha((ROOT/name).read_bytes())
    return result


class FastActorError(RuntimeError):
    def __init__(self,evidence):
        self.evidence = copy.deepcopy(evidence)
        super().__init__('Exact local actor batch failed; no fallback or automatic retry')


PoolExecutionError = FastActorError


def _entry(raw):
    require(type(raw) is dict and {'path','sha256'}<=set(raw)<=ENTRY_FIELDS
        and type(raw['path']) is str and _hex(raw['sha256']),'Unknown/credential field or malformed actor source entry')
    result = dict(path=str(Path(raw['path']).resolve()),sha256=raw['sha256'])
    require(sha(Path(result['path']).read_bytes())==result['sha256'],'Exact actor source bytes changed')
    return result


def _genes(value):
    def finite(item):
        try:
            return type(item) in (int,float) and math.isfinite(item)
        except OverflowError:
            return False
    require(type(value) is dict and len(value)<=256 and all(_name(key) and type(item) in (int,float)
        and finite(item) for key,item in value.items()),'Constructor genes must be bounded plain numeric data, never credentials/objects')
    require(len(canonical(value))<=32768,'Constructor genome exceeds explicit bound')
    return dict(value)


def _spec(raw,focal,sources):
    allowed = {'id','seat','family','seed','epsilon','commitment','genes','pair_parameter_id'}
    require(type(raw) is dict and {'id','seat','family','seed'}<=set(raw)<=allowed,
            'Unknown/credential field in exact actor constructor')
    require(_name(raw['id']) and type(raw['seat']) is int and raw['seat'] in range(4) and raw['seat']!=focal
        and type(raw['family']) is str and raw['family'] in SOURCE_FAMILIES|RIVAL_FAMILIES
        and type(raw['seed']) is int and 0<=raw['seed']<2**128,
        'Invalid rival identity/seat/family/full integer seed')
    if 'pair_parameter_id' in raw:
        require(_hex(raw['pair_parameter_id']),'pair_parameter_id must be lowercase64-hex provenance')
    result = {key:value for key,value in raw.items() if key not in ('genes','pair_parameter_id')}
    for key in ('epsilon','commitment'):
        if key in result:
            require(type(result[key]) in (int,float) and math.isfinite(result[key]) and 0<=result[key]<=1,
                    'Invalid numeric rival parameter')
    if raw['family'] in SOURCE_FAMILIES:
        require(raw['family'] in sources,'Exact registered rival source missing')
    if raw['family'] in ('planner','research'):
        require('genes' in raw,'Exact planner constructor genome required')
        result['genes'] = _genes(raw['genes'])
    else:
        require('genes' not in raw,'Unused/unknown constructor genome forbidden')
    if raw['family'] in RIVAL_FAMILIES:
        require({'epsilon','commitment'}<=set(raw),'Full registered behavioral rival constructor required')
    return result


def constructor_messages(registration,fixture_ids):
    """Host-only guards; return no registry, guard map, observer state or header."""
    require(type(registration) is dict and {'guards','candidates','sources','fixtures'}<=set(registration),
            'Guarded exact source registration subset required')
    require(type(fixture_ids) in (list,tuple) and fixture_ids and all(_name(key) for key in fixture_ids)
        and len(set(fixture_ids))==len(fixture_ids),'Ordered distinct lane identities required')
    guards = registration['guards']
    require(type(guards) is dict and guards,'Nonempty registered source guards required')
    for path,digest in guards.items():
        require(type(path) is str and _hex(digest) and sha(Path(path).read_bytes())==digest,'Registered source guard changed')
    require(type(registration['candidates']) is list and type(registration['sources']) is dict
        and all(name in SOURCE_FAMILIES for name in registration['sources']),'Exact candidate/source collections required')
    candidates = {entry['sha256']:_entry(entry) for entry in registration['candidates']}
    sources = {key:_entry(value) for key,value in registration['sources'].items()}
    fixtures = {row['id']:row for row in registration['fixtures']}
    require(len(candidates)==len(registration['candidates']) and len(fixtures)==len(registration['fixtures'])
        and set(fixture_ids)<=set(fixtures),'Duplicate/foreign candidate or lane')
    lanes = []
    for key in fixture_ids:
        fixture=fixtures[key];seat=fixture['seat']
        require(type(seat) is int and seat in range(4) and fixture['candidate'] in candidates,'Invalid focal source assignment')
        specs = [_spec(raw,seat,sources) for raw in fixture['opponents']]
        require(len(specs)==3 and {row['seat'] for row in specs}==set(range(4))-{seat}
            and len({row['id'] for row in specs})==3,'Exactly three distinct rival constructors required')
        lanes.append(dict(lane_id=key,candidate=candidates[fixture['candidate']],
                          fixture=dict(id=key,seat=seat,opponents=specs)))
    canonical(dict(lanes=lanes,sources=sources))
    return lanes,sources


def compact_lane(board,legal,priority):
    require(type(board) in (list,tuple) and len(board)==64,'One64-cell public board per lane required')
    cells = []
    for cell in board:
        require(type(cell) in (list,tuple) and len(cell)==6
            and type(cell[0]) is int and cell[0] in range(5) and type(cell[1]) is int and cell[1] in range(5)
            and all(type(cell[index]) is bool for index in (2,3,4))
            and type(cell[5]) is int and cell[5] in (1,2,3),'Six exact builtin public cell fields required')
        cells.append(tuple(cell))
    require(sorted(cell[0] for cell in cells if cell[0])==[1,2,3,4],'Exactly one occupant per public seat required')
    require(type(legal) in (list,tuple) and len(legal)==4 and all(type(row) in (list,tuple) and len(row)==6
        and all(type(value) is bool for value in row) and row[4] for row in legal),'Four builtin Boolean legal masks required')
    require(type(priority) in (list,tuple) and len(priority)==4 and all(type(value) is bool for value in priority)
        and sum(priority)==1,'Four consistent builtin public priority flags required')
    return tuple(cells),tuple(tuple(row) for row in legal),tuple(priority)


def freeze_lane(board,legal,priority):
    board,legal,priority = compact_lane(board,legal,priority)
    cells = tuple(Cell(*cell) for cell in board)
    shared = tuple(cells[row*8:(row+1)*8] for row in range(8))
    return tuple(View(shared,seat+1,priority[seat],tuple(action for action in LEGAL_ORDER
                        if legal[seat][ACTIONS.index(action)])) for seat in range(4))


def _projection(namespace,seat):
    if namespace is None:
        return None
    require(not namespace.get('_input_failures',0) and not namespace.get('_policy_failures',0),'Actor input/policy fallback flag')
    histories = namespace.get('_history',{})
    require(type(histories) is dict,'Malformed public actor history')
    memory = histories.get(seat+1,{})
    require(type(memory) is dict,'Malformed own public actor memory')
    if 'cooldown_possible' not in memory:
        return None
    require(not memory.get('inference_failures',0),'Actor public inference fallback')
    progress,scores = memory['progress'],memory['scores']
    require(type(progress) is int and 0<=progress<=80 and type(scores) in (list,tuple) and len(scores)==5
        and all(type(score) is int and 0<=score<2**63 for score in scores),'Malformed inferred public score/progress')
    possible = memory['cooldown_possible'];cooldowns = {}
    require(type(possible) in (dict,list,tuple),'Malformed inferred cooldown sets')
    for who in range(1,5):
        values=possible[who]
        require(type(values) in (set,frozenset,list,tuple) and values
            and all(type(value) is int and value in range(5) for value in values),'Malformed inferred cooldown support')
        cooldowns[str(who)] = sorted(set(values))
    return dict(progress=progress,scores=list(scores),cooldown_possible=cooldowns,inference_failures=0)


def _source_check():
    require(source_pins()==_PINS,'Worker runtime source changed during batch')
    for entry in _ENTRIES:
        _entry(entry)


def _error(error):
    try:
        message=str(error)[:1024]
    except BaseException:
        message='Exception message unavailable'
    return dict(type=type(error).__name__,message=message)


def _dispatch(command):
    global _LANES,_BATCH,_FAILED,_PINS,_ENTRIES
    operation=command.get('operation') if type(command) is dict else None
    active=dict(lane_id=None,seat=None);completed=[];current=None
    try:
        if operation=='reset':
            require(set(command)=={'operation'},'Unknown reset field')
            counters={key:dict(attempts_total=list(row['attempts']),returned_total=list(row['returned']),
                completed_total=list(row['completed']),next_turn=row['next_turn']) for key,row in _LANES.items()}
            failed=_FAILED;_LANES={};_BATCH=None;_FAILED=False;_PINS={};_ENTRIES=()
            return dict(ok=True,operation=operation,pid=os.getpid(),lanes=counters,failed_batch=failed)
        if operation=='initialize':
            require(set(command)=={'operation','batch','lanes','sources'} and _BATCH is None,'Fresh explicit worker reset required')
            _PINS=source_pins();_BATCH=command['batch'];_FAILED=False
            entries=list(command['sources'].values())
            for row in command['lanes']:
                key=row['lane_id'];active['lane_id']=key
                require(key not in _LANES,'Duplicate shard lane')
                entries.append(row['candidate'])
                actors,namespaces=oversight.make_actors(row['candidate'],row['fixture'],command['sources'])
                require(len(actors)==len(namespaces)==4,'Incomplete exact actor constructor result')
                _LANES[key]=dict(actors=actors,namespaces=namespaces,next_turn=1,attempts=[0]*4,returned=[0]*4,completed=[0]*4)
            _ENTRIES=tuple({(entry['path'],entry['sha256']):entry for entry in entries}.values())
            _source_check()
            return dict(ok=True,operation=operation,pid=os.getpid(),batch=_BATCH,lane_ids=list(_LANES),source_sha256=_PINS)
        require(operation=='decide' and set(command)=={'operation','batch','turn','lanes'},'Unknown trusted actor operation/field')
        require(not _FAILED and command['batch']==_BATCH and [row['lane_id'] for row in command['lanes']]==list(_LANES),
                'Failed/foreign/reordered actor shard; no retry')
        turn=command['turn']
        require(type(turn) is int and 1<=turn<=80 and all(row['next_turn']==turn for row in _LANES.values()),
                'Repeated/skipped/terminal actor turn')
        frozen={}
        for row in command['lanes']:
            require(type(row) is dict and set(row)=={'lane_id','board','legal','priority'},'Only compact public fields permitted')
            frozen[row['lane_id']]=freeze_lane(row['board'],row['legal'],row['priority'])
        for key,views in frozen.items():
            lane=_LANES[key];current=dict(lane_id=key,actions=[],proof=dict(attempted_callbacks=0,returned_callbacks=0,
                completed_callbacks=0,timing=[],memory=[]))
            proof=current['proof']
            for seat,view in enumerate(views):
                active.update(lane_id=key,seat=seat)
                item=dict(seat=seat,callback_ms=None,attempted=True,returned=False,completed=False,fallback=False)
                proof['timing'].append(item);proof['attempted_callbacks']+=1;lane['attempts'][seat]+=1
                began=time.perf_counter()
                try:
                    action=lane['actors'][seat](view)
                    item['returned']=True;proof['returned_callbacks']+=1;lane['returned'][seat]+=1
                finally:
                    elapsed=time.perf_counter()-began
                    if math.isfinite(elapsed) and elapsed>=0:
                        item['callback_ms']=elapsed*1000
                    else:
                        item['invalid_duration_repr']=repr(elapsed)
                require(item['callback_ms'] is not None and elapsed<=(2.0 if turn==1 else .2),'Actor callback deadline/nonfinite duration')
                require(type(action) is str and action in view.legal_actions,'Illegal actor decision; no STAY substitute')
                namespace=lane['namespaces'][seat]
                try:
                    memory=_projection(namespace,seat)
                except BaseException:
                    if namespace is not None:
                        histories=namespace.get('_history',{})
                        memory=histories.get(seat+1,{}) if type(histories) is dict else {}
                        item['fallback']=bool(namespace.get('_input_failures',0) or namespace.get('_policy_failures',0)
                                              or (type(memory) is dict and memory.get('inference_failures',0)))
                    raise
                item['completed']=True
                proof['completed_callbacks']+=1;lane['completed'][seat]+=1
                proof['memory'].append(memory);current['actions'].append(action)
            lane['next_turn']+=1
            proof.update(attempts_total=list(lane['attempts']),returned_total=list(lane['returned']),completed_total=list(lane['completed']))
            completed.append(current);current=None
        if turn==80:
            _source_check()
        return dict(ok=True,operation=operation,pid=os.getpid(),batch=_BATCH,turn=turn,lanes=completed)
    except BaseException as error:
        _FAILED=True
        return dict(ok=False,operation=operation,pid=os.getpid(),batch=_BATCH,active=active,error=_error(error),
            completed_lanes=completed,active_partial_lane=current,
            lane_counters={key:dict(attempts_total=list(row['attempts']),returned_total=list(row['returned']),
                completed_total=list(row['completed']),next_turn=row['next_turn']) for key,row in _LANES.items()})


class FastActorPool:
    def __init__(self,worker_count=4,startup_timeout_s=60):
        require(type(worker_count) is int and 1<=worker_count<=8,'One through eight local CPU shards required')
        require(type(startup_timeout_s) in (int,float) and math.isfinite(startup_timeout_s) and 1<=startup_timeout_s<=120,
                'Bounded worker startup timeout required')
        self.worker_count=worker_count;self.startup_timeout_s=startup_timeout_s
        self._executors=[];self._shards=[];self._batch=None;self._ids=[];self._turn=1;self._generation=0
        self._failed=False;self._closed=False;self._transport_failed=False;self._history=[];self._lock=threading.RLock()

    @property
    def evidence(self):
        return copy.deepcopy(self._history)

    def _collect(self,commands,timeout):
        futures=[]
        for executor,command in zip(self._executors,commands):
            try:
                futures.append((executor.submit(_dispatch,command),None))
            except BaseException as error:
                self._transport_failed=True
                futures.append((None,dict(ok=False,error=_error(error),attempt_counts_unknown=True,process_or_transport_failure=True)))
        result=[]
        for future,failure in futures:
            if failure is not None:
                result.append(failure);continue
            try:
                result.append(future.result(timeout=timeout))
            except BaseException as error:
                self._transport_failed=True
                result.append(dict(ok=False,error=_error(error),attempt_counts_unknown=True,process_or_transport_failure=True))
        return result

    def initialize_batch(self,registrationSubset,fixture_ids):
        with self._lock:
            require(not self._closed and not self._failed and self._batch is None,'Close/reset state forbids actor initialization')
            pins=source_pins();lanes,sources=constructor_messages(registrationSubset,fixture_ids)
            self._generation+=1;self._batch=sha(canonical([self._generation,lanes,sources]));self._ids=list(fixture_ids)
            target=min(self.worker_count,len(lanes))
            while len(self._executors)<target:
                self._executors.append(ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn')))
            self._shards=[lanes[index::len(self._executors)] for index in range(len(self._executors))]
            responses=self._collect([dict(operation='initialize',batch=self._batch,lanes=shard,sources=sources)
                                     for shard in self._shards],self.startup_timeout_s)
            event=dict(operation='initialize',batch=self._batch,lane_ids=list(self._ids),responses=responses,
                       source_sha256=pins,admission_credit=0)
            self._history.append(copy.deepcopy(event));self._turn=1
            self._failed=any(not row['ok'] or row.get('source_sha256')!=pins for row in responses)
            if self._failed:
                raise FastActorError(event)
            self._pins=pins
            return event

    def decide_turn(self,compact):
        with self._lock:
            require(not self._closed and not self._failed and self._batch is not None,'Pool inactive/failed; explicit reset required')
            try:
                require(type(compact) is dict and set(compact)=={'turn','lanes'} and type(compact['turn']) is int
                    and compact['turn']==self._turn and self._turn<=80,'Exact next nonterminal public turn required')
                rows=compact['lanes']
                require(type(rows) is list and all(type(row) is dict and set(row)=={'lane_id','board','legal','priority'} for row in rows)
                    and [row['lane_id'] for row in rows]==self._ids,'Exact ordered compact public lane envelope required')
                normalized={}
                for row in rows:
                    board,legal,priority=compact_lane(row['board'],row['legal'],row['priority'])
                    normalized[row['lane_id']]=dict(lane_id=row['lane_id'],board=board,legal=legal,priority=priority)
            except BaseException:
                # No worker call occurred, hence no speculative/hidden attempts.
                raise
            commands=[dict(operation='decide',batch=self._batch,turn=self._turn,
                lanes=[normalized[row['lane_id']] for row in shard]) for shard in self._shards]
            timeout=max(10,(2 if self._turn==1 else .2)*4*max(map(len,self._shards))+5)
            responses=self._collect(commands,timeout)
            if any(not row['ok'] for row in responses):
                self._failed=True
                event=dict(operation='decide',batch=self._batch,turn=self._turn,responses=responses,admission_credit=0)
                self._history.append(copy.deepcopy(event));raise FastActorError(event)
            try:
                returned=[lane for response in responses for lane in response['lanes']]
                indexed={lane['lane_id']:lane for lane in returned}
                require(len(returned)==len(indexed)==len(self._ids) and set(indexed)==set(self._ids),
                        'Incomplete/duplicate actor shard coverage')
                for lane in returned:
                    proof=lane['proof']
                    require(len(lane['actions'])==4 and all(type(action) is str and action in ACTIONS for action in lane['actions'])
                        and all(type(proof[key]) is int and proof[key]==4
                                for key in ('attempted_callbacks','returned_callbacks','completed_callbacks'))
                        and all(proof[key]==[self._turn]*4 and all(type(value) is int for value in proof[key])
                                for key in ('attempts_total','returned_total','completed_total'))
                        and len(proof['timing'])==len(proof['memory'])==4
                        and all(item['seat']==seat and item['attempted'] is True and item['returned'] is True
                                and item['completed'] is True and item['fallback'] is False
                                and type(item['callback_ms']) in (int,float) and math.isfinite(item['callback_ms'])
                                and 0<=item['callback_ms']<=(2000 if self._turn==1 else 200)
                                for seat,item in enumerate(proof['timing'])),
                        'Incomplete/nonfinite actor callback proof')
                if self._turn==80:
                    require(source_pins()==self._pins,'Host actor sources changed during batch')
            except BaseException as error:
                self._failed=True
                event=dict(operation='decide',batch=self._batch,turn=self._turn,responses=responses,
                           host_error=_error(error),admission_credit=0)
                self._history.append(copy.deepcopy(event));raise FastActorError(event) from None
            result=dict(turn=self._turn,lanes=[indexed[key] for key in self._ids],
                worker_chunks=responses,admission_credit=0)
            self._history.append(dict(operation='decide',batch=self._batch,turn=self._turn,
                worker_pids=[row['pid'] for row in responses],
                completed_callbacks=sum(lane['proof']['completed_callbacks'] for lane in returned),admission_credit=0))
            self._turn+=1
            return result

    def _terminate(self):
        for executor in self._executors:
            for process in list((getattr(executor,'_processes',None) or {}).values()):
                if process.is_alive():
                    process.terminate();process.join(timeout=1)
            executor.shutdown(wait=False,cancel_futures=True)
        self._executors=[]

    def reset(self):
        with self._lock:
            require(not self._closed,'Pool closed')
            if self._transport_failed:
                self._terminate();responses=[]
            else:
                responses=self._collect([dict(operation='reset') for _ in self._executors],self.startup_timeout_s) if self._executors else []
            event=dict(operation='reset',batch=self._batch,responses=responses,
                       process_counts_unknown=self._transport_failed,admission_credit=0)
            self._history.append(copy.deepcopy(event))
            if any(not row['ok'] for row in responses):
                self._failed=True;raise FastActorError(event)
            self._batch=None;self._shards=[];self._ids=[];self._turn=1;self._failed=False;self._transport_failed=False
            return event

    def close(self):
        with self._lock:
            if self._closed:
                return self.evidence
            try:
                self.reset()
            finally:
                if self._transport_failed:
                    self._terminate()
                else:
                    for executor in self._executors:
                        executor.shutdown(wait=True,cancel_futures=True)
                self._executors=[];self._closed=True
            return self.evidence

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()
