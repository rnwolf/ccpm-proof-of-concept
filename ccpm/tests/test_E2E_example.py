"""
    E2E example for the CCPM project.

    Returns:
        _type_: _description_


        This network has:

A main path that should become the critical chain (T1 → T2 → T3 → T4 → T5 → T6 → T7)
Three distinct feeding chains:

UI path (T8 → T9) connecting to T5
Database path (T10 → T11 → T12) connecting to T5
Security path (T13 → T14) connecting to either T4 or T5 (depending on how your algorithm resolves resource conflicts)

The network includes:

Resource dependencies that will create conflicts to resolve
Multiple merge points where feeding chains connect to the critical chain
A variety of task durations to create interesting buffer calculations
Clear separation of roles by resource assignment

This should produce a valid critical chain and multiple feeding chains that your visualization tools can effectively display.

"""

from datetime import datetime
from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler
import matplotlib.pyplot as plt
import os

# Import visualization functions
from ccpm.visualization.gantt import (
    create_gantt_chart,
    create_resource_gantt,
    create_buffer_chart,
)
from ccpm.visualization.network import create_network_diagram
from ccpm.visualization.fever_chart import create_fever_chart


def create_sample_network():
    # Create scheduler
    scheduler = CCPMScheduler()

    # Set start date
    start_date = datetime(2025, 5, 1)
    scheduler.set_start_date(start_date)

    # Define resources
    resources = [
        "Engineer A",
        "Engineer B",
        "Designer",
        "Tester",
        "Analyst",
        "Developer",
    ]
    scheduler.set_resources(resources)

    # Create tasks
    # Main path (will become critical chain)
    task1 = Task(
        id="T1",
        name="Project Initiation",
        aggressive_duration=5,
        safe_duration=8,
        resources=["Analyst"],
    )
    task2 = Task(
        id="T2",
        name="Requirements Analysis",
        aggressive_duration=10,
        safe_duration=15,
        dependencies=["T1"],
        resources=["Analyst"],
    )
    task3 = Task(
        id="T3",
        name="System Design",
        aggressive_duration=15,
        safe_duration=20,
        dependencies=["T2"],
        resources=["Designer"],
    )
    task4 = Task(
        id="T4",
        name="Core Development",
        aggressive_duration=20,
        safe_duration=30,
        dependencies=["T3"],
        resources=["Developer"],
    )
    task5 = Task(
        id="T5",
        name="System Integration",
        aggressive_duration=10,
        safe_duration=15,
        dependencies=["T4", "T8", "T12"],
        resources=["Engineer A"],
    )
    task6 = Task(
        id="T6",
        name="System Testing",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T5"],
        resources=["Tester"],
    )
    task7 = Task(
        id="T7",
        name="User Acceptance",
        aggressive_duration=5,
        safe_duration=10,
        dependencies=["T6"],
        resources=["Analyst"],
    )

    # First feeding chain
    task8 = Task(
        id="T8",
        name="UI Design",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T3"],
        resources=["Designer"],
    )
    task9 = Task(
        id="T9",
        name="UI Development",
        aggressive_duration=12,
        safe_duration=18,
        dependencies=["T8"],
        resources=["Developer"],
    )

    # Second feeding chain
    task10 = Task(
        id="T10",
        name="Database Design",
        aggressive_duration=7,
        safe_duration=10,
        dependencies=["T3"],
        resources=["Engineer B"],
    )
    task11 = Task(
        id="T11",
        name="Database Setup",
        aggressive_duration=5,
        safe_duration=8,
        dependencies=["T10"],
        resources=["Engineer B"],
    )
    task12 = Task(
        id="T12",
        name="Data Migration",
        aggressive_duration=6,
        safe_duration=10,
        dependencies=["T11"],
        resources=["Engineer A", "Engineer B"],
    )

    # Third feeding chain (short)
    task13 = Task(
        id="T13",
        name="Security Planning",
        aggressive_duration=4,
        safe_duration=6,
        dependencies=["T2"],
        resources=["Analyst"],
    )
    task14 = Task(
        id="T14",
        name="Security Implementation",
        aggressive_duration=7,
        safe_duration=10,
        dependencies=["T13"],
        resources=["Developer"],
    )

    # Add all tasks to scheduler
    for task in [
        task1,
        task2,
        task3,
        task4,
        task5,
        task6,
        task7,
        task8,
        task9,
        task10,
        task11,
        task12,
        task13,
        task14,
    ]:
        scheduler.add_task(task)

    # Schedule the project
    scheduler.schedule()

    # Print information about the chains
    print("\nCritical Chain:")
    if scheduler.critical_chain:
        print(f"  Tasks: {scheduler.critical_chain.tasks}")

    print("\nFeeding Chains:")
    for chain_id, chain in scheduler.chains.items():
        if chain.type == "feeding":
            print(f"  Chain {chain_id}: {chain.name}")
            print(f"    Tasks: {chain.tasks}")
            print(f"    Connects to: {chain.connects_to_task_id}")

    # Create visualizations
    create_visualizations(scheduler, "ccpm_test_network")

    return scheduler


