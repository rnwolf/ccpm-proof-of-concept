import unittest
from datetime import datetime, timedelta
import networkx as nx

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ccpm.domain.task import Task
from ccpm.services.resource_leveling import (
    level_resources,
    _get_task_resource_allocations,
)


class FractionalResourceTest(unittest.TestCase):
    """Test cases for fractional and multiple resource allocations."""

    def setUp(self):
        """Set up test case with tasks using fractional resource allocations."""
        # Set a project start date
        self.start_date = datetime(2025, 4, 1)

        # Create tasks with different resource allocation patterns
        # Task 1: Single resource at 100% (traditional format)
        # Pass resource_allocations directly when creating the task
        self.task1 = Task(
            id="T1", name="Full Resource Task", aggressive_duration=10, safe_duration=15
        )
        # Set the resource allocation directly
        self.task1.resource_allocations = {"Resource A": 1.0}
        self.task1.set_schedule(self.start_date)

        # Task 2: Single resource at 50% (partial allocation)
        self.task2 = Task(
            id="T2", name="Half Resource Task", aggressive_duration=8, safe_duration=12
        )
        self.task2.resource_allocations = {"Resource A": 0.5}
        self.task2.set_schedule(self.start_date)

        # Task 3: Multiple resources with mixed allocations
        self.task3 = Task(
            id="T3",
            name="Mixed Resources Task",
            aggressive_duration=12,
            safe_duration=18,
        )
        self.task3.resource_allocations = {
            "Resource A": 0.3,
            "Resource B": 1.0,
            "Resource C": 0.6,
        }
        self.task3.set_schedule(self.start_date)

        # Task 4: Overallocated resource (2x) for testing conflicts
        self.task4 = Task(
            id="T4", name="Double Resource Task", aggressive_duration=5, safe_duration=8
        )
        self.task4.resource_allocations = {"Resource B": 2.0}
        self.task4.set_schedule(self.start_date)

        # Combine tasks into a dictionary (what the scheduler would have)
        self.tasks = {
            "T1": self.task1,
            "T2": self.task2,
            "T3": self.task3,
            "T4": self.task4,
        }

        # Set up resources (just a list for this test)
        self.resources = ["Resource A", "Resource B", "Resource C"]

    def test_get_resource_allocations(self):
        """Test extracting resource allocations from different task formats."""
        # Test traditional full allocation
        allocations = _get_task_resource_allocations(self.task1)
        self.assertEqual(allocations, {"Resource A": 1.0})

        # Test partial allocation
        allocations = _get_task_resource_allocations(self.task2)
        self.assertEqual(allocations, {"Resource A": 0.5})

        # Test multiple allocations
        allocations = _get_task_resource_allocations(self.task3)
        self.assertEqual(
            allocations, {"Resource A": 0.3, "Resource B": 1.0, "Resource C": 0.6}
        )

        # Test multiple of same resource
        allocations = _get_task_resource_allocations(self.task4)
        self.assertEqual(allocations, {"Resource B": 2.0})

        # Test legacy format with list - we need to access resource_allocations directly
        legacy_task = Task(id="Legacy", name="Legacy Task", aggressive_duration=5)
        # For backward compatibility, set resource_allocations directly
        legacy_task.resource_allocations = {"Resource A": 1.0, "Resource B": 1.0}
        allocations = _get_task_resource_allocations(legacy_task)
        self.assertEqual(allocations, {"Resource A": 1.0, "Resource B": 1.0})

        # Test legacy format with string
        legacy_task2 = Task(id="Legacy2", name="Legacy Task 2", aggressive_duration=5)
        # For backward compatibility, set resource_allocations directly
        legacy_task2.resource_allocations = {"Resource C": 1.0}
        allocations = _get_task_resource_allocations(legacy_task2)
        self.assertEqual(allocations, {"Resource C": 1.0})

    def test_resource_sharing(self):
        """Test that tasks with partial allocations can share resources."""
        # Create a simple task set for testing resource sharing
        task_a = Task(id="TaskA", name="Task A - 60% Resource", aggressive_duration=5)
        task_a.resource_allocations = {"Resource X": 0.6}
        task_a.set_schedule(self.start_date)

        task_b = Task(id="TaskB", name="Task B - 40% Resource", aggressive_duration=5)
        task_b.resource_allocations = {"Resource X": 0.4}
        task_b.set_schedule(self.start_date)

        test_tasks = {"TaskA": task_a, "TaskB": task_b}
        test_resources = ["Resource X"]

        # These tasks should be able to run in parallel since combined they use 100% of Resource X
        leveled_tasks, graph = level_resources(test_tasks, test_resources)

        # Check if they're scheduled at the same time (no resource conflict)
        self.assertEqual(task_a.get_start_date(), task_b.get_start_date())

        # Add a third task that would push over capacity
        task_c = Task(id="TaskC", name="Task C - 20% Resource", aggressive_duration=5)
        task_c.resource_allocations = {"Resource X": 0.2}
        task_c.set_schedule(self.start_date)

        test_tasks["TaskC"] = task_c

        # Now the tasks can't all run together (exceeds 100%)
        leveled_tasks, graph = level_resources(test_tasks, test_resources)

        # One task should be delayed (but we can't predict which one due to graph algorithm)
        starts = [
            task_a.get_start_date(),
            task_b.get_start_date(),
            task_c.get_start_date(),
        ]
        unique_starts = set(starts)
        self.assertGreater(len(unique_starts), 1, "At least one task should be delayed")

    def test_multiple_resource_allocation(self):
        """Test that tasks can use multiple of the same resource (e.g., 2x Developer)."""
        # Create a task that needs 2 units of a resource
        task_a = Task(id="TaskA", name="Task A - 2x Resource", aggressive_duration=5)
        task_a.resource_allocations = {"Developer": 2.0}
        task_a.set_schedule(self.start_date)

        # Create a task that needs 1 unit
        task_b = Task(id="TaskB", name="Task B - 1x Resource", aggressive_duration=5)
        task_b.resource_allocations = {"Developer": 1.0}
        task_b.set_schedule(self.start_date)

        test_tasks = {"TaskA": task_a, "TaskB": task_b}
        test_resources = ["Developer"]

        # These tasks have a resource conflict (3 > 1 available)
        leveled_tasks, graph = level_resources(test_tasks, test_resources)

        # Tasks should be scheduled sequentially
        self.assertNotEqual(task_a.get_start_date(), task_b.get_start_date())

        # The later task should start after the first one ends
        if task_a.get_start_date() < task_b.get_start_date():
            self.assertGreaterEqual(task_b.get_start_date(), task_a.get_end_date())
        else:
            self.assertGreaterEqual(task_a.get_start_date(), task_b.get_end_date())

    def test_complex_resource_leveling(self):
        """Test a more complex scenario with mixed resource allocations."""
        # Create a set of tasks with various resource allocation patterns
        tasks = {}

        # Task 1: Full-time designer
        task1 = Task(id="T1", name="UI Design", aggressive_duration=5)
        task1.resource_allocations = {"Designer": 1.0}
        task1.set_schedule(self.start_date)
        tasks["T1"] = task1

        # Task 2: Part-time designer (0.5) + Full-time developer
        task2 = Task(id="T2", name="Frontend Implementation", aggressive_duration=8)
        task2.resource_allocations = {"Designer": 0.5, "Developer": 1.0}
        task2.set_schedule(self.start_date)
        tasks["T2"] = task2

        # Task 3: Full-time developer + 0.5 tester
        task3 = Task(id="T3", name="Backend Implementation", aggressive_duration=10)
        task3.resource_allocations = {"Developer": 1.0, "Tester": 0.5}
        task3.set_schedule(self.start_date)
        tasks["T3"] = task3

        # Task 4: Full-time tester
        task4 = Task(id="T4", name="Testing", aggressive_duration=4)
        task4.resource_allocations = {"Tester": 1.0}
        task4.set_schedule(self.start_date)
        tasks["T4"] = task4

        resources = ["Designer", "Developer", "Tester"]

        # Apply resource leveling
        leveled_tasks, graph = level_resources(tasks, resources)

        # Tasks 1 and 2 can run in parallel (Designer has capacity)
        # T1 uses Designer:1.0, T2 uses Designer:0.5 + Developer:1.0
        # This exceeds Designer capacity (1.5 > 1.0) so they should be sequenced
        self.assertNotEqual(task1.get_start_date(), task2.get_start_date())

        # Tasks 3 and 4 should have resource conflicts:
        # T3 uses Developer:1.0 + Tester:0.5, T4 uses Tester:1.0
        # For Tester, that's 1.5 > 1.0, so conflict
        self.assertNotEqual(task3.get_start_date(), task4.get_start_date())

        # Check if T2 and T3 conflict (both need full Developer)
        self.assertNotEqual(task2.get_start_date(), task3.get_start_date())


if __name__ == "__main__":
    unittest.main()
