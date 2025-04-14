from datetime import datetime, timedelta
from enum import Enum, auto
from typing import List, Dict, Union, Optional, Any


class TaskStatus(Enum):
    """
    Enum representing the possible status values of a task.
    """

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class ChainType(Enum):
    """
    Enum representing the type of chain a task belongs to.
    """

    NONE = "none"
    CRITICAL = "critical"
    FEEDING = "feeding"


class TaskError(Exception):
    """Exception raised for errors in the Task class."""

    pass


class Task:
    """
    Represents a task in a Critical Chain Project Management (CCPM) system.

    A task has properties including duration estimates, dependencies,
    resources required, scheduling information, and progress tracking.
    """

    def __init__(
        self,
        id: str,
        name: str,
        aggressive_duration: float,
        safe_duration: Optional[float] = None,
        dependencies: Optional[List] = None,
        resources: Optional[Union[List[str], str]] = None,
        tags: Optional[List[str]] = None,
        description: str = "",
    ):
        """
        Initialize a new Task.

        Args:
            id: Unique identifier for the task
            name: Name/description of the task
            aggressive_duration: Aggressive duration estimate (in days)
            safe_duration: Safe duration estimate (in days), defaults to 150% of aggressive
            dependencies: List of task IDs that this task depends on
            resources: List of resources required for this task, or a single resource as string
            tags: List of tags to categorize the task
            description: Detailed description of the task

        Raises:
            TaskError: If any input validation fails
        """
        # Validate inputs
        if id is None:
            raise TaskError("Task ID cannot be None")
        self.id = id

        if not name or not isinstance(name, str):
            raise TaskError("Task name must be a non-empty string")
        self.name = name

        if (
            not isinstance(aggressive_duration, (int, float))
            or aggressive_duration <= 0
        ):
            raise TaskError("Aggressive duration must be a positive number")
        self.aggressive_duration = float(aggressive_duration)

        # Set default safe duration if not provided
        if safe_duration is None:
            self.safe_duration = self.aggressive_duration * 1.5
        elif (
            not isinstance(safe_duration, (int, float))
            or safe_duration < aggressive_duration
        ):
            raise TaskError(
                "Safe duration must be a number greater than or equal to aggressive duration"
            )
        else:
            self.safe_duration = float(safe_duration)

        # Initialize dependencies
        self.dependencies = []
        if dependencies:
            if not isinstance(dependencies, list):
                raise TaskError("Dependencies must be a list")
            self.dependencies = list(dependencies)

        # Initialize resources
        if isinstance(resources, str):
            self.resources = [resources]  # Convert single string to list
        elif isinstance(resources, list):
            self.resources = resources
        else:
            self.resources = []

        # Initialize tags
        self.tags = list(tags) if tags else []

        # Additional metadata
        self.description = description

        # Schedule attributes
        self.planned_duration = (
            self.aggressive_duration
        )  # Default to aggressive duration
        self.early_start = None
        self.early_finish = None
        self.late_start = None
        self.late_finish = None
        self.slack = None

        # Execution attributes
        self._status = TaskStatus.PLANNED
        self.start_date = None  # Original planned start
        self.end_date = None  # Original planned end
        self.new_start_date = None  # Updated planned start
        self.new_end_date = None  # Updated planned end
        self.actual_start_date = None
        self.actual_end_date = None

        # Progress tracking
        self.remaining_duration = self.planned_duration
        self.progress_history = []

        # Visual attributes for rendering
        self._color = None
        self._border_color = None
        self._pattern = None
        self._opacity = None

        # Chain membership
        self._chain_id = None
        self._chain_type = ChainType.NONE

        # Full kitting
        self.is_full_kitted = False
        self.full_kitted_date = None

        # Notes
        self.notes = []

    @property
    def status(self) -> str:
        """Get the current status of the task."""
        return self._status.value

    @status.setter
    def status(self, value: str):
        """Set the status of the task."""
        try:
            self._status = TaskStatus(value)
        except ValueError:
            valid_statuses = [s.value for s in TaskStatus]
            raise TaskError(f"Invalid status: {value}. Must be one of {valid_statuses}")

    @property
    def chain_id(self) -> str:
        """Get the chain ID that this task belongs to."""
        return self._chain_id

    @chain_id.setter
    def chain_id(self, value):
        """Set the chain ID that this task belongs to."""
        self._chain_id = value

    @property
    def chain_type(self) -> str:
        """Get the type of chain this task belongs to."""
        return self._chain_type.value

    @chain_type.setter
    def chain_type(self, value):
        """Set the type of chain this task belongs to."""
        if isinstance(value, str):
            try:
                self._chain_type = ChainType(value)
            except ValueError:
                valid_types = [t.value for t in ChainType]
                raise TaskError(
                    f"Invalid chain type: {value}. Must be one of {valid_types}"
                )
        elif isinstance(value, ChainType):
            self._chain_type = value
        else:
            raise TaskError(
                f"Chain type must be a string or ChainType enum, got {type(value)}"
            )

    @property
    def color(self) -> str:
        """Get the display color for the task."""
        # If no color is explicitly set, determine based on chain type
        if self._color is None:
            if self._chain_type == ChainType.CRITICAL:
                return "red"
            elif self._chain_type == ChainType.FEEDING:
                return "orange"
            else:
                return "blue"  # Default color
        return self._color

    @color.setter
    def color(self, value: str):
        """Set the display color for the task."""
        self._color = value

    @property
    def border_color(self) -> str:
        """Get the border color for the task."""
        return self._border_color or "black"  # Default border color

    @border_color.setter
    def border_color(self, value: str):
        """Set the border color for the task."""
        self._border_color = value

    @property
    def pattern(self) -> str:
        """Get the pattern for the task."""
        # Default pattern based on status
        if self._pattern is None:
            if self._status == TaskStatus.IN_PROGRESS:
                return "///"  # Diagonal hatch for in-progress tasks
            elif self._status == TaskStatus.COMPLETED:
                return ""  # No pattern for completed tasks
            else:
                return ""  # No pattern for planned tasks
        return self._pattern

    @pattern.setter
    def pattern(self, value: str):
        """Set the pattern for the task."""
        self._pattern = value

    @property
    def opacity(self) -> float:
        """Get the opacity for the task."""
        # Default opacity based on status
        if self._opacity is None:
            if self._status == TaskStatus.COMPLETED:
                return 1.0  # Full opacity for completed tasks
            elif self._status == TaskStatus.IN_PROGRESS:
                return 0.8  # Slightly transparent for in-progress tasks
            else:
                return 0.6  # More transparent for planned tasks
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        """Set the opacity for the task."""
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            raise TaskError("Opacity must be a number between 0 and 1")
        self._opacity = float(value)

    def start_task(self, start_date: datetime) -> "Task":
        """
        Mark task as started on the given date.

        Args:
            start_date: The date the task was started

        Returns:
            self: For method chaining

        Raises:
            TaskError: If task is already started or completed
        """
        if self._status != TaskStatus.PLANNED and self._status != TaskStatus.ON_HOLD:
            raise TaskError(
                f"Cannot start task {self.id} as it is already {self._status.value}"
            )

        if not isinstance(start_date, datetime):
            raise TaskError("Start date must be a datetime object")

        self.status = "in_progress"
        self.actual_start_date = start_date
        self.remaining_duration = self.planned_duration

        # Also update the new_start_date to match actual
        self.new_start_date = start_date

        # Store original duration for later calculations
        if not hasattr(self, "original_duration"):
            self.original_duration = self.planned_duration

        # Add to progress history
        self._add_to_progress_history(
            status_date=start_date,
            remaining=self.remaining_duration,
            status_change="started",
        )

        return self

    def update_progress(
        self,
        remaining_duration: float,
        status_date: datetime,
        completed_percentage: float = None,
    ) -> "Task":
        """
        Update task progress with remaining duration.

        Args:
            remaining_duration: Remaining duration in days
            status_date: The date of this progress update
            completed_percentage: Optional explicit completion percentage

        Returns:
            self: For method chaining

        Raises:
            TaskError: If task is not in progress or invalid values are provided
        """
        if self._status != TaskStatus.IN_PROGRESS:
            raise TaskError(
                f"Cannot update progress for task {self.id} as it is {self._status.value}"
            )

        if not isinstance(status_date, datetime):
            raise TaskError("Status date must be a datetime object")

        if not isinstance(remaining_duration, (int, float)) or remaining_duration < 0:
            raise TaskError("Remaining duration must be a non-negative number")

        # Store the previous remaining duration
        previous_remaining = self.remaining_duration

        # Update the remaining duration
        self.remaining_duration = float(remaining_duration)

        # Calculate progress
        if not hasattr(self, "original_duration"):
            self.original_duration = self.planned_duration

        # Calculate completion percentage
        if completed_percentage is not None:
            if (
                not isinstance(completed_percentage, (int, float))
                or completed_percentage < 0
                or completed_percentage > 100
            ):
                raise TaskError(
                    "Completion percentage must be a number between 0 and 100"
                )
            completion_percentage = completed_percentage
        else:
            if self.original_duration > 0:
                completed_work = self.original_duration - self.remaining_duration
                completion_percentage = min(
                    100, (completed_work / self.original_duration * 100)
                )
            else:
                completion_percentage = 0

        # Update expected end date
        self.expected_end_date = status_date + timedelta(days=self.remaining_duration)
        self.new_end_date = self.expected_end_date

        # Add to progress history
        self._add_to_progress_history(
            status_date=status_date,
            remaining=self.remaining_duration,
            previous_remaining=previous_remaining,
            progress_percentage=completion_percentage,
        )

        # If remaining duration is 0, mark as completed
        if self.remaining_duration <= 0:
            self.complete_task(status_date)
            # Don't add another history entry, as complete_task will detect it was called from here

        return self

    def complete_task(self, completion_date: datetime) -> "Task":
        """
        Mark task as completed on the given date.

        Args:
            completion_date: The date the task was completed

        Returns:
            self: For method chaining

        Raises:
            TaskError: If task is already completed
        """
        if self._status == TaskStatus.COMPLETED:
            raise TaskError(f"Task {self.id} is already marked as completed")

        # Record previous status before changing it
        previous_status = self._status

        # Update task state
        self.status = "completed"
        self.actual_end_date = completion_date
        self.remaining_duration = 0
        self.new_end_date = completion_date

        # Calculate actual duration
        if self.actual_start_date:
            self.actual_duration = (completion_date - self.actual_start_date).days
            # Ensure minimum of 0 days
            self.actual_duration = max(0, self.actual_duration)

        # Only add to progress history if not already in progress
        # This prevents duplicate entries when called from update_progress
        if previous_status != TaskStatus.IN_PROGRESS:
            self._add_to_progress_history(
                status_date=completion_date,
                remaining=0,
                progress_percentage=100,
                status_change="completed",
            )

        return self

    def pause_task(self, pause_date: datetime, reason: str = None) -> "Task":
        """
        Mark task as on hold.

        Args:
            pause_date: The date the task was paused
            reason: Optional reason for pausing

        Returns:
            self: For method chaining

        Raises:
            TaskError: If task is not in progress
        """
        if self._status != TaskStatus.IN_PROGRESS:
            raise TaskError(
                f"Cannot pause task {self.id} as it is {self._status.value}"
            )

        self.status = "on_hold"

        # Add to progress history
        self._add_to_progress_history(
            status_date=pause_date,
            remaining=self.remaining_duration,
            status_change="paused",
            note=reason,
        )

        return self

    def resume_task(self, resume_date: datetime) -> "Task":
        """
        Resume a paused task.

        Args:
            resume_date: The date the task was resumed

        Returns:
            self: For method chaining

        Raises:
            TaskError: If task is not on hold
        """
        if self._status != TaskStatus.ON_HOLD:
            raise TaskError(f"Cannot resume task {self.id} as it is not on hold")

        self.status = "in_progress"

        # Add to progress history
        self._add_to_progress_history(
            status_date=resume_date,
            remaining=self.remaining_duration,
            status_change="resumed",
        )

        return self

    def cancel_task(self, cancel_date: datetime, reason: str = None) -> "Task":
        """
        Mark task as cancelled.

        Args:
            cancel_date: The date the task was cancelled
            reason: Optional reason for cancellation

        Returns:
            self: For method chaining
        """
        prev_status = self.status
        self.status = "cancelled"

        # Add to progress history
        self._add_to_progress_history(
            status_date=cancel_date,
            remaining=self.remaining_duration,
            status_change=f"cancelled (was {prev_status})",
            note=reason,
        )

        return self

    def get_progress_percentage(self) -> float:
        """
        Calculate the current progress percentage of the task.

        Returns:
            float: Percentage of completion (0-100)
        """
        if self._status == TaskStatus.COMPLETED:
            return 100.0

        if not hasattr(self, "original_duration") or self.original_duration <= 0:
            # Fall back to planned duration if original not available
            duration = self.planned_duration
        else:
            duration = self.original_duration

        if duration <= 0:
            return 0.0

        completed = duration - self.remaining_duration
        return min(99.9, max(0, (completed / duration) * 100))

    def get_elapsed_duration(self) -> float:
        """
        Get the elapsed duration of the task.

        Returns:
            float: Elapsed duration in days
        """
        if self._status == TaskStatus.PLANNED:
            return 0

        if self._status == TaskStatus.COMPLETED and hasattr(self, "actual_duration"):
            return self.actual_duration

        if not self.actual_start_date:
            return 0

        # Calculate elapsed duration based on status date or current date
        if self.progress_history:
            latest_status_date = self.progress_history[-1]["date"]
        else:
            latest_status_date = datetime.now()

        elapsed = (latest_status_date - self.actual_start_date).days
        return max(0, elapsed)

    def get_variance(self) -> float:
        """
        Calculate schedule variance (positive is ahead of schedule, negative is behind).

        Returns:
            float: Schedule variance in days
        """
        if self._status == TaskStatus.PLANNED:
            return 0

        if not hasattr(self, "original_duration") or not self.actual_start_date:
            return 0

        if self._status == TaskStatus.COMPLETED and self.actual_end_date:
            # For completed tasks
            planned_end = self.start_date + timedelta(days=self.planned_duration)
            return (
                planned_end - self.actual_end_date
            ).total_seconds() / 86400  # Convert to days
        else:
            # For in-progress tasks
            planned_progress = min(self.planned_duration, self.get_elapsed_duration())
            actual_progress = self.planned_duration - self.remaining_duration
            return actual_progress - planned_progress

    def get_start_date(self) -> Optional[datetime]:
        """
        Get the effective start date based on status.

        Returns:
            datetime: The effective start date
        """
        if (
            self._status in [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]
            and self.actual_start_date
        ):
            return self.actual_start_date
        elif hasattr(self, "new_start_date") and self.new_start_date:
            return self.new_start_date
        else:
            return self.start_date if hasattr(self, "start_date") else None

    def get_end_date(self) -> Optional[datetime]:
        """
        Get the effective end date based on status.

        Returns:
            datetime: The effective end date
        """
        if self._status == TaskStatus.COMPLETED and self.actual_end_date:
            return self.actual_end_date

        if self._status == TaskStatus.IN_PROGRESS:
            if hasattr(self, "expected_end_date") and self.expected_end_date:
                return self.expected_end_date
            elif self.actual_start_date and self.remaining_duration is not None:
                # Calculate from remaining duration
                latest_date = self.actual_start_date
                if self.progress_history:
                    latest_date = self.progress_history[-1]["date"]
                return latest_date + timedelta(days=self.remaining_duration)

        # For planned tasks
        if hasattr(self, "new_end_date") and self.new_end_date:
            return self.new_end_date
        elif hasattr(self, "end_date") and self.end_date:
            return self.end_date
        elif (
            hasattr(self, "start_date")
            and self.start_date
            and hasattr(self, "planned_duration")
        ):
            return self.start_date + timedelta(days=self.planned_duration)

        return None

    def is_critical(self) -> bool:
        """
        Check if the task is on the critical chain.

        Returns:
            bool: True if the task is on the critical chain
        """
        return self._chain_type == ChainType.CRITICAL

    def is_feeding_chain(self) -> bool:
        """
        Check if the task is on a feeding chain.

        Returns:
            bool: True if the task is on a feeding chain
        """
        return self._chain_type == ChainType.FEEDING

    def is_delayed(self) -> bool:
        """
        Check if the task is delayed compared to the original schedule.

        Returns:
            bool: True if the task is delayed
        """
        # Always return False for planned tasks
        if self._status == TaskStatus.PLANNED:
            return False

        # Check for delayed start
        if (
            hasattr(self, "start_date")
            and hasattr(self, "actual_start_date")
            and self.start_date is not None
            and self.actual_start_date is not None
        ):
            if self.actual_start_date > self.start_date:
                return True

        # Check for delayed completion
        if self._status == TaskStatus.COMPLETED:
            if (
                hasattr(self, "start_date")
                and hasattr(self, "planned_duration")
                and hasattr(self, "actual_end_date")
                and self.start_date is not None
                and self.actual_end_date is not None
            ):
                # Calculate planned end date
                planned_end = self.start_date + timedelta(days=self.planned_duration)
                # Check if actual end date is later than planned end date
                if self.actual_end_date > planned_end:
                    return True

        # Default case - not delayed
        return False

    def add_tag(self, tag: str) -> "Task":
        """
        Add a tag to this task if it doesn't already exist.

        Args:
            tag: Tag to add

        Returns:
            self: For method chaining
        """
        if not isinstance(tag, str):
            raise TaskError("Tag must be a string")

        if tag not in self.tags:
            self.tags.append(tag)

        return self

    def remove_tag(self, tag: str) -> bool:
        """
        Remove a tag from this task if it exists.

        Args:
            tag: Tag to remove

        Returns:
            bool: True if tag was removed, False if it wasn't found
        """
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def has_tag(self, tag: str) -> bool:
        """
        Check if this task has a specific tag.

        Args:
            tag: Tag to check for

        Returns:
            bool: True if task has the tag
        """
        return tag in self.tags

    def filter_by_tags(self, tags: List[str], match_all: bool = True) -> bool:
        """
        Check if this task has all or any of the specified tags.

        Args:
            tags: List of tags to check for
            match_all: If True, task must have all tags; if False, any one tag is sufficient

        Returns:
            bool: True if task matches the tag filter
        """
        if not tags:
            return True

        if match_all:
            return all(tag in self.tags for tag in tags)
        else:
            return any(tag in self.tags for tag in tags)

    def set_full_kitted(
        self, is_kitted: bool, date: Optional[datetime] = None, note: str = None
    ) -> "Task":
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

        if not isinstance(date, datetime):
            raise TaskError("Date must be a datetime object")

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

    def add_note(self, text: str, date: Optional[datetime] = None) -> Dict:
        """
        Add a timestamped note to the task.

        Args:
            text: Note text
            date: Date of the note (defaults to now)

        Returns:
            dict: The added note

        Raises:
            TaskError: If text is not a string
        """
        if not isinstance(text, str):
            raise TaskError("Note text must be a string")

        if date is None:
            date = datetime.now()

        if not isinstance(date, datetime):
            raise TaskError("Date must be a datetime object")

        note = {"date": date, "text": text}
        self.notes.append(note)

        return note

    def get_notes(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get notes, optionally filtered by date range.

        Args:
            start_date: Filter notes on or after this date
            end_date: Filter notes on or before this date

        Returns:
            list: Filtered notes
        """
        if start_date and not isinstance(start_date, datetime):
            raise TaskError("Start date must be a datetime object")

        if end_date and not isinstance(end_date, datetime):
            raise TaskError("End date must be a datetime object")

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

    def set_schedule(self, start_date: datetime, duration: float = None) -> "Task":
        """
        Set the planned schedule for the task.

        Args:
            start_date: Planned start date
            duration: Optional duration (defaults to planned_duration)

        Returns:
            self: For method chaining

        Raises:
            TaskError: If start_date is not a datetime object
        """
        if not isinstance(start_date, datetime):
            raise TaskError("Start date must be a datetime object")

        self.start_date = start_date

        if duration is not None:
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise TaskError("Duration must be a positive number")
            self.planned_duration = float(duration)
            self.remaining_duration = float(duration)

        self.end_date = start_date + timedelta(days=self.planned_duration)

        return self

    def update_schedule(
        self, start_date: datetime = None, duration: float = None
    ) -> "Task":
        """
        Update the planned schedule.

        Args:
            start_date: New start date
            duration: New duration

        Returns:
            self: For method chaining
        """
        if start_date is not None:
            if not isinstance(start_date, datetime):
                raise TaskError("Start date must be a datetime object")
            self.new_start_date = start_date

            # Update end date based on new start date
            if hasattr(self, "remaining_duration"):
                duration_to_use = self.remaining_duration
            elif duration is not None:
                duration_to_use = duration
            else:
                duration_to_use = self.planned_duration

            self.new_end_date = start_date + timedelta(days=duration_to_use)

        elif duration is not None:
            # Only duration was provided
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise TaskError("Duration must be a positive number")

            self.planned_duration = float(duration)
            if self._status == TaskStatus.PLANNED:
                self.remaining_duration = float(duration)

            # Update end date if we have a start date
            if hasattr(self, "new_start_date") and self.new_start_date:
                self.new_end_date = self.new_start_date + timedelta(days=duration)
            elif hasattr(self, "start_date") and self.start_date:
                self.end_date = self.start_date + timedelta(days=duration)

        return self

    def _add_to_progress_history(
        self,
        status_date: datetime,
        remaining: float,
        previous_remaining: float = None,
        progress_percentage: float = None,
        status_change: str = None,
        note: str = None,
    ) -> None:
        """
        Add an entry to the progress history.

        Args:
            status_date: Date of the progress update
            remaining: Remaining duration at this point
            previous_remaining: Previous remaining duration
            progress_percentage: Calculated progress percentage
            status_change: Description of status change if any
            note: Optional note
        """
        if not hasattr(self, "progress_history"):
            self.progress_history = []

        # Calculate elapsed days
        elapsed_days = 0
        if self.actual_start_date:
            elapsed_days = max(0, (status_date - self.actual_start_date).days)

        # Calculate progress percentage if not provided
        if (
            progress_percentage is None
            and hasattr(self, "original_duration")
            and self.original_duration > 0
        ):
            completed = self.original_duration - remaining
            progress_percentage = min(
                100, max(0, (completed / self.original_duration * 100))
            )

        # Create history entry
        entry = {
            "date": status_date,
            "remaining": remaining,
            "elapsed_days": elapsed_days,
            "status": self.status,
        }

        # Add optional fields if provided
        if previous_remaining is not None:
            entry["previous_remaining"] = previous_remaining

        if progress_percentage is not None:
            entry["progress_percentage"] = progress_percentage

        if status_change:
            entry["status_change"] = status_change

        if note:
            entry["note"] = note

        self.progress_history.append(entry)

    def get_visual_properties(self) -> Dict:
        """
        Get all visual properties for rendering the task.

        Returns:
            dict: Dictionary with visual properties
        """
        # Calculate opacity based on status if not explicitly set
        opacity = self.opacity

        # Determine color based on chain type if not explicitly set
        color = self.color

        # Determine pattern based on status if not explicitly set
        pattern = self.pattern

        # Get progress percentage for rendering
        progress = self.get_progress_percentage()

        return {
            "color": color,
            "border_color": self.border_color,
            "pattern": pattern,
            "opacity": opacity,
            "progress_percentage": progress,
            "status": self.status,
            "is_critical": self.is_critical(),
            "is_feeding": self.is_feeding_chain(),
            "is_delayed": self.is_delayed(),
        }

    def reset_visual_properties(self) -> "Task":
        """
        Reset all visual properties to their default values.

        Returns:
            self: For method chaining
        """
        self._color = None
        self._border_color = None
        self._pattern = None
        self._opacity = None
        return self

    def set_visual_properties(
        self,
        color: str = None,
        border_color: str = None,
        pattern: str = None,
        opacity: float = None,
    ) -> "Task":
        """
        Set multiple visual properties at once.

        Args:
            color: Fill color
            border_color: Border color
            pattern: Fill pattern
            opacity: Opacity (0.0-1.0)

        Returns:
            self: For method chaining
        """
        if color is not None:
            self.color = color

        if border_color is not None:
            self.border_color = border_color

        if pattern is not None:
            self.pattern = pattern

        if opacity is not None:
            self.opacity = opacity

        return self

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task to a dictionary representation.

        Returns:
            dict: Dictionary representation of the task
        """
        result = {
            "id": self.id,
            "name": self.name,
            "aggressive_duration": self.aggressive_duration,
            "safe_duration": self.safe_duration,
            "planned_duration": self.planned_duration,
            "dependencies": self.dependencies.copy(),
            "resources": self.resources.copy(),
            "tags": self.tags.copy(),
            "description": self.description,
            "status": self.status,
            "chain_id": self.chain_id,
            "chain_type": self.chain_type,
            "is_full_kitted": self.is_full_kitted,
            "remaining_duration": self.remaining_duration,
            "progress_percentage": self.get_progress_percentage(),
        }

        # Add dates if available
        for attr in [
            "start_date",
            "end_date",
            "new_start_date",
            "new_end_date",
            "actual_start_date",
            "actual_end_date",
            "full_kitted_date",
        ]:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                result[attr] = getattr(self, attr)

        # Add scheduling attributes if available
        for attr in [
            "early_start",
            "early_finish",
            "late_start",
            "late_finish",
            "slack",
        ]:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                result[attr] = getattr(self, attr)

        # Add visual properties
        result["visual"] = self.get_visual_properties()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """
        Create a task from a dictionary representation.

        Args:
            data: Dictionary representation of the task

        Returns:
            Task: New task instance
        """
        # Create task with required fields
        task = cls(
            id=data["id"],
            name=data["name"],
            aggressive_duration=data["aggressive_duration"],
            safe_duration=data.get("safe_duration"),
            dependencies=data.get("dependencies", []),
            resources=data.get("resources", []),
            tags=data.get("tags", []),
            description=data.get("description", ""),
        )

        # Set additional attributes
        if "planned_duration" in data:
            task.planned_duration = data["planned_duration"]

        if "status" in data:
            task.status = data["status"]

        if "chain_id" in data:
            task.chain_id = data["chain_id"]

        if "chain_type" in data:
            task.chain_type = data["chain_type"]

        if "is_full_kitted" in data:
            task.is_full_kitted = data["is_full_kitted"]

        if "remaining_duration" in data:
            task.remaining_duration = data["remaining_duration"]

        # Set dates if available
        for attr in [
            "start_date",
            "end_date",
            "new_start_date",
            "new_end_date",
            "actual_start_date",
            "actual_end_date",
            "full_kitted_date",
        ]:
            if attr in data:
                setattr(task, attr, data[attr])

        # Set scheduling attributes if available
        for attr in [
            "early_start",
            "early_finish",
            "late_start",
            "late_finish",
            "slack",
        ]:
            if attr in data:
                setattr(task, attr, data[attr])

        # Set visual properties if available
        if "visual" in data:
            visual = data["visual"]
            task.set_visual_properties(
                color=visual.get("color"),
                border_color=visual.get("border_color"),
                pattern=visual.get("pattern"),
                opacity=visual.get("opacity"),
            )

        return task

    def copy(self) -> "Task":
        """
        Create a deep copy of this task.

        Returns:
            Task: New task instance with the same properties
        """
        return self.from_dict(self.to_dict())

    def __repr__(self) -> str:
        """
        Get string representation of the task.

        Returns:
            str: String representation
        """
        status_str = f", status={self.status}"
        chain_str = f", chain={self.chain_id}" if self.chain_id else ""
        progress_str = ""
        if self._status == TaskStatus.IN_PROGRESS:
            progress_str = f", progress={self.get_progress_percentage():.1f}%"

        return f"Task(id={self.id}, name={self.name}, duration={self.planned_duration}{status_str}{chain_str}{progress_str})"
