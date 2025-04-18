"""
Test script for CCPM visualization components.
This script creates a sample project and generates various chart visualizations.
"""

import sys
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Add the parent directory to the path if needed
# import sys
# sys.path.append('..')

from ccpm.domain.task import Task
from ccpm.domain.buffer import Buffer
from ccpm.domain.chain import Chain
from ccpm.services.scheduler import CCPMScheduler
from ccpm.visualization.network import create_network_diagram
from ccpm.visualization.gantt import (
    create_gantt_chart,
    create_resource_gantt,
    create_buffer_chart,
)


def create_test_project():
    """Create a test project with tasks, chains, and buffers for visualization."""
    # Create a scheduler
    scheduler = CCPMScheduler()

    # Set start date
    start_date = datetime(2025, 4, 1)
    scheduler.start_date = start_date

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
        resources=["Developer C"],
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
        resources=["Developer A", "Developer C"],
    )
    task7 = Task(
        id="T7",
        name="Testing",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T6"],
        resources=["Tester"],
    )
    task8 = Task(
        id="T8",
        name="Deployment",
        aggressive_duration=3,
        safe_duration=5,
        dependencies=["T7"],
        resources=["DevOps"],
    )

    # Add tasks to scheduler
    scheduler.add_task(task1)
    scheduler.add_task(task2)
    scheduler.add_task(task3)
    scheduler.add_task(task4)
    scheduler.add_task(task5)
    scheduler.add_task(task6)
    scheduler.add_task(task7)
    scheduler.add_task(task8)

    # Set task schedules
    for i, task in enumerate(scheduler.tasks.values()):
        task_start = start_date + timedelta(days=i * 5)  # Spread out for visualization
        task.set_schedule(task_start)

    # Create chains
    critical_chain = Chain(id="CC", name="Critical Chain", type="critical")
    critical_chain.add_task("T1").add_task("T2").add_task("T4").add_task("T6").add_task(
        "T7"
    ).add_task("T8")

    feeding_chain1 = Chain(id="FC1", name="Frontend Chain", type="feeding")
    feeding_chain1.add_task("T3")
    feeding_chain1.set_connection("T6")

    feeding_chain2 = Chain(id="FC2", name="Database Chain", type="feeding")
    feeding_chain2.add_task("T5")
    feeding_chain2.set_connection("T6")

    # Add chains to scheduler
    scheduler.chains = {
        "CC": critical_chain,
        "FC1": feeding_chain1,
        "FC2": feeding_chain2,
    }
    scheduler.critical_chain = critical_chain

    # Update task chain information
    for task_id in critical_chain.tasks:
        scheduler.tasks[task_id].chain_id = "CC"
        scheduler.tasks[task_id].chain_type = "critical"

    for task_id in feeding_chain1.tasks:
        scheduler.tasks[task_id].chain_id = "FC1"
        scheduler.tasks[task_id].chain_type = "feeding"

    for task_id in feeding_chain2.tasks:
        scheduler.tasks[task_id].chain_id = "FC2"
        scheduler.tasks[task_id].chain_type = "feeding"

    # Create buffers
    project_buffer = Buffer(
        id="PB", name="Project Buffer", size=10.0, buffer_type="project"
    )

    feeding_buffer1 = Buffer(
        id="FB1",
        name="Frontend Buffer",
        size=5.0,
        buffer_type="feeding",
        connected_to="T6",
    )

    feeding_buffer2 = Buffer(
        id="FB2",
        name="Database Buffer",
        size=3.0,
        buffer_type="feeding",
        connected_to="T6",
    )

    # Set buffer dates
    last_task = scheduler.tasks["T8"]
    project_buffer.start_date = last_task.get_end_date()
    project_buffer.end_date = project_buffer.start_date + timedelta(
        days=project_buffer.size
    )

    t3_end = scheduler.tasks["T3"].get_end_date()
    feeding_buffer1.start_date = t3_end
    feeding_buffer1.end_date = feeding_buffer1.start_date + timedelta(
        days=feeding_buffer1.size
    )

    t5_end = scheduler.tasks["T5"].get_end_date()
    feeding_buffer2.start_date = t5_end
    feeding_buffer2.end_date = feeding_buffer2.start_date + timedelta(
        days=feeding_buffer2.size
    )

    # Add buffers to scheduler
    scheduler.buffers = {
        "PB": project_buffer,
        "FB1": feeding_buffer1,
        "FB2": feeding_buffer2,
    }

    # Simulate some progress
    execution_date = start_date + timedelta(days=25)  # 25 days into the project
    scheduler.execution_date = execution_date

    # Mark T1 and T2 as completed
    task1.status = "completed"
    task1.actual_start_date = task1.start_date
    task1.actual_end_date = task1.start_date + timedelta(days=5)

    task2.status = "completed"
    task2.actual_start_date = task2.start_date
    task2.actual_end_date = task2.start_date + timedelta(days=10)

    # Mark T3, T4, T5 as in progress with different completion percentages
    task3.status = "in_progress"
    task3.actual_start_date = task3.start_date
    task3.remaining_duration = 5.0  # 10 of 15 days done

    task4.status = "in_progress"
    task4.actual_start_date = task4.start_date
    task4.remaining_duration = 6.0  # 6 of 12 days done

    task5.status = "in_progress"
    task5.actual_start_date = task5.start_date
    task5.remaining_duration = 2.0  # 6 of 8 days done

    # Consume some buffer
    project_buffer.consume(2.0, execution_date, "Delay in Backend Development")
    feeding_buffer1.consume(
        1.5, execution_date, "Frontend components took longer than expected"
    )
    feeding_buffer2.consume(0.5, execution_date, "Minor database configuration issue")

    return scheduler


