"""
Example usage of the enhanced Task class demonstrating the new features
including validation, duration handling, color management, and progress calculation.
"""

from datetime import datetime, timedelta
from ccpm.domain.task import Task, TaskStatus, ChainType

# Current date for the examples
today = datetime(2025, 4, 10)


def print_section(title):
    """Helper to print section titles."""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50)


def print_task_info(task, label=None):
    """Helper to print task information."""
    if label:
        print(f"\n--- {label} ---")

    print(f"Task: {task.id} - {task.name}")
    print(f"Status: {task.status}")

    if task.get_start_date():
        print(f"Start Date: {task.get_start_date().strftime('%Y-%m-%d')}")

    if task.get_end_date():
        print(f"End Date: {task.get_end_date().strftime('%Y-%m-%d')}")

    if hasattr(task, "original_duration"):
        print(f"Original Duration: {task.original_duration} days")

    print(f"Planned Duration: {task.planned_duration} days")
    print(f"Remaining Duration: {task.remaining_duration} days")
    print(f"Progress: {task.get_progress_percentage():.1f}%")

    if task.chain_id:
        print(f"Chain: {task.chain_id} (Type: {task.chain_type})")

    visual = task.get_visual_properties()
    print(
        f"Visual: Color={visual['color']}, Pattern={visual['pattern']}, "
        f"Opacity={visual['opacity']:.1f}"
    )

    print(f"Resources: {', '.join(task.resources)}")
    print(f"Tags: {', '.join(task.tags)}")

    if task.notes:
        print(f"Notes: {len(task.notes)}")
        for i, note in enumerate(task.notes[-2:], 1):
            print(f"  {i}. {note['date'].strftime('%Y-%m-%d')}: {note['text']}")
        if len(task.notes) > 2:
            print(f"  ... and {len(task.notes) - 2} more")


