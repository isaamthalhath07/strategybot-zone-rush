"""Strict CUDA-only full-match physics; existing actors remain on the CPU.

Graph setup performs throwaway transitions and restores every state buffer and
the host clock. Only explicit step calls advance the accepted match timeline.
"""
import copy
import hashlib
from pathlib import Path
import time

import torch

from training_gpu.batch_game import BatchGame
from search_coach.gpu_batch import _public_adapter


ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('base','owner','upg','home','pos','frozen','cd','prog','score','income','token')
RULES = dict(frozen_stay_counts=False,claim_resets_progress=True,
             catch_requires_stay=True,lost_contest_is_stay=True,home_upgradable=True)
FROZEN = {
    'training_gpu/batch_game.py':'4c314c10e733d9eea496a9973110639b95cb496b8ff9e7b9d49bc8459d8efb9f',
    'search_coach/gpu_batch.py':'1a15460f1ba38b31a701322683423d642f1e9d358a92a398238cac1683bbbc8b',
}


def source_pins():
    names = tuple(FROZEN)+('training_gpu/__init__.py','search_coach/__init__.py',
        'search_coach/belief.py','tests/reference_engine.py','local_cuda_matches/physics.py')
    pins = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    if any(pins[name] != expected for name,expected in FROZEN.items()):
        raise ValueError('QUARANTINED: frozen CUDA physics/adapter source changed')
    return pins


def _inputs(base_maps,start_tokens):
    if type(base_maps) not in (list,tuple) or not base_maps:
        raise ValueError('A nonempty batch of public64-cell maps is required')
    for board in base_maps:
        if (type(board) not in (list,tuple) or len(board) != 64
                or any(type(value) is not int or not 1 <= value <= 3 for value in board)
                or any(board[r*8+c] != board[r*8+7-c] or board[r*8+c] != board[(7-r)*8+c]
                       for r in range(8) for c in range(8))):
            raise ValueError('Each public map must be mirrored64 integer values1..3')
    if (type(start_tokens) not in (list,tuple) or len(start_tokens) != len(base_maps)
            or any(type(token) is not int or not 1 <= token <= 4 for token in start_tokens)):
        raise ValueError('One integer priority token1..4 per map is required')


