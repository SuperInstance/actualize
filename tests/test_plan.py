"""Tests for actualize.plan."""

import pytest

from actualize.plan import Plan, Step, StepStatus


def _noop():
    pass


def _fail():
    raise RuntimeError("boom")


def _rollback():
    _rollback.called = True


_rollback.called = False


class TestStep:
    def test_step_creation(self):
        s = Step(name="s1", action=_noop)
        assert s.status == StepStatus.PENDING
        assert s.error is None

    def test_step_reset(self):
        s = Step(name="s1", action=_noop)
        s.status = StepStatus.DONE
        s.error = ValueError("x")
        s.reset()
        assert s.status == StepStatus.PENDING
        assert s.error is None


class TestPlanBasic:
    def test_empty_plan(self):
        p = Plan(name="empty")
        assert p.total_steps == 0
        assert p.completed_steps == 0
        assert p.progress_pct == 0.0

    def test_add_step(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        assert p.total_steps == 1

    def test_progress(self):
        p = Plan()
        s1 = Step(name="a", action=_noop)
        s2 = Step(name="b", action=_noop)
        p.add_step(s1)
        p.add_step(s2)
        s1.status = StepStatus.DONE
        assert p.progress_pct == 50.0
        s2.status = StepStatus.DONE
        assert p.progress_pct == 100.0


class TestTopologicalOrder:
    def test_no_deps(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        p.add_step(Step(name="b", action=_noop))
        order = [s.name for s in p.topological_order()]
        assert set(order) == {"a", "b"}

    def test_linear_chain(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        p.add_step(Step(name="b", action=_noop, depends_on=["a"]))
        p.add_step(Step(name="c", action=_noop, depends_on=["b"]))
        order = [s.name for s in p.topological_order()]
        assert order == ["a", "b", "c"]

    def test_diamond(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        p.add_step(Step(name="b", action=_noop, depends_on=["a"]))
        p.add_step(Step(name="c", action=_noop, depends_on=["a"]))
        p.add_step(Step(name="d", action=_noop, depends_on=["b", "c"]))
        order = [s.name for s in p.topological_order()]
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_unknown_dep_raises(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop, depends_on=["missing"]))
        with pytest.raises(ValueError, match="unknown step"):
            p.topological_order()

    def test_cycle_raises(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop, depends_on=["b"]))
        p.add_step(Step(name="b", action=_noop, depends_on=["a"]))
        with pytest.raises(ValueError, match="Circular"):
            p.topological_order()


class TestParallelGroups:
    def test_fully_parallel(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        p.add_step(Step(name="b", action=_noop))
        groups = p.parallel_groups()
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_sequential(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        p.add_step(Step(name="b", action=_noop, depends_on=["a"]))
        groups = p.parallel_groups()
        assert len(groups) == 2
        assert groups[0][0].name == "a"
        assert groups[1][0].name == "b"

    def test_diamond_groups(self):
        p = Plan()
        p.add_step(Step(name="a", action=_noop))
        p.add_step(Step(name="b", action=_noop, depends_on=["a"]))
        p.add_step(Step(name="c", action=_noop, depends_on=["a"]))
        p.add_step(Step(name="d", action=_noop, depends_on=["b", "c"]))
        groups = p.parallel_groups()
        assert len(groups) == 3  # [a], [b,c], [d]
        assert {s.name for s in groups[1]} == {"b", "c"}
