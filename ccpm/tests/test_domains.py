import unittest
from datetime import datetime, timedelta
from ccpm.domain.task import Task
from ccpm.domain.chain import Chain
from ccpm.domain.buffer import Buffer
from ccpm.services.buffer_strategies import SumOfSquaresMethod


import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class DomainIntegrationTestCase(unittest.TestCase):
    """Integration tests for the domain models working together."""

    def setUp(self):
        """Set up a simple project structure with tasks, chains, and buffers."""
        self.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create tasks
        self.tasks = {
            "t1": Task(
                id="t1", name="Task 1", aggressive_duration=10, safe_duration=15
            ),
            "t2": Task(
                id="t2",
                name="Task 2",
                aggressive_duration=20,
                safe_duration=30,
                dependencies=["t1"],
            ),
            "t3": Task(
                id="t3",
                name="Task 3",
                aggressive_duration=15,
                safe_duration=25,
                dependencies=["t2"],
            ),
            "t4": Task(id="t4", name="Task 4", aggressive_duration=5, safe_duration=10),
            "t5": Task(
                id="t5",
                name="Task 5",
                aggressive_duration=15,
                safe_duration=20,
                dependencies=["t4"],
            ),
        }

        # Create chains
        self.critical_chain = Chain(
            id="cc", name="Critical Chain", type="critical", buffer_ratio=0.5
        )
        self.feeding_chain = Chain(
            id="fc1", name="Feeding Chain 1", type="feeding", buffer_ratio=0.3
        )

        # Assign tasks to chains
        self.critical_chain.add_task("t1").add_task("t2").add_task("t3")
        self.feeding_chain.add_task("t4").add_task("t5")

        # Set feeding chain connection
        self.feeding_chain.set_connection("t2")

        # Set chain types on tasks
        for task_id in self.critical_chain.tasks:
            self.tasks[task_id].chain_id = self.critical_chain.id
            self.tasks[task_id].chain_type = "critical"

        for task_id in self.feeding_chain.tasks:
            self.tasks[task_id].chain_id = self.feeding_chain.id
            self.tasks[task_id].chain_type = "feeding"

        # Create buffer strategy
        self.buffer_strategy = SumOfSquaresMethod()

        # Create buffers
        self.project_buffer = Buffer(
            id="PB",
            name="Project Buffer",
            size=20,  # Will be calculated in real system
            buffer_type="project",
        )

        self.feeding_buffer = Buffer(
            id="FB1",
            name="Feeding Buffer 1",
            size=10,  # Will be calculated in real system
            buffer_type="feeding",
            connected_to="t2",
            strategy_name=self.buffer_strategy.get_name(),
        )

        # Associate buffers with chains
        self.critical_chain.set_buffer(self.project_buffer)
        self.feeding_chain.set_buffer(self.feeding_buffer)

        # Set up schedule with dates
        start_date = self.today - timedelta(days=30)

        for i, task_id in enumerate(self.critical_chain.tasks):
            task = self.tasks[task_id]
            task_start = start_date + timedelta(days=i * 15)
            task.set_schedule(task_start)

        feeding_start = start_date + timedelta(days=10)
        for i, task_id in enumerate(self.feeding_chain.tasks):
            task = self.tasks[task_id]
            task_start = feeding_start + timedelta(days=i * 10)
            task.set_schedule(task_start)

        # Set buffer dates
        last_cc_task = self.tasks[self.critical_chain.tasks[-1]]
        self.project_buffer.start_date = last_cc_task.end_date
        self.project_buffer.end_date = self.project_buffer.start_date + timedelta(
            days=self.project_buffer.size
        )

        last_fc_task = self.tasks[self.feeding_chain.tasks[-1]]
        self.feeding_buffer.start_date = last_fc_task.end_date
        self.feeding_buffer.end_date = self.feeding_buffer.start_date + timedelta(
            days=self.feeding_buffer.size
        )

    def test_project_execution(self):
        """Test project execution with task updates and buffer consumption."""
        # Start tasks in sequence and update progress

        # Start and complete first critical task
        first_task = self.tasks["t1"]
        first_task.start_task(first_task.start_date)
        first_task.complete_task(first_task.end_date + timedelta(days=5))  # 5 days late

        # Start second critical task
        second_task = self.tasks["t2"]
        second_task.start_task(
            first_task.actual_end_date
        )  # Start after first task ended
        second_task.update_progress(
            10, second_task.actual_start_date + timedelta(days=10)
        )  # 50% progress

        # Start and make progress on feeding chain tasks
        feeding_task1 = self.tasks["t4"]
        feeding_task1.start_task(feeding_task1.start_date)
        feeding_task1.complete_task(
            feeding_task1.start_date + timedelta(days=8)
        )  # 3 days late

        feeding_task2 = self.tasks["t5"]
        feeding_task2.start_task(feeding_task1.actual_end_date)
        feeding_task2.update_progress(
            10, feeding_task2.actual_start_date + timedelta(days=5)
        )  # 33% progress

        # Update feeding chain status
        # Update critical chain status
        self.critical_chain.update_status(self.tasks)
        self.feeding_chain.update_status(self.tasks)

        # Debug After updating task progress but before assertions
        for task_id in self.critical_chain.tasks:
            task = self.tasks[task_id]
            print(
                f"Task {task_id}: status={task.status}, planned_duration={task.planned_duration}, "
                f"progress={task.get_progress_percentage() if hasattr(task, 'get_progress_percentage') else 'N/A'}"
            )

        # After updating chain status
        print(
            f"Critical chain: completion={self.critical_chain.completion_percentage}%"
        )
        print(
            f"Total duration: {self.critical_chain.status_history[-1]['total_duration']}"
        )
        print(
            f"Completed duration: {self.critical_chain.status_history[-1]['completed_duration']}"
        )

        # Check critical chain completion
        # t1 complete (10 days), t2 half done (10 days), t3 not started (0 days)
        # 10 + 10 + 0 = 20 completed out of 45 days = ~44.4%
        self.assertAlmostEqual(
            self.critical_chain.completion_percentage, 44.4, delta=0.1
        )

        # Check feeding chain completion
        # t4 complete (5 days), t5 one-third done (5 days)
        # 5 + 5 = 10 completed out of 20 days = 50%
        self.assertEqual(self.feeding_chain.completion_percentage, 50)

        # Consume buffer based on task delays
        self.project_buffer.consume(5, self.today, "Task t1 delay")

        # Calculate buffer states
        project_buffer_consumption = self.project_buffer.get_consumption_percentage()
        self.assertEqual(project_buffer_consumption, 25)  # 5/20 = 25%

        # Get performance metrics
        cc_performance = self.critical_chain.get_performance_index()
        self.assertAlmostEqual(cc_performance, 44.4 / 25, delta=0.1)  # About 1.78, good

        # Generate CFD data for tasks
        task_cfd = self.tasks["t1"].get_cumulative_flow_data()
        self.assertIn("status_counts", task_cfd)
        self.assertIn("planned", task_cfd["status_counts"])
        self.assertIn("in_progress", task_cfd["status_counts"])
        self.assertIn("completed", task_cfd["status_counts"])

        # Generate CFD data for chains
        chain_cfd = self.critical_chain.get_cumulative_flow_data(None, None, self.tasks)
        self.assertIn("status_counts", chain_cfd)
        self.assertIn("completion_percentage", chain_cfd)

        # Generate CFD data for buffers
        buffer_cfd = self.project_buffer.get_cumulative_flow_data()
        self.assertIn("remaining", buffer_cfd)
        self.assertIn("consumed", buffer_cfd)
        self.assertIn("status", buffer_cfd)

    def test_serialization_integration(self):
        """Test serializing and deserializing the entire project structure."""
        # Serialize all components
        serialized_tasks = {
            task_id: task.to_dict() for task_id, task in self.tasks.items()
        }
        serialized_cc = self.critical_chain.to_dict()
        serialized_fc = self.feeding_chain.to_dict()
        serialized_pb = self.project_buffer.to_dict()
        serialized_fb = self.feeding_buffer.to_dict()

        # Deserialize components
        deserialized_tasks = {
            task_id: Task.from_dict(task_data)
            for task_id, task_data in serialized_tasks.items()
        }
        deserialized_cc = Chain.from_dict(serialized_cc)
        deserialized_fc = Chain.from_dict(serialized_fc)
        deserialized_pb = Buffer.from_dict(serialized_pb)
        deserialized_fb = Buffer.from_dict(serialized_fb)

        # Verify integrity
        # Check tasks
        for task_id, original_task in self.tasks.items():
            deserialized_task = deserialized_tasks[task_id]
            self.assertEqual(deserialized_task.id, original_task.id)
            self.assertEqual(deserialized_task.name, original_task.name)
            self.assertEqual(
                deserialized_task.aggressive_duration, original_task.aggressive_duration
            )
            self.assertEqual(deserialized_task.chain_id, original_task.chain_id)
            self.assertEqual(deserialized_task.chain_type, original_task.chain_type)

        # Check chains
        self.assertEqual(deserialized_cc.id, self.critical_chain.id)
        self.assertEqual(deserialized_cc.type, self.critical_chain.type)
        self.assertEqual(deserialized_cc.tasks, self.critical_chain.tasks)

        self.assertEqual(deserialized_fc.id, self.feeding_chain.id)
        self.assertEqual(deserialized_fc.type, self.feeding_chain.type)
        self.assertEqual(deserialized_fc.tasks, self.feeding_chain.tasks)
        self.assertEqual(
            deserialized_fc.connects_to_task_id, self.feeding_chain.connects_to_task_id
        )

        # Check buffers
        self.assertEqual(deserialized_pb.id, self.project_buffer.id)
        self.assertEqual(deserialized_pb.buffer_type, self.project_buffer.buffer_type)
        self.assertEqual(deserialized_pb.size, self.project_buffer.size)

        self.assertEqual(deserialized_fb.id, self.feeding_buffer.id)
        self.assertEqual(deserialized_fb.buffer_type, self.feeding_buffer.buffer_type)
        self.assertEqual(deserialized_fb.connected_to, self.feeding_buffer.connected_to)


if __name__ == "__main__":
    unittest.main()
