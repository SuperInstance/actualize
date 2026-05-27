"""Goal definition with decomposition, priority, and dependency management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable


class Priority(IntEnum):
    """Goal priority levels. Higher value = higher priority."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Goal:
    """A goal that can be decomposed into sub-goals.

    Attributes:
        name: Human-readable goal name.
        description: What this goal represents.
        priority: Priority level for scheduling.
        parent: Optional parent goal (set automatically for sub-goals).
        sub_goals: Child goals this goal decomposes into.
        depends_on: Goals that must complete before this one can start.
        action: Optional callable to execute when this goal is reached directly.
        id: Unique identifier (auto-generated if not provided).
    """

    name: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    parent: Goal | None = field(default=None, repr=False)
    sub_goals: list[Goal] = field(default_factory=list)
    depends_on: list[Goal] = field(default_factory=list)
    action: Callable[[], None] | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # -- mutation helpers --

    def add_sub_goal(self, goal: Goal) -> Goal:
        """Add a sub-goal and link it back to this parent."""
        goal.parent = self
        self.sub_goals.append(goal)
        return goal

    def depends_on_goal(self, *goals: Goal) -> None:
        """Register one or more goals as dependencies."""
        for g in goals:
            if g not in self.depends_on:
                self.depends_on.append(g)

    # -- queries --

    @property
    def is_leaf(self) -> bool:
        """True if this goal has no sub-goals."""
        return len(self.sub_goals) == 0

    @property
    def depth(self) -> int:
        """Depth in the goal tree (root = 0)."""
        return 0 if self.parent is None else self.parent.depth + 1

    @property
    def root(self) -> Goal:
        """Walk up to the root goal."""
        return self if self.parent is None else self.parent.root

    def all_goals(self) -> list[Goal]:
        """Flatten this goal and all descendants."""
        result = [self]
        for sg in self.sub_goals:
            result.extend(sg.all_goals())
        return result

    def leaf_goals(self) -> list[Goal]:
        """Return only leaf goals (no sub-goals)."""
        if self.is_leaf:
            return [self]
        result: list[Goal] = []
        for sg in self.sub_goals:
            result.extend(sg.leaf_goals())
        return result

    def validate(self) -> list[str]:
        """Check for issues. Returns a list of warnings (empty = valid)."""
        warnings: list[str] = []
        seen_ids: set[str] = set()
        for g in self.all_goals():
            if g.id in seen_ids:
                warnings.append(f"Duplicate goal id: {g.id}")
            seen_ids.add(g.id)
            if not g.name.strip():
                warnings.append(f"Goal {g.id} has an empty name")
        # Check for circular dependencies among all goals
        all_goals = self.all_goals()
        goal_map = {g.id: g for g in all_goals}
        for g in all_goals:
            visited: set[str] = set()
            queue = list(g.depends_on)
            while queue:
                dep = queue.pop()
                if dep.id == g.id:
                    warnings.append(f"Circular dependency involving goal {g.id}")
                    break
                if dep.id not in visited:
                    visited.add(dep.id)
                    queue.extend(dep.depends_on)
        return warnings
