"""Plan representation with steps, ordering, and parallelization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class StepStatus(Enum):
    """Status of a single plan step."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


@dataclass
class Step:
    """A single executable step in a plan.

    Attributes:
        name: Human-readable step name.
        action: Callable to execute. Receives no arguments; return value ignored.
        rollback: Optional callable to undo side-effects on failure.
        depends_on: Step names this step must wait for.
        status: Current execution status.
        error: Exception stored on failure, if any.
        id: Unique identifier.
    """

    name: str
    action: Callable[[], Any]
    rollback: Callable[[], None] | None = None
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    error: Exception | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def reset(self) -> None:
        """Reset step to pending state."""
        self.status = StepStatus.PENDING
        self.error = None


@dataclass
class Plan:
    """An ordered collection of steps, built from goals.

    Attributes:
        name: Plan name (usually the root goal name).
        steps: Ordered list of steps.
        id: Unique identifier.
    """

    name: str = "plan"
    steps: list[Step] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # -- mutation --

    def add_step(self, step: Step) -> Step:
        """Add a step to the plan."""
        self.steps.append(step)
        return step

    # -- queries --

    def topological_order(self) -> list[Step]:
        """Return steps in dependency-respecting order.

        Raises ValueError if there's a cycle.
        """
        name_map = {s.name: s for s in self.steps}
        in_degree: dict[str, int] = {s.name: 0 for s in self.steps}
        adjacency: dict[str, list[str]] = {s.name: [] for s in self.steps}

        for s in self.steps:
            for dep_name in s.depends_on:
                if dep_name not in name_map:
                    raise ValueError(
                        f"Step '{s.name}' depends on unknown step '{dep_name}'"
                    )
                adjacency[dep_name].append(s.name)
                in_degree[s.name] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        order: list[Step] = []

        while queue:
            queue.sort()  # deterministic ordering
            current = queue.pop(0)
            order.append(name_map[current])
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.steps):
            raise ValueError("Circular dependency detected in plan steps")

        return order

    def parallel_groups(self) -> list[list[Step]]:
        """Group steps into layers that can run in parallel.

        Each inner list contains steps that have no inter-dependencies
        and can execute concurrently.
        """
        order = self.topological_order()
        name_map = {s.name: s for s in self.steps}
        group_of: dict[str, int] = {}

        for step in order:
            if not step.depends_on:
                group_of[step.name] = 0
            else:
                group_of[step.name] = max(group_of[d] for d in step.depends_on) + 1

        max_group = max(group_of.values()) if group_of else 0
        result: list[list[Step]] = [[] for _ in range(max_group + 1)]
        for name, gi in group_of.items():
            result[gi].append(name_map[name])
        return result

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.DONE)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    @property
    def progress_pct(self) -> float:
        """Completion percentage (0.0 - 100.0)."""
        if not self.steps:
            return 0.0
        return (self.completed_steps / len(self.steps)) * 100.0
