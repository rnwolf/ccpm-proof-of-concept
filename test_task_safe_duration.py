import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler

# Test 1: Try creating a task with the parameters from the issue description (all named parameters)
try:
    print("Test 1: Creating task with all named parameters...")
    task1 = Task(
        id="T1.1",
        name="Task 1.1",
        aggressive_duration=15,
        safe_duration=30,
        dependencies=[],
        resources=["Red"],
    )
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task1.aggressive_duration}")
    print(f"Task safe_duration: {task1.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Try creating a task with positional parameters for id and name (like in simple_project.py)
try:
    print("\nTest 2: Creating task with positional parameters for id and name...")
    task2 = Task("T1.1", "Task 1.1", aggressive_duration=15, safe_duration=30, dependencies=[], resources=["Red"])
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task2.aggressive_duration}")
    print(f"Task safe_duration: {task2.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Try creating a task with all positional parameters
try:
    print("\nTest 3: Creating task with all positional parameters...")
    task3 = Task("T1.1", "Task 1.1", 15, 30, [], ["Red"])
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task3.aggressive_duration}")
    print(f"Task safe_duration: {task3.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Try creating a task with named parameters in a different order
try:
    print("\nTest 4: Creating task with named parameters in a different order...")
    task4 = Task(
        safe_duration=30,
        aggressive_duration=15,
        name="Task 1.1",
        id="T1.1",
        resources=["Red"],
        dependencies=[],
    )
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task4.aggressive_duration}")
    print(f"Task safe_duration: {task4.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Try creating a task with safe_duration as a keyword parameter but with dependencies as positional
try:
    print("\nTest 5: Creating task with safe_duration as a keyword parameter but with dependencies as positional...")
    task5 = Task("T1.1", "Task 1.1", 15, safe_duration=30, dependencies=[], resources=["Red"])
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task5.aggressive_duration}")
    print(f"Task safe_duration: {task5.safe_duration}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Try creating a task and adding it to a scheduler
try:
    print("\nTest 6: Creating task and adding it to a scheduler...")
    task6 = Task(
        id="T1.1",
        name="Task 1.1",
        aggressive_duration=15,
        safe_duration=30,
        dependencies=[],
        resources=["Red"],
    )
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task6.aggressive_duration}")
    print(f"Task safe_duration: {task6.safe_duration}")

    # Create a scheduler and add the task
    scheduler = CCPMScheduler()
    scheduler.add_task(task6)
    print("Task added to scheduler successfully!")

    # Check if the task's safe_duration is still correct
    task_from_scheduler = scheduler.tasks["T1.1"]
    print(f"Task from scheduler aggressive_duration: {task_from_scheduler.aggressive_duration}")
    print(f"Task from scheduler safe_duration: {task_from_scheduler.safe_duration}")

    # Try to run the scheduler
    print("Running scheduler...")
    scheduler.schedule()
    print("Scheduler ran successfully!")

    # Check if the task's safe_duration is still correct after scheduling
    task_after_scheduling = scheduler.tasks["T1.1"]
    print(f"Task after scheduling aggressive_duration: {task_after_scheduling.aggressive_duration}")
    print(f"Task after scheduling safe_duration: {task_after_scheduling.safe_duration}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Try creating a task with dependencies parameter before safe_duration parameter
try:
    print("\nTest 7: Creating task with dependencies parameter before safe_duration parameter...")
    task7 = Task(
        id="T1.1",
        name="Task 1.1",
        aggressive_duration=15,
        dependencies=[],
        safe_duration=30,
        resources=["Red"],
    )
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task7.aggressive_duration}")
    print(f"Task safe_duration: {task7.safe_duration}")
    print(f"Task dependencies: {task7.dependencies}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Try creating a task with dependencies parameter as a positional parameter
try:
    print("\nTest 8: Creating task with dependencies parameter as a positional parameter...")
    task8 = Task("T1.1", "Task 1.1", 15, [], 30, ["Red"])
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task8.aggressive_duration}")
    print(f"Task safe_duration: {task8.safe_duration}")
    print(f"Task dependencies: {task8.dependencies}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()

# Test 9: Try creating a task with dependencies parameter as a positional parameter and safe_duration as a keyword parameter
try:
    print("\nTest 9: Creating task with dependencies parameter as a positional parameter and safe_duration as a keyword parameter...")
    task9 = Task("T1.1", "Task 1.1", 15, [], safe_duration=30, resources=["Red"])
    print("Task created successfully!")
    print(f"Task aggressive_duration: {task9.aggressive_duration}")
    print(f"Task safe_duration: {task9.safe_duration}")
    print(f"Task dependencies: {task9.dependencies}")
except Exception as e:
    print(f"Error creating task: {e}")
    import traceback
    traceback.print_exc()