def test_gantt_visualization():
    """Test the Gantt chart visualization."""
    print("Testing Gantt Chart Visualization...")
    scheduler = create_test_project()

    # Create Gantt chart
    create_gantt_chart(scheduler, filename="test_project_gantt.png")
    print("Gantt chart saved as 'test_project_gantt.png'")


def test_resource_gantt():
    """Test the Resource Gantt chart visualization."""
    print("Testing Resource Allocation Chart...")
    scheduler = create_test_project()

    # Create Resource Gantt chart
    create_resource_gantt(scheduler, filename="test_resource_gantt.png")
    print("Resource allocation chart saved as 'test_resource_gantt.png'")


def test_buffer_chart():
    """Test the Buffer consumption chart."""
    print("Testing Buffer Consumption Chart...")
    scheduler = create_test_project()

    # Create Buffer chart
    create_buffer_chart(scheduler, filename="test_buffer_chart.png")
    print("Buffer consumption chart saved as 'test_buffer_chart.png'")


def test_network_diagram():
    """Test the Network Diagram visualization."""
    print("Testing Network Diagram...")
    scheduler = create_test_project()

    # Create Network Diagram with different layouts
    create_network_diagram(
        scheduler, filename="test_network_spring.png", layout="spring"
    )
    print("Network diagram (spring layout) saved as 'test_network_spring.png'")

    create_network_diagram(
        scheduler, filename="test_network_circular.png", layout="circular"
    )
    print("Network diagram (circular layout) saved as 'test_network_circular.png'")

    try:
        create_network_diagram(scheduler, filename="test_network_dot.png", layout="dot")
        print("Network diagram (dot layout) saved as 'test_network_dot.png'")
    except Exception as e:
        print(f"Note: Dot layout unavailable - {str(e)}")


def test_gantt_with_dependencies():
    """Test Gantt chart with dependency lines."""
    print("Testing Gantt Chart with Dependencies...")
    scheduler = create_test_project()

    # Create Gantt chart with dependencies
    create_gantt_chart(
        scheduler, filename="test_gantt_with_deps.png", show_dependencies=True
    )
    print("Gantt chart with dependencies saved as 'test_gantt_with_deps.png'")


def test_resource_visualization():
    """Test the Resource Loading visualization method in CriticalChainScheduler."""
    print("Testing Resource Loading Visualization...")

    # Import the CriticalChainScheduler class
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    from ai_ccpm_vba_to_py import CriticalChainScheduler, Task, Resource

    # Create a scheduler
    scheduler = CriticalChainScheduler()

    # Create resources
    resource1 = Resource("R1", "Developer")
    resource2 = Resource("R2", "Designer")
    resource3 = Resource("R3", "Tester")

    scheduler.add_resource(resource1)
    scheduler.add_resource(resource2)
    scheduler.add_resource(resource3)

    # Create tasks with resources
    task1 = Task(1, "Task 1", 5)
    task1.resources = ["R1", "R2"]
    task1.start = 0
    task1.finish = 5
    task1.type = 1  # Critical chain

    task2 = Task(2, "Task 2", 8)
    task2.resources = ["R1", "R3"]
    task2.start = 5
    task2.finish = 13
    task2.type = 1  # Critical chain

    task3 = Task(3, "Task 3", 6)
    task3.resources = ["R2"]
    task3.start = 3
    task3.finish = 9
    task3.type = 2  # Secondary chain

    task4 = Task(4, "Task 4", 4)
    task4.resources = ["R3"]
    task4.start = 13
    task4.finish = 17
    task4.type = 1  # Critical chain

    # Add tasks to scheduler
    scheduler.critical_chain = [task1, task2, task4]
    scheduler.secondary_chains = [[task3]]

    # Call the visualize_resource method
    scheduler.visualize_resource()

    print("Resource Loading visualization test completed.")


def run_all_tests():
    """Run all visualization tests."""
    test_gantt_visualization()
    test_resource_gantt()
    test_buffer_chart()
    test_network_diagram()
    test_gantt_with_dependencies()
    test_resource_visualization()
    print("All visualization tests completed successfully.")


if __name__ == "__main__":
    run_all_tests()
