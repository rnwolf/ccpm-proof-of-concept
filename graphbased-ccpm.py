# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "matplotlib",
#     "networkx",
# ]
# ///

import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime, timedelta


class Task:
    def __init__(self, id, name, duration, dependencies=None, resources=None):
        self.id = id
        self.name = name
        self.duration = duration  # Duration in days
        self.dependencies = dependencies if dependencies else []
        self.resources = resources if resources else []
        self.early_start = None
        self.early_finish = None
        self.late_start = None
        self.late_finish = None
        self.slack = None
        self.is_critical = False
        self.start_date = None
        self.end_date = None
        self.color = None  # For resource scheduling


class CCPMScheduler:
    def __init__(
        self,
        tasks,
        resources,
        buffer_percentage=0.5,
        feeding_buffer_percentage=0.3,
        start_date=None,
    ):
        self.tasks = tasks
        self.resources = resources
        self.buffer_percentage = buffer_percentage
        self.feeding_buffer_percentage = feeding_buffer_percentage
        self.start_date = start_date if start_date else datetime.now()
        self.task_graph = None
        self.critical_chain = None
        self.project_buffer = None
        self.feeding_chains = []  # Will hold lists of tasks that form feeding chains
        self.feeding_buffers = {}  # Will map the last task in a feeding chain to its buffer

    def build_dependency_graph(self):
        """Build a directed graph representing task dependencies."""
        G = nx.DiGraph()

        # Add nodes
        for task_id, task in self.tasks.items():
            G.add_node(task_id, task=task)

        # Add edges
        for task_id, task in self.tasks.items():
            for dep_id in task.dependencies:
                G.add_edge(dep_id, task_id)

        # Check for cycles
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("Task dependencies contain cycles!")

        self.task_graph = G
        return G

    def forward_pass(self):
        """Calculate early start and early finish times."""
        # Topological sort to get tasks in order
        task_order = list(nx.topological_sort(self.task_graph))

        # Initialize start task
        for task_id in task_order:
            task = self.tasks[task_id]
            if not task.dependencies:  # Start task
                task.early_start = 0
                task.early_finish = task.duration
            else:
                # Find maximum early finish of all predecessors
                max_finish = 0
                for dep_id in task.dependencies:
                    dep_task = self.tasks[dep_id]
                    if dep_task.early_finish > max_finish:
                        max_finish = dep_task.early_finish

                task.early_start = max_finish
                task.early_finish = max_finish + task.duration

    def backward_pass(self):
        """Calculate late start and late finish times."""
        # Reverse topological sort
        task_order = list(reversed(list(nx.topological_sort(self.task_graph))))

        # Find project duration
        project_duration = max(task.early_finish for task in self.tasks.values())

        # Initialize end tasks
        for task_id in task_order:
            task = self.tasks[task_id]
            successors = list(self.task_graph.successors(task_id))

            if not successors:  # End task
                task.late_finish = project_duration
                task.late_start = task.late_finish - task.duration
            else:
                # Find minimum late start of all successors
                min_start = float("inf")
                for succ_id in successors:
                    succ_task = self.tasks[succ_id]
                    if succ_task.late_start < min_start:
                        min_start = succ_task.late_start

                task.late_finish = min_start
                task.late_start = min_start - task.duration

            # Calculate slack
            task.slack = task.late_start - task.early_start
            task.is_critical = task.slack == 0

    def identify_critical_chain(self):
        """Identify the critical chain considering both dependencies and resources."""
        # First, find the critical path based on zero slack
        critical_path = [
            task_id for task_id, task in self.tasks.items() if task.is_critical
        ]

        # Now we need to consider resource constraints
        # We'll use the resource graph to check for conflicts along the critical path
        self.critical_chain = critical_path

        # Calculate project buffer
        total_critical_duration = sum(
            self.tasks[task_id].duration for task_id in self.critical_chain
        )
        self.project_buffer = total_critical_duration * self.buffer_percentage

        return self.critical_chain, self.project_buffer

    def identify_feeding_chains(self):
        """Identify feeding chains - paths that feed into the critical chain."""
        if not self.critical_chain:
            raise ValueError("Critical chain must be identified before feeding chains")

        # Get all nodes in the graph
        all_nodes = set(self.task_graph.nodes())

        # Set of critical chain tasks
        critical_set = set(self.critical_chain)

        # Identify feeding points - where non-critical tasks connect to critical chain
        feeding_points = {}  # Maps critical chain task to list of feeding tasks

        # For each critical task, find its non-critical predecessors
        for critical_task_id in self.critical_chain:
            predecessors = list(self.task_graph.predecessors(critical_task_id))
            for pred_id in predecessors:
                if pred_id not in critical_set:
                    if critical_task_id not in feeding_points:
                        feeding_points[critical_task_id] = []
                    feeding_points[critical_task_id].append(pred_id)

        # For each feeding point, trace back to find complete feeding chains
        self.feeding_chains = []

        for critical_task_id, feeding_tasks in feeding_points.items():
            for feeding_task_id in feeding_tasks:
                # Start a new feeding chain with this task
                chain = [feeding_task_id]

                # Trace backward to find the origin of this chain
                current_task = feeding_task_id
                while True:
                    # Get predecessors that aren't in the critical chain
                    preds = [
                        pred
                        for pred in self.task_graph.predecessors(current_task)
                        if pred not in critical_set
                    ]

                    if not preds:
                        # No more predecessors, chain is complete
                        break

                    # For simplicity, we'll take the "longest" predecessor path
                    # In a more complex implementation, we might handle multiple branches
                    if len(preds) > 1:
                        # Sort predecessors by their duration
                        preds.sort(key=lambda x: self.tasks[x].duration, reverse=True)

                    # Add the predecessor to our chain and continue
                    current_task = preds[0]
                    chain.append(current_task)

                # Reverse the chain so it's in topological order
                chain.reverse()

                # Add information about where this chain connects to the critical chain
                self.feeding_chains.append(
                    {
                        "chain": chain,
                        "connects_to": critical_task_id,
                        "last_task": feeding_task_id,
                    }
                )

        return self.feeding_chains

    def calculate_feeding_buffers(self):
        """Calculate feeding buffer sizes for each feeding chain."""
        if not self.feeding_chains:
            self.identify_feeding_chains()

        self.feeding_buffers = {}

        for chain_info in self.feeding_chains:
            chain = chain_info["chain"]
            last_task_id = chain_info["last_task"]

            # Calculate the sum of task durations in the chain
            chain_duration = sum(self.tasks[task_id].duration for task_id in chain)

            # Calculate buffer size based on feeding buffer percentage
            buffer_size = max(1, int(chain_duration * self.feeding_buffer_percentage))

            # Store the buffer size
            self.feeding_buffers[last_task_id] = buffer_size

        return self.feeding_buffers

    def apply_feeding_buffers(self):
        """Adjust task schedule to account for feeding buffers."""
        if not self.feeding_buffers:
            self.calculate_feeding_buffers()

        # For each feeding chain, add buffer between the last task and the critical chain
        for chain_info in self.feeding_chains:
            last_task_id = chain_info["last_task"]
            connects_to = chain_info["connects_to"]
            buffer_size = self.feeding_buffers[last_task_id]

            last_task = self.tasks[last_task_id]
            critical_task = self.tasks[connects_to]

            # Insert buffer by pushing the critical task's start date if needed
            buffer_end = last_task.end_date + timedelta(days=buffer_size)

            if critical_task.start_date < buffer_end:
                # Need to push critical task (and all its dependents) later
                delay = (buffer_end - critical_task.start_date).days
                self._delay_task_and_dependents(connects_to, delay)

        return self.tasks

    def _delay_task_and_dependents(self, task_id, delay_days):
        """Recursively delay a task and all its dependent tasks by a number of days."""
        if delay_days <= 0:
            return

        task = self.tasks[task_id]

        # Delay this task
        task.start_date += timedelta(days=delay_days)
        task.end_date += timedelta(days=delay_days)

        # Recursively delay all dependent tasks
        for succ_id in self.task_graph.successors(task_id):
            self._delay_task_and_dependents(succ_id, delay_days)

    def resource_graph_coloring(self):
        """Use graph coloring to schedule tasks with resource constraints."""
        # Create a conflict graph where nodes are tasks
        # and edges represent tasks that cannot be executed simultaneously due to resource conflicts
        conflict_graph = nx.Graph()

        # Add all tasks as nodes
        for task_id in self.tasks.keys():
            conflict_graph.add_node(task_id)

        # Add edges between tasks that share resources
        for task1_id, task1 in self.tasks.items():
            for task2_id, task2 in self.tasks.items():
                if task1_id != task2_id:
                    # Check if tasks share any resources
                    shared_resources = set(task1.resources) & set(task2.resources)
                    if shared_resources and not self._is_dependent(task1_id, task2_id):
                        conflict_graph.add_edge(task1_id, task2_id)

        # Use graph coloring to assign colors (time slots) to tasks
        coloring = nx.greedy_color(conflict_graph, strategy="largest_first")

        # Assign colors to tasks
        for task_id, color in coloring.items():
            self.tasks[task_id].color = color

        # Use coloring to adjust early_start times to avoid resource conflicts
        self._adjust_schedule_based_on_coloring(coloring)

        return coloring

    def _is_dependent(self, task1_id, task2_id):
        """Check if task1 and task2 have any dependency relationship."""
        # Check if there's a path from task1 to task2 or vice versa
        try:
            path1 = nx.has_path(self.task_graph, task1_id, task2_id)
            path2 = nx.has_path(self.task_graph, task2_id, task1_id)
            return path1 or path2
        except nx.NetworkXError:
            return False

    def _adjust_schedule_based_on_coloring(self, coloring):
        """Adjust task schedule based on graph coloring results."""
        # Group tasks by color
        color_groups = {}
        for task_id, color in coloring.items():
            if color not in color_groups:
                color_groups[color] = []
            color_groups[color].append(task_id)

        # Sort colors
        sorted_colors = sorted(color_groups.keys())

        # Assign start dates based on colors and dependencies
        for color in sorted_colors:
            tasks_in_color = color_groups[color]
            # Sort tasks by their dependencies
            tasks_in_color.sort(key=lambda x: self.tasks[x].early_start)

            for task_id in tasks_in_color:
                task = self.tasks[task_id]

                # Make sure task starts after all its dependencies
                max_dep_finish = 0
                for dep_id in task.dependencies:
                    # Check if the dependency task has a start_date
                    if self.tasks[dep_id].start_date is not None:
                        dep_end = self.tasks[dep_id].start_date + timedelta(
                            days=self.tasks[dep_id].duration
                        )
                        if dep_end.timestamp() > max_dep_finish:
                            max_dep_finish = dep_end.timestamp()

                if max_dep_finish > 0:
                    max_dep_finish_date = datetime.fromtimestamp(max_dep_finish)
                    task.start_date = max_dep_finish_date
                else:
                    task.start_date = self.start_date + timedelta(days=task.early_start)

                task.end_date = task.start_date + timedelta(days=task.duration)

    def schedule(self):
        """Run the full CCPM scheduling algorithm."""
        # Build the dependency graph
        self.build_dependency_graph()

        # Calculate the initial schedule
        self.forward_pass()
        self.backward_pass()

        # Identify the critical chain
        self.identify_critical_chain()

        # Initialize start_date for all tasks to None
        for task in self.tasks.values():
            task.start_date = None
            task.end_date = None

        # Apply resource scheduling using graph coloring
        self.resource_graph_coloring()

        # Set actual dates for all tasks
        for task_id, task in self.tasks.items():
            if task.start_date is None:
                task.start_date = self.start_date + timedelta(days=task.early_start)
                task.end_date = task.start_date + timedelta(days=task.duration)

        # Identify feeding chains and calculate buffers
        self.identify_feeding_chains()
        self.calculate_feeding_buffers()

        # Apply feeding buffers to the schedule
        self.apply_feeding_buffers()

        return self.tasks

    def visualize_dependency_network(self, filename=None):
        """Visualize the task dependency network with critical chain and feeding chains highlighted."""
        G = self.task_graph

        # Set node colors
        node_colors = []
        for node in G.nodes:
            if node in self.critical_chain:
                node_colors.append("red")
            elif any(node in chain_info["chain"] for chain_info in self.feeding_chains):
                node_colors.append("orange")
            else:
                node_colors.append("skyblue")

        # Set edge colors - highlight edges in feeding chains
        edge_colors = []
        for u, v in G.edges:
            # Check if this edge is part of a feeding chain connection to critical chain
            is_feeding_connection = False
            for chain_info in self.feeding_chains:
                if v == chain_info["connects_to"] and u == chain_info["last_task"]:
                    is_feeding_connection = True
                    break

            # Check if both nodes are in the same feeding chain
            in_same_feeding_chain = False
            for chain_info in self.feeding_chains:
                chain = chain_info["chain"]
                if u in chain and v in chain:
                    # Check if they're adjacent in the chain
                    try:
                        u_idx = chain.index(u)
                        v_idx = chain.index(v)
                        if abs(u_idx - v_idx) == 1:
                            in_same_feeding_chain = True
                            break
                    except ValueError:
                        pass

            if is_feeding_connection:
                edge_colors.append("yellow")
            elif in_same_feeding_chain:
                edge_colors.append("orange")
            elif u in self.critical_chain and v in self.critical_chain:
                edge_colors.append("red")
            else:
                edge_colors.append("gray")

        # Create positions for nodes
        pos = nx.spring_layout(G, seed=42)

        # Create the plot
        plt.figure(figsize=(12, 8))

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500)

        # Draw edges
        nx.draw_networkx_edges(G, pos, edge_color=edge_colors, arrows=True)

        # Draw labels
        labels = {node: f"{node}: {self.tasks[node].name}" for node in G.nodes}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=10)

        # Create a legend
        from matplotlib.lines import Line2D

        legend_elements = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="red",
                markersize=10,
                label="Critical Chain",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="orange",
                markersize=10,
                label="Feeding Chain",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="skyblue",
                markersize=10,
                label="Other Tasks",
            ),
            Line2D([0], [0], color="red", lw=2, label="Critical Chain Dependency"),
            Line2D([0], [0], color="orange", lw=2, label="Feeding Chain Dependency"),
            Line2D(
                [0], [0], color="yellow", lw=2, label="Feeding → Critical Connection"
            ),
        ]
        plt.legend(handles=legend_elements, loc="upper right")

        plt.title("Project Task Dependencies with Critical and Feeding Chains")
        plt.axis("off")

        # Save or show the chart
        if filename:
            plt.savefig(filename)
        plt.tight_layout()
        plt.show()

    def generate_report(self):
        """Generate a text report of the project schedule."""
        report = []
        report.append("CCPM Project Schedule Report")
        report.append("===========================")
        report.append(f"Project Start Date: {self.start_date.strftime('%Y-%m-%d')}")

        # Find project end date (accounting for buffer)
        last_task_end = max(task.end_date for task in self.tasks.values())
        buffer_end = last_task_end + timedelta(days=self.project_buffer)
        report.append(f"Projected End Date: {buffer_end.strftime('%Y-%m-%d')}")
        report.append(f"Project Duration: {(buffer_end - self.start_date).days} days")
        report.append(f"Project Buffer: {self.project_buffer} days")

        report.append("\nCritical Chain Tasks:")
        report.append("-------------------")
        for task_id in self.critical_chain:
            task = self.tasks[task_id]
            report.append(
                f"Task {task.id}: {task.name} - Duration: {task.duration} days"
            )

        report.append("\nFeeding Chains:")
        report.append("--------------")
        for i, chain_info in enumerate(self.feeding_chains, 1):
            chain = chain_info["chain"]
            connects_to = chain_info["connects_to"]
            last_task_id = chain_info["last_task"]
            buffer_size = self.feeding_buffers.get(last_task_id, 0)

            report.append(f"Feeding Chain {i}:")
            report.append(
                f"  Connects to Critical Task: {connects_to} ({self.tasks[connects_to].name})"
            )
            report.append(f"  Feeding Buffer Size: {buffer_size} days")
            report.append(
                f"  Tasks in Chain: {' -> '.join(str(task_id) for task_id in chain)}"
            )
            report.append(f"  Task Details:")

            for task_id in chain:
                task = self.tasks[task_id]
                report.append(f"    Task {task.id}: {task.name}")
                report.append(
                    f"      Start: {task.start_date.strftime('%Y-%m-%d')}, End: {task.end_date.strftime('%Y-%m-%d')}"
                )
                report.append(f"      Duration: {task.duration} days")

            report.append("")

        report.append("\nComplete Task Schedule:")
        report.append("----------------------")
        sorted_tasks = sorted(self.tasks.values(), key=lambda x: x.start_date)
        for task in sorted_tasks:
            resources_str = ", ".join(task.resources)

            # Determine if task is in a feeding chain
            feeding_chain_info = ""
            for i, chain_info in enumerate(self.feeding_chains, 1):
                if task.id in chain_info["chain"]:
                    feeding_chain_info = f"Feeding Chain {i}"
                    break

            # Determine task type
            if task.id in self.critical_chain:
                task_type = "Critical Chain"
            elif feeding_chain_info:
                task_type = feeding_chain_info
            else:
                task_type = "Regular Task"

            report.append(f"Task {task.id}: {task.name}")
            report.append(
                f"  Start: {task.start_date.strftime('%Y-%m-%d')}, End: {task.end_date.strftime('%Y-%m-%d')}"
            )
            report.append(
                f"  Duration: {task.duration} days, Resources: {resources_str}"
            )
            report.append(f"  Type: {task_type}")
            report.append("")

        return "\n".join(report)

    def visualize_schedule(self, filename=None):
        """Visualize the project schedule as a Gantt chart with resource utilization."""
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        from matplotlib.ticker import FuncFormatter

        # Calculate the project duration for x-axis sizing
        last_task_end = max(task.end_date for task in self.tasks.values())
        project_duration = (last_task_end - self.start_date).days
        if self.project_buffer:
            project_duration += self.project_buffer

        # Convert to integer to avoid the range() error
        project_duration_int = int(project_duration)

        # Create figure with GridSpec to have two subplots
        fig = plt.figure(figsize=(14, 12))
        gs = gridspec.GridSpec(
            2, 1, height_ratios=[3, 1], hspace=0.3
        )  # 3:1 ratio for Gantt:Resources with spacing

        # Gantt chart subplot
        ax_gantt = fig.add_subplot(gs[0])

        # Sort tasks by start date
        sorted_tasks = sorted(self.tasks.values(), key=lambda x: x.start_date)

        # Plot each task
        for i, task in enumerate(sorted_tasks):
            start_day = (task.start_date - self.start_date).days
            duration = task.duration

            # Critical chain tasks in red, feeding chain tasks in orange, others in blue
            if task.id in self.critical_chain:
                color = "red"
                alpha = 0.6
            elif any(
                task.id in chain_info["chain"] for chain_info in self.feeding_chains
            ):
                color = "orange"
                alpha = 0.6
            else:
                color = "blue"
                alpha = 0.6

            # Plot the task bar
            ax_gantt.barh(i, duration, left=start_day, color=color, alpha=alpha)

            # Format the resource list
            if isinstance(task.resources, str):
                resource_str = task.resources
            elif isinstance(task.resources, list):
                resource_str = ", ".join(task.resources)
            else:
                resource_str = ""

            # Add task name, ID and resources
            ax_gantt.text(
                start_day + duration / 2,
                i,
                f"{task.id}: {task.name} [{resource_str}]",
                ha="center",
                va="center",
                color="black",
            )

        # Add feeding buffers
        buffer_count = 0
        for chain_info in self.feeding_chains:
            last_task_id = chain_info["last_task"]
            buffer_size = self.feeding_buffers.get(last_task_id, 0)

            if buffer_size > 0:
                last_task = self.tasks[last_task_id]
                buffer_start_day = (last_task.end_date - self.start_date).days

                # Plot the feeding buffer
                ax_gantt.barh(
                    len(sorted_tasks) + 1 + buffer_count,
                    buffer_size,
                    left=buffer_start_day,
                    color="yellow",
                    alpha=0.6,
                )
                ax_gantt.text(
                    buffer_start_day + buffer_size / 2,
                    len(sorted_tasks) + 1 + buffer_count,
                    f"Feeding Buffer ({chain_info['last_task']} → {chain_info['connects_to']})",
                    ha="center",
                    va="center",
                    color="black",
                )
                buffer_count += 1

        # Add project buffer
        if self.project_buffer:
            last_task_end = max(task.end_date for task in self.tasks.values())
            buffer_start_day = (last_task_end - self.start_date).days
            ax_gantt.barh(
                len(sorted_tasks) + 1 + buffer_count,
                self.project_buffer,
                left=buffer_start_day,
                color="green",
                alpha=0.6,
            )
            ax_gantt.text(
                buffer_start_day + self.project_buffer / 2,
                len(sorted_tasks) + 1 + buffer_count,
                "Project Buffer",
                ha="center",
                va="center",
                color="black",
            )

        # Format the Gantt chart
        row_count = len(sorted_tasks) + 2 + buffer_count
        ax_gantt.set_yticks(range(row_count))
        yticklabels = [task.name for task in sorted_tasks] + [""] * (buffer_count + 1)

        # Define a formatter for y-axis labels if needed
        formatter = FuncFormatter(
            lambda x, _: yticklabels[int(x)] if int(x) < len(yticklabels) else ""
        )
        ax_gantt.yaxis.set_major_formatter(formatter)
        ax_gantt.set_title("CCPM Project Schedule")
        ax_gantt.grid(axis="x", alpha=0.3)

        # Calculate resource utilization
        resource_usage = self._calculate_resource_utilization()

        # Resource utilization subplot
        ax_resource = fig.add_subplot(gs[1], sharex=ax_gantt)

        # Use the defined resources from the scheduler
        all_resources = self.resources

        # Plot resource utilization
        for i, resource in enumerate(all_resources):
            usage = resource_usage.get(resource, {})
            days = list(usage.keys())
            demands = [usage[day] for day in days]

            # For each day with demand, place a text annotation
            for day, demand in zip(days, demands):
                if demand > 0:
                    ax_resource.text(
                        day,
                        i,
                        str(demand),
                        ha="center",
                        va="center",
                        fontweight="bold",
                        bbox=dict(
                            boxstyle="round,pad=0.3",
                            fc=self._get_demand_color(demand),
                            ec="black",
                            alpha=0.6,
                        ),
                    )

        # Format the resource chart
        ax_resource.set_xlabel("Days from project start")
        ax_resource.set_ylabel("Resources")
        ax_resource.set_title("Resource Utilization")
        ax_resource.set_yticks(range(len(all_resources)))
        ax_resource.set_yticklabels(all_resources)

        # Create grid aligned with days - Make sure to use integers for range()
        ax_resource.set_xticks(
            range(0, project_duration_int + 10, 10)
        )  # Major grid every 10 days
        ax_resource.set_xticks(
            range(0, project_duration_int + 10, 1), minor=True
        )  # Minor grid every day
        ax_resource.grid(which="major", color="gray", linestyle="-", alpha=0.5)
        ax_resource.grid(which="minor", color="lightgray", linestyle="-", alpha=0.2)

        ax_resource.set_xlim(0, project_duration + 5)  # Add some padding

        # Set y-axis limits to give room for the annotations
        ax_resource.set_ylim(-0.5, len(all_resources) - 0.5)

        # Add a legend for resource demand colors
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(
                facecolor=self._get_demand_color(1),
                edgecolor="black",
                alpha=0.6,
                label="1 Task",
            ),
            Patch(
                facecolor=self._get_demand_color(2),
                edgecolor="black",
                alpha=0.6,
                label="2 Tasks",
            ),
            Patch(
                facecolor=self._get_demand_color(3),
                edgecolor="black",
                alpha=0.6,
                label="3+ Tasks",
            ),
        ]
        ax_resource.legend(handles=legend_elements, loc="upper right", ncol=3)

        # Adjust layout
        plt.tight_layout()

        # Save or show the chart
        if filename:
            plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.show()

    def _calculate_resource_utilization(self):
        """Calculate the daily demand for each resource throughout the project."""
        # Find the latest project date
        latest_date = max(task.end_date for task in self.tasks.values())
        if self.project_buffer:
            latest_date = latest_date + timedelta(days=self.project_buffer)

        # Initialize a dictionary to hold resource utilization
        # Format: {resource_name: {day_number: demand_count}}
        resource_usage = {}

        # Calculate the demand for each resource on each day
        for task in self.tasks.values():
            start_day = (task.start_date - self.start_date).days

            # Process each day of the task duration
            for day in range(start_day, start_day + task.duration):
                # Handle resources whether it's a string or a list
                resources_list = []
                if isinstance(task.resources, str):
                    # Case when resources is a single string (like "Magenta")
                    resources_list = [task.resources]
                elif isinstance(task.resources, list):
                    # Case when resources is a list
                    resources_list = task.resources

                for resource in resources_list:
                    # Initialize resource if not yet in dictionary
                    if resource not in resource_usage:
                        resource_usage[resource] = {}

                    # Initialize day if not yet tracked for this resource
                    if day not in resource_usage[resource]:
                        resource_usage[resource][day] = 0

                    # Increment the demand count for this resource on this day
                    resource_usage[resource][day] += 1

        return resource_usage

    def _get_demand_color(self, demand):
        """Return a color based on resource demand level."""
        if demand == 1:
            return "#90EE90"  # Light green
        elif demand == 2:
            return "#FFEB3B"  # Yellow
        else:  # 3 or more
            return "#FF8A80"  # Light red/salmon


