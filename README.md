# actualize

An intent actualization engine that transforms abstract goals and high-level intents into concrete, executable action plans. It bridges the gap between strategic objectives and tactical implementation by decomposing intents into actionable steps.

## Installation

```bash
pip install actualize
```

For development:

```bash
git clone https://github.com/SuperInstance/actualize.git
cd actualize
pip install -e ".[dev]"
```

## Quick Start

### Define Goals

```python
from actualize import Goal

# Create a goal hierarchy
project = Goal(name="Launch Website", description="Deploy the new marketing site")

design = project.add_sub_goal(Goal(name="Design Mockups"))
frontend = project.add_sub_goal(Goal(name="Build Frontend"))
deploy = project.add_sub_goal(Goal(name="Deploy to Production"))

# Set dependencies — frontend needs designs first
frontend.depends_on_goal(design)
deploy.depends_on_goal(frontend)

# Validate the goal tree
warnings = project.validate()
assert warnings == []
```

### Generate a Plan

```python
from actualize import Scheduler

scheduler = Scheduler()
plan = scheduler.goals_to_plan(project)

# Inspect step ordering
for step in plan.topological_order():
    print(f"  {step.name} (deps: {step.depends_on})")
```

### Detect Parallelizable Steps

```python
# Steps grouped into phases that can run concurrently
for i, group in enumerate(plan.parallel_groups()):
    names = [s.name for s in group]
    print(f"Phase {i}: {names}")
    # Phase 0: ['Design Mockups']
    # Phase 1: ['Build Frontend']
    # Phase 2: ['Deploy to Production']
```

### Execute with Progress Tracking

```python
from actualize import Executor, Tracker

# Execute the plan
executor = Executor(stop_on_failure=True, rollback_on_failure=True)
result = executor.execute(plan)

print(f"Success: {result.success}")
print(f"Completed: {result.completed}/{result.total_steps}")

# Track progress with milestones
tracker = Tracker(plan)
tracker.add_milestone("development_done", ["Build Frontend"])
snapshot = tracker.snapshot()
print(f"Progress: {snapshot.progress_pct:.1f}%")
```

### Rollback on Failure

```python
from actualize import Plan, Step, Executor

plan = Plan(name="risky")
plan.add_step(Step(
    name="create_file",
    action=lambda: open("tmp.txt", "w").write("hello"),
    rollback=lambda: __import__("os").remove("tmp.txt"),
))
plan.add_step(Step(
    name="upload",
    action=lambda: (_ for _ in ()).throw(RuntimeError("upload failed")),
    depends_on=["create_file"],
))

result = Executor().execute(plan)
# create_file gets rolled back automatically
```

### Schedule with Resource Constraints

```python
from actualize import Scheduler, ResourceConstraint

scheduler = Scheduler()
plan = scheduler.goals_to_plan(my_goal)

schedule = scheduler.optimize_schedule(
    plan,
    resources=[ResourceConstraint("cpu", capacity=4)],
)
for phase in schedule.phases:
    print(f"Run in parallel: {phase}")
```

## Architecture

```
actualize/
├── goal.py       — Goal class with decomposition, priority, dependencies
├── plan.py       — Plan/Step with topological ordering, parallelization
├── executor.py   — Plan executor with rollback and callbacks
├── scheduler.py  — Goal-to-plan conversion, resource-constrained scheduling
└── tracker.py    — Progress tracking, milestones, JSONL persistence
```

## Key Features

- **Goal decomposition** — Break high-level goals into sub-goals with dependencies
- **Auto-plan generation** — Convert goal trees into executable step plans
- **Dependency-aware execution** — Topological sort ensures correct ordering
- **Parallelization detection** — Identify steps that can run concurrently
- **Rollback support** — Automatically undo completed steps on failure
- **Progress tracking** — Milestones, completion percentages, snapshot history
- **Zero dependencies** — Only requires Python 3.10+ (pytest for testing)
- **Type-hinted** — Full type annotations throughout

## License

MIT

---

Part of the [Cocapn fleet](https://github.com/Lucineer/the-fleet). Built with [Cocapn](https://github.com/Lucineer/cocapn-ai).
