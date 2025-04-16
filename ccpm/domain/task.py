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
        resources: Optional[Union[List[str], str, Dict[str, float]]] = None,
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

        # Just maintain resource_allocations
        self.resource_allocations = {}

        # Process resources input
        if isinstance(resources, str):
            # Single resource with full allocation
            self.resource_allocations = {resources: 1.0}
        elif isinstance(resources, list):
            # List of resources, all with full allocation
            self.resource_allocations = {r: 1.0 for r in resources}
        elif isinstance(resources, dict):
            # Dictionary of {resource_id: allocation_amount}
            self.resource_allocations = resources.copy()

    # resources property becomes a dynamic property
    @property
    def resources(self):
        """Return list of resources for backward compatibility"""
        return list(self.resource_allocations.keys())

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
                    latest_date = max(
                        (
                            entry["date"]
                            for entry in self.progress_history
                            if entry["date"] is not None
                        ),
                        default=latest_date,
                    )
                # Only return if we have a valid latest_date
                if latest_date:
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

    def get_cumulative_flow_data(self, start_date=None, end_date=None):
        """
        Generate data for a cumulative flow diagram showing task state transitions over time.

        Args:
            start_date: Start date for the diagram (defaults to planned start date)
            end_date: End date for the diagram (defaults to actual/expected end date or today)

        Returns:
            dict: Data formatted for a cumulative flow diagram
                {
                    'dates': [date strings],
                    'status_counts': {status: [counts]},
                    'status_transitions': [{'date': datetime, 'from': status, 'to': status}],
                    'cycle_time': float or None  # If task is completed
                }
        """
        # Default start date to planned start if not provided
        if start_date is None:
            start_date = self.get_start_date() or datetime.now()

        # Default end date to actual end, expected end, or today
        if end_date is None:
            if (
                self.status == "completed"
                and hasattr(self, "actual_end_date")
                and self.actual_end_date
            ):
                end_date = self.actual_end_date
            else:
                end_date = self.get_end_date() or datetime.now()
                end_date = max(end_date, datetime.now())

        # Ensure dates are datetime objects
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Generate daily date range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Get all status transitions from history
        transitions = []
        status_at_date = {}  # Maps date to status

        # Add initial status (planned)
        initial_status = "planned"
        initial_date = self.start_date
        if initial_date and initial_date < start_date:
            status_at_date[initial_date.strftime("%Y-%m-%d")] = initial_status

        # Extract status changes from progress history
        if hasattr(self, "progress_history"):
            for entry in self.progress_history:
                if "status_change" in entry or "status" in entry:
                    date = entry["date"]
                    new_status = entry.get("status", initial_status)
                    date_str = date.strftime("%Y-%m-%d")

                    # Skip if before our range
                    if date < start_date:
                        status_at_date[date_str] = new_status
                        continue

                    # Find the previous status
                    prev_status = None
                    for prev_date in sorted(status_at_date.keys(), reverse=True):
                        if datetime.strptime(prev_date, "%Y-%m-%d") < date:
                            prev_status = status_at_date[prev_date]
                            break

                    if prev_status is None:
                        prev_status = initial_status

                    # Record transition
                    transitions.append(
                        {"date": date, "from": prev_status, "to": new_status}
                    )

                    # Update status map
                    status_at_date[date_str] = new_status

        # Build status counts for each date
        status_counts = {}
        possible_statuses = [
            "planned",
            "in_progress",
            "completed",
            "on_hold",
            "cancelled",
        ]

        for status in possible_statuses:
            status_counts[status] = []

        # For each date, determine the task's status
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            current_status = None

            # Find the latest status before or on this date
            for history_date in sorted(status_at_date.keys(), reverse=True):
                if datetime.strptime(history_date, "%Y-%m-%d") <= date:
                    current_status = status_at_date[history_date]
                    break

            # If no status found, determine based on actual dates
            if current_status is None:
                # Default to planned
                current_status = "planned"

                # Check if started by this date
                if (
                    hasattr(self, "actual_start_date")
                    and self.actual_start_date is not None
                ):
                    if self.actual_start_date <= date:
                        current_status = "in_progress"

                        # Check if completed by this date
                        if (
                            hasattr(self, "actual_end_date")
                            and self.actual_end_date is not None
                            and self.actual_end_date <= date
                        ):
                            current_status = "completed"

            # Add counts for this date (1 for current status, 0 for others)
            for status in possible_statuses:
                if status == current_status:
                    status_counts[status].append(1)
                else:
                    status_counts[status].append(0)

        # Calculate cycle time if task is completed
        cycle_time = None
        if (
            self.status == "completed"
            and hasattr(self, "actual_start_date")
            and self.actual_start_date is not None
            and hasattr(self, "actual_end_date")
            and self.actual_end_date is not None
        ):
            cycle_time = (self.actual_end_date - self.actual_start_date).days

        return {
            "dates": date_strs,
            "status_counts": status_counts,
            "status_transitions": transitions,
            "cycle_time": cycle_time,
        }

    def get_flow_metrics(self):
        """
        Calculate flow metrics for this task.

        Returns:
            dict: Flow metrics including:
                - cycle_time: Days from start to completion (if completed)
                - lead_time: Days from creation/planning to completion (if completed)
                - wait_time: Days spent in on_hold status
                - touch_time: Days spent in in_progress status
                - efficiency: Ratio of touch_time to cycle_time (%)
        """
        metrics = {
            "cycle_time": None,
            "lead_time": None,
            "wait_time": 0,
            "touch_time": 0,
            "efficiency": None,
        }

        # Only calculate full metrics for completed tasks
        if (
            self.status == "completed"
            and self.actual_start_date
            and self.actual_end_date
        ):
            # Cycle time = actual end - actual start
            metrics["cycle_time"] = (self.actual_end_date - self.actual_start_date).days

            # Lead time = actual end - planned start
            if self.start_date:
                metrics["lead_time"] = (self.actual_end_date - self.start_date).days

        # Calculate time spent in each status
        if hasattr(self, "progress_history") and self.progress_history:
            status_periods = {}
            current_status = None
            current_start = None

            # Add a synthetic entry for "now" if task isn't completed
            history = self.progress_history.copy()
            if self.status != "completed":
                history.append({"date": datetime.now(), "status": self.status})

            for idx, entry in enumerate(history):
                if idx == 0:
                    # First entry, start tracking
                    current_status = entry.get("status", "planned")
                    current_start = entry["date"]
                    continue

                # Calculate duration for the previous status
                if current_status:
                    duration = (entry["date"] - current_start).days
                    if current_status not in status_periods:
                        status_periods[current_status] = 0
                    status_periods[current_status] += duration

                # Update for next iteration
                current_status = entry.get("status", current_status)
                current_start = entry["date"]

            # Update metrics based on collected periods
            if "on_hold" in status_periods:
                metrics["wait_time"] = status_periods["on_hold"]

            if "in_progress" in status_periods:
                metrics["touch_time"] = status_periods["in_progress"]

            # Calculate efficiency if we have both touch time and cycle time
            if metrics["cycle_time"] and metrics["cycle_time"] > 0:
                metrics["efficiency"] = (
                    metrics["touch_time"] / metrics["cycle_time"]
                ) * 100

        return metrics

    def get_cumulative_flow_data(self, start_date=None, end_date=None):
        """
        Generate data for a cumulative flow diagram showing task state transitions over time.

        Args:
            start_date: Start date for the diagram (defaults to planned start date)
            end_date: End date for the diagram (defaults to actual/expected end date or today)

        Returns:
            dict: Data formatted for a cumulative flow diagram
                {
                    'dates': [date strings],
                    'status_counts': {status: [counts]},
                    'status_transitions': [{'date': datetime, 'from': status, 'to': status}],
                    'cycle_time': float or None  # If task is completed
                }
        """
        # Default start date to planned start if not provided
        if start_date is None:
            start_date = self.get_start_date() or datetime.now()

        # Default end date to actual end, expected end, or today
        if end_date is None:
            if self.status == "completed" and self.actual_end_date:
                end_date = self.actual_end_date
            else:
                calculated_end_date = self.get_end_date()
                if calculated_end_date:
                    end_date = calculated_end_date
                else:
                    end_date = datetime.now()  # Fallback to current date
            end_date = max(end_date, datetime.now())

        # Ensure dates are datetime objects
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Generate daily date range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Get all status transitions from history
        transitions = []
        status_at_date = {}  # Maps date to status

        # Add initial status (planned)
        initial_status = "planned"
        initial_date = self.start_date
        if initial_date and initial_date < start_date:
            status_at_date[initial_date.strftime("%Y-%m-%d")] = initial_status

        # Extract status changes from progress history
        if hasattr(self, "progress_history"):
            for entry in self.progress_history:
                if "status_change" in entry:
                    date = entry["date"]
                    new_status = entry["status"]
                    date_str = date.strftime("%Y-%m-%d")

                    # Skip if before our range
                    if date < start_date:
                        status_at_date[date_str] = new_status
                        continue

                    # Find the previous status
                    prev_status = None
                    for prev_date in sorted(status_at_date.keys(), reverse=True):
                        if datetime.strptime(prev_date, "%Y-%m-%d") < date:
                            prev_status = status_at_date[prev_date]
                            break

                    if prev_status is None:
                        prev_status = initial_status

                    # Record transition
                    transitions.append(
                        {"date": date, "from": prev_status, "to": new_status}
                    )

                    # Update status map
                    status_at_date[date_str] = new_status

        # Build status counts for each date
        status_counts = {}
        possible_statuses = [s.value for s in TaskStatus]

        for status in possible_statuses:
            status_counts[status] = []

        # For each date, determine the task's status
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            current_status = None

            # Find the latest status before or on this date
            for history_date in sorted(status_at_date.keys(), reverse=True):
                if datetime.strptime(history_date, "%Y-%m-%d") <= date:
                    current_status = status_at_date[history_date]
                    break

            # Use planned as default if no status found
            if current_status is None:
                current_status = initial_status

            # Add counts for this date (1 for current status, 0 for others)
            for status in possible_statuses:
                if status == current_status:
                    status_counts[status].append(1)
                else:
                    status_counts[status].append(0)

        # Calculate cycle time if task is completed
        cycle_time = None
        if (
            self.status == "completed"
            and self.actual_start_date
            and self.actual_end_date
        ):
            cycle_time = (self.actual_end_date - self.actual_start_date).days

        return {
            "dates": date_strs,
            "status_counts": status_counts,
            "status_transitions": transitions,
            "cycle_time": cycle_time,
        }

    def get_flow_metrics(self):
        """
        Calculate flow metrics for this task.

        Returns:
            dict: Flow metrics including:
                - cycle_time: Days from start to completion (if completed)
                - lead_time: Days from creation/planning to completion (if completed)
                - wait_time: Days spent in on_hold status
                - touch_time: Days spent in in_progress status
                - efficiency: Ratio of touch_time to cycle_time (%)
        """
        metrics = {
            "cycle_time": None,
            "lead_time": None,
            "wait_time": 0,
            "touch_time": 0,
            "efficiency": None,
        }

        # Only calculate full metrics for completed tasks
        if (
            self.status == "completed"
            and self.actual_start_date
            and self.actual_end_date
        ):
            # Cycle time = actual end - actual start
            metrics["cycle_time"] = (self.actual_end_date - self.actual_start_date).days

            # Lead time = actual end - planned start
            if self.start_date:
                metrics["lead_time"] = (self.actual_end_date - self.start_date).days

        # Calculate time spent in each status
        if hasattr(self, "progress_history") and self.progress_history:
            status_periods = {}
            current_status = None
            current_start = None

            # Add a synthetic entry for "now" if task isn't completed
            history = self.progress_history.copy()
            if self.status != "completed":
                history.append({"date": datetime.now(), "status": self.status})

            for idx, entry in enumerate(history):
                if idx == 0:
                    # First entry, start tracking
                    current_status = entry.get("status", "planned")
                    current_start = entry["date"]
                    continue

                # Calculate duration for the previous status
                if current_status:
                    duration = (entry["date"] - current_start).days
                    if current_status not in status_periods:
                        status_periods[current_status] = 0
                    status_periods[current_status] += duration

                # Update for next iteration
                current_status = entry.get("status", current_status)
                current_start = entry["date"]

            # Update metrics based on collected periods
            if "on_hold" in status_periods:
                metrics["wait_time"] = status_periods["on_hold"]

            if "in_progress" in status_periods:
                metrics["touch_time"] = status_periods["in_progress"]

            # Calculate efficiency if we have both touch time and cycle time
            if metrics["cycle_time"] and metrics["cycle_time"] > 0:
                metrics["efficiency"] = (
                    metrics["touch_time"] / metrics["cycle_time"]
                ) * 100

        return metrics

    @classmethod
    def aggregate_flow_data(cls, tasks, start_date=None, end_date=None):
        """
        Aggregate cumulative flow data across multiple tasks.

        Args:
            tasks: List of Task objects
            start_date: Start date for analysis (defaults to earliest start date)
            end_date: End date for analysis (defaults to latest end date or today)

        Returns:
            dict: Aggregated flow data suitable for visualization
        """
        if not tasks:
            return None

        # Find date range if not specified
        if start_date is None:
            start_dates = [t.get_start_date() for t in tasks if t.get_start_date()]
            start_date = min(start_dates) if start_dates else datetime.now()

        if end_date is None:
            end_dates = [t.get_end_date() for t in tasks if t.get_end_date()]
            end_date = max(end_dates) if end_dates else datetime.now()
            end_date = max(end_date, datetime.now())

        # Generate daily date range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Initialize aggregated data structure
        possible_statuses = [s.value for s in TaskStatus]
        aggregated_status_counts = {
            status: [0] * len(dates) for status in possible_statuses
        }

        # Collect data from each task
        for task in tasks:
            # Get flow data for this task
            flow_data = task.get_cumulative_flow_data(start_date, end_date)

            # Add to aggregated counts
            for status, counts in flow_data["status_counts"].items():
                # For each date in the task's data, add to our aggregate
                for i, count in enumerate(counts):
                    if i < len(aggregated_status_counts[status]):
                        aggregated_status_counts[status][i] += count

        # Calculate cycle time and throughput metrics
        completed_tasks = [t for t in tasks if t.status == "completed"]
        cycle_times = [
            (t.actual_end_date - t.actual_start_date).days
            for t in completed_tasks
            if hasattr(t, "actual_start_date") and hasattr(t, "actual_end_date")
        ]

        avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else None

        # Calculate throughput by week
        weekly_throughput = {}
        for task in completed_tasks:
            if not hasattr(task, "actual_end_date"):
                continue

            week_key = task.actual_end_date.strftime("%Y-W%W")
            if week_key not in weekly_throughput:
                weekly_throughput[week_key] = 0
            weekly_throughput[week_key] += 1

        # Return aggregated data
        return {
            "dates": date_strs,
            "status_counts": aggregated_status_counts,
            "avg_cycle_time": avg_cycle_time,
            "weekly_throughput": weekly_throughput,
            "total_completed": len(completed_tasks),
            "total_tasks": len(tasks),
        }

    def get_throughput_data(cls, tasks, period="week"):
        """
        Calculate throughput data (tasks completed per time period).

        Args:
            tasks: List of Task objects
            period: Time period for bucketing ('day', 'week', or 'month')

        Returns:
            dict: Throughput data {period_key: count}
        """
        completed_tasks = [
            t
            for t in tasks
            if t.status == "completed" and hasattr(t, "actual_end_date")
        ]

        throughput = {}

        for task in completed_tasks:
            if period == "day":
                period_key = task.actual_end_date.strftime("%Y-%m-%d")
            elif period == "week":
                period_key = task.actual_end_date.strftime("%Y-W%W")
            elif period == "month":
                period_key = task.actual_end_date.strftime("%Y-%m")
            else:
                raise ValueError(
                    f"Invalid period: {period}. Use 'day', 'week', or 'month'"
                )

            if period_key not in throughput:
                throughput[period_key] = 0
            throughput[period_key] += 1

        return throughput

    def calculate_avg_flowtime(cls, tasks):
        """
        Calculate average flow time metrics across multiple tasks.

        Args:
            tasks: List of Task objects

        Returns:
            dict: Average flow metrics including cycle_time, lead_time, etc.
        """
        # Only include completed tasks
        completed_tasks = [t for t in tasks if t.status == "completed"]

        if not completed_tasks:
            return {
                "avg_cycle_time": None,
                "avg_lead_time": None,
                "avg_wait_time": None,
                "avg_touch_time": None,
                "avg_efficiency": None,
            }

        # Collect metrics from each task
        all_metrics = [task.get_flow_metrics() for task in completed_tasks]

        # Calculate averages
        result = {}
        for metric in [
            "cycle_time",
            "lead_time",
            "wait_time",
            "touch_time",
            "efficiency",
        ]:
            values = [m[metric] for m in all_metrics if m[metric] is not None]
            result[f"avg_{metric}"] = sum(values) / len(values) if values else None

        return result

        """
        Aggregate cumulative flow data across multiple tasks.

        Args:
            tasks: List of Task objects
            start_date: Start date for analysis (defaults to earliest start date)
            end_date: End date for analysis (defaults to latest end date or today)

        Returns:
            dict: Aggregated flow data suitable for visualization
        """
        if not tasks:
            return None

        # Find date range if not specified
        if start_date is None:
            start_dates = [t.get_start_date() for t in tasks if t.get_start_date()]
            start_date = min(start_dates) if start_dates else datetime.now()

        if end_date is None:
            end_dates = [t.get_end_date() for t in tasks if t.get_end_date()]
            end_date = max(end_dates) if end_dates else datetime.now()
            end_date = max(end_date, datetime.now())

        # Generate daily date range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Initialize aggregated data structure
        possible_statuses = [s.value for s in TaskStatus]
        aggregated_status_counts = {
            status: [0] * len(dates) for status in possible_statuses
        }

        # Collect data from each task
        for task in tasks:
            # Get flow data for this task
            flow_data = task.get_cumulative_flow_data(start_date, end_date)

            # Add to aggregated counts
            for status, counts in flow_data["status_counts"].items():
                # For each date in the task's data, add to our aggregate
                for i, count in enumerate(counts):
                    if i < len(aggregated_status_counts[status]):
                        aggregated_status_counts[status][i] += count

        # Calculate cycle time and throughput metrics
        completed_tasks = [t for t in tasks if t.status == "completed"]
        cycle_times = [
            (t.actual_end_date - t.actual_start_date).days
            for t in completed_tasks
            if hasattr(t, "actual_start_date") and hasattr(t, "actual_end_date")
        ]

        avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else None

        # Calculate throughput by week
        weekly_throughput = {}
        for task in completed_tasks:
            if not hasattr(task, "actual_end_date"):
                continue

            week_key = task.actual_end_date.strftime("%Y-W%W")
            if week_key not in weekly_throughput:
                weekly_throughput[week_key] = 0
            weekly_throughput[week_key] += 1

        # Return aggregated data
        return {
            "dates": date_strs,
            "status_counts": aggregated_status_counts,
            "avg_cycle_time": avg_cycle_time,
            "weekly_throughput": weekly_throughput,
            "total_completed": len(completed_tasks),
            "total_tasks": len(tasks),
        }

    def set_resource_allocation(self, resource_id, amount):
        """Set the allocation amount for a specific resource."""
        if amount <= 0:
            raise ValueError("Resource allocation must be positive")

        if resource_id not in self.resource_allocations:
            self.resource_allocations.append(resource_id)

        self.resource_allocations[resource_id] = amount
        return self

    def get_resource_allocation(self, resource_id):
        """Get the allocation amount for a specific resource."""
        return self.resource_allocations.get(resource_id, 0.0)