def create_sample_project():
    # Define resources
    # resources = ["Developer A", "Developer B", "Tester", "Designer", "Manager"]

    # Define tasks - ID: Task(ID, Name, Duration, Dependencies, Resources)
    # tasks = {
    #     1: Task(1, 'Project Planning', 5, [], ['Manager']),
    #     2: Task(2, 'Requirements Gathering', 7, [1], ['Manager', 'Designer']),
    #     3: Task(3, 'System Design', 8, [2], ['Designer']),
    #     4: Task(4, 'Database Design', 6, [2], ['Developer A']),
    #     5: Task(5, 'Frontend Development', 10, [3], ['Developer B', 'Designer']),
    #     6: Task(6, 'Backend Development', 12, [3, 4], ['Developer A']),
    #     7: Task(7, 'API Integration', 5, [5, 6], ['Developer A', 'Developer B']),
    #     8: Task(8, 'Testing', 8, [7], ['Tester']),
    #     9: Task(9, 'Bug Fixing', 5, [8], ['Developer A', 'Developer B', 'Tester']),
    #     10: Task(10, 'Deployment', 3, [9], ['Developer A', 'Manager']),
    #     11: Task(11, 'Documentation', 4, [10], ['Developer B']),
    # }

    # # Small example from Larry Leech's book
    # resources = ['Red', 'Green', 'Magenta', 'Blue']
    # # Define tasks - ID: Task(ID, Name, Duration, Dependencies, Resources)
    # tasks = {
    #     1: Task(1, 'T1.1', 30, [], ['Red']),
    #     2: Task(2, 'T1.2', 20, [1], ['Green']),
    #     3: Task(3, 'T3', 30, [5, 2], ['Magenta']),
    #     4: Task(4, 'T2.1', 20, [], ['Blue']),
    #     5: Task(5, 'T2.2', 10, [4], ['Green']),
    # }

    # Large example from Larry Leech's book
    resources = ["Red", "Green", "Magenta", "Blue", "Black"]
    # Define tasks - ID: Task(ID, Name, Duration, Dependencies, Resources)
    tasks = {
        1: Task(1, "A-1", 10, [], "Magenta"),
        2: Task(2, "A-2", 20, [1], "Black"),
        3: Task(3, "A-3", 30, [2], "Green"),
        4: Task(4, "A-4", 20, [3], "Red"),
        5: Task(5, "A-5", 40, [4, 9], "Magenta"),
        6: Task(6, "A-6", 28, [5], "Red"),
        7: Task(7, "B-2", 20, [], "Magenta"),
        8: Task(8, "B-3", 20, [7], "Blue"),
        9: Task(9, "B-4", 10, [8], "Red"),
        10: Task(10, "C-3", 30, [], "Blue"),
        11: Task(11, "C-4", 20, [10], "Green"),
        12: Task(12, "C-5", 30, [11, 15], "Red"),
        13: Task(13, "C-6", 10, [12], "Magenta"),
        14: Task(14, "D-3", 40, [], "Blue"),
        15: Task(15, "D-4", 10, [14], "Green"),
        16: Task(16, "Done", 0, [13, 6], "Black"),
    }

    # Create scheduler with both project buffer (50%) and feeding buffer (30%)
    start_date = datetime(2025, 4, 9)  # Today
    scheduler = CCPMScheduler(
        tasks,
        resources,
        buffer_percentage=0.5,
        feeding_buffer_percentage=0.3,
        start_date=start_date,
    )

    # Run scheduling
    scheduler.schedule()

    # Print feeding chains information
    print("Feeding Chains:")
    for i, chain_info in enumerate(scheduler.feeding_chains, 1):
        chain_tasks = [
            f"{task_id} ({scheduler.tasks[task_id].name})"
            for task_id in chain_info["chain"]
        ]
        print(f"Chain {i}: {' -> '.join(chain_tasks)}")
        print(
            f"  Connects to: Task {chain_info['connects_to']} ({scheduler.tasks[chain_info['connects_to']].name})"
        )
        print(
            f"  Buffer size: {scheduler.feeding_buffers.get(chain_info['last_task'], 0)} days"
        )
        print()

    # Visualize the schedule and dependency network
    scheduler.visualize_schedule("ccpm_gantt.png")
    scheduler.visualize_dependency_network("ccpm_network.png")

    # Generate and print report
    report = scheduler.generate_report()
    print(report)

    # Save report to file
    with open("ccpm_project_report.txt", "w") as f:
        f.write(report)


if __name__ == "__main__":
    create_sample_project()
