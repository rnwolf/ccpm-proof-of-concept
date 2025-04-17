from datetime import datetime, timedelta

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler
from ccpm.services.resource_leveling import level_resources


def test_scheduling_stages():
    """Test the individual stages of the scheduling process with proper resource leveling."""
    # Create a test scheduler
    scheduler = CCPMScheduler()

    # Set start date
    start_date = datetime(2025, 5, 1)
    scheduler.set_start_date(start_date)

    # Define resources
    resources = ["Resource A", "Resource B"]
    scheduler.set_resources(resources)

    # Create a simple test project with 3 tasks
    # T1 \
    #     -> T3
    # T2 /
    #
    # Both T1 and T2 use Resource A, which should create a conflict

    task1 = Task(
        id="T1",
        name="Task 1",
        aggressive_duration=5,
        safe_duration=10,
        resources=["Resource A"],  # Uses Resource A
    )

    task2 = Task(
        id="T2",
        name="Task 2",
        aggressive_duration=5,
        safe_duration=10,
        dependencies=[],
        resources=["Resource A"],  # Also uses Resource A - should cause conflict
    )

    task3 = Task(
        id="T3",
        name="Task 3",
        aggressive_duration=5,
        safe_duration=10,
        dependencies=["T1", "T2"],
        resources=["Resource C"],
    )

    # Add tasks to scheduler
    scheduler.add_task(task1)
    scheduler.add_task(task2)
    scheduler.add_task(task3)

    # Set up resources properly - make sure resource_allocations dict is created
    for task in scheduler.tasks.values():
        if not hasattr(task, "resource_allocations"):
            task.resource_allocations = {}
            if isinstance(task.resources, str):
                task.resource_allocations[task.resources] = 1.0
            elif isinstance(task.resources, list):
                for resource in task.resources:
                    task.resource_allocations[resource] = 1.0

    print("\n=== TEST: SCHEDULING STAGES WITH FIXED RESOURCES ===")

    # STAGE 1: Build dependency graph
    print("\n--- STAGE 1: Dependency Graph ---")
    dependency_graph = scheduler.build_dependency_graph()

    print(f"Graph nodes: {list(dependency_graph.nodes())}")
    print(f"Graph edges: {list(dependency_graph.edges())}")

    for node in dependency_graph.nodes():
        if node in scheduler.tasks:
            successors = list(dependency_graph.successors(node))
            predecessors = list(dependency_graph.predecessors(node))
            print(f"Task {node}: predecessors={predecessors}, successors={successors}")

    # STAGE 2: Calculate baseline schedule
    print("\n--- STAGE 2: Baseline Schedule ---")
    scheduler.calculate_baseline_schedule()

    print("Task schedules after baseline calculation:")
    for task_id, task in scheduler.tasks.items():
        print(f"Task {task_id}:")
        print(f"  - Early start: {task.early_start}")
        print(f"  - Early finish: {task.early_finish}")
        print(f"  - Late start: {task.late_start}")
        print(f"  - Late finish: {task.late_finish}")
        print(f"  - Slack: {task.slack}")
        print(f"  - Is critical: {getattr(task, 'is_critical', False)}")

    # STAGE 3: Calculate critical chain
    print("\n--- STAGE 3: Critical Chain ---")
    critical_chain = scheduler.calculate_critical_chain()

    print(f"Critical chain tasks (in order): {critical_chain.tasks}")
    print(f"Critical chain type: {critical_chain.type}")

    # Print chain membership for each task
    print("\nTask chain membership:")
    for task_id, task in scheduler.tasks.items():
        print(f"Task {task_id}:")
        print(f"  - Chain ID: {task.chain_id}")
        print(f"  - Chain type: {task.chain_type}")
        print(f"  - Is critical: {task.is_critical}")

    # Print buffer information
    if scheduler.buffers:
        print("\nBuffer information:")
        for buffer_id, buffer in scheduler.buffers.items():
            print(f"Buffer {buffer_id}:")
            print(f"  - Name: {buffer.name}")
            print(f"  - Type: {buffer.buffer_type}")
            print(f"  - Size: {buffer.size}")
            if buffer.buffer_type == "feeding":
                print(f"  - Connected to: {buffer.connected_to}")

    # STAGE 4: Apply resource leveling
    print("\n--- STAGE 4: Resource Leveling ---")
    if scheduler.resources:
        print("Before resource leveling:")
        for task_id, task in scheduler.tasks.items():
            print(
                f"Task {task_id}: early_start={task.early_start}, early_finish={task.early_finish}"
            )
            print(
                f"  - resources: {task.resource_allocations}"
            )  # Should show Resource A with allocation 1.0

        # Apply resource leveling
        scheduler.tasks, scheduler.task_graph = level_resources(
            scheduler.tasks,
            scheduler.resources,
            scheduler.critical_chain,
            scheduler.task_graph,
        )

        print("\nAfter resource leveling:")
        for task_id, task in scheduler.tasks.items():
            print(
                f"Task {task_id}: early_start={task.early_start}, early_finish={task.early_finish}"
            )
            if hasattr(task, "new_start_date") and task.new_start_date:
                print(f"  - new_start_date: {task.new_start_date}")
            if hasattr(task, "new_end_date") and task.new_end_date:
                print(f"  - new_end_date: {task.new_end_date}")

    # STAGE 5: Set actual dates for all tasks
    print("\n--- STAGE 5: Set Actual Dates ---")
    for task_id, task in scheduler.tasks.items():
        if not hasattr(task, "start_date") or task.start_date is None:
            task.start_date = start_date + timedelta(days=task.early_start)
            task.end_date = task.start_date + timedelta(days=task.planned_duration)
            print(
                f"Task {task_id}: start_date={task.start_date}, end_date={task.end_date}"
            )

    # STAGE 6: Identify feeding chains
    print("\n--- STAGE 6: Identify Feeding Chains ---")
    feeding_chains = scheduler.find_feeding_chains()

    print(f"Number of feeding chains identified: {len(feeding_chains)}")
    for i, chain in enumerate(feeding_chains, 1):
        print(f"Feeding Chain {i}:")
        print(f"  - ID: {chain.id}")
        print(f"  - Name: {chain.name}")
        print(f"  - Tasks: {chain.tasks}")
        print(f"  - Connects to: {chain.connects_to_task_id}")

    # STAGE 7: Calculate and add feeding buffers
    print("\n--- STAGE 7: Calculate Buffers ---")
    buffers = scheduler.calculate_buffers()

    print("Buffers after calculation:")
    for buffer_id, buffer in buffers.items():
        print(f"Buffer {buffer_id}:")
        print(f"  - Name: {buffer.name}")
        print(f"  - Type: {buffer.buffer_type}")
        print(f"  - Size: {buffer.size}")
        if buffer.buffer_type == "feeding":
            print(f"  - Connected to: {buffer.connected_to}")

    # STAGE 8: Update schedule with buffers
    print("\n--- STAGE 8: Apply Buffer to Schedule ---")
    scheduler.apply_buffer_to_schedule()

    print("Task and buffer dates after applying buffers:")

    # Print task dates
    for task_id, task in scheduler.tasks.items():
        print(f"Task {task_id}:")
        print(f"  - Start date: {task.start_date}")
        print(f"  - End date: {task.end_date}")
        if hasattr(task, "new_start_date") and task.new_start_date:
            print(f"  - New start date: {task.new_start_date}")
        if hasattr(task, "new_end_date") and task.new_end_date:
            print(f"  - New end date: {task.new_end_date}")

    # Print buffer dates
    for buffer_id, buffer in scheduler.buffers.items():
        print(f"Buffer {buffer_id}:")
        print(f"  - Start date: {buffer.start_date}")
        print(f"  - End date: {buffer.end_date}")
        if hasattr(buffer, "new_start_date") and buffer.new_start_date:
            print(f"  - New start date: {buffer.new_start_date}")
        if hasattr(buffer, "new_end_date") and buffer.new_end_date:
            print(f"  - New end date: {buffer.new_end_date}")

    # Print final project duration
    project_buffer = None
    for buffer in scheduler.buffers.values():
        if buffer.buffer_type == "project":
            project_buffer = buffer
            break

    if project_buffer and project_buffer.end_date:
        total_duration = (project_buffer.end_date - start_date).days
        print(f"\nTotal project duration: {total_duration} days")

    return scheduler


if __name__ == "__main__":
    test_scheduling_stages()