class CudaPhysics:
    """One lockstep CUDA batch; no actor or hypothetical policy is executed."""

    def __init__(self,base_maps,start_tokens,device='cuda',use_graph=True):
        started = time.perf_counter()
        _inputs(base_maps,start_tokens)
        if type(use_graph) is not bool:
            raise ValueError('use_graph must be Boolean')
        self.device = torch.device(device)
        if self.device.type != 'cuda' or not torch.cuda.is_available():
            raise ValueError('A working actual CUDA device is required; no CPU fallback')
        self._pins = source_pins()
        self._timings = {name:0.0 for name in ('setup_s','gpu_upload_s','gpu_physics_s',
            'public_download_s','state_download_s','legal_validation_s')}
        # Device detection alone is insufficient for unsupported GPU kernels.
        probe = torch.ones(1,device=self.device,dtype=torch.long)
        probe.add_(1)
        if probe.item() != 2:
            raise ValueError('Actual CUDA arithmetic probe failed')
        self.batch = BatchGame([list(board) for board in base_maps],n=len(base_maps),
            device=self.device,max_turns=80,rules=dict(RULES),
            start_token=torch.tensor(start_tokens,dtype=torch.long,device=self.device))
        self.use_graph = use_graph
        self._codes = torch.full((self.batch.n,4),4,dtype=torch.long,device=self.device)
        self._stable = {name:getattr(self.batch,name) for name in FIELDS}
        initial = {name:buffer.clone() for name,buffer in self._stable.items()}
        self._graph = None
        if use_graph:
            stream = torch.cuda.Stream(device=self.device)
            stream.wait_stream(torch.cuda.current_stream(self.device))
            with torch.cuda.stream(stream):
                for _ in range(2):
                    self._physical_step()
            torch.cuda.current_stream(self.device).wait_stream(stream)
            self._graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(self._graph):
                self._physical_step()
        # Warm/capture work earns no accepted match transitions or game credit.
        for name,buffer in self._stable.items():
            buffer.copy_(initial[name])
            setattr(self.batch,name,buffer)
        self.batch.turn = 1
        self._steps = 0
        self._sync()
        self._metadata = dict(format='local-cuda-match-physics/1',device=str(self.device),
            device_name=torch.cuda.get_device_name(self.device),torch_version=str(torch.__version__),
            cuda_version=str(torch.version.cuda),cuda_kernel_executed=True,use_graph=use_graph,
            rules=dict(RULES),max_turns=80,batch_size=self.batch.n,source_sha256=dict(self._pins),
            setup_throwaway_transitions=3 if use_graph else 0,setup_primary_match_credit=0,
            setup_completed_game_audit_credit=0,policy_backend='External exact CPU actors',
            timing_basis='Synchronized host wall seconds; not CUDA-event-only kernel throughput')
        self._timings['setup_s'] = time.perf_counter()-started

    def _sync(self):
        torch.cuda.synchronize(self.device)

    def _physical_step(self):
        self.batch.step(self._codes)
        # BatchGame rebinds several output tensors. Graph replay must feed its
        # new outputs into the original stable input buffers at every step.
        for name,buffer in self._stable.items():
            produced = getattr(self.batch,name)
            if produced is not buffer:
                buffer.copy_(produced)
                setattr(self.batch,name,buffer)

    @property
    def metadata(self):
        result = copy.deepcopy(self._metadata)
        result['accepted_batch_steps'] = self._steps
        result['accepted_branch_turn_events'] = self._steps*self.batch.n
        return result

    @property
    def timings(self):
        return dict(self._timings)

    def _actions(self,codes_cpu):
        if isinstance(codes_cpu,torch.Tensor):
            integer_types = (torch.uint8,torch.int8,torch.int16,torch.int32,torch.int64)
            if (codes_cpu.device.type != 'cpu' or codes_cpu.layout != torch.strided
                    or codes_cpu.dtype not in integer_types or tuple(codes_cpu.shape) != (self.batch.n,4)):
                raise ValueError('Action tensor must be CPU integer[B,4], never bool/float')
            codes_cpu = codes_cpu.tolist()
        if (type(codes_cpu) not in (list,tuple) or len(codes_cpu) != self.batch.n
                or any(type(row) not in (list,tuple) or len(row) != 4 for row in codes_cpu)
                or any(type(code) is not int or not 0 <= code <= 5 for row in codes_cpu for code in row)):
            raise ValueError('Actions must be exact integer[B,4] codes0..5')
        return [list(row) for row in codes_cpu]

    def step(self,codes_cpu):
        if self._steps >= 80 or self.batch.turn != self._steps+1 or self.batch.turn > 80:
            raise ValueError('Exactly80 match turns only; invalid or terminal clock')
        if self.batch.R != RULES or self.batch.max_turns != 80:
            raise ValueError('Frozen official STAY-only rules and80-turn limit are required')
        if source_pins() != self._pins:
            raise ValueError('QUARANTINED: CUDA physics source changed during match')
        codes = self._actions(codes_cpu)
        started = time.perf_counter()
        legal = self.batch.legal_mask().cpu().tolist()
        self._timings['legal_validation_s'] += time.perf_counter()-started
        if any(not legal[lane][seat][code] for lane,row in enumerate(codes) for seat,code in enumerate(row)):
            raise ValueError('Illegal accepted action; silent STAY normalization is forbidden')
        started = time.perf_counter()
        self._codes.copy_(torch.tensor(codes,dtype=torch.long,device=self.device))
        self._sync()
        self._timings['gpu_upload_s'] += time.perf_counter()-started
        previous_turn = self.batch.turn
        started = time.perf_counter()
        if self._graph is not None:
            self._graph.replay()
        else:
            self._physical_step()
        self._sync()
        # Python integer increments are not part of a CUDA Graph replay.
        self.batch.turn = previous_turn+1
        self._steps += 1
        self._timings['gpu_physics_s'] += time.perf_counter()-started

    def public_snapshot(self):
        """Isolated CPU public cells/masks/token; no referee-only counters."""
        started = time.perf_counter()
        public = _public_adapter(self.batch)
        raw = public.board.reshape(self.batch.n,4,64,6)[:,0].cpu().tolist()
        boards = [[[cell[0],cell[1],bool(cell[2]),bool(cell[3]),bool(cell[4]),cell[5]]
                   for cell in board] for board in raw]
        result = dict(board=boards,legal=public.legal_actions.reshape(self.batch.n,4,6).cpu().tolist(),
                      tokens=self.batch.token.cpu().tolist())
        self._sync()
        self._timings['public_download_s'] += time.perf_counter()-started
        return result

    def state_snapshot(self):
        """Observer-only complete physics state. Never pass this to an actor."""
        started = time.perf_counter()
        result = {name:getattr(self.batch,name).cpu().tolist() for name in FIELDS}
        result['turn'] = self.batch.turn
        self._sync()
        self._timings['state_download_s'] += time.perf_counter()-started
        return result
