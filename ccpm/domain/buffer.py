from datetime import datetime, timedelta


class Buffer:
    def __init__(
        self, id, name, size, buffer_type, connected_to=None, strategy_name=None
    ):
        self.id = id
        self.name = name
        self.size = size  # Size in days
        self.buffer_type = buffer_type  # "project" or "feeding"
        self.connected_to = connected_to  # For feeding buffers, ID of critical task
        self.strategy_name = strategy_name  # Name of the calculation strategy used

        self.original_size = size  # Keep track of the original size
        self.remaining_size = size  # Track consumption
        self.consumption_history = []  # For tracking consumption over time

        # Schedule attributes
        self.start_date = None
        self.end_date = None
        self.new_start_date = None
        self.new_end_date = None

    def consume(self, amount, status_date, reason=None):
        """Consume a portion of the buffer"""
        if amount < 0:
            raise ValueError("Cannot consume negative amount of buffer")

        # Calculate remaining after consumption
        new_remaining = max(0, self.remaining_size - amount)
        consumed = self.remaining_size - new_remaining

        # Update buffer state
        old_remaining = self.remaining_size
        self.remaining_size = new_remaining

        # Record consumption
        self.consumption_history.append(
            {
                "date": status_date,
                "consumed": consumed,
                "old_remaining": old_remaining,
                "new_remaining": new_remaining,
                "reason": reason,
            }
        )

        return consumed

    def get_consumption_percentage(self):
        """Calculate percentage of buffer consumed"""
        if self.original_size == 0:
            return 0

        consumed = self.original_size - self.remaining_size
        return (consumed / self.original_size) * 100

    def get_effective_start_date(self):
        """Get the effective start date"""
        return (
            self.new_start_date
            if hasattr(self, "new_start_date") and self.new_start_date
            else self.start_date
        )

    def get_effective_end_date(self):
        """Get the effective end date"""
        return (
            self.new_end_date
            if hasattr(self, "new_end_date") and self.new_end_date
            else self.end_date
        )