def create_visualizations(scheduler, output_prefix):
    """Create and save all visualizations."""
    print("\nGenerating visualizations...")

    # Create output directory if it doesn't exist
    output_dir = "visualization_output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define output paths
    gantt_path = os.path.join(output_dir, f"{output_prefix}_gantt.png")
    resource_gantt_path = os.path.join(
        output_dir, f"{output_prefix}_resource_gantt.png"
    )
    buffer_path = os.path.join(output_dir, f"{output_prefix}_buffer.png")
    network_path = os.path.join(output_dir, f"{output_prefix}_network.png")
    fever_path = os.path.join(output_dir, f"{output_prefix}_fever.png")

    # Create Gantt chart
    print("Creating Gantt chart...")
    gantt_fig = create_gantt_chart(scheduler, filename=gantt_path, show=False)
    plt.close(gantt_fig)

    # Create Resource Gantt chart
    print("Creating Resource Gantt chart...")
    resource_fig = create_resource_gantt(
        scheduler, filename=resource_gantt_path, show=False
    )
    plt.close(resource_fig)

    # Create Buffer chart
    print("Creating Buffer chart...")
    buffer_fig = create_buffer_chart(scheduler, filename=buffer_path, show=False)
    plt.close(buffer_fig)

    # Create Network diagram
    print("Creating Network diagram...")
    network_fig = create_network_diagram(scheduler, filename=network_path, show=False)
    plt.close(network_fig)

    # Create Fever chart
    print("Creating Fever chart...")
    try:
        fever_fig = create_fever_chart(scheduler, filename=fever_path, show=False)
        plt.close(fever_fig)
    except Exception as e:
        print(f"Could not create fever chart: {e}")

    print(f"\nVisualizations created in '{output_dir}' directory:")
    print(f"1. Gantt Chart: {gantt_path}")
    print(f"2. Resource Gantt Chart: {resource_gantt_path}")
    print(f"3. Buffer Chart: {buffer_path}")
    print(f"4. Network Diagram: {network_path}")
    print(f"5. Fever Chart: {fever_path}")

    # Simulate some execution for fever chart data
    simulate_execution(scheduler)


def simulate_execution(scheduler):
    """Simulate execution progress to populate fever chart data."""
    print("\nSimulating execution for fever chart data...")

    # Week 1 progress
    week1_date = scheduler.start_date + timedelta(days=7)
    # Find first task and start it
    first_task_id = scheduler.critical_chain.tasks[0]
    scheduler.update_task_progress(first_task_id, 2, week1_date)  # Partially complete

    # Week 2 progress
    week2_date = scheduler.start_date + timedelta(days=14)
    scheduler.update_task_progress(first_task_id, 0, week2_date)  # Complete first task

    # Create updated fever chart
    fever_updated_path = os.path.join(
        "visualization_output", "ccpm_test_network_fever_updated.png"
    )
    try:
        fever_fig = create_fever_chart(
            scheduler,
            filename=fever_updated_path,
            show=False,
            project_name="Sample Project (With Progress)",
        )
        plt.close(fever_fig)
        print(f"6. Updated Fever Chart: {fever_updated_path}")
    except Exception as e:
        print(f"Could not create updated fever chart: {e}")

    return scheduler


if __name__ == "__main__":
    from datetime import timedelta  # Import here for simulate_execution

    network = create_sample_network()
