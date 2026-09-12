"""
Long-running JMeter execution support.

Provides a run registry, an async run manager, and live JTL metrics.
"""

from runs.registry import RunRecord, RunRegistry
from runs.manager import RunManager, get_run_manager

__all__ = ['RunRecord', 'RunRegistry', 'RunManager', 'get_run_manager']