def example_task_creation():
    """Example of creating tasks with validation."""
    print_section("1. Task Creation with Validation")

    print("Creating a basic task:")
    try:
        basic_task = Task(
            id="T1", name="Basic Task", aggressive_duration=10, safe_duration=15
        )
        print("✓ Task created successfully")
        print_task_info(basic_task)

        # Creating a task with default safe duration (1.5x aggressive)
        default_safe_task = Task(
            id="T2", name="Default Safe Duration", aggressive_duration=8
        )
        print("\n✓ Task created with default safe duration")
        print(f"Aggressive Duration: {default_safe_task.aggressive_duration} days")
        print(f"Safe Duration: {default_safe_task.safe_duration} days")
        print(
            f"Ratio: {default_safe_task.safe_duration / default_safe_task.aggressive_duration:.2f}x"
        )

        # Creating a task with resources as a string (automatically converted to list)
        resource_task = Task(
            id="T3",
            name="Resource Task",
            aggressive_duration=5,
            resources="Developer A",
        )
        print("\n✓ Task created with string resource (converted to list)")
        print(f"Resources: {resource_task.resources}")

        # Demonstrating validation errors
        print("\nDemonstrating validation errors:")

        try:
            invalid_task = Task(id=None, name="Invalid Task", aggressive_duration=10)
            print("This should not print - task creation should fail")
        except Exception as e:
            print(f"✓ Error caught: {e}")

        try:
            invalid_duration_task = Task(
                id="I1", name="Invalid Duration", aggressive_duration=-5
            )
            print("This should not print - task creation should fail")
        except Exception as e:
            print(f"✓ Error caught: {e}")

        try:
            invalid_safe_task = Task(
                id="I2",
                name="Invalid Safe Duration",
                aggressive_duration=10,
                safe_duration=5,
            )
            print("This should not print - task creation should fail")
        except Exception as e:
            print(f"✓ Error caught: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def example_task_scheduling_and_progress():
    """Example of task scheduling and progress tracking."""
    print_section("2. Task Scheduling and Progress Tracking")

    # Create a task
    task = Task(
        id="P1",
        name="Development Task",
        aggressive_duration=10,
        safe_duration=15,
        resources=["Developer A", "Developer B"],
        tags=["development", "phase1"],
    )

    # Set initial schedule
    start_date = datetime(2025, 4, 1)
    task.set_schedule(start_date)
    print_task_info(task, "Initial Schedule")

    # Start the task
    actual_start = datetime(2025, 4, 3)  # Started 2 days late
    task.start_task(actual_start)
    print_task_info(task, "After Starting")

    # Update progress at 30%
    update_date1 = actual_start + timedelta(days=3)  # 3 days after starting
    task.update_progress(7, update_date1)  # 3 days done, 7 remaining
    print_task_info(task, "Progress Update 1 (30%)")

    # Update progress at 60%
    update_date2 = actual_start + timedelta(days=6)  # 6 days after starting
    task.update_progress(4, update_date2)  # 6 days done, 4 remaining
    print_task_info(task, "Progress Update 2 (60%)")

    # Show progress history
    print("\n--- Progress History ---")
    for i, entry in enumerate(task.progress_history):
        date_str = entry["date"].strftime("%Y-%m-%d")
        if "status_change" in entry:
            print(
                f"{i+1}. {date_str}: Status changed to {entry['status']} ({entry['status_change']})"
            )
        else:
            print(
                f"{i+1}. {date_str}: Remaining={entry['remaining']} days, "
                f"Progress={entry.get('progress_percentage', 0):.1f}%"
            )

    # Complete the task
    completion_date = actual_start + timedelta(
        days=9
    )  # Finished in 9 days (faster than planned)
    task.complete_task(completion_date)
    print_task_info(task, "After Completion")

    # Check if task was delayed
    if task.is_delayed():
        print("\nThis task was delayed compared to the original schedule")
    else:
        print("\nThis task was completed on time or early")


def example_chain_and_colors():
    """Example of working with chain types and visual properties."""
    print_section("3. Chain Types and Visual Properties")

    # Create three tasks: critical, feeding, and regular
    critical_task = Task(id="C1", name="Critical Chain Task", aggressive_duration=5)
    feeding_task = Task(id="F1", name="Feeding Chain Task", aggressive_duration=7)
    regular_task = Task(id="R1", name="Regular Task", aggressive_duration=3)

    # Set chain types
    critical_task.chain_id = "critical_chain_1"
    critical_task.chain_type = "critical"

    feeding_task.chain_id = "feeding_chain_1"
    feeding_task.chain_type = "feeding"

    # Display default visual properties
    print("Default Visual Properties based on Chain Type:")
    print(f"Critical Task Color: {critical_task.color}")
    print(f"Feeding Task Color: {feeding_task.color}")
    print(f"Regular Task Color: {regular_task.color}")

    # Start tasks to see the pattern changes
    now = datetime.now()
    critical_task.start_task(now)
    feeding_task.start_task(now)

    print("\nPatterns after starting tasks:")
    print(f"Critical Task Pattern: {critical_task.pattern}")
    print(f"Feeding Task Pattern: {feeding_task.pattern}")

    # Customize visual properties
    regular_task.set_visual_properties(
        color="purple", border_color="blue", pattern="+++", opacity=0.9
    )

    print("\nCustomized Visual Properties:")
    visual = regular_task.get_visual_properties()
    print(f"Color: {visual['color']}")
    print(f"Border Color: {visual['border_color']}")
    print(f"Pattern: {visual['pattern']}")
    print(f"Opacity: {visual['opacity']}")

    # Reset properties
    regular_task.reset_visual_properties()
    print(f"\nAfter Reset - Color: {regular_task.color}")


def example_task_state_management():
    """Example of managing task state: pausing, resuming, and cancelling."""
    print_section("4. Task State Management")

    # Create a task
    task = Task(id="S1", name="State Management Demo", aggressive_duration=20)
    task.set_schedule(datetime(2025, 4, 1))

    # Start the task
    start_date = datetime(2025, 4, 5)
    task.start_task(start_date)
    print_task_info(task, "After Starting")

    # Do some progress
    update_date = start_date + timedelta(days=4)
    task.update_progress(16, update_date)  # 4 days done, 16 remaining
    print_task_info(task, "After Initial Progress")

    # Pause the task
    pause_date = start_date + timedelta(days=6)
    task.pause_task(pause_date, "Waiting for design approval")
    print_task_info(task, "After Pausing")

    # Resume the task
    resume_date = pause_date + timedelta(days=3)
    task.resume_task(resume_date)
    print_task_info(task, "After Resuming")

    # More progress
    update_date2 = resume_date + timedelta(days=5)
    task.update_progress(10, update_date2)  # 10 days done, 10 remaining
    print_task_info(task, "After More Progress")

    # Show all status changes in history
    print("\n--- Status Change History ---")
    for entry in task.progress_history:
        if "status_change" in entry:
            date_str = entry["date"].strftime("%Y-%m-%d")
            status = entry["status"]
            change = entry["status_change"]
            note = entry.get("note", "")
            print(f"{date_str}: {status} ({change}) {note}")


def example_full_kitting_and_notes():
    """Example of full kitting and notes functionality."""
    print_section("5. Full Kitting and Notes Management")

    # Create a task
    task = Task(id="K1", name="Full Kitting Demo", aggressive_duration=15)

    # Add some planning notes
    task.add_note("Initial requirements gathered", datetime(2025, 3, 15))
    task.add_note("Resource estimation completed", datetime(2025, 3, 20))

    # Mark as full kitted
    kitting_date = datetime(2025, 3, 25)
    task.set_full_kitted(True, kitting_date, "All materials and documentation ready")

    # Start the task
    start_date = datetime(2025, 4, 1)
    task.set_schedule(start_date)
    task.start_task(start_date)

    # Add progress notes
    task.add_note("Phase 1 completed successfully", datetime(2025, 4, 5))
    task.add_note("Found integration issue - needs rework", datetime(2025, 4, 8))

    # Display task info with notes
    print_task_info(task, "Task with Notes and Full Kitting")

    # Display all notes chronologically
    print("\n--- All Notes Chronologically ---")
    for i, note in enumerate(sorted(task.notes, key=lambda x: x["date"]), 1):
        date_str = note["date"].strftime("%Y-%m-%d")
        print(f"{i}. {date_str}: {note['text']}")

    # Filter notes by date range
    start_filter = datetime(2025, 4, 1)
    end_filter = datetime(2025, 4, 10)
    filtered_notes = task.get_notes(start_filter, end_filter)

    print(
        f"\n--- Notes from {start_filter.strftime('%Y-%m-%d')} to {end_filter.strftime('%Y-%m-%d')} ---"
    )
    for i, note in enumerate(filtered_notes, 1):
        date_str = note["date"].strftime("%Y-%m-%d")
        print(f"{i}. {date_str}: {note['text']}")


def example_task_serialization():
    """Example of serializing and deserializing tasks."""
    print_section("6. Task Serialization and Copying")

    # Create a complex task with various properties set
    task = Task(
        id="SER1",
        name="Serialization Demo",
        aggressive_duration=12,
        safe_duration=18,
        resources=["Developer A", "Tester B"],
        tags=["critical", "backend"],
        description="A task to demonstrate serialization",
    )

    # Set chain info
    task.chain_id = "critical_1"
    task.chain_type = "critical"

    # Set schedule
    start_date = datetime(2025, 4, 1)
    task.set_schedule(start_date)

    # Start and make progress
    task.start_task(datetime(2025, 4, 5))
    task.update_progress(8, datetime(2025, 4, 9))

    # Add notes
    task.add_note("Important implementation details")

    # Set visual properties
    task.set_visual_properties(color="darkred", opacity=0.85)

    # Convert to dictionary
    task_dict = task.to_dict()

    print("Task serialized to dictionary with keys:")
    for key in task_dict.keys():
        print(f"- {key}")

    # Create a new task from the dictionary
    new_task = Task.from_dict(task_dict)
    print_task_info(new_task, "Task created from dictionary")

    # Create a copy
    task_copy = task.copy()
    print_task_info(task_copy, "Task created using copy()")

    # Modify the copy to show it's independent
    task_copy.name = "Modified Copy"
    task_copy.update_progress(4, datetime(2025, 4, 15))

    print("\n--- Original vs. Modified Copy ---")
    print(
        f"Original name: {task.name}, Progress: {task.get_progress_percentage():.1f}%"
    )
    print(
        f"Copy name: {task_copy.name}, Progress: {task_copy.get_progress_percentage():.1f}%"
    )


def main():
    """Run all examples."""
    print("ENHANCED TASK CLASS DEMONSTRATION")
    print("=================================")
    print("This script demonstrates the enhanced Task class with improved")
    print("validation, duration handling, color support, and progress tracking.")

    example_task_creation()
    example_task_scheduling_and_progress()
    example_chain_and_colors()
    example_task_state_management()
    example_full_kitting_and_notes()
    example_task_serialization()


if __name__ == "__main__":
    main()
