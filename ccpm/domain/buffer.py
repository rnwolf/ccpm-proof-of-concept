from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union


class BufferError(Exception):
    """Exception raised for errors in the Buffer class."""

    pass


class Buffer:
    """
    Represents a buffer in a Critical Chain Project Management (CCPM) system.

    Buffers protect against uncertainty by providing time reserves. They can be:
    - Project Buffer: Protects the entire project completion date
    - Feeding Buffer: Protects the critical chain from delays in feeding chains
    """

    def __init__(
        self,
        id: str,
        name: str,
        size: float,
        buffer_type: str,
        connected_to: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ):
        """
        Initialize a new Buffer.

        Args:
            id: Unique identifier for the buffer
            name: Name/description of the buffer
            size: Size of the buffer in days
            buffer_type: Type of buffer ("project" or "feeding")
            connected_to: ID of the task this buffer protects (for feeding buffers)
            strategy_name: Name of the calculation strategy used

        Raises:
            BufferError: If any input validation fails
        """
        # Validate id
        if id is None or str(id).strip() == "":
            raise BufferError("Buffer ID cannot be None or empty")
        self.id = id

        # Validate name
        if not name or not isinstance(name, str):
            raise BufferError("Buffer name must be a non-empty string")
        self.name = name

        # Validate size
        if not isinstance(size, (int, float)):
            raise BufferError("Buffer size must be a number")
        if size < 0:
            raise BufferError("Buffer size cannot be negative")
        self.size = float(size)

        # Validate buffer_type
        if buffer_type not in ["project", "feeding"]:
            raise BufferError("Buffer type must be either 'project' or 'feeding'")
        self.buffer_type = buffer_type

        # Validate connected_to for feeding buffers
        if buffer_type == "feeding" and (
            connected_to is None or str(connected_to).strip() == ""
        ):
            raise BufferError("Feeding buffers must specify connected_to task ID")
        self.connected_to = connected_to

        self.strategy_name = strategy_name

        # Initialize tracking attributes
        self.original_size = self.size
        self.remaining_size = self.size
        self.consumption_history = []

        # Schedule attributes
        self.start_date = None
        self.end_date = None
        self.new_start_date = None
        self.new_end_date = None

        # Status tracking
        self.status_date = None
        self.status = "green"  # green, yellow, red

        # Notes functionality
        self.notes = []

    def consume(
        self, amount: float, status_date: datetime, reason: Optional[str] = None
    ) -> float:
        """
        Consume a portion of the buffer.

        Args:
            amount: Amount to consume in days
            status_date: The date of this consumption
            reason: Optional reason for consumption

        Returns:
            float: Amount actually consumed

        Raises:
            BufferError: If amount is negative
        """
        if amount < 0:
            raise BufferError("Cannot consume negative amount of buffer")

        # Calculate remaining after consumption
        new_remaining = max(0, self.remaining_size - amount)
        consumed = self.remaining_size - new_remaining

        # Update buffer state
        old_remaining = self.remaining_size
        self.remaining_size = new_remaining
        self.status_date = status_date

        # Update status based on consumption percentage
        consumption_pct = self.get_consumption_percentage()
        if consumption_pct >= 67:
            self.status = "red"
        elif consumption_pct >= 33:
            self.status = "yellow"
        else:
            self.status = "green"

        # Record consumption
        self.consumption_history.append(
            {
                "date": status_date,
                "consumed": consumed,
                "old_remaining": old_remaining,
                "new_remaining": new_remaining,
                "consumption_percentage": consumption_pct,
                "reason": reason,
                "status": self.status,
            }
        )

        return consumed

    def add(
        self, amount: float, status_date: datetime, reason: Optional[str] = None
    ) -> float:
        """
        Add size to the buffer (e.g., when replanning).

        Args:
            amount: Amount to add in days
            status_date: The date of this addition
            reason: Optional reason for addition

        Returns:
            float: New size of the buffer

        Raises:
            BufferError: If amount is negative
        """
        if amount < 0:
            raise BufferError("Cannot add negative amount to buffer")

        # Update buffer state
        old_size = self.size
        old_remaining = self.remaining_size

        self.size += amount
        self.remaining_size += amount
        self.status_date = status_date

        # Record the change
        self.consumption_history.append(
            {
                "date": status_date,
                "action": "add",
                "amount": amount,
                "old_size": old_size,
                "new_size": self.size,
                "old_remaining": old_remaining,
                "new_remaining": self.remaining_size,
                "reason": reason,
            }
        )

        return self.size

    def reset(self, status_date: datetime, reason: Optional[str] = None) -> float:
        """
        Reset buffer consumption (e.g., after replanning).

        Args:
            status_date: The date of this reset
            reason: Optional reason for reset

        Returns:
            float: Amount of buffer restored
        """
        old_remaining = self.remaining_size
        restored = self.size - old_remaining

        self.remaining_size = self.size
        self.status_date = status_date
        self.status = "green"

        # Record the reset
        self.consumption_history.append(
            {
                "date": status_date,
                "action": "reset",
                "restored": restored,
                "old_remaining": old_remaining,
                "new_remaining": self.size,
                "reason": reason,
            }
        )

        return restored

    def get_consumption_percentage(self) -> float:
        """
        Calculate percentage of buffer consumed.

        Returns:
            float: Percentage consumed (0-100)
        """
        if self.size == 0:
            return 0

        consumed = self.size - self.remaining_size
        return (consumed / self.size) * 100

    def get_effective_start_date(self) -> Optional[datetime]:
        """
        Get the effective start date.

        Returns:
            datetime: Effective start date or None
        """
        return (
            self.new_start_date
            if hasattr(self, "new_start_date") and self.new_start_date
            else self.start_date
        )

    def get_effective_end_date(self) -> Optional[datetime]:
        """
        Get the effective end date.

        Returns:
            datetime: Effective end date or None
        """
        return (
            self.new_end_date
            if hasattr(self, "new_end_date") and self.new_end_date
            else self.end_date
        )

    def add_note(self, text: str, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Add a timestamped note to the buffer.

        Args:
            text: Note text
            date: Date of the note (defaults to now)

        Returns:
            dict: The added note

        Raises:
            BufferError: If text is not a string
        """
        if not isinstance(text, str):
            raise BufferError("Note text must be a string")

        if date is None:
            date = datetime.now()

        note = {"date": date, "text": text}
        self.notes.append(note)

        return note

    def get_notes(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
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

    def get_cumulative_flow_data(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate data for a cumulative flow diagram showing buffer consumption over time.

        Args:
            start_date: Start date for the diagram
            end_date: End date for the diagram

        Returns:
            dict: Data formatted for a cumulative flow diagram
        """
        # Set default start date if not provided
        if start_date is None:
            # Use earliest consumption date or buffer start date
            dates = []

            if self.consumption_history:
                dates.append(min(entry["date"] for entry in self.consumption_history))

            if self.start_date:
                dates.append(self.start_date)

            if hasattr(self, "new_start_date") and self.new_start_date:
                dates.append(self.new_start_date)

            start_date = min(dates) if dates else datetime.now()

        # Set default end date if not provided
        if end_date is None:
            # Use latest consumption date, buffer end date, or today
            dates = []

            if self.consumption_history:
                dates.append(max(entry["date"] for entry in self.consumption_history))

            if hasattr(self, "end_date") and self.end_date:
                dates.append(self.end_date)

            if hasattr(self, "new_end_date") and self.new_end_date:
                dates.append(self.new_end_date)

            end_date = max(dates) if dates else datetime.now()
            end_date = max(end_date, datetime.now())

        # Generate list of all dates in the range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Initialize data structures
        remaining = [0] * len(dates)
        consumed = [0] * len(dates)
        status = [""] * len(dates)

        # Create sorted consumption events
        events = (
            sorted(self.consumption_history, key=lambda x: x["date"])
            if self.consumption_history
            else []
        )

        # For each date, calculate buffer state
        current_remaining = self.original_size
        current_consumed = 0
        current_status = "green"

        for i, date in enumerate(dates):
            # Find all consumption events up to this date
            while events and events[0]["date"] <= date:
                event = events.pop(0)
                if "new_remaining" in event:
                    current_remaining = event["new_remaining"]
                    current_consumed = self.original_size - current_remaining
                if "status" in event:
                    current_status = event["status"]

            # Record state for this date
            remaining[i] = current_remaining
            consumed[i] = current_consumed
            status[i] = current_status

        return {
            "dates": date_strs,
            "remaining": remaining,
            "consumed": consumed,
            "status": status,
            "original_size": self.original_size,
        }

    def get_fever_chart_data(self, project_completion_pct: float) -> Dict[str, Any]:
        """
        Generate data for a fever chart (buffer consumption vs project completion).

        Args:
            project_completion_pct: Current project completion percentage

        Returns:
            dict: Data for fever chart plotting
        """
        consumption_pct = self.get_consumption_percentage()

        # Get consumption history for trend analysis
        history_points = []

        for entry in self.consumption_history:
            if "consumption_percentage" in entry:
                # For each history point, we need project completion %
                # This is approximate since we don't have the exact project completion for past dates
                history_points.append(
                    {
                        "date": entry["date"],
                        "buffer_consumption": entry["consumption_percentage"],
                        # Since we don't have historical project completion %, we'll leave it empty
                        # The scheduler would need to fill this in
                        "project_completion": None,
                    }
                )

        # Determine status zones
        if consumption_pct < 33:
            zone = "green"
        elif consumption_pct < 67:
            zone = "yellow"
        else:
            zone = "red"

        # Calculate performance ratio
        if consumption_pct == 0:
            performance_ratio = float("inf")  # Perfect performance
        else:
            performance_ratio = project_completion_pct / consumption_pct

        return {
            "current_point": {
                "project_completion": project_completion_pct,
                "buffer_consumption": consumption_pct,
            },
            "history_points": history_points,
            "zone": zone,
            "performance_ratio": performance_ratio,
            "original_size": self.original_size,
            "remaining": self.remaining_size,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert buffer to a dictionary representation.

        Returns:
            dict: Dictionary representation of the buffer
        """
        result = {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "buffer_type": self.buffer_type,
            "connected_to": self.connected_to,
            "strategy_name": self.strategy_name,
            "original_size": self.original_size,
            "remaining_size": self.remaining_size,
            "status": self.status,
        }

        # Add dates if available
        for attr in [
            "start_date",
            "end_date",
            "new_start_date",
            "new_end_date",
            "status_date",
        ]:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                result[attr] = getattr(self, attr)

        # Add consumption history (but trim for size)
        if self.consumption_history:
            # Include first, last, and critical events
            if len(self.consumption_history) <= 5:
                result["consumption_history"] = self.consumption_history
            else:
                # Include first, last, and key events where status changed
                first = self.consumption_history[0]
                last = self.consumption_history[-1]
                key_events = [
                    e
                    for e in self.consumption_history[1:-1]
                    if "status" in e and e.get("status") != first.get("status")
                ]

                # Take up to 3 key events to keep size reasonable
                key_events = sorted(key_events, key=lambda x: x["date"])[:3]

                result["consumption_history"] = [first] + key_events + [last]
                result["consumption_history_truncated"] = True

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Buffer":
        """
        Create a buffer from a dictionary representation.

        Args:
            data: Dictionary representation of the buffer

        Returns:
            Buffer: New buffer instance
        """
        buffer = cls(
            id=data["id"],
            name=data["name"],
            size=data["size"],
            buffer_type=data["buffer_type"],
            connected_to=data.get("connected_to"),
            strategy_name=data.get("strategy_name"),
        )

        # Set additional attributes
        for attr in ["original_size", "remaining_size", "status"]:
            if attr in data:
                setattr(buffer, attr, data[attr])

        # Set dates if available
        for attr in [
            "start_date",
            "end_date",
            "new_start_date",
            "new_end_date",
            "status_date",
        ]:
            if attr in data:
                setattr(buffer, attr, data[attr])

        # Set consumption history if available
        if "consumption_history" in data:
            buffer.consumption_history = data["consumption_history"]

        return buffer

    def __repr__(self) -> str:
        """
        Get string representation of the buffer.

        Returns:
            str: String representation
        """
        consumed = self.original_size - self.remaining_size
        consumption_pct = self.get_consumption_percentage()

        return (
            f"Buffer(id={self.id}, name={self.name}, "
            f"type={self.buffer_type}, size={self.size}, "
            f"consumed={consumed:.1f} ({consumption_pct:.1f}%), "
            f"status={self.status})"
        )
