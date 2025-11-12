"""
Subsystem Pipeline & Registry

This module provides the extensibility framework for the tick system.
Subsystems can be registered and will be executed in a deterministic order
based on phases and dependencies.
"""

from .phase import SubsystemPhase
from .protocol import Subsystem, TickContext
from .registry import SubsystemRegistry
from .context import TickContextImpl

__all__ = [
    "SubsystemPhase",
    "Subsystem",
    "TickContext",
    "SubsystemRegistry",
    "TickContextImpl",
]
