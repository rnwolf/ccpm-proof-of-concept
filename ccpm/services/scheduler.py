from datetime import datetime, timedelta
import networkx as nx

from ccpm.domain.task import Task
from ccpm.domain.buffer import Buffer
from ccpm.domain.chain import Chain
from ccpm.utils.graph import (
    build_dependency_graph,
    forward_pass,
    backward_pass,
    find_critical_path,
)
from ccpm.services.buffer_strategies import (
    CutAndPasteMethod,
    SumOfSquaresMethod,
    RootSquareErrorMethod,
    AdaptiveBufferMethod,
)

from ccpm.services.critical_chain import (
    identify_critical_chain,
    resolve_resource_conflicts,
)
from ccpm.services.feeding_chain import identify_feeding_chains
from ccpm.services.resource_leveling import level_resources

from ..utils.tag_utils import (
    get_all_tags,
    refresh_all_tags,
    get_resources_by_tags,
    get_tasks_by_tags,
)


class CCPMScheduler:
    def __init__(
        self,
        project_buffer_ratio=0.5,
        default_feeding_buffer_ratio=0.3,
        project_buffer_strategy=None,
        default_feeding_buffer_strategy=None,
        allow_resource_overallocation=False,
    ):
        self.allow_resource_overallocation = allow_resource_overallocation  # Allow over allocation and report on it with a view to topping up capacity
        self.tasks = {}  # Dictionary of Task objects
        self.chains = {}  # Dictionary of Chain objects
        self.buffers = {}  # Dictionary of Buffer objects
        self.resources = []  # List of resource names

        self.project_buffer_ratio = project_buffer_ratio
        self.default_feeding_buffer_ratio = default_feeding_buffer_ratio

        # Set default buffer calculation strategies
        self.project_buffer_strategy = project_buffer_strategy or CutAndPasteMethod()
        self.default_feeding_buffer_strategy = (
            default_feeding_buffer_strategy or SumOfSquaresMethod()
        )

        # Available buffer calculation strategies
        self.buffer_strategies = {
            "cpm": CutAndPasteMethod(),
            "ssq": SumOfSquaresMethod(),
            "rsem": RootSquareErrorMethod(),
            "adaptive": AdaptiveBufferMethod(),
        }

        # The critical chain (special chain)
        self.critical_chain = None

        # Graph representation
        self.task_graph = None

        # Start date
        self.start_date = datetime.now()

        # Current execution date for tracking progress
        self.execution_date = None

    def add_task(self, task):
        """Add a task to the scheduler"""
        self.tasks[task.id] = task
        return self

    def set_resources(self, resources):
        """Set the resources available for the project"""
        self.resources = resources
        return self

    def set_start_date(self, start_date):
        """Set the project start date"""
        self.start_date = start_date
        return self

    def build_dependency_graph(self):
        """Build a directed graph representing task dependencies, including buffers."""
        self.task_graph = build_dependency_graph(self.tasks)
        return self.task_graph

    def calculate_baseline_schedule(self):
        """Calculate the baseline schedule (early/late start/finish)"""
        if not self.task_graph:
            self.build_dependency_graph()

        # Calculate early start/finish
        forward_pass(self.task_graph, self.tasks)

        # Calculate late start/finish and identify critical path
        backward_pass(self.task_graph, self.tasks)

        return self.tasks

    def calculate_critical_chain(self):
        """
        Calculate the critical chain for the project using the service function.
        This method integrates the critical chain service with the scheduler.
        """
        if not self.task_graph:
            self.build_dependency_graph()

        # Calculate schedule if not already done
        if not all(hasattr(task, "early_start") for task in self.tasks.values()):
            self.calculate_baseline_schedule()

        # Use the critical_chain service to identify the critical chain
        self.critical_chain = identify_critical_chain(
            self.tasks, self.resources, self.task_graph
        )

        # Resolve resource conflicts if there are shared resources
        if self.resources:
            resolved_path = resolve_resource_conflicts(
                self.critical_chain.tasks, self.tasks, self.resources, self.task_graph
            )
            # Update critical chain with resolved path
            self.critical_chain.tasks = resolved_path
            # Update chain membership for tasks
            for task_id in self.tasks:
                if task_id in resolved_path:
                    self.tasks[task_id].chain_id = self.critical_chain.id
                    self.tasks[task_id].chain_type = "critical"

        # Add critical chain to chains dictionary
        self.chains[self.critical_chain.id] = self.critical_chain

        # Set buffer strategy
        self.critical_chain.set_buffer_strategy(self.project_buffer_strategy)

        # Calculate project buffer
        critical_tasks = [self.tasks[task_id] for task_id in self.critical_chain.tasks]
        buffer_size = self.project_buffer_strategy.calculate_buffer_size(
            critical_tasks, self.project_buffer_ratio
        )
        buffer_size = round(buffer_size)  # Round to nearest integer

        # Create project buffer
        buffer_id = "PB"
        project_buffer = Buffer(
            id=buffer_id,
            name="Project Buffer",
            size=buffer_size,
            buffer_type="project",
            strategy_name=self.project_buffer_strategy.get_name(),
        )

        # Add to buffers dictionary
        self.buffers[buffer_id] = project_buffer

        # Associate buffer with critical chain
        self.critical_chain.set_buffer(project_buffer)

        # Add buffer to the graph
        last_critical_task = (
            self.critical_chain.tasks[-1] if self.critical_chain.tasks else None
        )
        if last_critical_task and self.task_graph:
            self.task_graph.add_node(
                buffer_id, node_type="buffer", buffer=project_buffer
            )
            self.task_graph.add_edge(last_critical_task, buffer_id)

        return self.critical_chain

    def find_feeding_chains(self):
        """
        Identify feeding chains using the service function.
        This method integrates the feeding_chain service with the scheduler.
        """
        if not self.critical_chain:
            self.calculate_critical_chain()

        # Use the feeding_chain service
        feeding_chains = identify_feeding_chains(
            self.tasks, self.critical_chain, self.task_graph
        )

        # Add feeding chains to scheduler
        for chain in feeding_chains:
            # Set buffer strategy
            chain.set_buffer_strategy(self.default_feeding_buffer_strategy)
            chain.buffer_ratio = self.default_feeding_buffer_ratio

            # Add to dictionary
            self.chains[chain.id] = chain

        return feeding_chains

    def calculate_buffers(self):
        """Calculate all buffers based on chains and their selected strategies"""
        if not self.critical_chain:
            self.calculate_critical_chain()

        # Project buffer should already be calculated in calculate_critical_chain
        # Focus on feeding buffers here
        for chain_id, chain in self.chains.items():
            # Skip critical chain (project buffer already created)
            if chain.type == "critical":
                continue

            # Get tasks in this chain
            chain_tasks = [
                self.tasks[task_id] for task_id in chain.tasks if task_id in self.tasks
            ]

            if not chain_tasks:
                continue  # Skip empty chains

            # Calculate feeding buffer size using chain's strategy
            feeding_buffer_size = chain.buffer_strategy.calculate_buffer_size(
                chain_tasks, chain.buffer_ratio
            )

            # Round to nearest integer
            feeding_buffer_size = round(feeding_buffer_size)

            # Create feeding buffer
            buffer_id = f"FB_{chain_id}"
            feeding_buffer = Buffer(
                id=buffer_id,
                name=f"Feeding Buffer {chain_id}",
                size=feeding_buffer_size,
                buffer_type="feeding",
                connected_to=chain.connects_to_task_id,
                strategy_name=chain.buffer_strategy.get_name(),
            )

            self.buffers[buffer_id] = feeding_buffer
            chain.set_buffer(feeding_buffer)

            # Add buffer to the graph
            last_feeding_task = chain.tasks[-1] if chain.tasks else None
            connects_to = chain.connects_to_task_id

            if last_feeding_task and connects_to and self.task_graph:
                # Add buffer node
                self.task_graph.add_node(
                    buffer_id, node_type="buffer", buffer=feeding_buffer
                )

                # Remove direct connection
                if self.task_graph.has_edge(last_feeding_task, connects_to):
                    self.task_graph.remove_edge(last_feeding_task, connects_to)

                # Add connections through buffer
                self.task_graph.add_edge(last_feeding_task, buffer_id)
                self.task_graph.add_edge(buffer_id, connects_to)

        return self.buffers

    def schedule(self):
        """Run the full CCPM scheduling algorithm."""
        # Build the dependency graph
        self.build_dependency_graph()

        # Calculate the initial schedule
        self.calculate_baseline_schedule()

        # Identify the critical chain
        self.calculate_critical_chain()

        # Identify feeding chains before resource leveling
        # This allows the resource leveling algorithm to properly schedule
        # feeding chain tasks as late as possible (ALAP)
        self.find_feeding_chains()

        # Apply resource leveling
        # Use the resource_leveling service
        if self.resources:
            self.tasks, self.task_graph = level_resources(
                self.tasks, self.resources, self.critical_chain, self.task_graph
            )

        # Set actual dates for all tasks
        for task_id, task in self.tasks.items():
            if not hasattr(task, "start_date") or task.start_date is None:
                task.start_date = self.start_date + timedelta(days=task.early_start)
                task.end_date = task.start_date + timedelta(days=task.planned_duration)

        # Calculate and add feeding buffers to the network
        self.calculate_buffers()

        # Update schedule with buffers
        self.apply_buffer_to_schedule()

        return {"tasks": self.tasks, "chains": self.chains, "buffers": self.buffers}

    def apply_buffer_to_schedule(self):
        """Update the schedule to account for buffers, positioning feeding buffers ALAP."""
        if not hasattr(self, "buffers"):
            return

        # First, ensure all tasks have start and end dates
        for task_id, task in self.tasks.items():
            if task.start_date is None:
                task.start_date = self.start_date + timedelta(days=task.early_start)
            if task.end_date is None:
                task.end_date = task.start_date + timedelta(days=task.planned_duration)

        # Now process each buffer
        for buffer_id, buffer in self.buffers.items():
            if buffer.buffer_type == "project":
                # Project buffer comes after the last task in critical chain
                last_task_id = (
                    buffer.connected_to
                    if buffer.connected_to
                    else self.critical_chain.tasks[-1]
                )
                last_task = self.tasks[last_task_id]

                # Set buffer dates
                buffer.start_date = last_task.end_date
                buffer.end_date = buffer.start_date + timedelta(days=buffer.size)

            elif buffer.buffer_type == "feeding":
                # Feeding buffer comes between feeding chain and critical chain
                # Get the predecessor task (last in feeding chain) and successor task (on critical chain)
                predecessors = list(self.task_graph.predecessors(buffer_id))
                successors = list(self.task_graph.successors(buffer_id))

                if not predecessors or not successors:
                    continue  # Skip if buffer isn't properly connected

                predecessor_task_id = predecessors[0]
                successor_task_id = successors[0]

                predecessor_task = self.tasks[predecessor_task_id]
                successor_task = self.tasks[successor_task_id]

                # For ALAP positioning:
                # Calculate backward from when the critical task starts
                # Buffer end date should be the successor start date
                buffer.end_date = successor_task.start_date

                # Buffer start date is end date minus buffer size
                buffer.start_date = buffer.end_date - timedelta(days=buffer.size)

                # Check if the buffer start date is after the predecessor end date
                # If not, we need to adjust it and possibly delay the critical task
                if buffer.start_date < predecessor_task.end_date:
                    # Need to move buffer start date to right after predecessor ends
                    buffer.start_date = predecessor_task.end_date
                    buffer.end_date = buffer.start_date + timedelta(days=buffer.size)

                    # If this pushes the buffer end past the critical task start,
                    # we need to delay the critical task
                    if buffer.end_date > successor_task.start_date:
                        delay = (buffer.end_date - successor_task.start_date).days
                        self._delay_task_and_dependents(successor_task_id, delay)

        return self.tasks

    def _delay_task_and_dependents(self, task_id, delay_days):
        """Recursively delay a task and all its dependent tasks by a number of days."""
        if delay_days <= 0 or task_id not in self.tasks:
            return

        task = self.tasks[task_id]

        # Delay this task
        task.start_date += timedelta(days=delay_days)
        task.end_date += timedelta(days=delay_days)

        # Recursively delay all dependent tasks
        if self.task_graph:
            for succ_id in self.task_graph.successors(task_id):
                if succ_id in self.tasks:
                    self._delay_task_and_dependents(succ_id, delay_days)
                elif succ_id in self.buffers:
                    # If successor is a buffer, move it too
                    buffer = self.buffers[succ_id]
                    buffer.start_date += timedelta(days=delay_days)
                    buffer.end_date += timedelta(days=delay_days)

    def set_execution_date(self, execution_date):
        """
        Set the current execution date for tracking and reporting.

        Args:
            execution_date: The date to use for execution phase calculations

        Returns:
            datetime: The updated execution date
        """
        self.execution_date = execution_date

        # Recalculate the network based on current progress
        self.recalculate_network_from_progress(execution_date)

        return execution_date

    def update_task_progress(self, task_id, remaining_duration, status_date=None):
        """
        Update task progress during execution phase.

        Args:
            task_id: The ID of the task to update
            remaining_duration: The remaining duration in days
            status_date: The date of this update (defaults to execution_date or today)

        Returns:
            Task: The updated task
        """
        # Default to execution_date or today
        if status_date is None:
            if hasattr(self, "execution_date") and self.execution_date:
                status_date = self.execution_date
            else:
                status_date = datetime.now()

        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found in the project")

        task = self.tasks[task_id]

        # Store the original duration if not already tracking
        if not hasattr(task, "original_duration"):
            task.original_duration = task.planned_duration

        # Store the previous remaining duration
        previous_remaining = getattr(task, "remaining_duration", task.planned_duration)

        # Update the remaining duration
        task.remaining_duration = remaining_duration

        # If this is the first update, set the actual start date
        if not hasattr(task, "actual_start_date") or not task.actual_start_date:
            # For first update, if status_date is after scheduled start,
            # use the scheduled start date
            if hasattr(task, "start_date") and status_date >= task.start_date:
                task.actual_start_date = task.start_date
            else:
                # Use status_date if it's before the scheduled start
                task.actual_start_date = status_date

            # Also set new_start_date for consistency
            task.new_start_date = task.actual_start_date

        # Calculate elapsed calendar days since actual start
        elapsed_days = (status_date - task.actual_start_date).days
        elapsed_days = max(0, elapsed_days)  # Ensure non-negative

        # Calculate completed work based on original duration and remaining
        completed_work = task.original_duration - remaining_duration
        completed_work = max(0, completed_work)  # Ensure non-negative

        # Calculate progress percentage
        total_duration = task.original_duration
        if total_duration > 0:
            progress_percentage = (completed_work / total_duration) * 100
        else:
            progress_percentage = 0

        # Keep history of updates for this task
        if not hasattr(task, "progress_history"):
            task.progress_history = []

        # Add to history with completed work calculations
        task.progress_history.append(
            {
                "date": status_date,
                "remaining": remaining_duration,
                "completed_work": completed_work,
                "progress_percentage": progress_percentage,
                "elapsed_days": elapsed_days,
            }
        )

        # Update task status
        if remaining_duration <= 0:
            # Task is now complete
            task.status = "completed"
            task.actual_end_date = status_date
            task.actual_duration = elapsed_days
            task.new_end_date = status_date
            task.remaining_duration = 0  # Ensure it's exactly zero
        else:
            # Task is in progress
            task.status = "in_progress"

            # Update the expected end date based on status date and remaining duration
            task.expected_end_date = status_date + timedelta(days=remaining_duration)
            task.new_end_date = task.expected_end_date

        # Create a set with this task ID as the only directly updated task
        directly_updated_tasks = {task_id}

        # Recalculate the network with these changes
        self.recalculate_network_from_progress(status_date, directly_updated_tasks)

        # Update buffer consumption based on progress
        self._update_buffer_consumption(status_date)

        return task

    def recalculate_network_from_progress(
        self, status_date, directly_updated_tasks=None
    ):
        """
        Recalculate the entire network schedule based on task progress.

        Args:
            status_date: Current status date
            directly_updated_tasks: Set of task IDs that received direct updates in this round
        """
        # Initialize directly_updated_tasks if not provided
        if directly_updated_tasks is None:
            directly_updated_tasks = set()

        # Get topological sort of tasks
        if self.task_graph:
            task_order = list(nx.topological_sort(self.task_graph))
        else:
            # If no task graph, just use task IDs
            task_order = list(self.tasks.keys())

        # Keep track of tasks that have received updates in this recalculation
        updated_tasks = set(directly_updated_tasks)

        # First pass: update task start dates based on progress
        for node in task_order:
            # Skip if not a task
            if node not in self.tasks:
                continue

            task = self.tasks[node]

            # If the task is completed or in progress, handle actual dates
            if hasattr(task, "status") and task.status in ["completed", "in_progress"]:
                # Task has started - use actual start date and remaining duration
                if not hasattr(task, "remaining_duration"):
                    task.remaining_duration = (
                        task.planned_duration
                    )  # Default if not set

                # For completed tasks, ensure end date is set
                if task.status == "completed":
                    if not hasattr(task, "actual_end_date"):
                        task.actual_end_date = status_date

                    # Use the actual dates for new_start_date and new_end_date
                    task.new_start_date = task.actual_start_date
                    task.new_end_date = task.actual_end_date

                    # Add to updated tasks set
                    updated_tasks.add(node)
                else:
                    # For in-progress tasks, handle dates
                    task.new_start_date = task.actual_start_date

                    # Only update expected_end_date if this task received a direct update
                    if node in directly_updated_tasks:
                        # This task was directly updated, so recalculate expected end date
                        task.expected_end_date = status_date + timedelta(
                            days=task.remaining_duration
                        )
                        # Update new_end_date to match
                        task.new_end_date = task.expected_end_date
                    else:
                        # This task did not receive a direct update, so maintain its previous expected_end_date
                        if hasattr(task, "expected_end_date"):
                            # Use existing expected end date
                            task.new_end_date = task.expected_end_date
                        else:
                            # If no expected_end_date exists yet, initialize it
                            task.expected_end_date = status_date + timedelta(
                                days=task.remaining_duration
                            )
                            task.new_end_date = task.expected_end_date

                    # Add to updated tasks set
                    updated_tasks.add(node)
            else:
                # Task hasn't started yet - calculate based on predecessors
                if not self.task_graph:
                    continue

                predecessors = list(self.task_graph.predecessors(node))

                # If no predecessors or none of them have been updated, skip this task
                if not predecessors or not any(
                    pred in updated_tasks for pred in predecessors
                ):
                    continue

                # Calculate start based on predecessors
                if not predecessors:
                    # Start task with no predecessors - keep original date if in future
                    if (
                        not hasattr(task, "new_start_date")
                        or task.start_date > status_date
                    ):
                        task.new_start_date = task.start_date
                        task.remaining_duration = task.planned_duration
                    else:
                        # Should have started by now but hasn't - update to today
                        task.new_start_date = status_date
                        task.remaining_duration = task.planned_duration
                else:
                    # Find the latest end date of all predecessors
                    latest_end = status_date  # Default to today

                    for pred_id in predecessors:
                        if pred_id in self.tasks:
                            pred_task = self.tasks[pred_id]

                            # Calculate predecessor end date based on its status
                            if (
                                hasattr(pred_task, "status")
                                and pred_task.status == "completed"
                            ):
                                pred_end = pred_task.actual_end_date
                            elif (
                                hasattr(pred_task, "status")
                                and pred_task.status == "in_progress"
                            ):
                                # In progress - end date is today + remaining duration
                                pred_end = status_date + timedelta(
                                    days=pred_task.remaining_duration
                                )
                            elif (
                                hasattr(pred_task, "new_end_date")
                                and pred_task.new_end_date is not None
                            ):
                                # Not started but rescheduled - use new dates
                                pred_end = pred_task.new_end_date
                            else:
                                # Not started or updated - use original schedule
                                pred_end = pred_task.end_date

                            # Safely compare dates, handling None values
                            if pred_end is not None and (
                                latest_end is None or pred_end > latest_end
                            ):
                                latest_end = pred_end
                        elif hasattr(self, "buffers") and pred_id in self.buffers:
                            # Predecessor is a buffer
                            buffer = self.buffers[pred_id]
                            if (
                                hasattr(buffer, "new_end_date")
                                and buffer.new_end_date is not None
                            ):
                                # Safely compare dates, handling None values
                                if (
                                    latest_end is None
                                    or buffer.new_end_date > latest_end
                                ):
                                    latest_end = buffer.new_end_date

                    # Set new start date to latest predecessor end
                    task.new_start_date = latest_end
                    task.remaining_duration = (
                        task.planned_duration
                    )  # Reset to full duration for not-started tasks

                    # Add to updated tasks set since we've changed this task
                    updated_tasks.add(node)

                # Calculate new end date
                task.new_end_date = task.new_start_date + timedelta(
                    days=task.remaining_duration
                )

        # Apply resource leveling to tasks that have been updated
        if self.resources and updated_tasks:
            # Only apply resource leveling to not-started tasks
            not_started_tasks = {
                task_id
                for task_id in updated_tasks
                if not hasattr(self.tasks[task_id], "status")
                or self.tasks[task_id].status not in ["completed", "in_progress"]
            }

            if not_started_tasks:
                # Create a subset of tasks for resource leveling
                tasks_subset = {
                    task_id: self.tasks[task_id]
                    for task_id in self.tasks
                    if task_id in not_started_tasks
                }

                # Apply resource leveling to just these tasks
                tasks_subset, _ = level_resources(
                    tasks_subset,
                    self.resources,
                    None,  # No priority chain for this subset
                    self.task_graph,
                )

                # Update the main tasks dictionary with the leveled subset
                for task_id, task in tasks_subset.items():
                    self.tasks[task_id] = task

        # Update buffer positions
        self._update_buffer_positions(status_date, updated_tasks)

        return self.tasks

    def _update_buffer_positions(self, status_date, updated_tasks=None):
        """
        Update buffer positions based on task progress and changes.

        Args:
            status_date: Current status date
            updated_tasks: Set of task IDs that were updated
        """
        if not hasattr(self, "buffers") or not self.buffers:
            return

        if not self.task_graph:
            return

        # Process each buffer
        for buffer_id, buffer in self.buffers.items():
            predecessors = list(self.task_graph.predecessors(buffer_id))
            successors = list(self.task_graph.successors(buffer_id))

            if not predecessors:
                continue

            # Get predecessor task (what buffer protects)
            pred_id = predecessors[0]

            if pred_id not in self.tasks:
                continue

            pred_task = self.tasks[pred_id]

            # Determine predecessor end date
            if hasattr(pred_task, "status") and pred_task.status == "completed":
                pred_end = pred_task.actual_end_date
            elif hasattr(pred_task, "status") and pred_task.status == "in_progress":
                pred_end = status_date + timedelta(days=pred_task.remaining_duration)
            elif (
                hasattr(pred_task, "new_end_date")
                and pred_task.new_end_date is not None
            ):
                pred_end = pred_task.new_end_date
            else:
                pred_end = pred_task.end_date

            # Update buffer position
            buffer.new_start_date = pred_end
            buffer.new_end_date = buffer.new_start_date + timedelta(days=buffer.size)

            # If this is a feeding buffer, check if it pushes critical tasks
            if buffer.buffer_type == "feeding" and successors:
                succ_id = successors[0]

                if succ_id in self.tasks:
                    succ_task = self.tasks[succ_id]

                    # Only adjust not-started tasks
                    if not hasattr(succ_task, "status") or succ_task.status not in [
                        "completed",
                        "in_progress",
                    ]:
                        # If buffer end pushes successor start, delay the successor
                        # Use safe comparison to handle None values
                        if (
                            buffer.new_end_date is not None
                            and succ_task.new_start_date is not None
                            and buffer.new_end_date > succ_task.new_start_date
                        ):
                            succ_task.new_start_date = buffer.new_end_date
                            succ_task.new_end_date = (
                                succ_task.new_start_date
                                + timedelta(days=succ_task.planned_duration)
                            )

                            # Propagate this delay downstream
                            self._propagate_delay(succ_id, status_date)

        return self.buffers

    def _propagate_delay(self, task_id, status_date):
        """
        Propagate delay from the given task to all downstream tasks.

        Args:
            task_id: ID of the task causing the delay
            status_date: Current status date
        """
        if task_id not in self.tasks or not self.task_graph:
            return

        # Get successors
        successors = list(self.task_graph.successors(task_id))

        for succ_id in successors:
            # Skip if not a task
            if succ_id not in self.tasks:
                continue

            succ_task = self.tasks[succ_id]

            # Skip tasks that already started
            if hasattr(succ_task, "status") and succ_task.status in [
                "completed",
                "in_progress",
            ]:
                continue

            task = self.tasks[task_id]

            # Check if successor needs to be delayed - handle None values safely
            if (
                task.new_end_date is not None
                and succ_task.new_start_date is not None
                and task.new_end_date > succ_task.new_start_date
            ):
                # Delay successor
                succ_task.new_start_date = task.new_end_date
                succ_task.new_end_date = succ_task.new_start_date + timedelta(
                    days=succ_task.planned_duration
                )

                # Recursively propagate to downstream tasks
                self._propagate_delay(succ_id, status_date)

    def _update_buffer_consumption(self, status_date):
        """
        Update buffer consumption based on task progress.

        Args:
            status_date: Current status date
        """
        if not hasattr(self, "buffers") or not self.buffers:
            return

        # Update project buffer consumption based on critical chain progress
        for buffer_id, buffer in self.buffers.items():
            if buffer.buffer_type == "project":
                # Calculate project buffer consumption based on critical chain end date
                last_task_id = self.critical_chain.tasks[-1]
                last_task = self.tasks[last_task_id]

                # Get current projected end date
                if hasattr(last_task, "status") and last_task.status == "completed":
                    projected_end = last_task.actual_end_date
                elif hasattr(last_task, "status") and last_task.status == "in_progress":
                    projected_end = status_date + timedelta(
                        days=last_task.remaining_duration
                    )
                elif hasattr(last_task, "new_end_date"):
                    projected_end = last_task.new_end_date
                else:
                    projected_end = last_task.end_date

                # Get original end date
                original_end = last_task.end_date

                # Calculate buffer consumption
                if projected_end > original_end:
                    delay = (projected_end - original_end).days
                    # Consume buffer based on delay
                    buffer_consumed = min(buffer.size, delay)
                    buffer.remaining_size = max(0, buffer.size - buffer_consumed)

                    # Record consumption
                    buffer.consume(buffer_consumed, status_date, "Critical chain delay")

            elif buffer.buffer_type == "feeding":
                # Find the feeding chain this buffer belongs to
                feeding_chain = None
                for chain_id, chain in self.chains.items():
                    if chain.type == "feeding" and chain.buffer == buffer:
                        feeding_chain = chain
                        break

                if not feeding_chain or not feeding_chain.tasks:
                    continue

                # Get last task in the feeding chain
                last_feeding_task_id = feeding_chain.tasks[-1]
                last_feeding_task = self.tasks[last_feeding_task_id]

                # Calculate original end date
                original_end = last_feeding_task.end_date

                # Get current projected end date
                if (
                    hasattr(last_feeding_task, "status")
                    and last_feeding_task.status == "completed"
                ):
                    projected_end = last_feeding_task.actual_end_date
                elif (
                    hasattr(last_feeding_task, "status")
                    and last_feeding_task.status == "in_progress"
                ):
                    projected_end = status_date + timedelta(
                        days=last_feeding_task.remaining_duration
                    )
                elif hasattr(last_feeding_task, "new_end_date"):
                    projected_end = last_feeding_task.new_end_date
                else:
                    projected_end = last_feeding_task.end_date

                # Calculate buffer consumption
                if projected_end > original_end:
                    delay = (projected_end - original_end).days
                    # Consume buffer based on delay
                    buffer_consumed = min(buffer.size, delay)
                    buffer.remaining_size = max(0, buffer.size - buffer_consumed)

                    # Record consumption
                    buffer.consume(buffer_consumed, status_date, "Feeding chain delay")

        return self.buffers

    def get_all_project_tags(self):
        """Get all tags used in this project"""
        return get_all_tags(self)

    def get_resources_by_tags(self, tags, match_all=True):
        """Get resources that match the specified tags"""
        return get_resources_by_tags(self.resources, tags, match_all)

    def get_tasks_by_tags(self, tags, match_all=True):
        """Get tasks that match the specified tags"""
        return get_tasks_by_tags(self.tasks, tags, match_all)

    def set_task_full_kitted(self, task_id, is_kitted=True, date=None, note=None):
        """
        Set the full kitted status of a task.

        Args:
            task_id: ID of the task to update
            is_kitted: Whether the task is full kitted
            date: Date of the status change (defaults to now)
            note: Optional note about the status change

        Returns:
            bool: True if successful, False if task not found
        """
        if task_id not in self.tasks:
            return False

        self.tasks[task_id].set_full_kitted(is_kitted, date, note)
        return True

    def get_task_resources(self, task_id):
        """
        Get the resources assigned to a task.

        Args:
            task_id: ID of the task

        Returns:
            list: List of resource IDs assigned to the task
        """
        if task_id not in self.tasks:
            return []

        task = self.tasks[task_id]

        # Handle different ways resources might be stored
        if hasattr(task, "resources"):
            if isinstance(task.resources, list):
                return task.resources
            elif isinstance(task.resources, str):
                return [task.resources]

        return []

    def get_full_kitted_tasks(self):
        """
        Get all tasks that are marked as full kitted.

        Returns:
            dict: Dictionary of full kitted tasks keyed by ID
        """
        return {
            task_id: task for task_id, task in self.tasks.items() if task.is_full_kitted
        }

    def add_task_note(self, task_id, note_text, date=None):
        """
        Add a note to a task.

        Args:
            task_id: ID of the task
            note_text: Text of the note
            date: Date of the note (defaults to now)

        Returns:
            dict: The added note, or None if task not found
        """
        if task_id not in self.tasks:
            return None

        return self.tasks[task_id].add_note(note_text, date)

    def add_buffer_note(self, buffer_id, note_text, date=None):
        """
        Add a note to a buffer.

        Args:
            buffer_id: ID of the buffer
            note_text: Text of the note
            date: Date of the note (defaults to now)

        Returns:
            dict: The added note, or None if buffer not found
        """
        if buffer_id not in self.buffers:
            return None

        return self.buffers[buffer_id].add_note(note_text, date)

    def generate_execution_report(self, status_date=None):
        """
        Generate a text report of the project's execution status.

        Args:
            status_date: The date to use for the report (defaults to self.execution_date or today)

        Returns:
            str: A formatted string with the execution report
        """
        if status_date is None:
            if hasattr(self, "execution_date") and self.execution_date:
                status_date = self.execution_date
            else:
                status_date = datetime.now()

        report = []
        report.append("CCPM Project Execution Status Report")
        report.append("===================================")
        report.append(f"Report Date: {status_date.strftime('%Y-%m-%d')}")
        report.append(f"Project Start Date: {self.start_date.strftime('%Y-%m-%d')}")

        # Calculate overall project completion
        total_duration = sum(task.planned_duration for task in self.tasks.values())
        completed_duration = sum(
            task.planned_duration
            - getattr(task, "remaining_duration", task.planned_duration)
            for task in self.tasks.values()
        )

        if total_duration > 0:
            completion_pct = completed_duration / total_duration * 100
            report.append(f"Project Completion: {completion_pct:.1f}%")

        # Buffer Status
        if hasattr(self, "buffers") and self.buffers:
            report.append("\nBuffer Status:")
            report.append("-------------")

            for buffer_id, buffer in self.buffers.items():
                buffer_type = (
                    "Project Buffer"
                    if buffer.buffer_type == "project"
                    else "Feeding Buffer"
                )
                original_size = buffer.size
                remaining = getattr(buffer, "remaining_size", original_size)
                consumed = original_size - remaining
                consumption_pct = (
                    (consumed / original_size * 100) if original_size > 0 else 0
                )

                report.append(f"{buffer_type} ({buffer.name}):")
                report.append(f"  Original Size: {original_size} days")
                report.append(f"  Consumed: {consumed} days ({consumption_pct:.1f}%)")
                report.append(f"  Remaining: {remaining} days")

                # Status indicator
                if consumption_pct < 33:
                    status = "GREEN (Safe)"
                elif consumption_pct < 67:
                    status = "YELLOW (Warning)"
                else:
                    status = "RED (Critical)"

                report.append(f"  Status: {status}")
                report.append("")

        # Tasks in progress
        in_progress = [
            task
            for task in self.tasks.values()
            if hasattr(task, "status") and task.status == "in_progress"
        ]

        if in_progress:
            report.append("\nTasks In Progress:")
            report.append("-----------------")

            for task in in_progress:
                report.append(f"Task {task.id}: {task.name}")
                report.append(f"  Original Duration: {task.planned_duration} days")
                report.append(f"  Remaining Duration: {task.remaining_duration} days")

                # Calculate progress percentage
                if hasattr(task, "original_duration") and task.original_duration > 0:
                    progress = (
                        (task.original_duration - task.remaining_duration)
                        / task.original_duration
                        * 100
                    )
                    report.append(f"  Progress: {progress:.1f}%")

                report.append(
                    f"  Started On: {task.actual_start_date.strftime('%Y-%m-%d')}"
                )
                report.append(
                    f"  Expected Completion: {(status_date + timedelta(days=task.remaining_duration)).strftime('%Y-%m-%d')}"
                )
                report.append("")

        # Completed tasks
        completed = [
            task
            for task in self.tasks.values()
            if hasattr(task, "status") and task.status == "completed"
        ]

        if completed:
            report.append("\nCompleted Tasks:")
            report.append("---------------")
            report.append(f"Total Completed: {len(completed)} of {len(self.tasks)}")

            for task in completed:
                report.append(f"Task {task.id}: {task.name}")
                report.append(f"  Planned Duration: {task.planned_duration} days")

                if hasattr(task, "actual_start_date") and hasattr(
                    task, "actual_end_date"
                ):
                    actual_duration = (
                        task.actual_end_date - task.actual_start_date
                    ).days
                    report.append(f"  Actual Duration: {actual_duration} days")

                if hasattr(task, "actual_start_date") and hasattr(task, "start_date"):
                    planned_start = task.start_date
                    actual_start = task.actual_start_date
                    if actual_start > planned_start:
                        delay = (actual_start - planned_start).days
                        report.append(f"  Started {delay} days late")
                    elif actual_start < planned_start:
                        early = (planned_start - actual_start).days
                        report.append(f"  Started {early} days early")
                    else:
                        report.append(f"  Started on schedule")

                if hasattr(task, "actual_end_date") and hasattr(task, "end_date"):
                    planned_end = task.end_date
                    actual_end = task.actual_end_date
                    if actual_end > planned_end:
                        delay = (actual_end - planned_end).days
                        report.append(f"  Finished {delay} days late")
                    elif actual_end < planned_end:
                        early = (planned_end - actual_end).days
                        report.append(f"  Finished {early} days early")
                    else:
                        report.append(f"  Finished on schedule")

                report.append("")

        # Upcoming tasks (not started yet)
        not_started = [
            task
            for task in self.tasks.values()
            if not hasattr(task, "status")
            or task.status not in ["completed", "in_progress"]
        ]

        # Sort by start date
        not_started.sort(key=lambda x: getattr(x, "new_start_date", x.start_date))

        if not_started:
            report.append("\nUpcoming Tasks:")
            report.append("--------------")

            # Show the next 5 tasks to start
            for task in not_started[: min(5, len(not_started))]:
                # Get the appropriate start date (new or original)
                start_date = getattr(task, "new_start_date", task.start_date)

                report.append(f"Task {task.id}: {task.name}")
                report.append(f"  Planned Duration: {task.planned_duration} days")
                report.append(f"  Scheduled Start: {start_date.strftime('%Y-%m-%d')}")

                # Get resource info
                resources = []
                if hasattr(task, "resources"):
                    if isinstance(task.resources, list):
                        resources = task.resources
                    elif isinstance(task.resources, str):
                        resources = [task.resources]

                if resources:
                    report.append(f"  Resources: {', '.join(resources)}")

                # Show chain information if available
                if hasattr(task, "chain_id") and task.chain_id:
                    chain_type = (
                        "Critical Chain"
                        if task.chain_type == "critical"
                        else "Feeding Chain"
                    )
                    report.append(f"  Chain: {chain_type} ({task.chain_id})")

                report.append("")

        # Find projected end date including project buffer
        latest_task_end = max(
            (
                getattr(task, "new_end_date", task.end_date)
                for task in self.tasks.values()
            ),
            default=status_date,
        )

        project_buffer = None
        for buffer in self.buffers.values():
            if buffer.buffer_type == "project":
                project_buffer = buffer
                break

        if project_buffer:
            if hasattr(project_buffer, "new_end_date") and project_buffer.new_end_date:
                projected_end = project_buffer.new_end_date
            else:
                projected_end = latest_task_end + timedelta(days=project_buffer.size)

            # Add this null check before using projected_end
            if projected_end:
                report.append(
                    f"\nProjected End Date: {projected_end.strftime('%Y-%m-%d')}"
                )

                # Calculate if project is ahead or behind schedule
                if hasattr(project_buffer, "end_date") and project_buffer.end_date:
                    original_end = project_buffer.end_date

                    # Add null check for both variables
                    if projected_end and original_end:
                        if projected_end > original_end:
                            delay = (projected_end - original_end).days
                            report.append(
                                f"Project is currently {delay} days behind schedule"
                            )
                        elif projected_end < original_end:
                            ahead = (original_end - projected_end).days
                            report.append(
                                f"Project is currently {ahead} days ahead of schedule"
                            )
                        else:
                            report.append("Project is currently on schedule")
            else:
                report.append("\nProjected End Date: Not available")

        return "\n".join(report)

    def simulate_execution(
        self,
        simulation_date,
        completed_task_ids=None,
        in_progress_task_ids=None,
        progress_percentages=None,
    ):
        """
        Simulate project execution by marking tasks as completed or in progress.

        Args:
            simulation_date: The date to use for simulation
            completed_task_ids: List of task IDs to mark as completed
            in_progress_task_ids: List of task IDs to mark as in progress
            progress_percentages: Dict mapping task IDs to progress percentage (0-100)

        Returns:
            dict: Updated tasks and buffers
        """
        # Set execution date
        self.set_execution_date(simulation_date)

        # Default params
        if completed_task_ids is None:
            completed_task_ids = []

        if in_progress_task_ids is None:
            in_progress_task_ids = []

        if progress_percentages is None:
            progress_percentages = {}

        # Mark tasks as completed
        for task_id in completed_task_ids:
            if task_id in self.tasks:
                self.update_task_progress(task_id, 0, simulation_date)

        # Mark tasks as in progress with specified progress
        for task_id in in_progress_task_ids:
            if task_id in self.tasks:
                task = self.tasks[task_id]

                # Get progress percentage (default to 50%)
                progress_pct = progress_percentages.get(task_id, 50)

                # Calculate remaining duration
                original_duration = task.planned_duration
                remaining = original_duration * (1 - progress_pct / 100)
                remaining = max(0.1, remaining)  # Ensure some work remains

                # Update progress
                self.update_task_progress(task_id, remaining, simulation_date)

        return self.tasks, self.buffers
