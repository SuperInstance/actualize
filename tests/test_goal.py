"""Tests for actualize.goal."""

from actualize.goal import Goal, Priority


class TestGoalCreation:
    def test_basic_goal(self):
        g = Goal(name="Build app", description="Create a web app")
        assert g.name == "Build app"
        assert g.priority == Priority.MEDIUM
        assert g.is_leaf

    def test_goal_with_priority(self):
        g = Goal(name="Fix bug", priority=Priority.CRITICAL)
        assert g.priority == Priority.CRITICAL

    def test_auto_id(self):
        g1 = Goal(name="A")
        g2 = Goal(name="B")
        assert g1.id != g2.id


class TestGoalHierarchy:
    def test_add_sub_goal(self):
        parent = Goal(name="Project")
        child = parent.add_sub_goal(Goal(name="Task 1"))
        assert child.parent is parent
        assert child in parent.sub_goals
        assert not parent.is_leaf
        assert child.is_leaf

    def test_depth(self):
        root = Goal(name="Root")
        mid = root.add_sub_goal(Goal(name="Mid"))
        leaf = mid.add_sub_goal(Goal(name="Leaf"))
        assert root.depth == 0
        assert mid.depth == 1
        assert leaf.depth == 2

    def test_root_property(self):
        root = Goal(name="Root")
        child = root.add_sub_goal(Goal(name="Child"))
        grandchild = child.add_sub_goal(Goal(name="GC"))
        assert grandchild.root is root
        assert child.root is root

    def test_all_goals(self):
        root = Goal(name="Root")
        a = root.add_sub_goal(Goal(name="A"))
        b = root.add_sub_goal(Goal(name="B"))
        a1 = a.add_sub_goal(Goal(name="A1"))
        all_g = root.all_goals()
        names = [g.name for g in all_g]
        assert names == ["Root", "A", "A1", "B"]

    def test_leaf_goals(self):
        root = Goal(name="Root")
        a = root.add_sub_goal(Goal(name="A"))
        b = root.add_sub_goal(Goal(name="B"))
        a.add_sub_goal(Goal(name="A1"))
        leaves = root.leaf_goals()
        names = [g.name for g in leaves]
        assert set(names) == {"A1", "B"}


class TestGoalDependencies:
    def test_depends_on(self):
        a = Goal(name="A")
        b = Goal(name="B")
        b.depends_on_goal(a)
        assert a in b.depends_on

    def test_no_duplicate_deps(self):
        a = Goal(name="A")
        b = Goal(name="B")
        b.depends_on_goal(a)
        b.depends_on_goal(a)
        assert len(b.depends_on) == 1


class TestGoalValidation:
    def test_valid_goal(self):
        g = Goal(name="Valid")
        assert g.validate() == []

    def test_empty_name_warning(self):
        g = Goal(name="  ")
        warnings = g.validate()
        assert any("empty name" in w for w in warnings)
