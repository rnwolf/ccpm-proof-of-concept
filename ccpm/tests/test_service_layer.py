"""
Integration test for CCPM service components.

This test verifies that all the service layer components work together properly.
"""

import unittest
from datetime import datetime, timedelta
import os

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ccpm.domain.task import Task
from ccpm.domain.buffer import Buffer
from ccpm.domain.chain import Chain
from ccpm.services.scheduler import CCPMScheduler
from ccpm.services.buffer_strategies import CutAndPasteMethod, SumOfSquaresMethod
from ccpm.services.critical_chain import (
    # identify_critical_chain,
    resolve_resource_conflicts,
)

# from ccpm.services.feeding_chain import identify_feeding_chains
from ccpm.services.resource_leveling import level_resources

from ccpm.services.scheduler import calculate_critical_chain
from ccpm.services.scheduler import find_feeding_chains


class CCPMServiceIntegrationTest(unittest.TestCase):
    def setUp(self):
        """Set up a test project with tasks and resources."""
        # Create tasks
        self.tasks = {
            "T1": Task(
                id="T1", name="Task 1", aggressive_duration=10, resources=["Resource A"]
            ),
            "T2": Task(
                id="T2",
                name="Task 2",
                aggressive_duration=15,
                resources=["Resource B"],
                dependencies=["T1"],
            ),
            "T3": Task(
                id="T3",
                name="Task 3",
                aggressive_duration=12,
                resources=["Resource A"],
                dependencies=["T2"],
            ),
            "T4": Task(
                id="T4", name="Task 4", aggressive_duration=8, resources=["Resource C"]
            ),
            "T5": Task(
                id="T5",
                name="Task 5",
                aggressive_duration=10,
                resources=["Resource B"],
                dependencies=["T4"],
            ),
        }

        # Create resources
        self.resources = ["Resource A", "Resource B", "Resource C"]

    def test_service_components(self):
        """Test that service components work together properly."""
        # Test critical_chain service
        import networkx as nx

        # Create a task graph
        task_graph = nx.DiGraph()

        # Add task nodes
        for task_id, task in self.tasks.items():
            task_graph.add_node(task_id, node_type="task", task=task)

        # Add task dependencies
        for task_id, task in self.tasks.items():
            for dep_id in task.dependencies:
                task_graph.add_edge(dep_id, task_id)

        # Test calculate_critical_chain
        critical_chain = calculate_critical_chain(
            self.tasks, self.resources, task_graph
        )

        # Verify critical chain - should be T1, T2, T3
        self.assertEqual(len(critical_chain.tasks), 3)
        self.assertEqual(critical_chain.tasks[0], "T1")
        self.assertEqual(critical_chain.tasks[1], "T2")
        self.assertEqual(critical_chain.tasks[2], "T3")

        # Test resolve_resource_conflicts
        resolved_path = resolve_resource_conflicts(
            critical_chain.tasks, self.tasks, self.resources, task_graph
        )

        # Verify the path is still valid after resource leveling
        self.assertEqual(len(resolved_path), 3)

        # Test feeding_chain service
        feeding_chains = find_feeding_chains(self.tasks, critical_chain, task_graph)

        # Verify feeding chains - should be one chain with T4, T5
        self.assertEqual(len(feeding_chains), 1)
        feeding_chain = feeding_chains[0]
        self.assertEqual(len(feeding_chain.tasks), 2)
        self.assertEqual(feeding_chain.tasks[0], "T4")
        self.assertEqual(feeding_chain.tasks[1], "T5")

        # Test resource_leveling service
        leveled_tasks, leveled_graph = level_resources(
            self.tasks, self.resources, critical_chain, task_graph
        )

        # Verify all tasks were leveled
        self.assertEqual(len(leveled_tasks), 5)

        # Verify task dates were set based on dependencies
        # T1 should start first (critical chain start)
        # T4 should start in parallel with T1 (different resource)
        # T2 should start after T1 (dependency)
        # T5 should start after T4 (dependency)
        # T3 should start after T2 (dependency)

        # Now test the scheduler that integrates all services
        scheduler = CCPMScheduler(
            project_buffer_ratio=0.5,
            default_feeding_buffer_ratio=0.3,
            project_buffer_strategy=CutAndPasteMethod(),
            default_feeding_buffer_strategy=SumOfSquaresMethod(),
        )

        # Set start date and resources
        start_date = datetime(2025, 4, 1)
        scheduler.set_start_date(start_date)
        scheduler.set_resources(self.resources)

        # Add tasks to scheduler
        for task_id, task in self.tasks.items():
            scheduler.add_task(task)

        # Run scheduling algorithm
        result = scheduler.schedule()

        # Verify results
        self.assertEqual(len(result["tasks"]), 5)
        self.assertEqual(len(result["chains"]), 2)  # 1 critical chain + 1 feeding chain
        self.assertEqual(
            len(result["buffers"]), 2
        )  # 1 project buffer + 1 feeding buffer

        # Verify critical chain was identified
        self.assertIsNotNone(scheduler.critical_chain)
        self.assertEqual(len(scheduler.critical_chain.tasks), 3)

        # Verify project buffer was created
        project_buffer = None
        for buffer_id, buffer in scheduler.buffers.items():
            if buffer.buffer_type == "project":
                project_buffer = buffer
                break

        self.assertIsNotNone(project_buffer)

        # Verify feeding buffer was created
        feeding_buffer = None
        for buffer_id, buffer in scheduler.buffers.items():
            if buffer.buffer_type == "feeding":
                feeding_buffer = buffer
                break

        self.assertIsNotNone(feeding_buffer)

        # Test execution functions
        # Week 1: Start T1 and T4
        week1_date = start_date + timedelta(days=7)
        scheduler.update_task_progress("T1", 5, week1_date)  # 50% complete
        scheduler.update_task_progress("T4", 4, week1_date)  # 50% complete

        # Verify task status
        self.assertEqual(scheduler.tasks["T1"].status, "in_progress")
        self.assertEqual(scheduler.tasks["T4"].status, "in_progress")

        # Week 2: Complete T1 and T4
        week2_date = start_date + timedelta(days=14)
        scheduler.update_task_progress("T1", 0, week2_date)  # 100% complete
        scheduler.update_task_progress("T4", 0, week2_date)  # 100% complete

        # Verify task status
        self.assertEqual(scheduler.tasks["T1"].status, "completed")
        self.assertEqual(scheduler.tasks["T4"].status, "completed")

        # Verify buffer consumption was calculated
        self.assertLessEqual(project_buffer.remaining_size, project_buffer.size)

        # Print execution report
        report = scheduler.generate_execution_report(week2_date)
        print("\n=== Week 2 Execution Report ===")
        print(report)

        print("\nService integration test completed successfully.")


if __name__ == "__main__":
    unittest.main()
