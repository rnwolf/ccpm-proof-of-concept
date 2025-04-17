import unittest
from datetime import datetime, timedelta
import os

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler


class FractionalResourceIntegrationTest(unittest.TestCase):
    """
    Integration test for the CCPM scheduler with fractional resource allocations.
    This test verifies that the entire pipeline correctly handles partial and multiple allocations.
    """

    def setUp(self):
        """Set up a test project with tasks that use fractional resources."""
        # Create scheduler
        self.scheduler = CCPMScheduler()

        # Set start date
        self.start_date = datetime(2025, 5, 1)
        self.scheduler.set_start_date(self.start_date)

        # Create resources
        self.resources = [
            "Designer",  # Will be used both full-time and half-time
            "Dev A",  # Will be used at different fractional amounts (0.5, 0.3)
            "Dev B",  # Will be used at 2x capacity in some tasks
            "Tester",  # Will be used in different combinations
        ]
        self.scheduler.set_resources(self.resources)

    def test_scheduler_with_fractional_resources(self):
        """Test the full scheduler with various fractional resource patterns."""
        # Create tasks with various resource allocation patterns

        # Task 1: Full-time designer for initial design
        task1 = Task(
            id="T1",
            name="Initial Design",
            aggressive_duration=5,
            safe_duration=8,
            dependencies=[],  # Empty list for dependencies
        )
        task1.resource_allocations = {"Designer": 1.0}

        # Task 2: Half-time designer for continued design + half-time Dev A
        task2 = Task(
            id="T2",
            name="Frontend Structure",
            aggressive_duration=8,
            safe_duration=12,
            dependencies=["T1"],
        )
        task2.resource_allocations = {"Designer": 0.5, "Dev A": 0.5}

        # Task 3: Two full-time Dev B resources (showing multiple allocation)
        task3 = Task(
            id="T3",
            name="Core Development",
            aggressive_duration=10,
            safe_duration=15,
            dependencies=["T2"],
        )
        task3.resource_allocations = {"Dev B": 2.0}

        # Task 4: Partial Dev A + Partial Tester allocations
        task4 = Task(
            id="T4",
            name="Initial Testing",
            aggressive_duration=6,
            safe_duration=9,
            dependencies=["T3"],
        )
        task4.resource_allocations = {"Dev A": 0.3, "Tester": 0.7}

        # Task 5: Parallel task with half designer (can run with Task 2)
        task5 = Task(
            id="T5",
            name="Documentation",
            aggressive_duration=7,
            safe_duration=10,
            dependencies=["T1"],
        )
        task5.resource_allocations = {"Designer": 0.5}

        # Add all tasks to scheduler
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)
        self.scheduler.add_task(task3)
        self.scheduler.add_task(task4)
        self.scheduler.add_task(task5)

        # Run the scheduler (which includes resource leveling)
        self.scheduler.schedule()

        # Verify scheduling results

        # 1. Tasks 2 and 5 should be able to run in parallel since they each use
        # only half of the Designer resource
        task2_start = self.scheduler.tasks["T2"].get_start_date()
        task5_start = self.scheduler.tasks["T5"].get_start_date()

        # Their start dates should be the same (both depend on T1 and share Designer)
        self.assertEqual(task2_start, task5_start)

        # 2. Task 3 requires 2x Dev B, which should be scheduled without conflicts
        # but should not overlap with other tasks using Dev B
        task3 = self.scheduler.tasks["T3"]
        task3_start = task3.get_start_date()
        task3_end = task3.get_end_date()

        # 3. Task 4 uses partial allocations and should be scheduled after Task 3
        task4 = self.scheduler.tasks["T4"]
        task4_start = task4.get_start_date()

        # Task 4 should start after Task 3 ends (dependency)
        self.assertGreaterEqual(task4_start, task3_end)

        # 4. Verify resulting chain structure
        critical_chain = self.scheduler.critical_chain
        self.assertIsNotNone(critical_chain)

        # The critical chain should include at least some of our tasks
        self.assertGreater(len(critical_chain.tasks), 0)

        # Generate a simple execution report as additional validation
        report = self.scheduler.generate_execution_report(self.start_date)
        self.assertIsNotNone(report)
        print("\nExecution Report:\n" + report)

    def test_resource_conflict_resolution(self):
        """Test that conflicts are properly detected when resource capacity is exceeded."""
        # Create two tasks that combined exceed available resource capacity
        task1 = Task(id="T1", name="Design A", aggressive_duration=5, safe_duration=8)
        task1.resource_allocations = {"Designer": 0.7}

        task2 = Task(id="T2", name="Design B", aggressive_duration=6, safe_duration=9)
        task2.resource_allocations = {"Designer": 0.4}  # 0.7 + 0.4 > 1.0, conflict!

        # Add tasks
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)

        # Run scheduler
        self.scheduler.schedule()

        # Verify that tasks are scheduled sequentially, not in parallel
        task1_end = self.scheduler.tasks["T1"].get_end_date()
        task2_start = self.scheduler.tasks["T2"].get_start_date()
        task1_start = self.scheduler.tasks["T1"].get_start_date()
        task2_end = self.scheduler.tasks["T2"].get_end_date()

        # One of these should be true (scheduler may order them either way)
        either_sequential = (task2_start >= task1_end) or (task1_start >= task2_end)

        self.assertTrue(
            either_sequential,
            "Tasks should be scheduled sequentially due to resource conflict",
        )

        task1 = Task(
            id="T2",
            name="Parallel Development",
            aggressive_duration=7,
            safe_duration=10,
        )
        task2.resource_allocations = {"Dev B": 2.0}

        # Add tasks
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)

        # Run scheduler
        self.scheduler.schedule()

        # These tasks should conflict on Dev B (1.0 + 2.0 > capacity)
        task1_start = self.scheduler.tasks["T1"].get_start_date()
        task1_end = self.scheduler.tasks["T1"].get_end_date()
        task2_start = self.scheduler.tasks["T2"].get_start_date()
        task2_end = self.scheduler.tasks["T2"].get_end_date()

        # Check if they're sequential
        non_overlapping = (task1_end <= task2_start) or (task2_end <= task1_start)
        self.assertTrue(
            non_overlapping,
            "Tasks with overlapping resources should be scheduled sequentially",
        )

    def test_backward_compatibility(self):
        """Test that the system still works with the legacy resource specification format."""
        # For backward compatibility testing, we'll have to update resource_allocations directly
        # since the resources property no longer has a setter
        task1 = Task(
            id="T1", name="Legacy Task Single", aggressive_duration=5, safe_duration=8
        )
        # Directly set resource_allocations as if it came from the legacy format
        task1.resource_allocations = {"Designer": 1.0}

        task2 = Task(
            id="T2", name="Legacy Task Multiple", aggressive_duration=6, safe_duration=9
        )
        # Directly set resource_allocations as if it came from the legacy format
        task2.resource_allocations = {"Dev A": 1.0, "Tester": 1.0}

        # Add tasks
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)

        # Run scheduler
        self.scheduler.schedule()

        # Verify both tasks were scheduled
        self.assertIsNotNone(self.scheduler.tasks["T1"].get_start_date())
        self.assertIsNotNone(self.scheduler.tasks["T2"].get_start_date())

        # The resources should be treated as full allocations
        # T1 should use Designer: 1.0
        # T2 should use Dev A: 1.0 and Tester: 1.0


if __name__ == "__main__":
    unittest.main()
