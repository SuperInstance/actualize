"""Plan executor with progress tracking, rollback, and callbacks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from actualize.plan import Plan, Step, StepStatus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a plan.

    Attributes:
        plan_name: Name of the plan that was executed.
        total_steps: Total number of steps.
        completed: Number of successfully completed steps.
        failed: Number of failed steps.
        rolled_back: Number of steps that were rolled back.
        success: True if all steps completed without failure.
        errors: Map of step name to error message for failures.
    """

    plan_name: str
    total_steps: int
    completed: int = 0
    failed: int = 0
    rolled_back: int = 0
    success: bool = True
    errors: dict[str, str] = field(default_factory=dict)


# Callback type: (step, status) -> None
StepCallback = Callable[[Step, StepStatus], None]


class Executor:
    """Execute a Plan's steps respecting dependencies.

    Args:
        on_step_change: Optional callback invoked when a step's status changes.
        stop_on_failure: If True (default), halt execution when a step fails
            and attempt rollback on already-completed steps.
        rollback_on_failure: If True (default), run rollback callbacks for
            completed steps when a failure occurs.
    """

    def __init__(
        self,
        on_step_change: StepCallback | None = None,
        stop_on_failure: bool = True,
        rollback_on_failure: bool = True,
    ) -> None:
        self._on_step_change = on_step_change
        self.stop_on_failure = stop_on_failure
        self.rollback_on_failure = rollback_on_failure

    def execute(self, plan: Plan) -> ExecutionResult:
        """Execute the plan. Returns an ExecutionResult summary."""
        if not plan.steps:
            return ExecutionResult(plan_name=plan.name, total_steps=0)

        ordered = plan.topological_order()
        result = ExecutionResult(plan_name=plan.name, total_steps=len(ordered))
        completed_steps: list[Step] = []

        for step in ordered:
            # Check if any dependency failed
            dep_failed = any(
                plan_step.name in step.depends_on
                and plan_step.status == StepStatus.FAILED
                for plan_step in plan.steps
            )
            if dep_failed:
                step.status = StepStatus.SKIPPED
                self._notify(step)
                continue

            step.status = StepStatus.RUNNING
            self._notify(step)

            try:
                step.action()
                step.status = StepStatus.DONE
                completed_steps.append(step)
                result.completed += 1
                self._notify(step)
            except Exception as exc:
                step.status = StepStatus.FAILED
                step.error = exc
                result.failed += 1
                result.errors[step.name] = str(exc)
                result.success = False
                self._notify(step)
                logger.warning("Step '%s' failed: %s", step.name, exc)

                if self.stop_on_failure:
                    break

        # Mark remaining pending steps as skipped after early exit
        if not result.success and self.stop_on_failure:
            for step in ordered:
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.SKIPPED
                    self._notify(step)

        # Rollback completed steps on failure if configured
        if not result.success and self.rollback_on_failure:
            result.rolled_back = self._rollback(completed_steps)

        return result

    def _rollback(self, steps: list[Step]) -> int:
        """Roll back completed steps in reverse order. Returns count rolled back."""
        rolled_back = 0
        for step in reversed(steps):
            if step.rollback is not None:
                try:
                    step.rollback()
                    step.status = StepStatus.ROLLED_BACK
                    rolled_back += 1
                    self._notify(step)
                except Exception as exc:
                    logger.error(
                        "Rollback failed for step '%s': %s", step.name, exc
                    )
        return rolled_back

    def _notify(self, step: Step) -> None:
        if self._on_step_change is not None:
            self._on_step_change(step, step.status)
