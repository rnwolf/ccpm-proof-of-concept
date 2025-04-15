from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union


class ChainError(Exception):
    """Exception raised for errors in the Chain class."""

    pass


class Chain:
    """
    Represents a chain of tasks in a Critical Chain Project Management (CCPM) system.

    A chain can be either a critical chain (the primary sequence of tasks that determines
    project duration) or a feeding chain (a sequence that feeds into the critical chain).
    """

    def __init__(
        self, id: str, name: str, type: str = "feeding", buffer_ratio: float = 0.3
    ):
        """
        Initialize a new Chain.

        Args:
            id: Unique identifier for the chain
            name: Descriptive name for the chain
            type: Chain type ("critical" or "feeding")
            buffer_ratio: Default ratio for buffer calculation (0.0 to 1.0)

        Raises:
            ChainError: If any input validation fails
        """
        # Validate id
        if id is None or str(id).strip() == "":
            raise ChainError("Chain ID cannot be None or empty")
        self.id = id

        # Validate name
        if not name or not isinstance(name, str):
            raise ChainError("Chain name must be a non-empty string")
        self.name = name

        # Validate type
        if type not in ["critical", "feeding"]:
            raise ChainError("Chain type must be either 'critical' or 'feeding'")
        self.type = type

        # Validate buffer_ratio
        if not isinstance(buffer_ratio, (int, float)):
            raise ChainError("Buffer ratio must be a number")
        if buffer_ratio < 0 or buffer_ratio > 1:
            raise ChainError("Buffer ratio must be between 0 and 1")
        self.buffer_ratio = buffer_ratio

        # Initialize other attributes
        self.tasks = []  # List of task IDs in this chain (in order)
        self.connects_to_task_id = None  # For feeding chains, task ID it connects to
        self.connects_to_chain_id = None  # Chain ID it connects to
        self.buffer = None  # Associated buffer object
        self.buffer_strategy = None  # Buffer calculation strategy

        # Status tracking
        self.status_date = None  # Last status update date
        self.completion_percentage = 0  # Overall completion percentage

        # History tracking
        self.status_history = []  # History of status updates

    def add_task(self, task_id: str) -> "Chain":
        """
        Add a task to this chain.

        Args:
            task_id: ID of the task to add

        Returns:
            self: For method chaining

        Raises:
            ChainError: If task_id is None or empty
        """
        if task_id is None or str(task_id).strip() == "":
            raise ChainError("Task ID cannot be None or empty")

        if task_id not in self.tasks:
            self.tasks.append(task_id)
        return self

    def remove_task(self, task_id: str) -> "Chain":
        """
        Remove a task from this chain.

        Args:
            task_id: ID of the task to remove

        Returns:
            self: For method chaining
        """
        if task_id in self.tasks:
            self.tasks.remove(task_id)
        return self

    def set_connection(self, task_id: str, chain_id: Optional[str] = None) -> "Chain":
        """
        Set where this feeding chain connects to.

        Args:
            task_id: ID of the task this chain connects to
            chain_id: ID of the chain containing the task

        Returns:
            self: For method chaining

        Raises:
            ChainError: If task_id is None or this is not a feeding chain
        """
        if task_id is None or str(task_id).strip() == "":
            raise ChainError("Task ID cannot be None or empty")

        if self.type != "feeding":
            raise ChainError("Only feeding chains can connect to other tasks/chains")

        self.connects_to_task_id = task_id
        self.connects_to_chain_id = chain_id
        return self

    def get_tasks(self) -> List[str]:
        """
        Get the list of task IDs in this chain.

        Returns:
            List of task IDs
        """
        return self.tasks.copy()

    def is_critical(self) -> bool:
        """
        Check if this is a critical chain.

        Returns:
            True if this is a critical chain, False otherwise
        """
        return self.type == "critical"

    def is_feeding(self) -> bool:
        """
        Check if this is a feeding chain.

        Returns:
            True if this is a feeding chain, False otherwise
        """
        return self.type == "feeding"

    def set_buffer(self, buffer_obj: Any) -> "Chain":
        """
        Set the buffer associated with this chain.

        Args:
            buffer_obj: Buffer object to associate with this chain

        Returns:
            self: For method chaining
        """
        self.buffer = buffer_obj
        return self

    def set_buffer_strategy(self, strategy: Any) -> "Chain":
        """
        Set the buffer calculation strategy for this chain.

        Args:
            strategy: Buffer calculation strategy object

        Returns:
            self: For method chaining
        """
        self.buffer_strategy = strategy
        return self

    def update_status(
        self, tasks_dict: Dict[str, Any], status_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Update chain status based on its tasks.

        Args:
            tasks_dict: Dictionary mapping task IDs to Task objects
            status_date: Status date (defaults to now)

        Returns:
            dict: Status information including completion percentage

        Raises:
            ChainError: If tasks_dict is None or not a dictionary
        """
        if tasks_dict is None or not isinstance(tasks_dict, dict):
            raise ChainError("Tasks dictionary cannot be None and must be a dictionary")

        if status_date is None:
            status_date = datetime.now()

        # Set status date
        self.status_date = status_date

        # Calculate chain completion
        total_duration = 0
        completed_duration = 0

        for task_id in self.tasks:
            if task_id in tasks_dict:
                task = tasks_dict[task_id]

                # Get task duration
                task_duration = getattr(task, "duration", 0)
                if hasattr(task, "planned_duration"):
                    task_duration = task.planned_duration

                total_duration += task_duration

                # Debug print
                print(f"Task {task_id}: duration={task_duration}")

                # Calculate completed duration
                task_completed = 0
                if hasattr(task, "status"):
                    print(f"  - has status: {task.status}")
                    if task.status == "completed":
                        # Task is complete
                        task_completed = task_duration
                        print(f"  - completed: {task_completed}")
                    elif task.status == "in_progress":
                        # Task is in progress - use completion percentage
                        print(f"  - in progress")
                        if hasattr(task, "get_progress_percentage"):
                            print(f"  - has get_progress_percentage method")
                            # Check if it's callable
                            if callable(getattr(task, "get_progress_percentage")):
                                progress_pct = task.get_progress_percentage() / 100
                                task_completed = task_duration * progress_pct
                                print(
                                    f"  - progress: {progress_pct*100}%, completed: {task_completed}"
                                )
                            else:
                                print(f"  - get_progress_percentage is not callable")
                        else:
                            print(f"  - no get_progress_percentage method")

                        if hasattr(task, "remaining_duration"):
                            print(
                                f"  - has remaining_duration: {task.remaining_duration}"
                            )
                            completed_work = task_duration - task.remaining_duration
                            print(
                                f"  - completed work based on remaining: {completed_work}"
                            )
                            if (
                                task_completed == 0
                            ):  # Only use if no progress percentage
                                task_completed = completed_work
                        else:
                            print(f"  - no remaining_duration")

                completed_duration += task_completed
                print(f"  - added to completed_duration: {task_completed}")

        # Calculate completion percentage
        if total_duration > 0:
            self.completion_percentage = (completed_duration / total_duration) * 100
        else:
            self.completion_percentage = 0

        # Add to status history
        self.status_history.append(
            {
                "date": status_date,
                "completion_percentage": self.completion_percentage,
                "total_duration": total_duration,
                "completed_duration": completed_duration,
            }
        )

        return {
            "date": status_date,
            "completion_percentage": self.completion_percentage,
            "total_duration": total_duration,
            "completed_duration": completed_duration,
        }

    def get_buffer_consumption(self) -> float:
        """
        Get the buffer consumption percentage for this chain.

        Returns:
            float: Buffer consumption percentage (0-100) or 0 if no buffer
        """
        if self.buffer is None:
            return 0

        if hasattr(self.buffer, "get_consumption_percentage"):
            return self.buffer.get_consumption_percentage()
        elif hasattr(self.buffer, "size") and hasattr(self.buffer, "remaining_size"):
            if self.buffer.size == 0:
                return 0
            consumed = self.buffer.size - self.buffer.remaining_size
            return (consumed / self.buffer.size) * 100

        return 0

    def get_performance_index(self) -> float:
        """
        Calculate the performance index (ratio of completion % to buffer consumption %).

        Returns:
            float: Performance index (>1 is good, <1 is concerning)
        """
        buffer_consumption = self.get_buffer_consumption()

        if buffer_consumption == 0:
            return float("inf")  # Perfect performance if no buffer consumed

        return self.completion_percentage / buffer_consumption

    def get_cumulative_flow_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tasks_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate data for a cumulative flow diagram for this chain.

        Args:
            start_date: Start date for the diagram
            end_date: End date for the diagram
            tasks_dict: Dictionary of tasks keyed by ID

        Returns:
            dict: Data formatted for a cumulative flow diagram
        """
        if tasks_dict is None or not self.tasks:
            return {"dates": [], "status_counts": {}, "completion_percentage": []}

        # Default dates if not provided
        if start_date is None:
            # Find earliest start date of any task in the chain
            start_dates = []
            for task_id in self.tasks:
                if task_id in tasks_dict:
                    task = tasks_dict[task_id]
                    if hasattr(task, "start_date") and task.start_date:
                        start_dates.append(task.start_date)

            start_date = min(start_dates) if start_dates else datetime.now()

        if end_date is None:
            # Find latest end date of any task in the chain
            end_dates = []
            for task_id in self.tasks:
                if task_id in tasks_dict:
                    task = tasks_dict[task_id]
                    if hasattr(task, "actual_end_date") and task.actual_end_date:
                        end_dates.append(task.actual_end_date)
                    elif hasattr(task, "end_date") and task.end_date:
                        end_dates.append(task.end_date)

            end_date = max(end_dates) if end_dates else datetime.now()
            end_date = max(end_date, datetime.now())

        # Generate list of all dates in the range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Initialize data structures
        status_counts = {
            "planned": [0] * len(dates),
            "in_progress": [0] * len(dates),
            "completed": [0] * len(dates),
            "on_hold": [0] * len(dates),
            "cancelled": [0] * len(dates),
        }

        completion_percentage = [0] * len(dates)

        # For each date, count tasks in each status
        for i, date in enumerate(dates):
            # Calculate status counts for this date
            for task_id in self.tasks:
                if task_id not in tasks_dict:
                    continue

                task = tasks_dict[task_id]

                # Determine task status on this date
                task_status = "planned"  # Default status

                # Check if task has started by this date
                if (
                    hasattr(task, "actual_start_date")
                    and task.actual_start_date is not None
                ):
                    if task.actual_start_date <= date:
                        # Task has started by this date

                        # Check if task has completed by this date
                        if (
                            hasattr(task, "actual_end_date")
                            and task.actual_end_date is not None
                            and task.actual_end_date <= date
                        ):
                            task_status = "completed"
                        else:
                            # Task has started but not completed
                            task_status = "in_progress"

                            # Check if task is on hold
                            if hasattr(task, "status") and task.status == "on_hold":
                                task_status = "on_hold"

                # For historical dates, try to determine from progress history
                if hasattr(task, "progress_history") and task.progress_history:
                    # Find the most recent status update before or on this date
                    for entry in reversed(task.progress_history):
                        if entry["date"] <= date and "status" in entry:
                            task_status = entry["status"]
                            break

                # Increment counter for this status
                if task_status in status_counts:
                    status_counts[task_status][i] += 1

            # Calculate completion percentage for this date
            if self.status_history:
                # Find the most recent status update before or on this date
                for entry in reversed(self.status_history):
                    if entry["date"] <= date:
                        completion_percentage[i] = entry["completion_percentage"]
                        break

        return {
            "dates": date_strs,
            "status_counts": status_counts,
            "completion_percentage": completion_percentage,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert chain to a dictionary representation.

        Returns:
            dict: Dictionary representation of the chain
        """
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "buffer_ratio": self.buffer_ratio,
            "tasks": self.tasks.copy(),
            "connects_to_task_id": self.connects_to_task_id,
            "connects_to_chain_id": self.connects_to_chain_id,
            "completion_percentage": self.completion_percentage,
        }

        # Add buffer information if available
        if self.buffer:
            if hasattr(self.buffer, "id"):
                result["buffer_id"] = self.buffer.id

            if hasattr(self.buffer, "size"):
                result["buffer_size"] = self.buffer.size

        # Add strategy information if available
        if self.buffer_strategy and hasattr(self.buffer_strategy, "get_name"):
            result["buffer_strategy"] = self.buffer_strategy.get_name()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chain":
        """
        Create a chain from a dictionary representation.

        Args:
            data: Dictionary representation of the chain

        Returns:
            Chain: New chain instance
        """
        chain = cls(
            id=data["id"],
            name=data["name"],
            type=data.get("type", "feeding"),
            buffer_ratio=data.get("buffer_ratio", 0.3),
        )

        # Set additional attributes
        if "tasks" in data:
            chain.tasks = data["tasks"].copy()

        if "connects_to_task_id" in data:
            chain.connects_to_task_id = data["connects_to_task_id"]

        if "connects_to_chain_id" in data:
            chain.connects_to_chain_id = data["connects_to_chain_id"]

        if "completion_percentage" in data:
            chain.completion_percentage = data["completion_percentage"]

        return chain

    def __repr__(self) -> str:
        """
        Get string representation of the chain.

        Returns:
            str: String representation
        """
        tasks_str = ", ".join(str(t) for t in self.tasks)
        return f"Chain(id={self.id}, name={self.name}, type={self.type}, tasks=[{tasks_str}])"
