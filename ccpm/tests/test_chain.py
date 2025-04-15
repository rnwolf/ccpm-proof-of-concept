import unittest
from datetime import datetime, timedelta
from ccpm.domain.chain import Chain, ChainError
from ccpm.domain.task import Task
from ccpm.domain.buffer import Buffer


class ChainTestCase(unittest.TestCase):
    """Test cases for the enhanced Chain class."""

    def setUp(self):
        """Set up test cases with a sample chain."""
        self.chain = Chain(
            id="chain1", name="Test Chain", type="feeding", buffer_ratio=0.3
        )

        # Create some tasks for testing
        self.tasks = {
            "task1": Task(
                id="task1", name="Task 1", aggressive_duration=5, safe_duration=10
            ),
            "task2": Task(
                id="task2", name="Task 2", aggressive_duration=10, safe_duration=15
            ),
            "task3": Task(
                id="task3", name="Task 3", aggressive_duration=7, safe_duration=12
            ),
        }

    def test_initialization_validation(self):
        """Test validation during chain initialization."""
        # Invalid ID
        with self.assertRaises(ChainError):
            Chain(id=None, name="Invalid Chain")

        # Invalid name
        with self.assertRaises(ChainError):
            Chain(id="c1", name="")

        # Invalid type
        with self.assertRaises(ChainError):
            Chain(id="c1", name="Invalid Type", type="invalid")

        # Invalid buffer ratio
        with self.assertRaises(ChainError):
            Chain(id="c1", name="Invalid Ratio", buffer_ratio=-0.1)

        with self.assertRaises(ChainError):
            Chain(id="c1", name="Invalid Ratio", buffer_ratio=1.5)

        # Valid chain
        chain = Chain(id="c1", name="Valid Chain", type="critical", buffer_ratio=0.5)
        self.assertEqual(chain.id, "c1")
        self.assertEqual(chain.name, "Valid Chain")
        self.assertEqual(chain.type, "critical")
        self.assertEqual(chain.buffer_ratio, 0.5)

    def test_task_management(self):
        """Test adding and removing tasks."""
        # Add tasks
        self.chain.add_task("task1")
        self.chain.add_task("task2")

        self.assertEqual(len(self.chain.tasks), 2)
        self.assertIn("task1", self.chain.tasks)
        self.assertIn("task2", self.chain.tasks)

        # Try adding a duplicate (should be ignored)
        self.chain.add_task("task1")
        self.assertEqual(len(self.chain.tasks), 2)

        # Remove task
        self.chain.remove_task("task1")
        self.assertEqual(len(self.chain.tasks), 1)
        self.assertNotIn("task1", self.chain.tasks)
        self.assertIn("task2", self.chain.tasks)

        # Try removing non-existent task
        self.chain.remove_task("task999")
        self.assertEqual(len(self.chain.tasks), 1)

        # Test validation
        with self.assertRaises(ChainError):
            self.chain.add_task(None)

    def test_connection_management(self):
        """Test setting connection points."""
        # Set connection
        self.chain.set_connection("critical_task1", "critical_chain")

        self.assertEqual(self.chain.connects_to_task_id, "critical_task1")
        self.assertEqual(self.chain.connects_to_chain_id, "critical_chain")

        # Test validation
        with self.assertRaises(ChainError):
            self.chain.set_connection(None)

        # Create a critical chain and try to set connection
        critical_chain = Chain(id="c2", name="Critical Chain", type="critical")
        with self.assertRaises(ChainError):
            critical_chain.set_connection("task1")

    def test_status_tracking(self):
        """Test status tracking and calculation."""
        # Add tasks to chain
        self.chain.add_task("task1")
        self.chain.add_task("task2")
        self.chain.add_task("task3")

        # Start tasks in the tasks dictionary
        now = datetime.now()
        self.tasks["task1"].start_task(now)
        self.tasks["task1"].update_progress(
            0, now + timedelta(days=5)
        )  # Complete task1

        self.tasks["task2"].start_task(now + timedelta(days=2))
        self.tasks["task2"].update_progress(5, now + timedelta(days=5))  # 50% complete

        # Calculate chain status
        result = self.chain.update_status(self.tasks, now + timedelta(days=5))

        # Calculate expected completion percentage
        # task1: 5/5 = 100%
        # task2: 5/10 = 50%
        # task3: 0/7 = 0%
        # Overall: (5 + 5 + 0) / (5 + 10 + 7) = 10/22 ≈ 45.45%

        self.assertAlmostEqual(result["completion_percentage"], 45.45, delta=0.1)
        self.assertEqual(result["total_duration"], 22)
        self.assertAlmostEqual(result["completed_duration"], 10, delta=0.1)

        # Check status history
        self.assertEqual(len(self.chain.status_history), 1)

    def test_buffer_integration(self):
        """Test integration with buffer."""
        # Create a buffer
        buffer = Buffer(
            id="buffer1",
            name="Test Buffer",
            size=5,
            buffer_type="feeding",
            connected_to="critical_task1",
        )

        # Associate buffer with chain
        self.chain.set_buffer(buffer)

        self.assertEqual(self.chain.buffer, buffer)

        # Consume some buffer
        now = datetime.now()
        buffer.consume(2, now, "Test consumption")

        # Check buffer consumption
        consumption_pct = self.chain.get_buffer_consumption()
        self.assertEqual(consumption_pct, 40)  # 2/5 = 40%

        # Check performance index
        # Assuming 50% completion with 40% buffer consumed
        self.chain.completion_percentage = 50
        performance_index = self.chain.get_performance_index()
        self.assertEqual(performance_index, 50 / 40)  # 1.25

    def test_serialization(self):
        """Test to_dict and from_dict methods."""
        # Set up a complex chain
        self.chain.add_task("task1")
        self.chain.add_task("task2")
        self.chain.set_connection("critical_task1", "critical_chain")

        # Create and associate a buffer
        buffer = Buffer(
            id="buffer1",
            name="Test Buffer",
            size=5,
            buffer_type="feeding",
            connected_to="critical_task1",
        )
        self.chain.set_buffer(buffer)

        # Add some status history
        self.chain.update_status(self.tasks, datetime.now())

        # Convert to dictionary
        chain_dict = self.chain.to_dict()

        # Verify key attributes
        self.assertEqual(chain_dict["id"], "chain1")
        self.assertEqual(chain_dict["name"], "Test Chain")
        self.assertEqual(chain_dict["type"], "feeding")
        self.assertEqual(chain_dict["buffer_ratio"], 0.3)
        self.assertEqual(len(chain_dict["tasks"]), 2)
        self.assertEqual(chain_dict["connects_to_task_id"], "critical_task1")
        self.assertEqual(chain_dict["connects_to_chain_id"], "critical_chain")

        # Create new chain from dictionary
        new_chain = Chain.from_dict(chain_dict)

        # Verify attributes match
        self.assertEqual(new_chain.id, self.chain.id)
        self.assertEqual(new_chain.name, self.chain.name)
        self.assertEqual(new_chain.type, self.chain.type)
        self.assertEqual(new_chain.buffer_ratio, self.chain.buffer_ratio)
        self.assertEqual(new_chain.tasks, self.chain.tasks)
        self.assertEqual(new_chain.connects_to_task_id, self.chain.connects_to_task_id)
        self.assertEqual(
            new_chain.connects_to_chain_id, self.chain.connects_to_chain_id
        )

    def test_flow_data(self):
        """Test cumulative flow data generation."""
        # Add tasks to chain
        self.chain.add_task("task1")
        self.chain.add_task("task2")

        # Start tasks
        now = datetime.now()
        self.tasks["task1"].start_task(now - timedelta(days=5))
        self.tasks["task1"].update_progress(
            0, now - timedelta(days=2)
        )  # Complete task1

        self.tasks["task2"].start_task(now - timedelta(days=3))
        self.tasks["task2"].update_progress(5, now)  # 50% complete

        # Update chain status
        self.chain.update_status(self.tasks, now)

        # Get flow data
        start_date = now - timedelta(days=7)
        end_date = now + timedelta(days=3)
        flow_data = self.chain.get_cumulative_flow_data(
            start_date, end_date, self.tasks
        )

        # Check data structure
        self.assertEqual(
            len(flow_data["dates"]), 11
        )  # 7 days before + today + 3 days after
        self.assertIn("planned", flow_data["status_counts"])
        self.assertIn("in_progress", flow_data["status_counts"])
        self.assertIn("completed", flow_data["status_counts"])

        # Check completion percentage tracking
        self.assertEqual(len(flow_data["completion_percentage"]), 11)

    def test_chain_cfd_with_none_dates(self):
        """Test generating chain cumulative flow data with None values and edge cases."""
        # Create a chain and tasks with minimal initialization
        chain = Chain(id="test_chain", name="Test Chain", type="feeding")

        # Add tasks to the chain
        chain.add_task("task1").add_task("task2")

        # Create tasks dictionary with one task having None dates
        tasks = {
            "task1": Task(id="task1", name="Task 1", aggressive_duration=5),
            "task2": Task(id="task2", name="Task 2", aggressive_duration=10),
        }

        # Task 1 has dates
        tasks["task1"].set_schedule(datetime.now() - timedelta(days=5))

        # Test with no dates specified
        cfd = chain.get_cumulative_flow_data(None, None, tasks)

        # Should return valid data structure
        self.assertIn("dates", cfd)
        self.assertIn("status_counts", cfd)

        # Start one task but don't complete
        tasks["task1"].start_task(datetime.now() - timedelta(days=3))
        cfd = chain.get_cumulative_flow_data(None, None, tasks)

        # Should show one task as in_progress
        in_progress_count = sum(cfd["status_counts"]["in_progress"])
        self.assertGreater(in_progress_count, 0)

        # Set actual_start_date to None for one task to test error handling
        tasks["task1"].actual_start_date = None

        # Should still work without errors
        try:
            cfd = chain.get_cumulative_flow_data(None, None, tasks)
            # Success if no exception raised
            self.assertTrue(True)
        except TypeError:
            self.fail(
                "get_cumulative_flow_data raised TypeError with None actual_start_date"
            )

        # Test with tasks_dict=None
        cfd = chain.get_cumulative_flow_data(None, None, None)
        # Should return empty structure
        self.assertEqual(len(cfd["dates"]), 0)


if __name__ == "__main__":
    unittest.main()
