"""
Integration test for CCPM visualization components.

This test creates a sample project, executes it, and generates visualizations
to verify that the visualization components work correctly.
"""

import unittest
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler
from ccpm.services.buffer_strategies import CutAndPasteMethod, SumOfSquaresMethod
from ccpm.visualization.gantt import create_gantt_chart, create_buffer_chart
from ccpm.visualization.network import create_network_diagram
from ccpm.visualization.fever_chart import create_fever_chart


class CCPMVisualizationTest(unittest.TestCase):
    def setUp(self):
        """Set up a sample project with tasks, chains, and buffers."""
        # Create a scheduler
        self.scheduler = CCPMScheduler()

        # Set start date
        self.start_date = datetime(2025, 4, 1)
        self.scheduler.set_start_date(self.start_date)

        # Set resources
        self.scheduler.set_resources(
            [
                "Business Analyst",
                "Architect",
                "Developer A",
                "Developer B",
                "DBA",
                "Tester",
            ]
        )

        # Create tasks
        task1 = Task(
            id="T1",
            name="Requirements Analysis",
            aggressive_duration=5,
            safe_duration=8,
            resources=["Business Analyst"],
        )

        task2 = Task(
            id="T2",
            name="System Design",
            aggressive_duration=10,
            safe_duration=15,
            dependencies=["T1"],
            resources=["Architect"],
        )

        task3 = Task(
            id="T3",
            name="Frontend Development",
            aggressive_duration=15,
            safe_duration=20,
            dependencies=["T2"],
            resources=["Developer A", "Developer B"],
        )

        task4 = Task(
            id="T4",
            name="Backend Development",
            aggressive_duration=12,
            safe_duration=18,
            dependencies=["T2"],
            resources=["Developer A"],
        )

        task5 = Task(
            id="T5",
            name="Database Setup",
            aggressive_duration=8,
            safe_duration=12,
            dependencies=["T2"],
            resources=["DBA"],
        )

        task6 = Task(
            id="T6",
            name="Integration",
            aggressive_duration=6,
            safe_duration=10,
            dependencies=["T3", "T4", "T5"],
            resources=["Developer A", "Developer B"],
        )

        task7 = Task(
            id="T7",
            name="Testing",
            aggressive_duration=8,
            safe_duration=12,
            dependencies=["T6"],
            resources=["Tester"],
        )

        # Add tasks to scheduler
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)
        self.scheduler.add_task(task3)
        self.scheduler.add_task(task4)
        self.scheduler.add_task(task5)
        self.scheduler.add_task(task6)
        self.scheduler.add_task(task7)

        # Run scheduler to create initial schedule
        self.scheduler.schedule()

    def test_visualization_components(self):
        """Test the visualization components with project execution."""
        # Set output directory
        output_dir = "test_outputs"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"\nGenerating visualizations in '{output_dir}' directory")

        # Generate initial visualizations
        print("\n=== Initial Project Schedule ===")

        # Create Gantt chart
        gantt_file = os.path.join(output_dir, "initial_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created initial Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        # Create Network diagram
        network_file = os.path.join(output_dir, "initial_network.png")
        network_fig = create_network_diagram(
            self.scheduler, filename=network_file, show=False
        )
        print(f"Created initial Network diagram: {network_file}")
        plt.close(network_fig)

        # Create Buffer chart
        buffer_file = os.path.join(output_dir, "initial_buffer.png")
        buffer_fig = create_buffer_chart(
            self.scheduler, filename=buffer_file, show=False
        )
        print(f"Created initial Buffer chart: {buffer_file}")
        plt.close(buffer_fig)

        # Create Fever chart - this will be mostly empty since no progress has been made
        fever_file = os.path.join(output_dir, "initial_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created initial Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Execute project for a few weeks
        # Week 1: Start T1
        week1_date = self.start_date + timedelta(days=7)
        print(f"\n=== Week 1 ({week1_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T1", 2, week1_date)  # 60% complete

        # Create Week 1 Gantt chart
        gantt_file = os.path.join(output_dir, "week1_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created Week 1 Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        # Create Week 1 Fever chart
        fever_file = os.path.join(output_dir, "week1_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created Week 1 Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Week 2: Complete T1, start T2
        week2_date = self.start_date + timedelta(days=14)
        print(f"\n=== Week 2 ({week2_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T1", 0, week2_date)  # 100% complete
        self.scheduler.update_task_progress("T2", 8, week2_date)  # 20% complete

        # Create Week 2 Gantt chart
        gantt_file = os.path.join(output_dir, "week2_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created Week 2 Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        # Create Week 2 Fever chart
        fever_file = os.path.join(output_dir, "week2_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created Week 2 Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Week 4: Complete T2, start T3, T4, T5
        week4_date = self.start_date + timedelta(days=28)
        print(f"\n=== Week 4 ({week4_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T2", 0, week4_date)  # 100% complete
        self.scheduler.update_task_progress("T3", 12, week4_date)  # 20% complete
        self.scheduler.update_task_progress("T4", 10, week4_date)  # 17% complete
        self.scheduler.update_task_progress("T5", 6, week4_date)  # 25% complete

        # Create Week 4 visualizations
        gantt_file = os.path.join(output_dir, "week4_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created Week 4 Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        network_file = os.path.join(output_dir, "week4_network.png")
        network_fig = create_network_diagram(
            self.scheduler, filename=network_file, show=False
        )
        print(f"Created Week 4 Network diagram: {network_file}")
        plt.close(network_fig)

        buffer_file = os.path.join(output_dir, "week4_buffer.png")
        buffer_fig = create_buffer_chart(
            self.scheduler, filename=buffer_file, show=False
        )
        print(f"Created Week 4 Buffer chart: {buffer_file}")
        plt.close(buffer_fig)

        fever_file = os.path.join(output_dir, "week4_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created Week 4 Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Week 6: T5 finished on time, T3 and T4 delayed
        week6_date = self.start_date + timedelta(days=42)
        print(f"\n=== Week 6 ({week6_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T5", 0, week6_date)  # 100% complete
        self.scheduler.update_task_progress("T3", 6, week6_date)  # 60% complete
        self.scheduler.update_task_progress("T4", 4, week6_date)  # 67% complete

        # Create Week 6 visualizations
        gantt_file = os.path.join(output_dir, "week6_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created Week 6 Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        fever_file = os.path.join(output_dir, "week6_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created Week 6 Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Week 8: T3 and T4 finished, T6 started
        week8_date = self.start_date + timedelta(days=56)
        print(f"\n=== Week 8 ({week8_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T3", 0, week8_date)  # 100% complete
        self.scheduler.update_task_progress("T4", 0, week8_date)  # 100% complete
        self.scheduler.update_task_progress("T6", 4, week8_date)  # 33% complete

        # Create Week 8 visualizations
        gantt_file = os.path.join(output_dir, "week8_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created Week 8 Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        fever_file = os.path.join(output_dir, "week8_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created Week 8 Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Week 9: T6 finished, T7 started
        week9_date = self.start_date + timedelta(days=63)
        print(f"\n=== Week 9 ({week9_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T6", 0, week9_date)  # 100% complete
        self.scheduler.update_task_progress("T7", 6, week9_date)  # 25% complete

        # Create Week 9 visualizations
        gantt_file = os.path.join(output_dir, "week9_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created Week 9 Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        fever_file = os.path.join(output_dir, "week9_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created Week 9 Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Week 11: T7 finished (project completed)
        week11_date = self.start_date + timedelta(days=77)
        print(f"\n=== Week 11 ({week11_date.strftime('%Y-%m-%d')}) ===")
        self.scheduler.update_task_progress("T7", 0, week11_date)  # 100% complete

        # Create final visualizations
        gantt_file = os.path.join(output_dir, "final_gantt.png")
        gantt_fig = create_gantt_chart(self.scheduler, filename=gantt_file, show=False)
        print(f"Created final Gantt chart: {gantt_file}")
        plt.close(gantt_fig)

        network_file = os.path.join(output_dir, "final_network.png")
        network_fig = create_network_diagram(
            self.scheduler, filename=network_file, show=False
        )
        print(f"Created final Network diagram: {network_file}")
        plt.close(network_fig)

        buffer_file = os.path.join(output_dir, "final_buffer.png")
        buffer_fig = create_buffer_chart(
            self.scheduler, filename=buffer_file, show=False
        )
        print(f"Created final Buffer chart: {buffer_file}")
        plt.close(buffer_fig)

        fever_file = os.path.join(output_dir, "final_fever.png")
        fever_fig = create_fever_chart(self.scheduler, filename=fever_file, show=False)
        print(f"Created final Fever chart: {fever_file}")
        plt.close(fever_fig)

        # Verify results
        # Check final project status
        completed_count = sum(
            1
            for task in self.scheduler.tasks.values()
            if hasattr(task, "status") and task.status == "completed"
        )
        self.assertEqual(completed_count, 7)  # All tasks should be completed

        # Get project buffer consumption
        project_buffer = None
        for buffer in self.scheduler.buffers.values():
            if buffer.buffer_type == "project":
                project_buffer = buffer
                break

        self.assertIsNotNone(project_buffer)

        # Print execution report
        report = self.scheduler.generate_execution_report(week11_date)
        print("\n=== Final Execution Report ===")
        print(report)

        print("\nVisualization test completed successfully.")


if __name__ == "__main__":
    unittest.main()
