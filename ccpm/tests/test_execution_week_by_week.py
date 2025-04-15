"""
Integration test for CCPM project execution.

This test simulates the execution of a project week by week, updating task progress
and checking that the service layer logic works as expected.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import unittest
from datetime import datetime, timedelta
from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler
from ccpm.services.buffer_strategies import CutAndPasteMethod, SumOfSquaresMethod


class CCPMExecutionTest(unittest.TestCase):
    def setUp(self):
        """Set up a simple project for testing execution."""
        # Create a scheduler with specific buffer strategies
        self.scheduler = CCPMScheduler(
            project_buffer_ratio=0.5,
            default_feeding_buffer_ratio=0.3,
            project_buffer_strategy=CutAndPasteMethod(),
            default_feeding_buffer_strategy=SumOfSquaresMethod(),
        )

        # Set start date
        self.start_date = datetime(2025, 4, 1)
        self.scheduler.set_start_date(self.start_date)

        # Set resources
        self.scheduler.set_resources(["Resource A", "Resource B", "Resource C"])

        # Create tasks
        task1 = Task(
            id="T1",
            name="Task 1",
            aggressive_duration=10,
            safe_duration=15,
            resources=["Resource A"],
        )

        task2 = Task(
            id="T2",
            name="Task 2",
            aggressive_duration=20,
            safe_duration=30,
            dependencies=["T1"],
            resources=["Resource B"],
        )

        task3 = Task(
            id="T3",
            name="Task 3",
            aggressive_duration=15,
            safe_duration=20,
            dependencies=["T2"],
            resources=["Resource A"],
        )

        task4 = Task(
            id="T4",
            name="Task 4",
            aggressive_duration=5,
            safe_duration=10,
            resources=["Resource C"],
        )

        task5 = Task(
            id="T5",
            name="Task 5",
            aggressive_duration=15,
            safe_duration=20,
            dependencies=["T4"],
            resources=["Resource B"],
        )

        # Add tasks to scheduler
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)
        self.scheduler.add_task(task3)
        self.scheduler.add_task(task4)
        self.scheduler.add_task(task5)

        # Run scheduler to create initial schedule
        self.scheduler.schedule()

    def test_execute_project(self):
        """Test project execution with weekly updates."""
        # Check initial state
        self.assertEqual(len(self.scheduler.tasks), 5)
        self.assertIsNotNone(self.scheduler.critical_chain)
        self.assertGreater(len(self.scheduler.buffers), 0)

        # Verify that T1, T2, T3 form the critical chain
        # (simplified assumption for this test)
        critical_tasks = self.scheduler.critical_chain.tasks
        self.assertIn("T1", critical_tasks)
        self.assertIn("T2", critical_tasks)
        self.assertIn("T3", critical_tasks)

        # Verify that T4, T5 form a feeding chain
        feeding_chains = [
            chain
            for chain_id, chain in self.scheduler.chains.items()
            if chain.type == "feeding"
        ]
        self.assertGreater(len(feeding_chains), 0)

        # Find the feeding chain containing T4 and T5
        feeding_chain = None
        for chain in feeding_chains:
            if "T4" in chain.tasks and "T5" in chain.tasks:
                feeding_chain = chain
                break

        self.assertIsNotNone(feeding_chain)

        # Week 1: Start T1 and T4
        week1_date = self.start_date + timedelta(days=7)
        print(f"\n=== Week 1 ({week1_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T1 is 30% complete, T4 is 40% complete
        self.scheduler.update_task_progress(
            "T1", 7, week1_date
        )  # 30% complete (3/10 days)
        self.scheduler.update_task_progress(
            "T4", 3, week1_date
        )  # 40% complete (2/5 days)

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T1"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T4"].status, "in_progress")

        # Verify remaining durations
        self.assertEqual(self.scheduler.tasks["T1"].remaining_duration, 7)
        self.assertEqual(self.scheduler.tasks["T4"].remaining_duration, 3)

        # Week 2: Complete T4, continue T1
        week2_date = self.start_date + timedelta(days=14)
        print(f"\n=== Week 2 ({week2_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T1 is 60% complete, T4 is complete
        self.scheduler.update_task_progress(
            "T1", 4, week2_date
        )  # 60% complete (6/10 days)
        self.scheduler.update_task_progress("T4", 0, week2_date)  # 100% complete

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T1"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T4"].status, "completed")

        # Verify that T5 can now start (after T4 + feeding buffer)
        # We're not explicitly starting it yet, but check if the scheduler updated its dates
        buffer_id = f"FB_{feeding_chain.id}"
        feeding_buffer = self.scheduler.buffers[buffer_id]

        # Verify buffer positioning and consumption
        self.assertIsNotNone(feeding_buffer.new_start_date)

        # Week 3: Complete T1, start T5
        week3_date = self.start_date + timedelta(days=21)
        print(f"\n=== Week 3 ({week3_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T1 is complete, T5 is 20% complete (started)
        self.scheduler.update_task_progress("T1", 0, week3_date)  # 100% complete
        self.scheduler.update_task_progress(
            "T5", 12, week3_date
        )  # 20% complete (3/15 days)

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T1"].status, "completed")
        self.assertEqual(self.scheduler.tasks["T5"].status, "in_progress")

        # T2 should be able to start now since T1 is complete
        # Start T2
        self.scheduler.update_task_progress(
            "T2", 20, week3_date
        )  # Just started, full duration remaining
        self.assertEqual(self.scheduler.tasks["T2"].status, "in_progress")

        # Week 4: Continue T2 and T5
        week4_date = self.start_date + timedelta(days=28)
        print(f"\n=== Week 4 ({week4_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T2 is 25% complete, T5 is 50% complete
        self.scheduler.update_task_progress(
            "T2", 15, week4_date
        )  # 25% complete (5/20 days)
        self.scheduler.update_task_progress(
            "T5", 7.5, week4_date
        )  # 50% complete (7.5/15 days)

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T2"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T5"].status, "in_progress")

        # Week 5: Continue T2, Complete T5
        week5_date = self.start_date + timedelta(days=35)
        print(f"\n=== Week 5 ({week5_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T2 is 50% complete, T5 is complete
        self.scheduler.update_task_progress(
            "T2", 10, week5_date
        )  # 50% complete (10/20 days)
        self.scheduler.update_task_progress("T5", 0, week5_date)  # 100% complete

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T2"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T5"].status, "completed")

        # Week 6: Complete T2
        week6_date = self.start_date + timedelta(days=42)
        print(f"\n=== Week 6 ({week6_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T2 is complete
        self.scheduler.update_task_progress("T2", 0, week6_date)  # 100% complete

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T2"].status, "completed")

        # T3 should be able to start now since T2 is complete
        # Start T3
        self.scheduler.update_task_progress(
            "T3", 15, week6_date
        )  # Just started, full duration remaining
        self.assertEqual(self.scheduler.tasks["T3"].status, "in_progress")

        # Week 7: Continue T3
        week7_date = self.start_date + timedelta(days=49)
        print(f"\n=== Week 7 ({week7_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T3 is 50% complete
        self.scheduler.update_task_progress(
            "T3", 7.5, week7_date
        )  # 50% complete (7.5/15 days)

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T3"].status, "in_progress")

        # Week 8: Complete T3
        week8_date = self.start_date + timedelta(days=56)
        print(f"\n=== Week 8 ({week8_date.strftime('%Y-%m-%d')}) ===")

        # Update task progress: T3 is complete
        self.scheduler.update_task_progress("T3", 0, week8_date)  # 100% complete

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T3"].status, "completed")

        # Check that all tasks are now complete
        completed_count = sum(
            1
            for task in self.scheduler.tasks.values()
            if hasattr(task, "status") and task.status == "completed"
        )
        self.assertEqual(completed_count, 5)

        # Check buffer consumption
        project_buffer = None
        for buffer in self.scheduler.buffers.values():
            if buffer.buffer_type == "project":
                project_buffer = buffer
                break

        self.assertIsNotNone(project_buffer)

        # Print buffer consumption
        print(
            f"\nProject buffer consumption: {project_buffer.get_consumption_percentage():.1f}%"
        )
        print(
            f"Project buffer remaining: {project_buffer.remaining_size} / {project_buffer.size} days"
        )

        # Generate execution report
        report = self.scheduler.generate_execution_report(week8_date)
        print("\n=== Final Execution Report ===")
        print(report)

    def test_simulation_function(self):
        """Test the project simulation function."""
        # Simulate week 1
        week1_date = self.start_date + timedelta(days=7)
        self.scheduler.simulate_execution(
            week1_date,
            in_progress_task_ids=["T1", "T4"],
            progress_percentages={"T1": 30, "T4": 40},
        )

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T1"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T4"].status, "in_progress")

        # Simulate week 2 - complete T4
        week2_date = self.start_date + timedelta(days=14)
        self.scheduler.simulate_execution(
            week2_date,
            completed_task_ids=["T4"],
            in_progress_task_ids=["T1"],
            progress_percentages={"T1": 60},
        )

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T1"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T4"].status, "completed")

        # Simulate week 3 - complete T1, start T2 and T5
        week3_date = self.start_date + timedelta(days=21)
        self.scheduler.simulate_execution(
            week3_date,
            completed_task_ids=["T1"],
            in_progress_task_ids=["T2", "T5"],
            progress_percentages={"T2": 0, "T5": 20},
        )

        # Verify task status
        self.assertEqual(self.scheduler.tasks["T1"].status, "completed")
        self.assertEqual(self.scheduler.tasks["T2"].status, "in_progress")
        self.assertEqual(self.scheduler.tasks["T5"].status, "in_progress")


if __name__ == "__main__":
    unittest.main()
