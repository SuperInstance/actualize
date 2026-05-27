"""Tests for actualize.tracker."""

import tempfile
from pathlib import Path

from actualize.plan import Plan, Step, StepStatus
from actualize.tracker import Tracker


def _noop():
    pass


class TestTrackerBasic:
    def test_snapshot(self):
        plan = Plan(name="p")
        plan.add_step(Step(name="a", action=_noop))
        t = Tracker(plan)
        snap = t.snapshot()
        assert snap.total_steps == 1
        assert snap.completed == 0
        assert snap.progress_pct == 0.0

    def test_snapshot_after_completion(self):
        plan = Plan(name="p")
        s = Step(name="a", action=_noop)
        plan.add_step(s)
        s.status = StepStatus.DONE
        t = Tracker(plan)
        snap = t.snapshot()
        assert snap.completed == 1
        assert snap.progress_pct == 100.0


class TestMilestones:
    def test_milestone_reached(self):
        plan = Plan(name="p")
        s1 = Step(name="a", action=_noop)
        s2 = Step(name="b", action=_noop)
        plan.add_step(s1)
        plan.add_step(s2)
        t = Tracker(plan)
        t.add_milestone("half", ["a"])
        t.snapshot()
        assert "half" in t.pending_milestones()

        s1.status = StepStatus.DONE
        t.snapshot()
        assert "half" in t.reached_milestones()

    def test_milestone_all_steps(self):
        plan = Plan(name="p")
        s1 = Step(name="a", action=_noop)
        s2 = Step(name="b", action=_noop)
        plan.add_step(s1)
        plan.add_step(s2)
        t = Tracker(plan)
        t.add_milestone("done", ["a", "b"])
        s1.status = StepStatus.DONE
        s2.status = StepStatus.DONE
        t.snapshot()
        assert "done" in t.reached_milestones()


class TestPersistence:
    def test_persist_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        plan = Plan(name="p")
        plan.add_step(Step(name="a", action=_noop))
        t = Tracker(plan, persistence_path=path)
        t.snapshot()

        content = Path(path).read_text().strip()
        assert '"plan_name": "p"' in content
        assert '"completed": 0' in content
        Path(path).unlink()


class TestSummary:
    def test_summary_dict(self):
        plan = Plan(name="p")
        plan.add_step(Step(name="a", action=_noop))
        plan.add_step(Step(name="b", action=_noop))
        t = Tracker(plan)
        t.add_milestone("all", ["a", "b"])
        summary = t.summary()
        assert summary["plan"] == "p"
        assert summary["steps"]["total"] == 2
        assert "all" in summary["milestones"]["pending"]
