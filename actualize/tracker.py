"""Progress tracker with milestones and completion metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actualize.plan import Plan, StepStatus


@dataclass
class Milestone:
    """A named checkpoint in plan execution.

    Attributes:
        name: Milestone identifier.
        step_names: Steps that must be DONE to consider this milestone reached.
        reached: Whether the milestone has been reached.
        reached_at: Timestamp when reached (None if not yet).
    """

    name: str
    step_names: list[str]
    reached: bool = False
    reached_at: datetime | None = None


@dataclass
class ProgressSnapshot:
    """A point-in-time snapshot of plan progress."""

    plan_name: str
    total_steps: int
    completed: int
    failed: int
    pending: int
    progress_pct: float
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Tracker:
    """Track plan execution progress with milestones and metrics.

    Args:
        plan: The plan to track.
        persistence_path: Optional file path to persist snapshots as JSONL.
    """

    def __init__(
        self,
        plan: Plan,
        persistence_path: str | Path | None = None,
    ) -> None:
        self._plan = plan
        self._milestones: list[Milestone] = []
        self._history: list[ProgressSnapshot] = []
        self._persistence_path = Path(persistence_path) if persistence_path else None

    # -- milestones --

    def add_milestone(self, name: str, step_names: list[str]) -> Milestone:
        """Register a milestone tied to specific step names."""
        m = Milestone(name=name, step_names=step_names)
        self._milestones.append(m)
        return m

    @property
    def milestones(self) -> list[Milestone]:
        return list(self._milestones)

    # -- snapshots --

    def snapshot(self) -> ProgressSnapshot:
        """Take a snapshot of current progress and check milestones."""
        s = ProgressSnapshot(
            plan_name=self._plan.name,
            total_steps=self._plan.total_steps,
            completed=self._plan.completed_steps,
            failed=self._plan.failed_steps,
            pending=sum(
                1 for s in self._plan.steps if s.status == StepStatus.PENDING
            ),
            progress_pct=self._plan.progress_pct,
        )
        self._history.append(s)
        self._check_milestones()
        self._persist(s)
        return s

    def _check_milestones(self) -> None:
        """Update milestone states based on current step statuses."""
        done_names = {
            s.name for s in self._plan.steps if s.status == StepStatus.DONE
        }
        now = datetime.now(timezone.utc)
        for m in self._milestones:
            if not m.reached and set(m.step_names).issubset(done_names):
                m.reached = True
                m.reached_at = now

    def _persist(self, snapshot: ProgressSnapshot) -> None:
        """Append snapshot to persistence file if configured."""
        if self._persistence_path is None:
            return
        record = {
            "plan_name": snapshot.plan_name,
            "total": snapshot.total_steps,
            "completed": snapshot.completed,
            "failed": snapshot.failed,
            "pending": snapshot.pending,
            "progress_pct": round(snapshot.progress_pct, 2),
            "timestamp": snapshot.timestamp.isoformat(),
        }
        with open(self._persistence_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    # -- queries --

    @property
    def history(self) -> list[ProgressSnapshot]:
        return list(self._history)

    def reached_milestones(self) -> list[str]:
        """Names of milestones that have been reached."""
        return [m.name for m in self._milestones if m.reached]

    def pending_milestones(self) -> list[str]:
        """Names of milestones not yet reached."""
        return [m.name for m in self._milestones if not m.reached]

    def summary(self) -> dict[str, Any]:
        """Human-readable summary dict."""
        snap = self.snapshot()
        return {
            "plan": snap.plan_name,
            "progress": f"{snap.progress_pct:.1f}%",
            "steps": {
                "total": snap.total_steps,
                "completed": snap.completed,
                "failed": snap.failed,
                "pending": snap.pending,
            },
            "milestones": {
                "reached": self.reached_milestones(),
                "pending": self.pending_milestones(),
            },
            "snapshots_taken": len(self._history),
        }
