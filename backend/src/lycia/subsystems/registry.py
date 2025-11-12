"""
Subsystem Registry

Manages registration, dependency resolution, and execution order of subsystems.
"""
from typing import Any
from collections import defaultdict, deque
from .protocol import Subsystem
from .phase import SubsystemPhase


class DependencyCycleError(Exception):
    """Raised when a dependency cycle is detected in subsystems."""
    pass


class SubsystemNotFoundError(Exception):
    """Raised when a referenced subsystem is not registered."""
    pass


class InvalidDependencyError(Exception):
    """Raised when a dependency violates phase ordering rules."""
    pass


class SubsystemRegistry:
    """
    Registry for managing subsystems and their execution order.

    Handles:
    - Subsystem registration and removal
    - Topological sorting based on dependencies
    - Dependency cycle detection
    - Phase ordering validation
    """

    def __init__(self):
        """Initialize empty registry."""
        self._subsystems: dict[str, Subsystem] = {}
        self._execution_order: list[Subsystem] = []
        self._sorted = False

    def register(self, subsystem: Subsystem) -> None:
        """
        Register a subsystem.

        Args:
            subsystem: Subsystem to register

        Raises:
            ValueError: If subsystem with same name already registered
        """
        if subsystem.name in self._subsystems:
            raise ValueError(f"Subsystem '{subsystem.name}' is already registered")

        self._subsystems[subsystem.name] = subsystem
        self._sorted = False  # Invalidate cached order

    def unregister(self, name: str) -> None:
        """
        Unregister a subsystem by name.

        Args:
            name: Name of subsystem to remove

        Raises:
            SubsystemNotFoundError: If subsystem not found
        """
        if name not in self._subsystems:
            raise SubsystemNotFoundError(f"Subsystem '{name}' not found")

        del self._subsystems[name]
        self._sorted = False  # Invalidate cached order

    def get_execution_order(self) -> list[Subsystem]:
        """
        Get subsystems in their execution order.

        Performs topological sort if needed, then caches the result.

        Returns:
            List of subsystems in execution order

        Raises:
            DependencyCycleError: If circular dependencies detected
            SubsystemNotFoundError: If a dependency references unknown subsystem
            InvalidDependencyError: If dependency violates phase rules
        """
        if not self._sorted:
            self._execution_order = self._topological_sort()
            self._sorted = True

        return self._execution_order.copy()

    def _topological_sort(self) -> list[Subsystem]:
        """
        Perform topological sort of subsystems.

        Uses Kahn's algorithm with phase grouping.

        Returns:
            Sorted list of subsystems

        Raises:
            DependencyCycleError: If circular dependencies exist
            SubsystemNotFoundError: If dependency not found
            InvalidDependencyError: If dependency violates phase rules
        """
        # Validate all dependencies exist and phase rules are satisfied
        self._validate_dependencies()

        # Group subsystems by phase
        by_phase: dict[SubsystemPhase, list[Subsystem]] = defaultdict(list)
        for subsystem in self._subsystems.values():
            by_phase[subsystem.phase].append(subsystem)

        result: list[Subsystem] = []

        # Process each phase in order
        for phase in SubsystemPhase.execution_order():
            phase_subsystems = by_phase.get(phase, [])
            if not phase_subsystems:
                continue

            # Sort subsystems within this phase by dependencies
            sorted_phase = self._sort_within_phase(phase_subsystems)
            result.extend(sorted_phase)

        return result

    def _sort_within_phase(self, subsystems: list[Subsystem]) -> list[Subsystem]:
        """
        Sort subsystems within a single phase using topological sort.

        Args:
            subsystems: Subsystems in this phase

        Returns:
            Topologically sorted subsystems

        Raises:
            DependencyCycleError: If circular dependencies exist within phase
        """
        # Build adjacency list and in-degree count for subsystems in this phase
        subsystem_names = {s.name for s in subsystems}
        in_degree: dict[str, int] = {s.name: 0 for s in subsystems}
        adjacency: dict[str, list[str]] = {s.name: [] for s in subsystems}

        for subsystem in subsystems:
            for dep in subsystem.dependencies:
                # Only consider dependencies within this phase
                if dep in subsystem_names:
                    adjacency[dep].append(subsystem.name)
                    in_degree[subsystem.name] += 1

        # Kahn's algorithm
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        sorted_names: list[str] = []

        while queue:
            current = queue.popleft()
            sorted_names.append(current)

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_names) != len(subsystems):
            unsorted = [name for name in in_degree if name not in sorted_names]
            raise DependencyCycleError(
                f"Dependency cycle detected among subsystems: {unsorted}"
            )

        # Convert names back to subsystem objects
        name_to_subsystem = {s.name: s for s in subsystems}
        return [name_to_subsystem[name] for name in sorted_names]

    def _validate_dependencies(self) -> None:
        """
        Validate all subsystem dependencies.

        Raises:
            SubsystemNotFoundError: If dependency not found
            InvalidDependencyError: If dependency violates phase rules
        """
        for subsystem in self._subsystems.values():
            for dep_name in subsystem.dependencies:
                # Check dependency exists
                if dep_name not in self._subsystems:
                    raise SubsystemNotFoundError(
                        f"Subsystem '{subsystem.name}' depends on '{dep_name}', "
                        f"which is not registered"
                    )

                # Check phase ordering: can only depend on same or earlier phases
                dep = self._subsystems[dep_name]
                if dep.phase > subsystem.phase:
                    raise InvalidDependencyError(
                        f"Subsystem '{subsystem.name}' (phase {subsystem.phase.value}) "
                        f"cannot depend on '{dep_name}' (phase {dep.phase.value}). "
                        f"Dependencies must be in the same or earlier phases."
                    )

    def clear(self) -> None:
        """Remove all registered subsystems."""
        self._subsystems.clear()
        self._execution_order.clear()
        self._sorted = False

    def get(self, name: str) -> Subsystem | None:
        """
        Get a subsystem by name.

        Args:
            name: Subsystem name

        Returns:
            Subsystem if found, None otherwise
        """
        return self._subsystems.get(name)

    def list_subsystems(self) -> list[str]:
        """
        Get names of all registered subsystems.

        Returns:
            List of subsystem names
        """
        return list(self._subsystems.keys())

    def count(self) -> int:
        """
        Get number of registered subsystems.

        Returns:
            Count of subsystems
        """
        return len(self._subsystems)
