"""
Action handler registry.

This module provides a registry for managing action handlers by intent@version.
The registry is used to route commands to the appropriate handler during
the INTENTS phase of tick execution.
"""

from typing import cast
from .protocol import ActionHandler


class ActionHandlerRegistry:
    """
    Registry for action handlers keyed by intent@version.

    This registry allows multiple versions of the same handler to coexist,
    enabling backward compatibility when handler logic changes.

    Example:
        registry = ActionHandlerRegistry()
        registry.register(MoveUnitHandlerV1())
        registry.register(MoveUnitHandlerV2())

        handler = registry.get("move_unit", version=2)
        handler = registry.get_latest("move_unit")
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._handlers: dict[str, ActionHandler] = {}

    def _make_key(self, intent: str, version: int) -> str:
        """Create registry key from intent and version."""
        return f"{intent}@{version}"

    def register(self, handler: ActionHandler) -> None:
        """
        Register an action handler.

        Args:
            handler: The handler to register

        Raises:
            ValueError: If a handler with the same intent@version is already registered
        """
        key = self._make_key(handler.intent, handler.version)
        if key in self._handlers:
            raise ValueError(
                f"Handler for {key} already registered. "
                f"Use a different version number or unregister the existing handler."
            )
        self._handlers[key] = handler

    def unregister(self, intent: str, version: int) -> None:
        """
        Unregister an action handler.

        Args:
            intent: The intent identifier
            version: The handler version

        Raises:
            KeyError: If no handler is registered for the given intent@version
        """
        key = self._make_key(intent, version)
        if key not in self._handlers:
            raise KeyError(f"No handler registered for {key}")
        del self._handlers[key]

    def get(self, intent: str, version: int) -> ActionHandler | None:
        """
        Get a specific version of a handler.

        Args:
            intent: The intent identifier
            version: The handler version

        Returns:
            The handler if found, None otherwise
        """
        key = self._make_key(intent, version)
        return self._handlers.get(key)

    def get_latest(self, intent: str) -> ActionHandler | None:
        """
        Get the latest version of a handler for an intent.

        Args:
            intent: The intent identifier

        Returns:
            The handler with the highest version number, or None if no handlers found
        """
        matching_handlers = [
            (handler.version, handler)
            for key, handler in self._handlers.items()
            if handler.intent == intent
        ]

        if not matching_handlers:
            return None

        # Return handler with highest version
        matching_handlers.sort(key=lambda x: x[0], reverse=True)
        return matching_handlers[0][1]

    def list_handlers(self) -> list[tuple[str, int]]:
        """
        List all registered handlers.

        Returns:
            List of (intent, version) tuples
        """
        return [(handler.intent, handler.version) for handler in self._handlers.values()]

    def list_versions(self, intent: str) -> list[int]:
        """
        List all versions of a specific intent.

        Args:
            intent: The intent identifier

        Returns:
            Sorted list of version numbers (highest first)
        """
        versions = [
            handler.version
            for handler in self._handlers.values()
            if handler.intent == intent
        ]
        return sorted(versions, reverse=True)

    def has_handler(self, intent: str, version: int) -> bool:
        """
        Check if a handler is registered.

        Args:
            intent: The intent identifier
            version: The handler version

        Returns:
            True if handler is registered, False otherwise
        """
        key = self._make_key(intent, version)
        return key in self._handlers

    def clear(self) -> None:
        """Clear all registered handlers (mainly for testing)."""
        self._handlers.clear()


# Global singleton registry
_global_registry: ActionHandlerRegistry | None = None


def get_action_handler_registry() -> ActionHandlerRegistry:
    """
    Get the global action handler registry.

    This is a singleton pattern to ensure all parts of the application
    use the same registry instance.

    Returns:
        The global ActionHandlerRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ActionHandlerRegistry()
    return _global_registry
