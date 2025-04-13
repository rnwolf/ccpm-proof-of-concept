from datetime import datetime
from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler
from ccpm.services.buffer_strategies import CutAndPasteMethod, SumOfSquaresMethod
from ccpm.visualization.gantt import create_gantt_chart


def create_sample_project():
    # Define resources
    resources = ["Red", "Green", "Magenta", "Blue"]

    # Create tasks
    task1 = Task(1, "T1.1", aggressive_duration=20, safe_duration=30, resources=["Red"])
    task2 = Task(
        2, "T1.2", aggressive_duration=15, safe_duration=20, resources=["Green"]
    )
    task2.dependencies = [1]  # Depends on task 1

    task3 = Task(
        3, "T3", aggressive_duration=30, safe_duration=40, resources=["Magenta"]
    )
    task3.dependencies = [5, 2]  # Depends on tasks 5 and 2

    task4 = Task(
        4, "T2.1", aggressive_duration=20, safe_duration=25, resources=["Blue"]
    )
    task5 = Task(
        5, "T2.2", aggressive_duration=10, safe_duration=15, resources=["Green"]
    )
    task5.dependencies = [4]  # Depends on task 4

    # Create the scheduler
    scheduler = CCPMScheduler(
        project_buffer_ratio=0.5,
        default_feeding_buffer_ratio=0.3,
        project_buffer_strategy=CutAndPasteMethod(),
        default_feeding_buffer_strategy=SumOfSquaresMethod(),
    )

    # Set start date and resources
    start_date = datetime(2025, 4, 1)
    scheduler.set_start_date(start_date)
    scheduler.set_resources(resources)

    # Add tasks to the scheduler
    scheduler.add_task(task1)
    scheduler.add_task(task2)
    scheduler.add_task(task3)
    scheduler.add_task(task4)
    scheduler.add_task(task5)

    # Run the scheduling algorithm
    scheduler.schedule()

    # Create visualization
    create_gantt_chart(scheduler, "ccpm_gantt_example.png")

    # Print report
    print("CCPM Project Schedule Report")
    print("===========================")
    print(f"Project Start Date: {start_date.strftime('%Y-%m-%d')}")

    # Find project end date (including project buffer)
    project_buffer = scheduler.buffers.get("PB")
    if project_buffer and hasattr(project_buffer, "end_date"):
        project_end = project_buffer.end_date
        print(f"Project End Date: {project_end.strftime('%Y-%m-%d')}")
        print(f"Project Duration: {(project_end - start_date).days} days")

    # Print critical chain
    if scheduler.critical_chain:
        print("\nCritical Chain:")
        for task_id in scheduler.critical_chain.tasks:
            if task_id in scheduler.tasks:
                task = scheduler.tasks[task_id]
                print(
                    f"  Task {task.id}: {task.name} - Duration: {task.planned_duration} days"
                )

    # Print feeding chains
    print("\nFeeding Chains:")
    for chain_id, chain in scheduler.chains.items():
        if chain.type == "feeding":
            print(f"  Chain {chain_id}: {chain.name}")
            print(f"    Connects to: {chain.connects_to_task_id}")
            print(f"    Tasks: {', '.join(str(task_id) for task_id in chain.tasks)}")

    # Print buffers
    print("\nBuffers:")
    for buffer_id, buffer in scheduler.buffers.items():
        print(f"  {buffer.name} ({buffer.size} days)")
        print(f"    Type: {buffer.buffer_type}")
        if hasattr(buffer, "strategy_name") and buffer.strategy_name:
            print(f"    Calculation: {buffer.strategy_name}")

    return scheduler


if __name__ == "__main__":
    create_sample_project()
