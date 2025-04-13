import unittest
from datetime import datetime, timedelta
from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler


class CCPMIntegrationTest(unittest.TestCase):
    def setUp(self):
        # Create a simple project
        self.scheduler = CCPMScheduler()
        self.scheduler.set_start_date(datetime(2025, 4, 1))

        # Create tasks
        task1 = Task(
            1,
            "Task 1",
            aggressive_duration=10,
            safe_duration=15,
            resources=["Resource A"],
        )
        task2 = Task(
            2,
            "Task 2",
            aggressive_duration=20,
            safe_duration=30,
            resources=["Resource B"],
        )
        task2.dependencies = [1]  # Task 2 depends on Task 1

        task3 = Task(
            3,
            "Task 3",
            aggressive_duration=15,
            safe_duration=20,
            resources=["Resource A"],
        )
        task3.dependencies = [2]  # Task 3 depends on Task 2

        # Add tasks to scheduler
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)
        self.scheduler.add_task(task3)

    def test_basic_scheduling(self):
        """Test that the basic scheduling workflow works end-to-end"""
        # Run scheduling
        result = self.scheduler.schedule()

        # Check that we got tasks, chains, and buffers back
        self.assertIn("tasks", result)
        self.assertIn("chains", result)
        self.assertIn("buffers", result)

        # Verify critical chain was identified
        self.assertIsNotNone(self.scheduler.critical_chain)

        # Verify project buffer was created
        self.assertIn("PB", self.scheduler.buffers)

        # Verify task dates were set
        for task in self.scheduler.tasks.values():
            self.assertIsNotNone(task.get_start_date())
            self.assertIsNotNone(task.get_end_date())

    def test_update_progress(self):
        """Test that updating task progress works correctly"""
        # Schedule the project
        self.scheduler.schedule()

        # Update progress for Task 1
        status_date = datetime(2025, 4, 5)  # 5 days into the project
        self.scheduler.update_task_progress(1, 5, status_date)  # 5 days remaining

        # Check that Task 1 is in progress
        task1 = self.scheduler.tasks[1]
        self.assertEqual(task1.status, "in_progress")
        self.assertEqual(task1.remaining_duration, 5)

        # Check that progress history was recorded
        self.assertTrue(hasattr(task1, "progress_history"))
        self.assertTrue(len(task1.progress_history) > 0)

        # Complete Task 1
        self.scheduler.update_task_progress(1, 0, datetime(2025, 4, 10))

        # Check that Task 1 is completed
        self.assertEqual(task1.status, "completed")
        self.assertEqual(task1.remaining_duration, 0)


if __name__ == "__main__":
    unittest.main()
