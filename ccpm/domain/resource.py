from datetime import datetime, timedelta


class ResourceOverallocationError(ValueError):
    """Exception raised when trying to allocate more resource units than available."""

    pass


class Resource:
    """
    Represents a resource that can be assigned to tasks in a project.
    Resources have availability tracking and allocation methods.
    """

    def __init__(
        self, id, name, capacity=1, calendar=None, allow_overallocation=False, tags=None
    ):
        """
        Initialize a resource with id, name, and capacity.

        Args:
            id: Unique identifier for the resource
            name: Human-readable name for the resource
            capacity: Maximum units of this resource available (default: 1)
            calendar: Optional calendar of availability (defaults to all days available)
            allow_overallocation: Whether to allow allocations beyond capacity (default: False)
            tags: List of tags associated with this resource (default: empty list)
        """
        # Resource identification
        self.id = id
        self.name = name
        self.tags = tags or []  # Store tags as a list of strings

        # Resource capacity and availability
        self.capacity = capacity
        self.calendar = calendar if calendar else {}  # Format: {date: available_units}
        self.allow_overallocation = allow_overallocation

        # Usage tracking
        self.allocations = {}  # Format: {date: {task_id: units}}
        self.utilization_history = []  # For tracking utilization over time
        self.overallocations = {}  # Format: {date: over_allocated_units}

        # Flow tracking (for cumulative flow diagram)
        self.arrivals = []  # Format: [{date, task_id, state}]
        self.departures = []  # Format: [{date, task_id, state}]
        self.work_in_progress = {}  # Format: {date: {task_id: state}}

        # Add tracking for planned assignments
        self.planned_assignments = {}  # Format: {task_id: {'planned_start': date, 'planned_end': date}}

    def deallocate(self, task_id, date):
        """
        Remove an allocation for a task on a specific date.

        Args:
            task_id: ID of the task to deallocate
            date: Date for the deallocation

        Returns:
            float: Units deallocated, or 0 if no allocation existed
        """
        date_str = date.strftime("%Y-%m-%d")

        # Check if there's an allocation to remove
        if date_str in self.allocations and task_id in self.allocations[date_str]:
            units = self.allocations[date_str].pop(task_id)

            # Clean up empty allocations
            if not self.allocations[date_str]:
                del self.allocations[date_str]

            # Record in history
            self.utilization_history.append(
                {
                    "date": date,
                    "task_id": task_id,
                    "units": -units,  # Negative to indicate deallocation
                    "remaining_capacity": self.get_available_capacity(date) + units,
                }
            )

            return units

        return 0

    def is_available_for_period(self, start_date, end_date, units=1):
        """
        Check if resource is available for a continuous period.

        Args:
            start_date: Start date of the period
            end_date: End date of the period (inclusive)
            units: Units needed for each day (default: 1)

        Returns:
            bool: True if resource is available for the entire period
        """
        current_date = start_date
        while current_date <= end_date:
            if self.get_available_capacity(current_date) < units:
                return False
            current_date += timedelta(days=1)

        return True

    def get_utilization_for_period(self, start_date, end_date):
        """
        Calculate resource utilization for a period.

        Args:
            start_date: Start date of the period
            end_date: End date of the period (inclusive)

        Returns:
            dict: Daily utilization {date_str: percentage}
        """
        utilization = {}
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            # Get total capacity for this date
            total_capacity = self.calendar.get(date_str, self.capacity)

            if total_capacity > 0:
                # Get existing allocations for this date
                date_allocations = self.allocations.get(date_str, {})
                allocated_capacity = sum(date_allocations.values())

                # Calculate utilization percentage
                utilization[date_str] = (allocated_capacity / total_capacity) * 100
            else:
                # Handle case where capacity is 0 (e.g., holiday)
                utilization[date_str] = 0

            current_date += timedelta(days=1)

        return utilization

    def set_calendar(self, calendar):
        """
        Set the availability calendar for this resource.

        Args:
            calendar: Dict mapping dates to available capacity {date_str: capacity}
        """
        self.calendar = calendar

    def add_calendar_exception(self, date, capacity):
        """
        Add or update a calendar exception for a specific date.

        Args:
            date: The date to set capacity for
            capacity: Available capacity on this date
        """
        date_str = date.strftime("%Y-%m-%d")
        self.calendar[date_str] = capacity

    def deallocate_for_task(self, task_id, start_date=None, end_date=None):
        """
        Remove all allocations for a specific task, optionally within a date range.

        Args:
            task_id: ID of the task to deallocate
            start_date: Optional start date of the deallocation period
            end_date: Optional end date of the deallocation period

        Returns:
            int: Number of days deallocated
        """
        days_deallocated = 0

        # Copy allocations dict to avoid modification during iteration
        allocations_copy = dict(self.allocations)

        for date_str, task_allocations in allocations_copy.items():
            if task_id in task_allocations:
                # Convert date string to datetime for range check
                alloc_date = datetime.strptime(date_str, "%Y-%m-%d")

                # Check if date is within specified range (if provided)
                in_range = True
                if start_date and alloc_date < start_date:
                    in_range = False
                if end_date and alloc_date > end_date:
                    in_range = False

                if in_range:
                    # Deallocate this day
                    self.deallocate(task_id, alloc_date)
                    days_deallocated += 1

        return days_deallocated

    def get_allocated_tasks(self, date):
        """
        Get all tasks allocated to this resource on a specific date.

        Args:
            date: The date to check allocations for

        Returns:
            dict: Task IDs and allocation units {task_id: units}
        """
        date_str = date.strftime("%Y-%m-%d")
        return self.allocations.get(date_str, {}).copy()

    def get_available_capacity(self, date):
        """
        Get the available capacity for this resource on a specific date.

        Args:
            date: The date to check availability

        Returns:
            float: Available units of this resource
        """
        # Get total capacity for this date (default to standard capacity)
        date_str = date.strftime("%Y-%m-%d")
        total_capacity = self.calendar.get(date_str, self.capacity)

        # Get existing allocations for this date
        date_allocations = self.allocations.get(date_str, {})
        allocated_capacity = sum(date_allocations.values())

        # Calculate available capacity
        return max(0, total_capacity - allocated_capacity)

    def allocate(self, task_id, date, units=1):
        """
        Allocate this resource to a task on a specific date.

        Args:
            task_id: ID of the task to allocate to
            date: Date for the allocation
            units: Units to allocate (default: 1)

        Returns:
            bool: True if allocation succeeded, False if insufficient capacity

        Raises:
            ValueError: If allocation would exceed capacity and overallocation is not allowed
        """
        date_str = date.strftime("%Y-%m-%d")

        # Check if there's enough available capacity
        available = self.get_available_capacity(date)

        # Handle over-allocation case
        if units > available and not self.allow_overallocation:
            raise ValueError(
                f"Cannot allocate {units} units to task {task_id} on {date_str}. "
                f"Only {available} units available."
            )

        # Initialize allocations for this date if needed
        if date_str not in self.allocations:
            self.allocations[date_str] = {}

        # Add allocation
        self.allocations[date_str][task_id] = units

        # Track over-allocation if applicable
        overallocated_units = max(0, allocated_capacity + units - total_capacity)
        if overallocated_units > 0:
            self.overallocations[date_str] = overallocated_units

            # Record the over-allocation in history
            self.utilization_history.append(
                {
                    "date": date,
                    "task_id": task_id,
                    "units": units,
                    "remaining_capacity": available - units,
                    "overallocated": True,
                    "overallocated_units": overallocated_units,
                }
            )
        else:
            # Record normal allocation in history
            self.utilization_history.append(
                {
                    "date": date,
                    "task_id": task_id,
                    "units": units,
                    "remaining_capacity": available - units,
                    "overallocated": False,
                }
            )

        return True

    def is_overallocated(self, date=None, start_date=None, end_date=None):
        """
        Check if this resource is overallocated on a specific date or period.

        Args:
            date: Specific date to check (optional)
            start_date: Start of period to check (optional)
            end_date: End of period to check (optional)

        Returns:
            bool: True if resource is overallocated in the specified timeframe
        """
        # For a single date
        if date:
            date_str = date.strftime("%Y-%m-%d")
            return date_str in self.overallocations

        # For a period
        if start_date and end_date:
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str in self.overallocations:
                    return True
                current_date += timedelta(days=1)

        # Default to checking all dates
        return bool(self.overallocations)

    def get_overallocation_report(self, start_date=None, end_date=None):
        """
        Generate a report of overallocations for this resource.

        Args:
            start_date: Start date of the period to report (optional)
            end_date: End date of the period to report (optional)

        Returns:
            dict: Report of overallocations by date
        """
        report = {}

        # If no dates specified, use all overallocations
        if not start_date and not end_date:
            for date_str, units in self.overallocations.items():
                date = datetime.strptime(date_str, "%Y-%m-%d")

                # Get tasks allocated on this date
                tasks = {}
                for task_id, task_units in self.allocations.get(date_str, {}).items():
                    tasks[task_id] = task_units

                # Add to report
                report[date_str] = {
                    "date": date,
                    "overallocated_units": units,
                    "total_allocated": sum(tasks.values()),
                    "capacity": self.calendar.get(date_str, self.capacity),
                    "tasks": tasks,
                }
        else:
            # Filter by date range
            start = start_date or datetime.min
            end = end_date or datetime.max

            for date_str, units in self.overallocations.items():
                date = datetime.strptime(date_str, "%Y-%m-%d")

                if start <= date <= end:
                    # Get tasks allocated on this date
                    tasks = {}
                    for task_id, task_units in self.allocations.get(
                        date_str, {}
                    ).items():
                        tasks[task_id] = task_units

                    # Add to report
                    report[date_str] = {
                        "date": date,
                        "overallocated_units": units,
                        "total_allocated": sum(tasks.values()),
                        "capacity": self.calendar.get(date_str, self.capacity),
                        "tasks": tasks,
                    }

        return report

    def allocate_for_task_duration(self, task_id, start_date, duration, units=1):
        """
        Allocate this resource for the entire duration of a task.

        Args:
            task_id: ID of the task to allocate to
            start_date: Start date of the allocation
            duration: Number of days to allocate for
            units: Units to allocate per day (default: 1)

        Returns:
            bool: True if allocation succeeded for the entire period

        Raises:
            ValueError: If allocation would exceed capacity on any day and overallocation is not allowed
        """
        end_date = start_date + timedelta(days=duration - 1)

        # First check if resource is available for the entire period (if not allowing overallocation)
        if not self.allow_overallocation and not self.is_available_for_period(
            start_date, end_date, units
        ):
            raise ValueError(
                f"Resource {self.name} is not available for the entire period "
                f"from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )

        # Allocate for each day in the period
        current_date = start_date
        allocations_made = []

        try:
            while current_date <= end_date:
                self.allocate(task_id, current_date, units)
                allocations_made.append(current_date)
                current_date += timedelta(days=1)
            return True
        except Exception as e:
            # If any allocation fails and we don't allow overallocation, roll back
            if not self.allow_overallocation:
                for date in allocations_made:
                    self.deallocate(task_id, date)
                raise e
            return True  # With overallocation allowed, return success despite issues

    def add_tag(self, tag):
        """Add a tag to this resource if it doesn't already exist"""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove a tag from this resource if it exists"""
        if tag in self.tags:
            self.tags.remove(tag)

    def has_tag(self, tag):
        """Check if this resource has a specific tag"""
        return tag in self.tags

    def filter_by_tags(self, tags):
        """
        Check if this resource has all the specified tags

        Args:
            tags: List of tags to check for

        Returns:
            bool: True if resource has all the specified tags
        """
        return all(tag in self.tags for tag in tags)

    def record_arrival(self, task_id, date, state="in_progress"):
        """
        Record a task arrival (work started on this resource)

        Args:
            task_id: ID of the task that arrived
            date: Date when the work arrived
            state: State of the work (default: "in_progress")
        """
        self.arrivals.append({"date": date, "task_id": task_id, "state": state})

        # Update work in progress
        date_str = date.strftime("%Y-%m-%d")
        if date_str not in self.work_in_progress:
            self.work_in_progress[date_str] = {}

        self.work_in_progress[date_str][task_id] = state

    def record_departure(self, task_id, date, state="completed"):
        """
        Record a task departure (work completed on this resource)

        Args:
            task_id: ID of the task that departed
            date: Date when the work departed
            state: Final state of the work (default: "completed")
        """
        self.departures.append({"date": date, "task_id": task_id, "state": state})

        # Update work in progress (remove the task)
        date_str = date.strftime("%Y-%m-%d")

        # Create a copy of all previous dates' WIP for this date
        if date_str not in self.work_in_progress:
            # Find the most recent date before this one
            previous_dates = [
                d
                for d in self.work_in_progress.keys()
                if datetime.strptime(d, "%Y-%m-%d") < date
            ]

            if previous_dates:
                latest_previous = max(
                    previous_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d")
                )
                self.work_in_progress[date_str] = dict(
                    self.work_in_progress[latest_previous]
                )
            else:
                self.work_in_progress[date_str] = {}

        # Remove the task from WIP
        if task_id in self.work_in_progress[date_str]:
            del self.work_in_progress[date_str][task_id]

    def update_task_state(self, task_id, date, state):
        """
        Update the state of a task in the work in progress

        Args:
            task_id: ID of the task to update
            date: Date when the state changed
            state: New state of the work
        """
        date_str = date.strftime("%Y-%m-%d")

        # Create a copy of all previous dates' WIP for this date if it doesn't exist
        if date_str not in self.work_in_progress:
            # Find the most recent date before this one
            previous_dates = [
                d
                for d in self.work_in_progress.keys()
                if datetime.strptime(d, "%Y-%m-%d") < date
            ]

            if previous_dates:
                latest_previous = max(
                    previous_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d")
                )
                self.work_in_progress[date_str] = dict(
                    self.work_in_progress[latest_previous]
                )
            else:
                self.work_in_progress[date_str] = {}

        # Update the state
        self.work_in_progress[date_str][task_id] = state

    def analyze_flow_balance(self, start_date, end_date):
        """
        Analyze whether the flow is balanced (arrivals ≈ departures)

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            dict: Analysis results
                {
                    'is_balanced': bool,
                    'arrival_rate': float,  # items per day
                    'departure_rate': float,  # items per day
                    'wip_trend': str,  # "increasing", "decreasing", or "stable"
                    'recommendation': str
                }
        """
        flow_data = self.get_cumulative_flow_data(start_date, end_date)

        # Calculate rates
        days = (end_date - start_date).days + 1

        arrival_rate = flow_data["arrivals_cumulative"][-1] / days if days > 0 else 0
        departure_rate = (
            flow_data["departures_cumulative"][-1] / days if days > 0 else 0
        )

        # Determine if balanced (within 10%)
        is_balanced = False
        if departure_rate > 0:
            ratio = arrival_rate / departure_rate
            is_balanced = 0.9 <= ratio <= 1.1

        # Determine WIP trend
        wip_trend = "stable"
        if len(flow_data["wip_by_date"]) > 1:
            first_half = flow_data["wip_by_date"][: len(flow_data["wip_by_date"]) // 2]
            second_half = flow_data["wip_by_date"][len(flow_data["wip_by_date"]) // 2 :]

            avg_first = sum(first_half) / len(first_half) if first_half else 0
            avg_second = sum(second_half) / len(second_half) if second_half else 0

            if avg_second > avg_first * 1.1:
                wip_trend = "increasing"
            elif avg_second < avg_first * 0.9:
                wip_trend = "decreasing"

        # Generate recommendation
        recommendation = ""
        if not is_balanced:
            if arrival_rate > departure_rate:
                recommendation = (
                    "Reduce arrival rate or increase departure rate to balance flow."
                )
            else:
                recommendation = (
                    "Resource may be underutilized. Consider increasing arrival rate."
                )
        else:
            recommendation = (
                "Flow is balanced. Maintain current arrival and departure rates."
            )

        # Check for potential constraint
        if wip_trend == "increasing" and arrival_rate > departure_rate:
            recommendation += " This resource may be a constraint in the workflow."

        return {
            "is_balanced": is_balanced,
            "arrival_rate": arrival_rate,
            "departure_rate": departure_rate,
            "wip_trend": wip_trend,
            "recommendation": recommendation,
        }

    def get_cumulative_flow_data(self, start_date, end_date, include_planned=True):
        """
        Generate data for a cumulative flow diagram, including future planned tasks

        Args:
            start_date: Start date for the diagram
            end_date: End date for the diagram
            include_planned: Whether to include future planned tasks (default: True)

        Returns:
            dict: Data formatted for a cumulative flow diagram
                {
                    'dates': [date strings],
                    'arrivals_cumulative': [count],
                    'departures_cumulative': [count],
                    'wip_by_date': [count],
                    'wip_by_state': {state: [counts]},
                    'includes_future': bool  # Whether data includes future projections
                }
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        includes_future = end_date > today

        # Generate list of all dates in the range
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        date_strs = [date.strftime("%Y-%m-%d") for date in dates]

        # Initialize data structures
        arrivals_cumulative = []
        departures_cumulative = []
        wip_by_date = []
        wip_by_state = defaultdict(list)
        all_states = set()

        # Get projected arrivals and departures (if including planned tasks)
        projected_arrivals = []
        projected_departures = []

        if include_planned and includes_future:
            # Collect planned assignments for this resource
            for task_id, dates in self.planned_assignments.items():
                # If the task is scheduled to start on this resource
                if "planned_start" in dates:
                    projected_arrivals.append(
                        {
                            "date": dates["planned_start"],
                            "task_id": task_id,
                            "state": "planned",
                        }
                    )

                # If the task is scheduled to end on this resource
                if "planned_end" in dates:
                    projected_departures.append(
                        {
                            "date": dates["planned_end"],
                            "task_id": task_id,
                            "state": "completed",
                        }
                    )

        # Process each date in the range
        for i, date in enumerate(dates):
            date_str = date_strs[i]
            is_future = date > today

            # ARRIVALS
            # Historical arrivals
            historical_arrival_count = sum(
                1
                for a in self.arrivals
                if a["date"] <= date and a["date"] >= start_date
            )

            # Future arrivals
            future_arrival_count = 0
            if is_future and include_planned:
                future_arrival_count = sum(
                    1
                    for a in projected_arrivals
                    if a["date"] <= date and a["date"] >= today
                )

            # Total arrivals
            total_arrivals = historical_arrival_count
            if is_future and include_planned:
                total_arrivals += future_arrival_count

            arrivals_cumulative.append(total_arrivals)

            # DEPARTURES
            # Historical departures
            historical_departure_count = sum(
                1
                for d in self.departures
                if d["date"] <= date and d["date"] >= start_date
            )

            # Future departures
            future_departure_count = 0
            if is_future and include_planned:
                future_departure_count = sum(
                    1
                    for d in projected_departures
                    if d["date"] <= date and d["date"] >= today
                )

            # Total departures
            total_departures = historical_departure_count
            if is_future and include_planned:
                total_departures += future_departure_count

            departures_cumulative.append(total_departures)

            # WORK IN PROGRESS
            if is_future and include_planned:
                # For future dates, use projected WIP
                # First get actual WIP from the last historical date
                if i > 0 and dates[i - 1] <= today:
                    # Copy WIP from previous date (last historical date)
                    current_wip = self._get_wip_for_date(dates[i - 1]).copy()
                else:
                    # If no previous historical date, start with recorded WIP or empty
                    current_wip = (
                        self._get_wip_for_date(today).copy() if date > today else {}
                    )

                # Add projected arrivals for this date
                for arrival in projected_arrivals:
                    if arrival["date"] == date:
                        current_wip[arrival["task_id"]] = arrival["state"]

                # Remove projected departures for this date
                for departure in projected_departures:
                    if (
                        departure["date"] == date
                        and departure["task_id"] in current_wip
                    ):
                        del current_wip[departure["task_id"]]
            else:
                # For historical dates, use recorded WIP
                current_wip = self._get_wip_for_date(date)

            # Count total WIP
            wip_count = len(current_wip)
            wip_by_date.append(wip_count)

            # Count WIP by state
            state_counts = defaultdict(int)
            for task_id, state in current_wip.items():
                state_counts[state] += 1
                all_states.add(state)

            # Record counts for each state
            for state in all_states:
                if len(wip_by_state[state]) < i:
                    # Fill in previous days if this is a new state
                    wip_by_state[state].extend([0] * (i - len(wip_by_state[state])))

                wip_by_state[state].append(state_counts[state])

        # Ensure all state lists are the same length
        for state in all_states:
            if len(wip_by_state[state]) < len(dates):
                wip_by_state[state].extend(
                    [0] * (len(dates) - len(wip_by_state[state]))
                )

        return {
            "dates": date_strs,
            "arrivals_cumulative": arrivals_cumulative,
            "departures_cumulative": departures_cumulative,
            "wip_by_date": wip_by_date,
            "wip_by_state": dict(wip_by_state),
            "includes_future": includes_future,
        }

    def _get_wip_for_date(self, date):
        """Helper method to get WIP for a specific date, handling missing dates"""
        date_str = date.strftime("%Y-%m-%d")

        # If we have WIP recorded for this date, use it
        if date_str in self.work_in_progress:
            return self.work_in_progress[date_str]

        # Find the most recent date before this one that has WIP data
        previous_dates = [
            d
            for d in self.work_in_progress.keys()
            if datetime.strptime(d, "%Y-%m-%d") < date
        ]

        if previous_dates:
            latest_previous = max(
                previous_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d")
            )
            return self.work_in_progress[latest_previous]

        # If no previous date, return empty dict
        return {}

    def add_planned_assignment(self, task_id, start_date, end_date):
        """
        Add a planned assignment for a future task

        Args:
            task_id: ID of the task
            start_date: Planned start date on this resource
            end_date: Planned end date on this resource
        """
        self.planned_assignments[task_id] = {
            "planned_start": start_date,
            "planned_end": end_date,
        }

    def update_planned_assignment(self, task_id, start_date=None, end_date=None):
        """
        Update a planned assignment

        Args:
            task_id: ID of the task to update
            start_date: New planned start date (optional)
            end_date: New planned end date (optional)
        """
        if task_id not in self.planned_assignments:
            if start_date and end_date:
                self.add_planned_assignment(task_id, start_date, end_date)
            return

        if start_date:
            self.planned_assignments[task_id]["planned_start"] = start_date

        if end_date:
            self.planned_assignments[task_id]["planned_end"] = end_date
            """Helper method to get WIP for a specific date, handling missing dates"""
            date_str = date.strftime("%Y-%m-%d")

            # If we have WIP recorded for this date, use it
            if date_str in self.work_in_progress:
                return self.work_in_progress[date_str]

            # Find the most recent date before this one that has WIP data
            previous_dates = [
                d
                for d in self.work_in_progress.keys()
                if datetime.strptime(d, "%Y-%m-%d") < date
            ]

            if previous_dates:
                latest_previous = max(
                    previous_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d")
                )
                return self.work_in_progress[latest_previous]

            # If no previous date, return empty dict
            return {}
