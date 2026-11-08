"""Optional CUDA Graph of one unchanged frozen-policy/physics public step."""
import torch

from search_coach.gpu_batch import _public_adapter, public_policy


class PublicStepGraph:
    def __init__(self, batch, focal, prefix_steps):
        from .tensor import packed_public
        if batch.dev.type != 'cuda':
            raise ValueError('CUDA Graph requires a CUDA batch')
        self.batch, self.focal = batch, focal
        self.row = torch.arange(batch.n, device=batch.dev)
        self.keys = torch.zeros(batch.n*4, device=batch.dev, dtype=torch.long)
        self.steps = prefix_steps.unsqueeze(1).expand(batch.n, 4).reshape(-1).clone()
        self.wanted = torch.full((batch.n,), 4, device=batch.dev, dtype=torch.long)
        self.override = torch.zeros(batch.n, device=batch.dev, dtype=torch.bool)
        self.powers = torch.tensor([1, 2, 4, 8, 16, 32], device=batch.dev, dtype=torch.long)
        names = ('owner', 'upg', 'pos', 'frozen', 'cd', 'prog', 'score', 'income', 'token')
        # BatchGame.step rebinds some state tensors. Copy its exact outputs into
        # stable input buffers so replay never reads the original capture state.
        stable = {name: getattr(batch, name) for name in names}
        def one_step():
            public = _public_adapter(batch)
            actions = public_policy(public, self.keys, self.steps).reshape(batch.n, 4)
            actions[self.row, focal] = torch.where(self.override, self.wanted, actions[self.row, focal])
            batch.step(actions)
            packed = packed_public(_public_adapter(batch), focal, powers=self.powers)
            for name, buffer in stable.items():
                buffer.copy_(getattr(batch, name))
                setattr(batch, name, buffer)
            return actions, packed
        # Warm/capture work is included in setup time and never receives game
        # credit. The caller restores every mutable field before simulation0.
        stream = torch.cuda.Stream(device=batch.dev)
        stream.wait_stream(torch.cuda.current_stream(batch.dev))
        with torch.cuda.stream(stream):
            for _ in range(2):
                one_step()
        torch.cuda.current_stream(batch.dev).wait_stream(stream)
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph):
            self.actions, self.packed = one_step()
        self.prefix_steps = prefix_steps

    def set_keys(self, keys):
        self.keys.copy_(keys.reshape(-1))

    def step(self, requested, depth):
        self.wanted.copy_(torch.tensor([4 if action is None else action for action in requested],
                                      device=self.batch.dev, dtype=torch.long))
        self.override.copy_(torch.tensor([action is not None for action in requested],
                                        device=self.batch.dev, dtype=torch.bool))
        self.steps.copy_((self.prefix_steps+depth).unsqueeze(1).expand(self.batch.n, 4).reshape(-1))
        self.graph.replay()
        return self.actions, self.packed
