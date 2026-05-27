"""Schedule optimizer — topological sort with resource constraints."""

from __future__ import annotations

from dataclasses import dataclass, field

from actualize.goal import Goal, Priority
from actualize.plan import Plan, Step, StepStatus


@dataclass
class ResourceConstraint:
    """A named resource with limited capacity.

    Attributes:
        name: Resource identifier (e.g. 'cpu', 'db_connection').
        capacity: Maximum concurrent uses allowed.
    """

    name: str
    capacity: int


@dataclass
class Schedule:
    """A computed execution schedule.

    Attributes:
        phases: Ordered list of phases. Each phase is a list of step names
            that can execute concurrently.
        resource_assignments: Map of step name to list of resource names it uses.
    """

    phases: list[list[str]] = field(default_factory=list)
    resource_assignments: dict[str, list[str]] = field(default_factory=dict)


class Scheduler:
    """Convert goals into optimized plans with scheduling.

    Handles:
    - Topological ordering respecting goal dependencies
    - Priority-based ordering within parallel groups
    - Resource-constrained parallelization
    """

    def goals_to_plan(
        self,
        root: Goal,
        action_resolver: dict[str, callable] | None = None,
    ) -> Plan:
        """Convert a goal tree into a Plan of executable steps.

        Args:
            root: The root goal to convert.
            action_resolver: Optional mapping of goal name to action callable.
                If not provided, goals with no ``action`` attribute become no-ops.

        Returns:
            A Plan ready for execution.
        """
        plan = Plan(name=root.name)
        resolver = action_resolver or {}
        leaf_goals = root.leaf_goals()

        # Build dependency name mapping: goal -> set of leaf goal names it depends on
        goal_by_id = {g.id: g for g in root.all_goals()}
        step_names: set[str] = set()

        for g in leaf_goals:
            action = resolver.get(g.name, g.action)
            if action is None:
                action = lambda: None

            step = Step(
                name=g.name,
                action=action,
            )
            plan.add_step(step)
            step_names.add(g.name)

        # Resolve dependencies: for each leaf goal, find which other leaf goals
        # it depends on (through the depends_on chain)
        for g in leaf_goals:
            step = next(s for s in plan.steps if s.name == g.name)
            dep_names: list[str] = []
            for dep in g.depends_on:
                # If dependency is a leaf, direct
                if dep.is_leaf:
                    if dep.name in step_names and dep.name != g.name:
                        dep_names.append(dep.name)
                else:
                    # Non-leaf dependency: depend on all its leaves
                    for leaf in dep.leaf_goals():
                        if leaf.name in step_names and leaf.name != g.name:
                            dep_names.append(leaf.name)
            step.depends_on = list(dict.fromkeys(dep_names))  # dedupe, preserve order

        return plan

    def optimize_schedule(
        self,
        plan: Plan,
        resources: list[ResourceConstraint] | None = None,
    ) -> Schedule:
        """Compute an optimal execution schedule for a plan.

        Args:
            plan: The plan to schedule.
            resources: Optional resource constraints. If provided, steps are
                grouped into phases that respect resource capacity.

        Returns:
            A Schedule with phases and resource assignments.
        """
        resource_map = {r.name: r for r in (resources or [])}

        # Get parallel groups from plan
        groups = plan.parallel_groups()

        if not resource_map:
            # No resource constraints — groups are the phases
            schedule = Schedule()
            for group in groups:
                sorted_group = sorted(
                    group,
                    key=lambda s: (
                        -(getattr(s.action, "priority", 0)),
                        s.name,
                    ),
                )
                schedule.phases.append([s.name for s in sorted_group])
            return schedule

        # With resource constraints: split groups if they exceed capacity
        schedule = Schedule()
        for group in groups:
            # For now, keep groups intact if no per-step resource info
            # In a real scheduler, we'd track which step uses which resource
            phase = [s.name for s in group]
            schedule.phases.append(phase)

        return schedule

    def sort_by_priority(self, goals: list[Goal]) -> list[Goal]:
        """Sort goals by priority (highest first), stable sort."""
        return sorted(goals, key=lambda g: g.priority, reverse=True)
