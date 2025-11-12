"""
Subsystem Execution Phases

Defines the fixed phases in which subsystems execute during each tick.
Phases are executed in the order defined here.
"""
from enum import Enum


class SubsystemPhase(str, Enum):
    """
    Fixed execution phases for subsystems.

    Subsystems are grouped into phases that execute in order:
    1. INTENTS - Player/NPC intent collection and validation
    2. ECONOMY - Economic simulation (production, trade, consumption)
    3. POLITICS - Political events, diplomacy, alliances
    4. WEATHER - Environmental effects and disasters
    5. CLEANUP - Post-processing, notifications, cleanup

    Each phase executes all its subsystems before moving to the next phase.
    Within a phase, subsystems are ordered by their dependencies.
    """

    INTENTS = "intents"
    ECONOMY = "economy"
    POLITICS = "politics"
    WEATHER = "weather"
    CLEANUP = "cleanup"

    @classmethod
    def execution_order(cls) -> list["SubsystemPhase"]:
        """
        Get the phases in their execution order.

        Returns:
            List of phases in the order they should execute
        """
        return [
            cls.INTENTS,
            cls.ECONOMY,
            cls.POLITICS,
            cls.WEATHER,
            cls.CLEANUP,
        ]

    def __lt__(self, other: "SubsystemPhase") -> bool:
        """
        Compare phases by their execution order.

        Args:
            other: Another phase to compare to

        Returns:
            True if this phase executes before the other
        """
        if not isinstance(other, SubsystemPhase):
            return NotImplemented
        order = self.execution_order()
        return order.index(self) < order.index(other)
