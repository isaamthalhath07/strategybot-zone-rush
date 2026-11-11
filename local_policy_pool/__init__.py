"""Unused local CPU actor-pool prototype; no CUDA/study admission integration."""

from .pool import ActorPool, PoolExecutionError

__all__ = ['ActorPool', 'PoolExecutionError']
