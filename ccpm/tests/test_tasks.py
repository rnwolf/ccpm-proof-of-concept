import unittest
from datetime import datetime, timedelta
from ccpm.domain.task import Task, TaskStatus, ChainType, TaskError


class TaskTestCase(unittest.TestCase):
    """Test cases for the enhanced Task class."""

    def setUp(self):
        """Set up test cases with a sample task."""
        self.start_date = datetime(2025, 4, 1)
        self.task = Task(
            id="T1",
            name="Test Task",
            aggressive_duration=10,
            safe_duration=15,
            dependencies=["T0"],
            resources=["Developer A"],
            tags=["high_priority", "frontend"],
        )
        self.task.set_schedule(self.start_date)

    def test_initialization_validation(self):
        """Test validation during task initialization."""
        # Invalid ID
        with self.assertRaises(TaskError):
            Task(id=None, name="Invalid Task", aggressive_duration=10)

        # Invalid name
        with self.assertRaises(TaskError):
            Task(id="I1", name="", aggressive_duration=10)

        # Invalid duration
        with self.assertRaises(TaskError):
            Task(id="I2", name="Invalid Duration", aggressive_duration=-5)

        # Safe duration less than aggressive
        with self.assertRaises(TaskError):
            Task(
                id="I3",
                name="Invalid Safe Duration",
                aggressive_duration=10,
                safe_duration=5,
            )

        # Default safe duration (1.5x aggressive)
        task = Task(id="D1", name="Default Safe Duration", aggressive_duration=10)
        self.assertEqual(task.safe_duration, 15)

        # Resource as string should be converted to list
        task = Task(
            id="D2",
            name="String Resource",
            aggressive_duration=10,
            resources="Developer A",
        )
        self.assertEqual(task.resources, ["Developer A"])

    def test_status_handling(self):
        """Test status transitions and validation."""
        # Default status
        self.assertEqual(self.task.status, "planned")

        # Valid status change
        self.task.status = "in_progress"
        self.assertEqual(self.task.status, "in_progress")

        # Invalid status change
        with self.assertRaises(TaskError):
            self.task.status = "invalid_status"

        # Task methods that change status
        task = Task(id="S1", name="Status Task", aggressive_duration=5)
        start_date = datetime(2025, 4, 10)

        # Start task
        task.start_task(start_date)
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(task.actual_start_date, start_date)

        # Cannot start an already started task
        with self.assertRaises(TaskError):
            task.start_task(start_date + timedelta(days=1))

        # Complete task
        completion_date = start_date + timedelta(days=4)
        task.complete_task(completion_date)
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.actual_end_date, completion_date)
        self.assertEqual(task.remaining_duration, 0)

        # Cannot update a completed task
        with self.assertRaises(TaskError):
            task.update_progress(2, datetime.now())

    def test_duration_handling(self):
        """Test duration handling and updates."""
        # Check initial values
        self.assertEqual(self.task.aggressive_duration, 10)
        self.assertEqual(self.task.safe_duration, 15)
        self.assertEqual(self.task.planned_duration, 10)  # Default to aggressive
        self.assertEqual(self.task.remaining_duration, 10)

        # Start the task
        start_date = datetime(2025, 4, 15)
        self.task.start_task(start_date)
        self.assertEqual(self.task.remaining_duration, 10)
        self.assertTrue(hasattr(self.task, "original_duration"))
        self.assertEqual(self.task.original_duration, 10)

        # Update progress
        update_date = start_date + timedelta(days=2)
        self.task.update_progress(8, update_date)
        self.assertEqual(self.task.remaining_duration, 8)
        self.assertEqual(len(self.task.progress_history), 2)  # start + update

        # Verify progress calculation
        self.assertEqual(
            self.task.get_progress_percentage(), 20
        )  # 2 of 10 days complete

        # Update to completion
        completion_date = start_date + timedelta(days=9)
        self.task.update_progress(0, completion_date)
        self.assertEqual(self.task.status, "completed")
        self.assertEqual(self.task.remaining_duration, 0)
        self.assertEqual(
            len(self.task.progress_history), 3
        )  # start + update + complete

    def test_chain_membership(self):
        """Test chain membership properties."""
        # Default chain type
        self.assertEqual(self.task.chain_type, "none")
        self.assertFalse(self.task.is_critical())
        self.assertFalse(self.task.is_feeding_chain())

        # Set chain ID
        self.task.chain_id = "critical"
        self.assertEqual(self.task.chain_id, "critical")

        # Set chain type
        self.task.chain_type = "critical"
        self.assertEqual(self.task.chain_type, "critical")
        self.assertTrue(self.task.is_critical())
        self.assertFalse(self.task.is_feeding_chain())

        # Invalid chain type
        with self.assertRaises(TaskError):
            self.task.chain_type = "invalid_type"

        # Set to feeding chain
        self.task.chain_type = "feeding"
        self.assertEqual(self.task.chain_type, "feeding")
        self.assertFalse(self.task.is_critical())
        self.assertTrue(self.task.is_feeding_chain())

    def test_visual_properties(self):
        """Test visual properties handling."""
        # Default properties based on chain type and status
        self.assertEqual(self.task.color, "blue")  # Default for "none" chain type
        self.assertEqual(self.task.border_color, "black")
        self.assertEqual(self.task.pattern, "")  # No pattern for planned tasks
        self.assertAlmostEqual(self.task.opacity, 0.6)  # Default for planned tasks

        # Set as critical chain task
        self.task.chain_type = "critical"
        self.assertEqual(self.task.color, "red")  # Critical chain color

        # Set as feeding chain task
        self.task.chain_type = "feeding"
        self.assertEqual(self.task.color, "orange")  # Feeding chain color

        # Start task and check pattern
        self.task.start_task(datetime.now())
        self.assertEqual(self.task.pattern, "///")  # Pattern for in-progress tasks
        self.assertAlmostEqual(self.task.opacity, 0.8)  # Default for in-progress tasks

        # Explicitly set properties
        self.task.set_visual_properties(
            color="purple", border_color="green", pattern="xxx", opacity=0.75
        )
        self.assertEqual(self.task.color, "purple")
        self.assertEqual(self.task.border_color, "green")
        self.assertEqual(self.task.pattern, "xxx")
        self.assertAlmostEqual(self.task.opacity, 0.75)

        # Get all visual properties
        properties = self.task.get_visual_properties()
        self.assertEqual(properties["color"], "purple")
        self.assertEqual(properties["border_color"], "green")
        self.assertEqual(properties["pattern"], "xxx")
        self.assertAlmostEqual(properties["opacity"], 0.75)
        self.assertFalse(properties["is_critical"])
        self.assertTrue(properties["is_feeding"])

        # Reset properties
        self.task.reset_visual_properties()
        self.assertEqual(self.task.color, "orange")  # Back to feeding chain color

    def test_schedule_management(self):
        """Test schedule management functions."""
        # Initial schedule
        self.assertEqual(self.task.start_date, self.start_date)
        self.assertEqual(self.task.end_date, self.start_date + timedelta(days=10))

        # Update schedule
        new_start = self.start_date + timedelta(days=5)
        self.task.update_schedule(new_start)
        self.assertEqual(self.task.new_start_date, new_start)
        self.assertEqual(self.task.new_end_date, new_start + timedelta(days=10))

        # Update duration only
        self.task.update_schedule(duration=15)
        self.assertEqual(self.task.planned_duration, 15)
        self.assertEqual(self.task.new_end_date, new_start + timedelta(days=15))

        # Check effective dates
        self.assertEqual(self.task.get_start_date(), new_start)
        self.assertEqual(self.task.get_end_date(), new_start + timedelta(days=15))

    def test_progress_tracking(self):
        """Test progress tracking functions."""
        # Start task
        start_date = datetime(2025, 4, 10)
        self.task.start_task(start_date)

        # Update progress three times over 6 days
        updates = [
            (start_date + timedelta(days=2), 8),  # Day 2: 2 days complete, 8 remaining
            (start_date + timedelta(days=4), 5),  # Day 4: 5 days complete, 5 remaining
            (start_date + timedelta(days=6), 2),  # Day 6: 8 days complete, 2 remaining
        ]

        for update_date, remaining in updates:
            self.task.update_progress(remaining, update_date)

        # Check progress history
        self.assertEqual(len(self.task.progress_history), 4)  # start + 3 updates

        # Check current progress
        self.assertEqual(self.task.remaining_duration, 2)
        self.assertEqual(self.task.get_progress_percentage(), 80)  # 8 of 10 complete

        # Check elapsed duration
        self.assertEqual(self.task.get_elapsed_duration(), 6)  # 6 days since start

        # Complete the task
        final_date = start_date + timedelta(days=9)
        self.task.complete_task(final_date)

        # Check final state
        self.assertEqual(self.task.status, "completed")
        self.assertEqual(self.task.actual_end_date, final_date)
        self.assertEqual(self.task.get_progress_percentage(), 100)

        # Actual duration should be 9 days (end - start)
        self.assertEqual(self.task.actual_duration, 9)

    def test_pause_and_resume(self):
        """Test pausing and resuming tasks."""
        # Start task
        start_date = datetime(2025, 4, 10)
        self.task.start_task(start_date)

        # Do some progress
        update_date = start_date + timedelta(days=3)
        self.task.update_progress(7, update_date)  # 3 days done, 7 remaining

        # Pause the task
        pause_date = start_date + timedelta(days=5)
        self.task.pause_task(pause_date, "Waiting for external dependency")
        self.assertEqual(self.task.status, "on_hold")

        # Cannot update a paused task
        with self.assertRaises(TaskError):
            self.task.update_progress(6, pause_date + timedelta(days=1))

        # Resume the task
        resume_date = pause_date + timedelta(days=3)
        self.task.resume_task(resume_date)
        self.assertEqual(self.task.status, "in_progress")

        # Can update again after resuming
        update_date = resume_date + timedelta(days=2)
        self.task.update_progress(5, update_date)  # Now 5 days done, 5 remaining

        # Progress history should include all events
        self.assertEqual(
            len(self.task.progress_history), 5
        )  # start, update, pause, resume, update

    def test_full_kitting(self):
        """Test full kitting functionality."""
        # Default is not full kitted
        self.assertFalse(self.task.is_full_kitted)
        self.assertIsNone(self.task.full_kitted_date)

        # Mark as full kitted
        kitting_date = datetime(2025, 3, 25)  # Before start date
        self.task.set_full_kitted(True, kitting_date, "All materials received")
        self.assertTrue(self.task.is_full_kitted)
        self.assertEqual(self.task.full_kitted_date, kitting_date)

        # Should have a note
        self.assertEqual(len(self.task.notes), 1)
        self.assertEqual(self.task.notes[0]["text"], "All materials received")

        # Mark as not full kitted
        self.task.set_full_kitted(False, datetime.now(), "Missing materials")
        self.assertFalse(self.task.is_full_kitted)
        # Date shouldn't change when unmarking
        self.assertEqual(self.task.full_kitted_date, kitting_date)

        # Should have another note
        self.assertEqual(len(self.task.notes), 2)

    def test_tags_management(self):
        """Test tags management functions."""
        # Initial tags
        self.assertEqual(self.task.tags, ["high_priority", "frontend"])

        # Add a tag
        self.task.add_tag("critical")
        self.assertEqual(self.task.tags, ["high_priority", "frontend", "critical"])

        # Add duplicate tag (should not add)
        self.task.add_tag("critical")
        self.assertEqual(self.task.tags, ["high_priority", "frontend", "critical"])

        # Check tag existence
        self.assertTrue(self.task.has_tag("frontend"))
        self.assertFalse(self.task.has_tag("backend"))

        # Remove tag
        result = self.task.remove_tag("frontend")
        self.assertTrue(result)  # Should return True when tag was found
        self.assertEqual(self.task.tags, ["high_priority", "critical"])

        # Remove non-existent tag
        result = self.task.remove_tag("backend")
        self.assertFalse(result)  # Should return False when tag wasn't found

        # Filter by tags - all tags must match
        self.assertTrue(self.task.filter_by_tags(["high_priority"]))
        self.assertTrue(self.task.filter_by_tags(["high_priority", "critical"]))
        self.assertFalse(self.task.filter_by_tags(["high_priority", "backend"]))

        # Filter by tags - any tag can match
        self.assertTrue(
            self.task.filter_by_tags(["backend", "critical"], match_all=False)
        )
        self.assertFalse(
            self.task.filter_by_tags(["backend", "frontend"], match_all=False)
        )

    def test_notes_management(self):
        """Test notes management functions."""
        # Add notes
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        self.task.add_note("Note from yesterday", yesterday)
        self.task.add_note("Note from today", today)
        self.task.add_note("Note from tomorrow", tomorrow)

        # Get all notes
        all_notes = self.task.get_notes()
        self.assertEqual(len(all_notes), 3)

        # Filter by date range - only today
        today_notes = self.task.get_notes(today, today)
        self.assertEqual(len(today_notes), 1)
        self.assertEqual(today_notes[0]["text"], "Note from today")

        # Filter by date range - today and tomorrow
        future_notes = self.task.get_notes(today)
        self.assertEqual(len(future_notes), 2)

        # Filter by date range - yesterday and today
        past_notes = self.task.get_notes(end_date=today)
        self.assertEqual(len(past_notes), 2)

    def test_serialization(self):
        """Test serialization to and from dictionary."""
        # Start a task and do some progress
        start_date = datetime(2025, 4, 15)
        self.task.start_task(start_date)
        self.task.update_progress(5, start_date + timedelta(days=5))
        self.task.add_note("Halfway done")

        # Convert to dictionary
        task_dict = self.task.to_dict()

        # Verify basic properties are preserved
        self.assertEqual(task_dict["id"], "T1")
        self.assertEqual(task_dict["name"], "Test Task")
        self.assertEqual(task_dict["aggressive_duration"], 10)
        self.assertEqual(task_dict["safe_duration"], 15)
        self.assertEqual(task_dict["status"], "in_progress")
        self.assertEqual(task_dict["remaining_duration"], 5)

        # Create a new task from dictionary
        new_task = Task.from_dict(task_dict)

        # Verify properties match
        self.assertEqual(new_task.id, self.task.id)
        self.assertEqual(new_task.name, self.task.name)
        self.assertEqual(new_task.aggressive_duration, self.task.aggressive_duration)
        self.assertEqual(new_task.safe_duration, self.task.safe_duration)
        self.assertEqual(new_task.status, self.task.status)
        self.assertEqual(new_task.remaining_duration, self.task.remaining_duration)
        self.assertEqual(
            new_task.get_progress_percentage(), self.task.get_progress_percentage()
        )

        # Times should match
        self.assertEqual(new_task.actual_start_date, self.task.actual_start_date)

        # Copy task
        task_copy = self.task.copy()
        self.assertEqual(task_copy.id, self.task.id)
        self.assertEqual(task_copy.name, self.task.name)

        # Modify copy
        task_copy.name = "Modified Copy"
        # Original should be unchanged
        self.assertEqual(self.task.name, "Test Task")

    def test_delayed_task_detection(self):
        """Test detection of delayed tasks."""
        # Planned task is not delayed
        self.assertFalse(self.task.is_delayed())

        # Task started on time is not delayed
        start_date = self.start_date
        self.task.start_task(start_date)
        self.assertFalse(self.task.is_delayed())

        # Task that finishes on time is not delayed
        task2 = Task(id="D1", name="On Time Task", aggressive_duration=5)
        task2.set_schedule(self.start_date)
        actual_start = self.start_date
        task2.start_task(actual_start)
        actual_end = actual_start + timedelta(days=5)
        task2.complete_task(actual_end)
        self.assertFalse(task2.is_delayed())

        # Task that starts late is delayed
        task3 = Task(id="D2", name="Late Start Task", aggressive_duration=5)
        task3.set_schedule(self.start_date)
        late_start = self.start_date + timedelta(days=2)
        task3.start_task(late_start)
        self.assertTrue(task3.is_delayed())

        # Task that finishes late is delayed
        task4 = Task(id="D3", name="Late Finish Task", aggressive_duration=5)
        task4.set_schedule(self.start_date)
        task4.start_task(self.start_date)
        late_end = self.start_date + timedelta(days=7)
        task4.complete_task(late_end)
        self.assertTrue(task4.is_delayed())


if __name__ == "__main__":
    unittest.main()
