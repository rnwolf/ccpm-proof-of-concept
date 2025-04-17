import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler

# Test 1: Try creating a task with safe_duration as a string that can be converted to a float
try:
    print("Test 1: Creating task with safe_duration as a string that can be converted to a float...")
    task1 = Task(
        id="T1",
        name="Task 1",
        aggressive_duration=5,
        safe_duration="10.0",  # This should now work with our fix
        resources=["Resource A"]
    )
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task1.aggressive_duration}")
    print(f"Task safe_duration: {task1.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

    # Create a task with valid durations as fallback
    print("\nCreating task with valid durations as fallback...")
    task1 = Task(
        id="T1",
        name="Task 1",
        aggressive_duration=5,
        safe_duration=10,
        resources=["Resource A"]
    )
    print("Fallback task created successfully!")
    print(f"Task aggressive_duration: {task1.aggressive_duration}")
    print(f"Task safe_duration: {task1.safe_duration}")

# Test 2: Try creating a task with safe_duration as a string that can't be converted to a float
try:
    print("\nTest 2: Creating task with safe_duration as a string that can't be converted to a float...")
    task2 = Task(
        id="T2",
        name="Task 2",
        aggressive_duration=5,
        safe_duration="abc",  # This should fail validation
        resources=["Resource B"]
    )
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task2.aggressive_duration}")
    print(f"Task safe_duration: {task2.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    # This is expected to fail, so we don't need a traceback
    # import traceback
    # traceback.print_exc()

# Create the scheduler
scheduler = CCPMScheduler()

# Try to add the task to the scheduler and schedule it
try:
    print("Adding task to scheduler...")
    scheduler.add_task(task1)
    print("Task added successfully!")

    # Print task details before scheduling
    print("\nTask details before scheduling:")
    print(f"Task ID: {task1.id}")
    print(f"Task Name: {task1.name}")
    print(f"Aggressive Duration: {task1.aggressive_duration}")
    print(f"Safe Duration: {task1.safe_duration}")
    print(f"Planned Duration: {task1.planned_duration}")

    # Try to schedule the task
    print("\nScheduling task...")
    scheduler.schedule()
    print("Task scheduled successfully!")

    # Print task details after scheduling
    print("\nTask details after scheduling:")
    print(f"Task ID: {task1.id}")
    print(f"Task Name: {task1.name}")
    print(f"Aggressive Duration: {task1.aggressive_duration}")
    print(f"Safe Duration: {task1.safe_duration}")
    print(f"Planned Duration: {task1.planned_duration}")
    print(f"Early Start: {task1.early_start}")
    print(f"Early Finish: {task1.early_finish}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
