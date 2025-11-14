"""
Action command processing framework.

This module provides the infrastructure for handling player and AI actions
through a command queue pattern with validation and event sourcing.

Key Components:
- ActionHandler: Protocol for action handlers
- ActionHandlerRegistry: Registry for managing handlers by intent@version
- ValidationResult: Structured validation results
- Example handlers in actions/handlers/
"""

from .protocol import ActionHandler, ValidationResult, ValidationError
from .registry import ActionHandlerRegistry, get_action_handler_registry

__all__ = [
    "ActionHandler",
    "ValidationResult",
    "ValidationError",
    "ActionHandlerRegistry",
    "get_action_handler_registry",
]
