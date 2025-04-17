"""
Example of using fractional resource allocations in CCPM.

This example demonstrates how to create a project using:
1. Partial resource allocations (e.g., Designer at 0.5 capacity)
2. Multiple resource allocations (e.g., 2 Developers)
3. Mixed allocation patterns

It shows how the resource leveling algorithm allows tasks to share resources
when their combined allocation doesn't exceed capacity.
"""

from datetime import datetime, timedelta
import matplotlib.pyplot as plt

from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler
from ccpm.visualization.gantt import create_gantt_chart, create_resource_gantt


def create_fractional_resource_project():
    """Create a sample project with tasks that use fractional resource allocations."""
    # Create scheduler
    scheduler = CCPMScheduler()

    # Set start date
    start_date = datetime(2025, 5, 1)
    scheduler.set_start_date(start_date)

    # Define resources
    resources = [
        "Designer",  # UI/UX designer
        "Dev A",  # Backend developer
        "Dev B",  # Frontend developer
        "Tester",  # QA tester
    ]
    scheduler.set_resources(resources)

    # Create tasks with various resource allocation patterns

    # Task 1: Full-time designer for initial design
    task1 = Task(id="T1", name="Initial Design", aggressive_duration=5, safe_duration=8)
    task1.resource_allocations = {"Designer": 1.0}

    # Task 2: Half-time designer for UI refinement + half-time Dev B for frontend setup
    # This allows the designer to work on documentation simultaneously
    task2 = Task(
        id="T2",
        name="UI Refinement & Frontend Setup",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T1"],
    )
    task2.resource_allocations = {"Designer": 0.5, "Dev B": 0.5}

    # Task 3: Half-time designer for documentation
    # This can run in parallel with Task 2 since they each use half of the Designer's time
    task3 = Task(
        id="T3",
        name="Design Documentation",
        aggressive_duration=7,
        safe_duration=10,
        dependencies=["T1"],
    )
    task3.resource_allocations = {"Designer": 0.5}

    # Task 4: Backend development using full-time Dev A
    task4 = Task(
        id="T4",
        name="Backend Development",
        aggressive_duration=10,
        safe_duration=15,
        dependencies=["T1"],
    )
    task4.resource_allocations = {"Dev A": 1.0}

    # Task 5: Frontend development using full-time Dev B
    # This will need to wait for Task 2 to finish since Dev B is partially allocated there
    task5 = Task(
        id="T5",
        name="Frontend Development",
        aggressive_duration=12,
        safe_duration=18,
        dependencies=["T2"],
    )
    task5.resource_allocations = {"Dev B": 1.0}

    # Task 6: Integration - uses both developers part-time
    # This shows how developers can split their time across work
    task6 = Task(
        id="T6",
        name="Integration",
        aggressive_duration=6,
        safe_duration=9,
        dependencies=["T4", "T5"],
    )
    task6.resource_allocations = {"Dev A": 0.7, "Dev B": 0.7}

    # Task 7: Testing - requires multiple testers (demonstrating multiple allocation)
    # In this case, we need 2 testers, which exceeds our capacity and will force
    # other tasks using testers to be scheduled sequentially
    task7 = Task(
        id="T7",
        name="Full Testing",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T6"],
    )
    task7.resource_allocations = {"Tester": 2.0}

    # Task 8: Parallel testing - can be done with a different team during development
    # Uses a partial tester allocation for ongoing feedback
    task8 = Task(
        id="T8",
        name="Continuous Testing",
        aggressive_duration=15,
        safe_duration=20,
        dependencies=["T2"],
    )
    task8.resource_allocations = {"Tester": 0.3}

    # Add all tasks to the scheduler
    scheduler.add_task(task1)
    scheduler.add_task(task2)
    scheduler.add_task(task3)
    scheduler.add_task(task4)
    scheduler.add_task(task5)
    scheduler.add_task(task6)
    scheduler.add_task(task7)
    scheduler.add_task(task8)

    # Run the scheduling algorithm
    scheduler.schedule()

    # Print information about the critical chain
    print("\nCritical Chain Tasks:")
    if scheduler.critical_chain:
        for task_id in scheduler.critical_chain.tasks:
            task = scheduler.tasks[task_id]
            print(f"  {task_id}: {task.name}")

            # Show resource allocations
            if hasattr(task, "resource_allocations") and task.resource_allocations:
                for res_id, amount in task.resource_allocations.items():
                    print(f"    - {res_id}: {amount}x")

    # Create visualizations
    create_gantt_chart(scheduler, filename="fractional_gantt.png", show=False)
    create_resource_gantt(
        scheduler, filename="fractional_resource_gantt.png", show=False
    )

    print("\nVisualizations saved as:")
    print("- fractional_gantt.png")
    print("- fractional_resource_gantt.png")

    # Display key observations about the schedule
    print("\nKey Schedule Observations:")

    # Example 1: Tasks 2 and 3 sharing Designer resource
    task2_start = scheduler.tasks["T2"].get_start_date()
    task3_start = scheduler.tasks["T3"].get_start_date()
    if task2_start == task3_start:
        print(
            "✓ Tasks 2 and 3 run in parallel, sharing the Designer resource (0.5 + 0.5 = 1.0)"
        )
    else:
        print("✗ Tasks 2 and 3 are not running in parallel as expected")

    # Example 2: Task 7 requiring multiple testers
    task7 = scheduler.tasks["T7"]
    task8 = scheduler.tasks["T8"]
    task7_start = task7.get_start_date()
    task7_end = task7.get_end_date()
    task8_start = task8.get_start_date()
    task8_end = task8.get_end_date()

    # Check if task8 and task7 overlap
    t7_range = range((task7_start - start_date).days, (task7_end - start_date).days)
    t8_range = range((task8_start - start_date).days, (task8_end - start_date).days)
    overlap = set(t7_range).intersection(set(t8_range))

    if not overlap:
        print(
            "✓ Tasks 7 and 8 don't overlap due to Tester resource constraints (2.0 + 0.3 > 1.0)"
        )
    else:
        print("✗ Tasks 7 and 8 are overlapping when they shouldn't")

    return scheduler


if __name__ == "__main__":
    scheduler = create_fractional_resource_project()

    # Generate and print execution report
    report = scheduler.generate_execution_report()
    print("\nProject Execution Report:")
    print("=========================")
    print(report)
