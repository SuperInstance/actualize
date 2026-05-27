"""Tests for actualize.executor."""

from actualize.executor import Executor, ExecutionResult
from actualize.plan import Plan, Step, StepStatus


def _noop():
    pass


class TestExecutorBasic:
    def test_empty_plan(self):
        ex = Executor()
        plan = Plan(name="empty")
        result = ex.execute(plan)
        assert result.success
        assert result.total_steps == 0

    def test_all_pass(self):
        plan = Plan(name="ok")
        order = []
        plan.add_step(Step(name="a", action=lambda: order.append("a")))
        plan.add_step(Step(name="b", action=lambda: order.append("b"), depends_on=["a"]))
        result = Executor().execute(plan)
        assert result.success
        assert result.completed == 2
        assert order == ["a", "b"]

    def test_step_failure(self):
        plan = Plan(name="fail")
        plan.add_step(Step(name="good", action=lambda: None))
        plan.add_step(Step(name="bad", action=lambda: (_ for _ in ()).throw(RuntimeError("nope"))))
        result = Executor().execute(plan)
        assert not result.success
        assert result.failed >= 1


class TestExecutorCallbacks:
    def test_on_step_change(self):
        transitions = []
        plan = Plan()
        plan.add_step(Step(name="x", action=lambda: None))
        ex = Executor(on_step_change=lambda s, st: transitions.append((s.name, st.value)))
        ex.execute(plan)
        assert ("x", "running") in transitions
        assert ("x", "done") in transitions


class TestExecutorRollback:
    def test_rollback_on_failure(self):
        rolled_back = []

        def action_good():
            pass

        def action_fail():
            raise RuntimeError("fail")

        def rb_good():
            rolled_back.append("good")

        plan = Plan()
        plan.add_step(Step(name="good", action=action_good, rollback=rb_good))
        plan.add_step(Step(name="fail", action=action_fail, depends_on=["good"]))
        result = Executor(rollback_on_failure=True).execute(plan)
        assert not result.success
        assert result.rolled_back >= 1
        assert "good" in rolled_back

    def test_no_rollback_when_configured_off(self):
        rolled_back = []

        plan = Plan()
        plan.add_step(Step(name="good", action=lambda: None, rollback=lambda: rolled_back.append(1)))
        plan.add_step(Step(name="bad", action=lambda: (_ for _ in ()).throw(RuntimeError("x")), depends_on=["good"]))
        result = Executor(rollback_on_failure=False).execute(plan)
        assert not result.success
        assert result.rolled_back == 0
        assert len(rolled_back) == 0


class TestExecutorSkip:
    def test_skipped_after_failure(self):
        plan = Plan()
        plan.add_step(Step(name="a", action=lambda: (_ for _ in ()).throw(RuntimeError("fail"))))
        plan.add_step(Step(name="b", action=lambda: None, depends_on=["a"]))
        result = Executor().execute(plan)
        assert not result.success
        steps_by_name = {s.name: s for s in plan.steps}
        assert steps_by_name["b"].status == StepStatus.SKIPPED
