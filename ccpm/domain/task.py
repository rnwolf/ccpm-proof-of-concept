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
    ):
        # Core identification
        self.id = id
        self.name = name

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
