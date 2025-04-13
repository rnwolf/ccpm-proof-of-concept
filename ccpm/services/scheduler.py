from datetime import datetime
import networkx as nx

from ..domain.task import Task
from ..domain.buffer import Buffer
from ..domain.chain import Chain
from ..utils.graph import (
    build_dependency_graph,
    forward_pass,
    backward_pass,
    find_critical_path,
)
from .buffer_strategies import (
    CutAndPasteMethod,
    SumOfSquaresMethod,
    RootSquareErrorMethod,
    AdaptiveBufferMethod,
)


class CCPMScheduler:
    def __init__(
        self,
        project_buffer_ratio=0.5,
        default_feeding_buffer_ratio=0.3,
        project_buffer_strategy=None,
        default_feeding_buffer_strategy=None,
    ):
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

    def identify_critical_chain(self):
        """Identify the critical chain (critical path with resource conflicts resolved)"""
        if not self.task_graph:
            self.build_dependency_graph()

        # Calculate schedule if not already done
        if not all(hasattr(task, "is_critical") for task in self.tasks.values()):
            self.calculate_baseline_schedule()

        # Get the critical path based on zero slack
        critical_path = find_critical_path(self.task_graph, self.tasks)

        # Resource leveling would be applied here to resolve conflicts
        # For now, we'll use the critical path as the critical chain

        # Create the critical chain object
        if critical_path:
            critical_chain = Chain("critical", "Critical Chain", type="critical")
            critical_chain.tasks = critical_path
            critical_chain.buffer_strategy = self.project_buffer_strategy

            self.chains["critical"] = critical_chain
            self.critical_chain = critical_chain

            # Update task chain membership
            for task_id in critical_path:
                self.tasks[task_id].chain_id = "critical"

        return critical_path

    def identify_feeding_chains(self):
        """Identify feeding chains - paths that feed into the critical chain."""
        if not self.critical_chain:
            self.identify_critical_chain()

        # Get critical chain tasks
        critical_chain_tasks = set(self.critical_chain.tasks)

        # Find tasks that feed into the critical chain
        feeding_points = {}  # Maps critical chain task to list of feeding tasks

        # For each critical task, find its non-critical predecessors
        for critical_task_id in critical_chain_tasks:
            predecessors = list(self.task_graph.predecessors(critical_task_id))
            for pred_id in predecessors:
                if pred_id not in critical_chain_tasks and pred_id in self.tasks:
                    if critical_task_id not in feeding_points:
                        feeding_points[critical_task_id] = []
                    feeding_points[critical_task_id].append(pred_id)

        # Create feeding chains
        chain_id = 1
        feeding_chains = []

        for critical_task_id, feeding_tasks in feeding_points.items():
            for feeding_task_id in feeding_tasks:
                # Trace back to find the complete chain
                chain = [feeding_task_id]

                # Trace backward to find the origin of this chain
                current_task = feeding_task_id
                while True:
                    # Get predecessors that aren't in the critical chain
                    preds = [
                        pred
                        for pred in self.task_graph.predecessors(current_task)
                        if pred not in critical_chain_tasks and pred in self.tasks
                    ]

                    if not preds:
                        # No more predecessors, chain is complete
                        break

                    # For simplicity, take the "longest" predecessor path
                    if len(preds) > 1:
                        # Sort predecessors by their duration
                        preds.sort(
                            key=lambda x: self.tasks[x].planned_duration, reverse=True
                        )

                    # Add the predecessor to our chain and continue
                    current_task = preds[0]
                    chain.append(current_task)

                # Reverse the chain so it's in topological order
                chain.reverse()

                # Create the chain object
                chain_name = f"Feeding Chain {chain_id}"
                feeding_chain = Chain(
                    f"feeding_{chain_id}",
                    chain_name,
                    type="feeding",
                    buffer_ratio=self.default_feeding_buffer_ratio,
                )
                feeding_chain.tasks = chain
                feeding_chain.connects_to_task_id = critical_task_id
                feeding_chain.connects_to_chain_id = "critical"
                feeding_chain.buffer_strategy = self.default_feeding_buffer_strategy

                # Add to chains dictionary
                self.chains[feeding_chain.id] = feeding_chain

                # Update task chain membership
                for task_id in chain:
                    self.tasks[task_id].chain_id = feeding_chain.id

                feeding_chains.append(feeding_chain)
                chain_id += 1

        return feeding_chains

    def calculate_buffers(self):
        """Calculate all buffers based on chains and their selected strategies"""
        if not self.critical_chain:
            self.identify_critical_chain()

        # Calculate project buffer
        critical_tasks = [
            self.tasks[task_id]
            for task_id in self.critical_chain.tasks
            if task_id in self.tasks
        ]

        # Calculate project buffer size using the selected strategy
        project_buffer_size = self.critical_chain.buffer_strategy.calculate_buffer_size(
            critical_tasks, self.project_buffer_ratio
        )

        # Round to nearest integer
        project_buffer_size = round(project_buffer_size)

        # Create project buffer
        project_buffer = Buffer(
            id="PB",
            name="Project Buffer",
            size=project_buffer_size,
            buffer_type="project",
            strategy_name=self.critical_chain.buffer_strategy.get_name(),
        )
        self.buffers["PB"] = project_buffer
        self.critical_chain.buffer = project_buffer

        # Add buffer to the graph
        last_critical_task = (
            self.critical_chain.tasks[-1] if self.critical_chain.tasks else None
        )
        if last_critical_task and self.task_graph:
            self.task_graph.add_node("PB", node_type="buffer", buffer=project_buffer)
            self.task_graph.add_edge(last_critical_task, "PB")

        # Calculate feeding buffers for each feeding chain
        for chain_id, chain in self.chains.items():
            if chain.type == "critical":
                continue  # Skip the critical chain

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
            chain.buffer = feeding_buffer

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
        self.identify_critical_chain()

        # Identify feeding chains
        self.identify_feeding_chains()

        # Calculate buffers
        self.calculate_buffers()

        # Apply resource leveling (future implementation)

        # Set actual dates for all tasks
        self.set_task_dates()

        return {"tasks": self.tasks, "chains": self.chains, "buffers": self.buffers}

    def set_task_dates(self):
        """Set actual calendar dates for all tasks and buffers"""
        for task_id, task in self.tasks.items():
            if not hasattr(task, "start_date"):
                task.start_date = self.start_date + timedelta(days=task.early_start)

            if not hasattr(task, "end_date"):
                task.end_date = task.start_date + timedelta(days=task.planned_duration)

        # Set buffer dates
        for buffer_id, buffer in self.buffers.items():
            if buffer.buffer_type == "project":
                # Project buffer comes after the last task in critical chain
                last_task_id = (
                    self.critical_chain.tasks[-1] if self.critical_chain.tasks else None
                )

                if last_task_id and last_task_id in self.tasks:
                    last_task = self.tasks[last_task_id]

                    # Set buffer dates
                    buffer.start_date = last_task.end_date
                    buffer.end_date = buffer.start_date + timedelta(days=buffer.size)

            elif buffer.buffer_type == "feeding" and buffer.connected_to:
                # Find the feeding chain this buffer belongs to
                feeding_chain = None
                for chain in self.chains.values():
                    if (
                        chain.type == "feeding"
                        and hasattr(chain, "buffer")
                        and chain.buffer == buffer
                    ):
                        feeding_chain = chain
                        break

                if not feeding_chain or not feeding_chain.tasks:
                    continue

                # Get the last task in feeding chain and the task it connects to
                last_feeding_task_id = feeding_chain.tasks[-1]
                critical_task_id = buffer.connected_to

                if (
                    last_feeding_task_id in self.tasks
                    and critical_task_id in self.tasks
                ):
                    last_feeding_task = self.tasks[last_feeding_task_id]
                    critical_task = self.tasks[critical_task_id]

                    # Position buffer between feeding chain and critical task
                    buffer.start_date = last_feeding_task.end_date
                    buffer.end_date = buffer.start_date + timedelta(days=buffer.size)

                    # If buffer pushes critical task later, adjust critical task
                    if buffer.end_date > critical_task.start_date:
                        critical_task.start_date = buffer.end_date
                        critical_task.end_date = critical_task.start_date + timedelta(
                            days=critical_task.planned_duration
                        )

                        # Propagate the delay to downstream tasks
                        self._propagate_delay(critical_task_id)

        return self.tasks

    def _propagate_delay(self, task_id):
        """Propagate delay from the given task to all downstream tasks"""
        if task_id not in self.tasks or not self.task_graph:
            return

        # Get successors
        successors = list(self.task_graph.successors(task_id))

        for succ_id in successors:
            # Skip buffers
            if succ_id in self.buffers:
                continue

            if succ_id not in self.tasks:
                continue

            task = self.tasks[task_id]
            succ_task = self.tasks[succ_id]

            # Check if successor needs to be delayed
            if task.end_date > succ_task.start_date:
                # Delay successor
                delay = (task.end_date - succ_task.start_date).days
                succ_task.start_date = task.end_date
                succ_task.end_date = succ_task.start_date + timedelta(
                    days=succ_task.planned_duration
                )

                # Recursively propagate to downstream tasks
                self._propagate_delay(succ_id)

    def update_task_progress(self, task_id, remaining_duration, status_date=None):
        """Update task progress with remaining duration"""
        # Default to current date
        if status_date is None:
            status_date = datetime.now()

        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]

        # If this is the first update, set the actual start date
        if task.status == "planned":
            task.start_task(status_date)

        # Update the task progress
        task.update_progress(remaining_duration, status_date)

        # If task is now complete, we need to update the schedule
        if task.status == "completed":
            # Propagate changes to downstream tasks
            self._recalculate_schedule_from_progress(status_date)

        return task

    def _recalculate_schedule_from_progress(self, status_date):
        """Recalculate the schedule based on current progress"""
        # This would be a more complex implementation that:
        # 1. Updates buffer consumption based on task delays
        # 2. Recalculates start/end dates for remaining tasks
        # 3. Adjusts resource allocation

        # For now, we'll implement a simple version
        for buffer_id, buffer in self.buffers.items():
            if buffer.buffer_type == "project":
                # Project buffer consumption based on critical chain delays
                critical_tasks = [
                    self.tasks[task_id]
                    for task_id in self.critical_chain.tasks
                    if task_id in self.tasks
                ]

                # Calculate expected project end date
                planned_end_date = None
                actual_end_date = None

                for task in critical_tasks:
                    if task.status == "completed":
                        # For completed tasks, use actual end date
                        if (
                            not actual_end_date
                            or task.actual_end_date > actual_end_date
                        ):
                            actual_end_date = task.actual_end_date
                    else:
                        # For non-completed tasks, use planned end date
                        if not planned_end_date or task.end_date > planned_end_date:
                            planned_end_date = task.end_date

                # If project is delayed, consume buffer
                if (
                    actual_end_date
                    and planned_end_date
                    and actual_end_date > planned_end_date
                ):
                    delay_days = (actual_end_date - planned_end_date).days
                    buffer.consume(delay_days, status_date, "Critical chain delay")

        return self.buffers
