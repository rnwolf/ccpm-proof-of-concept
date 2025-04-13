from datetime import datetime, timedelta


class Task:
    def __init__(
        self,
        id,
        name,
        aggressive_duration,
        safe_duration=None,
        dependencies=None,
        resources=None,
        tags=None,
    ):
        # Core identification
        self.id = id
        self.name = name
        self.tags = tags or []  # Store tags as a list of strings

        # Duration estimates
        self.aggressive_duration = aggressive_duration  # Optimistic estimate
        self.safe_duration = safe_duration or (
            aggressive_duration * 1.5
        )  # Safe estimate
        self.planned_duration = aggressive_duration  # Duration used for scheduling

        # References
        self.dependencies = dependencies if dependencies else []
        self.resources = resources if resources else []

        # Scheduling attributes
        self.early_start = None
        self.early_finish = None
        self.late_start = None
        self.late_finish = None
        self.slack = None
        self.is_critical = False

        # Status tracking
        self.status = "planned"  # "planned", "in_progress", "completed"
        self.actual_start_date = None
        self.actual_end_date = None
        self.remaining_duration = aggressive_duration

        # Chain membership (set by scheduler)
        self.chain_id = None

        # Progress tracking
        self.progress_history = []

        # Full kitting
        self.is_full_kitted = False  # Whether task is full kitted
        self.full_kitted_date = None  # When the task became full kitted

        # Notes functionality
        self.notes = []  # List of timestamped notes

    def start_task(self, start_date):
        """Mark task as started on the given date"""
        if self.status != "planned":
            raise ValueError(
                f"Cannot start task {self.id} as it is already {self.status}"
            )

        self.status = "in_progress"
        self.actual_start_date = start_date
        self.remaining_duration = self.planned_duration
        return self

    def update_progress(self, remaining_duration, status_date):
        """Update task progress with remaining duration"""
        if self.status != "in_progress":
            raise ValueError(
                f"Cannot update progress for task {self.id} as it is {self.status}"
            )

        # Store the previous remaining duration
        previous_remaining = self.remaining_duration

        # Update the remaining duration
        self.remaining_duration = remaining_duration

        # Calculate progress metrics
        if hasattr(self, "original_duration"):
            completed_work = self.original_duration - remaining_duration
            total_duration = self.original_duration
        else:
            completed_work = self.planned_duration - remaining_duration
            total_duration = self.planned_duration

        progress_percentage = (
            (completed_work / total_duration) * 100 if total_duration > 0 else 0
        )

        # Add to history
        self.progress_history.append(
            {
                "date": status_date,
                "remaining": remaining_duration,
                "previous_remaining": previous_remaining,
                "progress_percentage": progress_percentage,
            }
        )

        # Check if task is now complete
        if remaining_duration <= 0:
            self.complete_task(status_date)

        return self

    def complete_task(self, completion_date):
        """Mark task as completed on the given date"""
        self.status = "completed"
        self.actual_end_date = completion_date
        self.remaining_duration = 0
        return self

    def get_start_date(self):
        """Get the effective start date based on status"""
        if self.status in ["in_progress", "completed"] and self.actual_start_date:
            return self.actual_start_date
        elif hasattr(self, "new_start_date"):
            return self.new_start_date
        else:
            return self.start_date if hasattr(self, "start_date") else None

    def get_end_date(self):
        """Get the effective end date based on status"""
        if self.status == "completed" and self.actual_end_date:
            return self.actual_end_date

        if self.status == "in_progress":
            if hasattr(self, "new_end_date"):
                return self.new_end_date

            # Calculate from remaining duration
            if self.actual_start_date and self.remaining_duration is not None:
                latest_status = (
                    self.progress_history[-1]["date"]
                    if self.progress_history
                    else self.actual_start_date
                )
                return latest_status + timedelta(days=self.remaining_duration)

        # For planned tasks
        if hasattr(self, "new_end_date"):
            return self.new_end_date
        elif hasattr(self, "end_date"):
            return self.end_date

        return None

    def add_tag(self, tag):
        """Add a tag to this task if it doesn't already exist"""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove a tag from this task if it exists"""
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def has_tag(self, tag):
        """Check if this task has a specific tag"""
        return tag in self.tags

    def filter_by_tags(self, tags):
        """
        Check if this task has all the specified tags

        Args:
            tags: List of tags to check for

        Returns:
            bool: True if task has all the specified tags
        """
        return all(tag in self.tags for tag in tags)

    def set_full_kitted(self, is_kitted, date=None, note=None):
        """
        Mark the task as full kitted or not full kitted.

        Args:
            is_kitted: Boolean indicating if the task is full kitted
            date: Date when the status changed (defaults to now)
            note: Optional note about the status change

        Returns:
            self: For method chaining
        """
        # Set default date if not provided
        if date is None:
            date = datetime.now()

        # Update state
        previous_state = self.is_full_kitted
        self.is_full_kitted = is_kitted

        # Only update the date if the task is becoming full kitted
        if is_kitted and not previous_state:
            self.full_kitted_date = date

        # Add a note if provided
        if note:
            self.add_note(note, date)

        return self

    def add_note(self, text, date=None):
        """
        Add a timestamped note to the task.

        Args:
            text: Note text
            date: Date of the note (defaults to now)

        Returns:
            dict: The added note
        """
        if date is None:
            date = datetime.now()

        note = {"date": date, "text": text}

        self.notes.append(note)
        return note

    def get_notes(self, start_date=None, end_date=None):
        """
        Get notes, optionally filtered by date range.

        Args:
            start_date: Filter notes on or after this date
            end_date: Filter notes on or before this date

        Returns:
            list: Filtered notes
        """
        if start_date is None and end_date is None:
            return self.notes.copy()

        filtered_notes = []

        for note in self.notes:
            include = True

            if start_date and note["date"] < start_date:
                include = False

            if end_date and note["date"] > end_date:
                include = False

            if include:
                filtered_notes.append(note)

        return filtered_notes
