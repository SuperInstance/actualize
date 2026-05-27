"""Tests for actualize.scheduler."""

from actualize.goal import Goal, Priority
from actualize.plan import Plan, Step
from actualize.scheduler import Scheduler, ResourceConstraint


def _noop():
    pass


class TestGoalsToPlan:
    def test_flat_goals(self):
        root = Goal(name="Project")
        root.add_sub_goal(Goal(name="Task A", action=_noop))
        root.add_sub_goal(Goal(name="Task B", action=_noop))
        scheduler = Scheduler()
        plan = scheduler.goals_to_plan(root)
        assert plan.total_steps == 2
        assert plan.name == "Project"

    def test_dependencies_carried(self):
        root = Goal(name="Project")
        a = root.add_sub_goal(Goal(name="A", action=_noop))
        b = root.add_sub_goal(Goal(name="B", action=_noop))
        b.depends_on_goal(a)
        plan = Scheduler().goals_to_plan(root)
        step_b = next(s for s in plan.steps if s.name == "B")
        assert "A" in step_b.depends_on

    def test_action_resolver(self):
        calls = []
        root = Goal(name="R")
        root.add_sub_goal(Goal(name="Do X"))
        plan = Scheduler().goals_to_plan(
            root, action_resolver={"Do X": lambda: calls.append("x")}
        )
        step = plan.steps[0]
        step.action()
        assert calls == ["x"]

    def test_nested_subgoals_flatten_to_leaves(self):
        root = Goal(name="Project")
        sub = root.add_sub_goal(Goal(name="Sub"))
        sub.add_sub_goal(Goal(name="Leaf 1", action=_noop))
        sub.add_sub_goal(Goal(name="Leaf 2", action=_noop))
        plan = Scheduler().goals_to_plan(root)
        assert plan.total_steps == 2


class TestOptimizeSchedule:
    def test_parallel_no_resources(self):
        plan = Plan()
        plan.add_step(Step(name="a", action=_noop))
        plan.add_step(Step(name="b", action=_noop))
        schedule = Scheduler().optimize_schedule(plan)
        assert len(schedule.phases) == 1
        assert set(schedule.phases[0]) == {"a", "b"}

    def test_sequential_plan(self):
        plan = Plan()
        plan.add_step(Step(name="a", action=_noop))
        plan.add_step(Step(name="b", action=_noop, depends_on=["a"]))
        schedule = Scheduler().optimize_schedule(plan)
        assert len(schedule.phases) == 2


class TestSortByPriority:
    def test_sort(self):
        goals = [
            Goal(name="low", priority=Priority.LOW),
            Goal(name="crit", priority=Priority.CRITICAL),
            Goal(name="med", priority=Priority.MEDIUM),
        ]
        sorted_goals = Scheduler().sort_by_priority(goals)
        assert sorted_goals[0].name == "crit"
        assert sorted_goals[-1].name == "low"
