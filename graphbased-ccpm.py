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


class Buffer:
    def __init__(self, id, name, size, buffer_type, connected_to=None):
        self.id = id
        self.name = name
        self.size = size  # Size in days
        self.buffer_type = buffer_type  # "project" or "feeding"
        self.connected_to = connected_to  # For feeding buffers, ID of critical task
        self.original_size = size  # Keep track of the original size
        self.remaining_size = size  # Track consumption
        self.consumption_history = []  # For tracking consumption over time


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
        """Build a directed graph representing task dependencies, including buffers."""
        G = nx.DiGraph()

        # Add task nodes
        for task_id, task in self.tasks.items():
            G.add_node(task_id, node_type="task", task=task)

        # Add task dependencies (edges)
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
        buffer_size = total_critical_duration * self.buffer_percentage

        # Create project buffer
        last_critical_task = self.critical_chain[-1]
        buffer_id = f"PB{last_critical_task}"  # Unique buffer ID

        # Create the Buffer object
        project_buffer = Buffer(
            id=buffer_id,
            name=f"Project Buffer",
            size=buffer_size,
            buffer_type="project",
            connected_to=last_critical_task,
        )

        # Add to buffers dictionary if it doesn't exist
        if not hasattr(self, "buffers"):
            self.buffers = {}

        self.buffers[buffer_id] = project_buffer
        self.project_buffer_id = buffer_id  # Store reference to project buffer

        # Add buffer to the graph
        self.task_graph.add_node(buffer_id, node_type="buffer", buffer=project_buffer)
        self.task_graph.add_edge(last_critical_task, buffer_id)

        return self.critical_chain, buffer_size

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
        """Calculate feeding buffer sizes for each feeding chain and add them to the graph."""
        if not self.feeding_chains:
            self.identify_feeding_chains()

        if not hasattr(self, "buffers"):
            self.buffers = {}

        self.feeding_buffer_ids = {}  # Will map feeding chains to their buffer IDs

        for chain_info in self.feeding_chains:
            chain = chain_info["chain"]
            last_task_id = chain_info["last_task"]
            connects_to = chain_info["connects_to"]

            # Calculate the sum of task durations in the chain
            chain_duration = sum(self.tasks[task_id].duration for task_id in chain)

            # Calculate buffer size based on feeding buffer percentage
            buffer_size = max(1, int(chain_duration * self.feeding_buffer_percentage))

            # Create unique buffer ID
            buffer_id = f"FB{last_task_id}-{connects_to}"

            # Create the Buffer object
            feeding_buffer = Buffer(
                id=buffer_id,
                name=f"Feeding Buffer ({last_task_id}→{connects_to})",
                size=buffer_size,
                buffer_type="feeding",
                connected_to=connects_to,
            )

            # Add to buffers dictionary
            self.buffers[buffer_id] = feeding_buffer

            # Keep track of which feeding chain this buffer belongs to
            self.feeding_buffer_ids[last_task_id] = buffer_id

            # Add buffer to the graph
            self.task_graph.add_node(
                buffer_id, node_type="buffer", buffer=feeding_buffer
            )

            # Modify the network:
            # 1. Remove direct connection from last_task_id to connects_to
            if self.task_graph.has_edge(last_task_id, connects_to):
                self.task_graph.remove_edge(last_task_id, connects_to)

            # 2. Add edges: last_task_id → buffer → connects_to
            self.task_graph.add_edge(last_task_id, buffer_id)
            self.task_graph.add_edge(buffer_id, connects_to)

        return self.buffers

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

    def apply_buffer_to_schedule(self):
        """Update the schedule to account for buffers."""
        if not hasattr(self, "buffers"):
            return

        # First, ensure all tasks have start and end dates
        for task_id, task in self.tasks.items():
            if task.start_date is None:
                task.start_date = self.start_date + timedelta(days=task.early_start)
            if task.end_date is None:
                task.end_date = task.start_date + timedelta(days=task.duration)

        # Now process each buffer
        for buffer_id, buffer in self.buffers.items():
            if buffer.buffer_type == "project":
                # Project buffer comes after the last task in critical chain
                last_task_id = buffer.connected_to
                last_task = self.tasks[last_task_id]

                # Set buffer dates
                buffer.start_date = last_task.end_date
                buffer.end_date = buffer.start_date + timedelta(days=buffer.size)

            elif buffer.buffer_type == "feeding":
                # Feeding buffer comes between feeding chain and critical chain
                # We need to find the predecessor task (last in feeding chain)
                predecessors = list(self.task_graph.predecessors(buffer_id))
                if not predecessors:
                    continue  # Skip if no predecessors found

                predecessor_task_id = predecessors[0]
                predecessor_task = self.tasks[predecessor_task_id]

                # Set buffer start date
                buffer.start_date = predecessor_task.end_date
                buffer.end_date = buffer.start_date + timedelta(days=buffer.size)

                # Update the connected critical task's start date if needed
                critical_task_id = buffer.connected_to
                critical_task = self.tasks[critical_task_id]

                if critical_task.start_date < buffer.end_date:
                    # Need to push the critical task later
                    delay = (buffer.end_date - critical_task.start_date).days
                    self._delay_task_and_dependents(critical_task_id, delay)

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

        # Identify feeding chains
        self.identify_feeding_chains()

        # Calculate and add feeding buffers to the network
        self.calculate_feeding_buffers()

        # Update schedule with buffers
        self.apply_buffer_to_schedule()

        return self.tasks

    def visualize_dependency_network(self, filename=None):
        """Visualize the task dependency network with critical chain and feeding chains highlighted."""
        G = self.task_graph

        # Set node colors and shapes
        node_colors = []
        node_shapes = []
        for node in G.nodes:
            # Check if this is a buffer node
            is_buffer = False
            if hasattr(self, "buffers") and node in self.buffers:
                is_buffer = True
                if self.buffers[node].buffer_type == "project":
                    node_colors.append("green")
                else:  # feeding buffer
                    node_colors.append("yellow")
                node_shapes.append("s")  # square for buffers
            elif node in self.critical_chain:
                node_colors.append("red")
                node_shapes.append("o")  # circle for tasks
            elif any(node in chain_info["chain"] for chain_info in self.feeding_chains):
                node_colors.append("orange")
                node_shapes.append("o")
            else:
                node_colors.append("skyblue")
                node_shapes.append("o")

        # Set edge colors - highlight edges in feeding chains
        edge_colors = []
        for u, v in G.edges:
            # Check if either node is a buffer
            is_buffer_edge = False
            if hasattr(self, "buffers"):
                if u in self.buffers or v in self.buffers:
                    if u in self.buffers and self.buffers[u].buffer_type == "project":
                        edge_colors.append("green")
                        is_buffer_edge = True
                    elif v in self.buffers and self.buffers[v].buffer_type == "project":
                        edge_colors.append("green")
                        is_buffer_edge = True
                    else:
                        edge_colors.append("yellow")
                        is_buffer_edge = True

            if is_buffer_edge:
                continue

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

        # Draw nodes with different shapes for buffers
        for shape in set(node_shapes):
            # Get indices of nodes with this shape
            indices = [i for i, s in enumerate(node_shapes) if s == shape]

            # Get corresponding nodes and colors
            node_list = [list(G.nodes)[i] for i in indices]
            color_list = [node_colors[i] for i in indices]

            if shape == "o":  # circles for tasks
                nx.draw_networkx_nodes(
                    G,
                    pos,
                    nodelist=node_list,
                    node_color=color_list,
                    node_size=500,
                    node_shape=shape,
                )
            else:  # squares for buffers
                nx.draw_networkx_nodes(
                    G,
                    pos,
                    nodelist=node_list,
                    node_color=color_list,
                    node_size=700,
                    node_shape=shape,
                )

        # Draw edges
        nx.draw_networkx_edges(G, pos, edge_color=edge_colors, arrows=True)

        # Draw labels
        labels = {}
        for node in G.nodes:
            if hasattr(self, "buffers") and node in self.buffers:
                buffer = self.buffers[node]
                labels[node] = f"{buffer.id}\n{buffer.size}d"
            else:
                # It's a regular task
                if node in self.tasks:
                    labels[node] = f"{node}: {self.tasks[node].name}"
                else:
                    labels[node] = str(node)

        nx.draw_networkx_labels(G, pos, labels=labels, font_size=10)

        # Create a legend
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch

        legend_elements = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="red",
                markersize=10,
                label="Critical Chain Task",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="orange",
                markersize=10,
                label="Feeding Chain Task",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="skyblue",
                markersize=10,
                label="Other Task",
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="w",
                markerfacecolor="green",
                markersize=10,
                label="Project Buffer",
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="w",
                markerfacecolor="yellow",
                markersize=10,
                label="Feeding Buffer",
            ),
            Line2D([0], [0], color="red", lw=2, label="Critical Chain"),
            Line2D([0], [0], color="orange", lw=2, label="Feeding Chain"),
            Line2D([0], [0], color="yellow", lw=2, label="Buffer Connection"),
            Line2D([0], [0], color="green", lw=2, label="Project Buffer Connection"),
        ]
        plt.legend(handles=legend_elements, loc="upper right")

        plt.title(
            "Project Task Dependencies with Critical Chain, Feeding Chains, and Buffers"
        )
        plt.axis("off")

        # Save or show the chart
        if filename:
            plt.savefig(filename, dpi=300, bbox_inches="tight")
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

        # Check if project buffer exists and is not None
        if hasattr(self, "project_buffer") and self.project_buffer is not None:
            buffer_end = last_task_end + timedelta(days=self.project_buffer)
        else:
            # If we're using the new Buffer object approach
            if (
                hasattr(self, "project_buffer_id")
                and self.project_buffer_id in self.buffers
            ):
                project_buffer = self.buffers[self.project_buffer_id]
                buffer_size = project_buffer.size
                buffer_end = last_task_end + timedelta(days=buffer_size)
            else:
                # No buffer or couldn't find it - use task end date
                buffer_end = last_task_end

        report.append(f"Projected End Date: {buffer_end.strftime('%Y-%m-%d')}")
        report.append(f"Project Duration: {(buffer_end - self.start_date).days} days")

        # Report on buffer (if exists)
        buffer_size = None
        if hasattr(self, "project_buffer") and self.project_buffer is not None:
            buffer_size = self.project_buffer
        elif (
            hasattr(self, "project_buffer_id")
            and self.project_buffer_id in self.buffers
        ):
            buffer_size = self.buffers[self.project_buffer_id].size

        if buffer_size is not None:
            report.append(f"Project Buffer: {buffer_size} days")

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

            # Get buffer size either from the old or new approach
            if (
                hasattr(self, "feeding_buffers")
                and last_task_id in self.feeding_buffers
            ):
                buffer_size = self.feeding_buffers.get(last_task_id, 0)
            elif (
                hasattr(self, "feeding_buffer_ids")
                and last_task_id in self.feeding_buffer_ids
            ):
                buffer_id = self.feeding_buffer_ids[last_task_id]
                buffer_size = self.buffers[buffer_id].size
            else:
                buffer_size = 0

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
            # Format resources list
            if isinstance(task.resources, str):
                resources_str = task.resources
            elif isinstance(task.resources, list):
                resources_str = ", ".join(task.resources)
            else:
                resources_str = ""

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

        # Add buffer information if available
        if hasattr(self, "buffers") and self.buffers:
            report.append("\nBuffer Information:")
            report.append("------------------")
            for buffer_id, buffer in self.buffers.items():
                report.append(f"Buffer {buffer.id}: {buffer.name}")
                report.append(f"  Type: {buffer.buffer_type}")
                report.append(f"  Size: {buffer.size} days")
                if hasattr(buffer, "start_date") and hasattr(buffer, "end_date"):
                    report.append(
                        f"  Start: {buffer.start_date.strftime('%Y-%m-%d')}, End: {buffer.end_date.strftime('%Y-%m-%d')}"
                    )
                report.append("")

        return "\n".join(report)

    def visualize_schedule(self, filename=None):
        """Visualize the project schedule as a Gantt chart with resource utilization."""
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        from matplotlib.ticker import FuncFormatter
        from matplotlib.patches import Patch

        # Calculate the project duration for x-axis sizing
        all_end_dates = []

        # Include both original and updated end dates
        for task in self.tasks.values():
            all_end_dates.append(task.end_date)
            if hasattr(task, "new_end_date"):
                all_end_dates.append(task.new_end_date)
            if hasattr(task, "actual_end_date"):
                all_end_dates.append(task.actual_end_date)

        # Include buffer end dates if they exist
        if hasattr(self, "buffers"):
            for buffer in self.buffers.values():
                if hasattr(buffer, "end_date"):
                    all_end_dates.append(buffer.end_date)
                if hasattr(buffer, "new_end_date"):
                    all_end_dates.append(buffer.new_end_date)

        # Get current execution date if available
        if hasattr(self, "execution_date"):
            status_date = self.execution_date
            all_end_dates.append(status_date)  # Ensure status date is considered
        else:
            status_date = None

        last_end_date = max(all_end_dates) if all_end_dates else self.start_date
        project_duration = (last_end_date - self.start_date).days

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
        sorted_tasks = sorted(
            self.tasks.values(),
            key=lambda x: getattr(x, "new_start_date", x.start_date),
        )

        # Plot each task
        for i, task in enumerate(sorted_tasks):
            # Determine start and end days for the task
            if hasattr(task, "status") and task.status == "completed":
                # Completed task - use actual start and end
                start_day = (task.actual_start_date - self.start_date).days
                duration = (task.actual_end_date - task.actual_start_date).days
                # Use solid color for completed tasks
                alpha = 1.0
                hatch = None
            elif hasattr(task, "status") and task.status == "in_progress":
                # In progress task - use actual start and current date + remaining
                start_day = (task.actual_start_date - self.start_date).days

                # Show both completed and remaining portions
                original_duration = task.duration
                remaining_duration = task.remaining_duration
                completed_duration = original_duration - remaining_duration

                # Need to handle both portions separately
                if status_date:
                    # Define the completed portion end
                    completed_end_day = (
                        task.actual_start_date - self.start_date
                    ).days + completed_duration
                    # Show completed portion
                    ax_gantt.barh(
                        i, completed_duration, left=start_day, color="green", alpha=0.8
                    )

                    # Show remaining portion separately
                    start_remaining = completed_end_day
                    ax_gantt.barh(
                        i,
                        remaining_duration,
                        left=start_remaining,
                        color="lightblue",
                        alpha=0.6,
                        hatch="///",
                    )

                    # For main color determination, use full duration
                    duration = completed_duration + remaining_duration
                else:
                    # If no status date, show original duration
                    duration = original_duration
                    # Use pattern for in-progress tasks
                    alpha = 0.7
                    hatch = "///"
            elif hasattr(task, "new_start_date"):
                # Task with updated schedule but not started
                start_day = (task.new_start_date - self.start_date).days
                duration = (
                    task.remaining_duration
                    if hasattr(task, "remaining_duration")
                    else task.duration
                )
                # Use lighter color for scheduled but not started tasks
                alpha = 0.5
                hatch = None
            else:
                # Original planned schedule
                start_day = (task.start_date - self.start_date).days
                duration = task.duration
                # Use transparent for original plan
                alpha = 0.5
                hatch = None

            # Determine the color based on critical chain, feeding chain, etc.
            if task.id in self.critical_chain:
                color = "red"
            elif any(
                task.id in chain_info["chain"] for chain_info in self.feeding_chains
            ):
                color = "orange"
            else:
                color = "blue"

            # If not rendering progress separately, plot the full bar
            if not (
                hasattr(task, "status") and task.status == "in_progress" and status_date
            ):
                ax_gantt.barh(
                    i, duration, left=start_day, color=color, alpha=alpha, hatch=hatch
                )

            # Format the resource list
            if isinstance(task.resources, str):
                resource_str = task.resources
            elif isinstance(task.resources, list):
                resource_str = ", ".join(task.resources)
            else:
                resource_str = ""

            # Add status indicator if available
            status_str = ""
            if hasattr(task, "status"):
                if task.status == "completed":
                    status_str = " [DONE]"
                elif task.status == "in_progress":
                    progress_pct = (
                        (task.duration - task.remaining_duration) / task.duration * 100
                    )
                    status_str = f" [{progress_pct:.0f}%]"

            # Add task name, ID, resources and status
            ax_gantt.text(
                start_day + duration / 2,
                i,
                f"{task.id}: {task.name} [{resource_str}]{status_str}",
                ha="center",
                va="center",
                color="black",
            )

        # Plot buffers
        buffer_count = 0
        if hasattr(self, "buffers"):
            for buffer_id, buffer in self.buffers.items():
                if not hasattr(buffer, "start_date") and not hasattr(
                    buffer, "new_start_date"
                ):
                    continue

                # Determine buffer start and size based on execution status
                if hasattr(buffer, "new_start_date"):
                    # Updated buffer status
                    start_day = (buffer.new_start_date - self.start_date).days
                    remaining_size = getattr(buffer, "remaining_size", buffer.size)

                    # Plot consumed buffer portion if partially consumed
                    if remaining_size < buffer.size:
                        consumed_size = buffer.size - remaining_size
                        buffer_start_consumed = start_day - consumed_size

                        # Plot consumed portion in red
                        ax_gantt.barh(
                            len(sorted_tasks) + buffer_count,
                            consumed_size,
                            left=buffer_start_consumed,
                            color="red",
                            alpha=0.6,
                            hatch="///",
                        )

                        # Plot remaining portion
                        ax_gantt.barh(
                            len(sorted_tasks) + buffer_count,
                            remaining_size,
                            left=start_day,
                            color="green"
                            if buffer.buffer_type == "project"
                            else "yellow",
                            alpha=0.6,
                        )
                    else:
                        # Full buffer remaining
                        ax_gantt.barh(
                            len(sorted_tasks) + buffer_count,
                            buffer.size,
                            left=start_day,
                            color="green"
                            if buffer.buffer_type == "project"
                            else "yellow",
                            alpha=0.6,
                        )
                else:
                    # Original buffer plan
                    start_day = (buffer.start_date - self.start_date).days
                    ax_gantt.barh(
                        len(sorted_tasks) + buffer_count,
                        buffer.size,
                        left=start_day,
                        color="green" if buffer.buffer_type == "project" else "yellow",
                        alpha=0.4,
                    )

                # Add buffer label
                consumed_str = ""
                if (
                    hasattr(buffer, "remaining_size")
                    and buffer.remaining_size < buffer.size
                ):
                    consumed = buffer.size - buffer.remaining_size
                    consumed_str = f" (Used: {consumed}/{buffer.size})"

                ax_gantt.text(
                    start_day + buffer.size / 2,
                    len(sorted_tasks) + buffer_count,
                    f"{buffer.name}{consumed_str}",
                    ha="center",
                    va="center",
                    color="black",
                )

                buffer_count += 1

        # Add a vertical line for status date if available - EXPLICITLY ENSURE THIS HAPPENS
        if status_date:
            status_day = (status_date - self.start_date).days
            # Draw it with higher zorder to ensure it's on top of other elements
            ax_gantt.axvline(
                x=status_day, color="green", linestyle="--", linewidth=2, zorder=5
            )
            # Add label with rotation for better visibility
            ax_gantt.text(
                status_day,
                -0.5,
                f"Status Date: {status_date.strftime('%Y-%m-%d')}",
                ha="center",
                va="bottom",
                rotation=90,
                color="green",
                fontweight="bold",
            )

        # Format the Gantt chart
        row_count = len(sorted_tasks) + buffer_count
        ax_gantt.set_yticks(range(row_count))

        # Create custom y-tick labels
        yticklabels = []
        for task in sorted_tasks:
            yticklabels.append(task.name)

        if hasattr(self, "buffers"):
            for buffer_id, buffer in self.buffers.items():
                if hasattr(buffer, "start_date") or hasattr(buffer, "new_start_date"):
                    yticklabels.append(buffer.name)

        formatter = FuncFormatter(
            lambda x, _: yticklabels[int(x)] if 0 <= int(x) < len(yticklabels) else ""
        )
        ax_gantt.yaxis.set_major_formatter(formatter)

        # Add title with status date if available
        if status_date:
            ax_gantt.set_title(
                f"CCPM Project Schedule (Status as of {status_date.strftime('%Y-%m-%d')})"
            )
        else:
            ax_gantt.set_title("CCPM Project Schedule (Baseline Plan)")

        ax_gantt.grid(axis="x", alpha=0.3)

        # Add legend for task status
        legend_elements = [
            Patch(facecolor="red", alpha=0.6, label="Critical Chain Task"),
            Patch(facecolor="orange", alpha=0.6, label="Feeding Chain Task"),
            Patch(facecolor="blue", alpha=0.6, label="Regular Task"),
            Patch(facecolor="green", alpha=0.8, label="Completed Work"),
            Patch(
                facecolor="lightblue", alpha=0.6, hatch="///", label="Remaining Work"
            ),
            Patch(facecolor="yellow", alpha=0.6, label="Feeding Buffer"),
            Patch(facecolor="green", alpha=0.6, label="Project Buffer"),
            Patch(facecolor="red", alpha=0.6, hatch="///", label="Consumed Buffer"),
        ]
        ax_gantt.legend(handles=legend_elements, loc="upper right", ncol=2)

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

        ax_resource.set_xlim(0, project_duration_int + 5)  # Add some padding

        # Set y-axis limits to give room for the annotations
        ax_resource.set_ylim(-0.5, len(all_resources) - 0.5)

        # Add a legend for resource demand colors
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

        # Add vertical line for status date in resource chart too
        if status_date:
            status_day = (status_date - self.start_date).days
            ax_resource.axvline(
                x=status_day, color="green", linestyle="--", linewidth=2, zorder=5
            )

        # Adjust layout
        plt.tight_layout()

        # Save or show the chart
        if filename:
            plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.show()

    def _calculate_resource_utilization(self):
        """Calculate the daily demand for each resource throughout the project, accounting for task progress."""
        # Find the latest project date considering both original and updated schedules
        latest_date = self.start_date

        for task in self.tasks.values():
            # Check for actual end dates (completed tasks)
            if hasattr(task, "actual_end_date") and task.actual_end_date > latest_date:
                latest_date = task.actual_end_date

            # Check for expected end dates (in-progress tasks)
            elif hasattr(task, "new_end_date") and task.new_end_date > latest_date:
                latest_date = task.new_end_date

            # Check original end date
            elif task.end_date > latest_date:
                latest_date = task.end_date

        # Include project buffer (if exists)
        if (
            hasattr(self, "project_buffer_id")
            and self.project_buffer_id in self.buffers
        ):
            buffer = self.buffers[self.project_buffer_id]
            if hasattr(buffer, "new_end_date") and buffer.new_end_date > latest_date:
                latest_date = buffer.new_end_date
            elif hasattr(buffer, "end_date") and buffer.end_date > latest_date:
                latest_date = buffer.end_date

        # Initialize a dictionary to hold resource utilization
        # Format: {resource_name: {day_number: demand_count}}
        resource_usage = {}

        # Calculate the demand for each resource on each day
        for task in self.tasks.values():
            # Determine the task's current timeline based on its status
            if hasattr(task, "status") and task.status == "completed":
                # Completed task - use actual dates
                start_date = task.actual_start_date
                end_date = task.actual_end_date
                duration = (end_date - start_date).days
            elif hasattr(task, "status") and task.status == "in_progress":
                # In-progress task - use actual start and remaining duration
                start_date = task.actual_start_date
                current_date = getattr(self, "execution_date", datetime.now())

                # From start to current date, the task was active
                past_duration = (current_date - start_date).days

                # For future resource usage, use the remaining duration
                remaining_duration = task.remaining_duration

                # Total duration for this task
                duration = past_duration + remaining_duration

                # End date is calculated from the status date
                end_date = current_date + timedelta(days=remaining_duration)
            elif hasattr(task, "new_start_date") and hasattr(task, "new_end_date"):
                # Task with updated schedule
                start_date = task.new_start_date
                end_date = task.new_end_date
                duration = (end_date - start_date).days
            else:
                # Original planned schedule
                start_date = task.start_date
                end_date = task.end_date
                duration = task.duration

            # Calculate the start and end days relative to project start
            start_day = (start_date - self.start_date).days

            # Process each day of the task duration
            for day in range(
                start_day, start_day + max(1, duration)
            ):  # Ensure at least 1 day
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

    def visualize_fever_chart(self, filename=None):
        """
        Generate and display a CCPM fever chart showing buffer consumption over time.

        The fever chart shows:
        - X-axis: Project completion percentage
        - Y-axis: Buffer consumption percentage
        - Current status point
        - Status history (if available)
        - Warning zones (green, yellow, red)
        """
        if not hasattr(self, "buffers"):
            print("No buffers found. Please run the scheduler first.")
            return

        import matplotlib.pyplot as plt
        import numpy as np

        # Create the figure
        fig, ax = plt.subplots(figsize=(10, 8))

        # Calculate project completion percentage
        total_duration = sum(task.duration for task in self.tasks.values())
        completed_duration = sum(
            task.duration - getattr(task, "remaining_duration", task.duration)
            for task in self.tasks.values()
        )

        if total_duration == 0:
            completion_pct = 0
        else:
            completion_pct = completed_duration / total_duration * 100

        # Calculate buffer consumption
        # For project buffer
        if hasattr(self, "project_buffer_id"):
            project_buffer = self.buffers[self.project_buffer_id]
            original_size = project_buffer.size
            remaining = getattr(project_buffer, "remaining_size", original_size)

            if original_size == 0:
                buffer_consumption_pct = 0
            else:
                buffer_consumption_pct = (
                    (original_size - remaining) / original_size * 100
                )

            # Get history if available
            if hasattr(project_buffer, "consumption_history"):
                history = project_buffer.consumption_history
                history_x = []
                history_y = []

                # Calculate completion % for each historical point
                # This is an approximation since we don't have task completion at each point
                for i, entry in enumerate(history):
                    # Simplistic approach: assume linear progress
                    history_x.append(completion_pct * i / len(history))

                    # Calculate buffer consumption
                    hist_remaining = entry["remaining"]
                    hist_consumption_pct = (
                        (original_size - hist_remaining) / original_size * 100
                    )
                    history_y.append(hist_consumption_pct)
        else:
            # No project buffer defined
            buffer_consumption_pct = 0

        # Draw the background zones
        # Green zone (safe)
        ax.fill_between([0, 100], [0, 0], [33, 100], color="green", alpha=0.2)

        # Yellow zone (warning)
        ax.fill_between([0, 100], [33, 100], [67, 100], color="yellow", alpha=0.2)

        # Red zone (danger)
        ax.fill_between([0, 100], [67, 100], [100, 100], color="red", alpha=0.2)

        # Draw the OK line (diagonal)
        ax.plot([0, 100], [0, 100], "k--", alpha=0.5)

        # Plot history if available
        if hasattr(self, "project_buffer_id") and hasattr(
            project_buffer, "consumption_history"
        ):
            ax.plot(history_x, history_y, "bo-", alpha=0.6, label="Status History")

        # Plot the current point
        ax.plot(
            completion_pct,
            buffer_consumption_pct,
            "ro",
            markersize=10,
            label="Current Status",
        )

        # Add labels
        ax.text(
            completion_pct + 2,
            buffer_consumption_pct + 2,
            f"({completion_pct:.1f}%, {buffer_consumption_pct:.1f}%)",
            fontsize=10,
        )

        # Set axis labels and title
        ax.set_xlabel("Project Completion %")
        ax.set_ylabel("Buffer Consumption %")
        ax.set_title("CCPM Fever Chart")

        # Set axis limits
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)

        # Add grid
        ax.grid(True, linestyle="--", alpha=0.7)

        # Add legend
        ax.legend()

        # Add annotations for zones
        ax.text(5, 15, "Safe", fontsize=12, color="green")
        ax.text(5, 50, "Warning", fontsize=12, color="orange")
        ax.text(5, 85, "Critical", fontsize=12, color="red")

        # Save or display
        if filename:
            plt.savefig(filename, dpi=300, bbox_inches="tight")

        plt.tight_layout()
        plt.show()

        return completion_pct, buffer_consumption_pct

    def set_execution_date(self, execution_date):
        """
        Set the current execution date for tracking and reporting.

        Args:
            execution_date: The date to use for execution phase calculations
        """
        self.execution_date = execution_date

        # Initialize recalculate_network_from_progress if it doesn't exist yet
        if not hasattr(self, "recalculate_network_from_progress"):
            # Add placeholder that does nothing if the method doesn't exist yet
            # This allows partial implementation during transition
            self.recalculate_network_from_progress = lambda date: None
        else:
            # Recalculate the network based on current progress
            self.recalculate_network_from_progress(execution_date)

        return execution_date

    def recalculate_network_from_progress(self, status_date):
        """
        Recalculate the entire network schedule based on task progress.
        This will update all downstream task dates and buffer consumption.

        Args:
            status_date: The date to use for calculations (usually today)
        """
        # Get topological sort of tasks
        task_order = list(nx.topological_sort(self.task_graph))

        # First pass: update task start dates based on progress
        for node in task_order:
            # Check if this is a buffer
            if hasattr(self, "buffers") and node in self.buffers:
                continue  # Skip buffers in this pass, we'll handle them later

            # Skip if not a task
            if node not in self.tasks:
                continue

            task = self.tasks[node]

            # If the task is completed or in progress, handle actual dates
            if hasattr(task, "status") and task.status in ["completed", "in_progress"]:
                # Task has started - use actual start date and remaining duration
                if not hasattr(task, "remaining_duration"):
                    task.remaining_duration = task.duration  # Default if not set

                # For completed tasks, ensure end date is set
                if task.status == "completed":
                    if not hasattr(task, "actual_end_date"):
                        task.actual_end_date = status_date

                    # Use the actual dates for new_start_date and new_end_date
                    task.new_start_date = task.actual_start_date
                    task.new_end_date = task.actual_end_date
                else:
                    # For in-progress tasks, calculate expected end date
                    task.new_start_date = task.actual_start_date
                    task.new_end_date = status_date + timedelta(
                        days=task.remaining_duration
                    )
            else:
                # Task hasn't started yet - calculate based on predecessors
                predecessors = list(self.task_graph.predecessors(node))

                if not predecessors:
                    # Start task with no predecessors - keep original date if in future
                    if (
                        not hasattr(task, "new_start_date")
                        or task.start_date > status_date
                    ):
                        task.new_start_date = task.start_date
                        task.remaining_duration = task.duration
                    else:
                        # Should have started by now but hasn't - update to today
                        task.new_start_date = status_date
                        task.remaining_duration = task.duration
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
                            elif hasattr(pred_task, "new_end_date"):
                                # Not started but rescheduled - use new dates
                                pred_end = pred_task.new_end_date
                            else:
                                # Not started or updated - use original schedule
                                pred_end = pred_task.end_date

                            if pred_end > latest_end:
                                latest_end = pred_end
                        elif hasattr(self, "buffers") and pred_id in self.buffers:
                            # Predecessor is a buffer
                            buffer = self.buffers[pred_id]
                            if hasattr(buffer, "new_end_date"):
                                if buffer.new_end_date > latest_end:
                                    latest_end = buffer.new_end_date

                    # Set new start date to latest predecessor end
                    task.new_start_date = latest_end
                    task.remaining_duration = (
                        task.duration
                    )  # Reset to full duration for not-started tasks

                # Calculate new end date
                task.new_end_date = task.new_start_date + timedelta(
                    days=task.remaining_duration
                )

        # Second pass: update buffer dates and consumption
        if hasattr(self, "buffers"):
            for buffer_id, buffer in self.buffers.items():
                # Get predecessor and successor nodes
                predecessors = list(self.task_graph.predecessors(buffer_id))
                successors = list(self.task_graph.successors(buffer_id))

                if not predecessors or not successors:
                    continue  # Skip if buffer isn't properly connected

                # Get predecessor task
                pred_id = predecessors[0]
                if pred_id in self.tasks:
                    pred_task = self.tasks[pred_id]

                    # Calculate predecessor end date
                    if hasattr(pred_task, "status") and pred_task.status == "completed":
                        pred_end = pred_task.actual_end_date
                    elif (
                        hasattr(pred_task, "status")
                        and pred_task.status == "in_progress"
                    ):
                        pred_end = status_date + timedelta(
                            days=pred_task.remaining_duration
                        )
                    elif hasattr(pred_task, "new_end_date"):
                        pred_end = pred_task.new_end_date
                    else:
                        pred_end = pred_task.end_date

                    # Set buffer start date to predecessor end
                    buffer.new_start_date = pred_end

                    # Calculate buffer consumption based on successor task
                    succ_id = successors[0]
                    if succ_id in self.tasks:
                        succ_task = self.tasks[succ_id]

                        # Get the original scheduled start for successor
                        original_succ_start = succ_task.start_date

                        # Get the new expected start for successor
                        if hasattr(succ_task, "new_start_date"):
                            new_succ_start = succ_task.new_start_date
                        else:
                            new_succ_start = succ_task.start_date

                        # Calculate how much buffer is needed
                        if new_succ_start < buffer.new_start_date:
                            # Successor should start after buffer, but now it can't
                            # This means we need to consume the entire buffer and push the task
                            buffer.remaining_size = 0
                            buffer.new_end_date = buffer.new_start_date

                            # Update the successor task start date
                            succ_task.new_start_date = buffer.new_start_date
                            succ_task.new_end_date = (
                                succ_task.new_start_date
                                + timedelta(
                                    days=getattr(
                                        succ_task,
                                        "remaining_duration",
                                        succ_task.duration,
                                    )
                                )
                            )
                        else:
                            # Calculate how much buffer is consumed
                            buffer_needed = (
                                new_succ_start - buffer.new_start_date
                            ).days

                            # If buffer_needed is negative, we don't need any buffer
                            if buffer_needed <= 0:
                                buffer.remaining_size = buffer.size
                            else:
                                # Calculate remaining buffer
                                buffer.remaining_size = max(
                                    0, buffer.size - buffer_needed
                                )

                            # Set buffer end date
                            buffer.new_end_date = buffer.new_start_date + timedelta(
                                days=buffer.size
                            )

                    # Record buffer consumption history
                    if not hasattr(buffer, "consumption_history"):
                        buffer.consumption_history = []

                    buffer.consumption_history.append(
                        {"date": status_date, "remaining": buffer.remaining_size}
                    )

        # Return updated tasks and buffers
        return self.tasks, self.buffers if hasattr(self, "buffers") else None

    def generate_execution_report(self, status_date=None):
        """
        Generate a text report of the project's execution status.

        Args:
            status_date: The date to use for the report (defaults to self.execution_date or today)

        Returns:
            A formatted string with the execution report
        """
        if status_date is None:
            if hasattr(self, "execution_date"):
                status_date = self.execution_date
            else:
                status_date = datetime.now()

        report = []
        report.append("CCPM Project Execution Status Report")
        report.append("===================================")
        report.append(f"Report Date: {status_date.strftime('%Y-%m-%d')}")
        report.append(f"Project Start Date: {self.start_date.strftime('%Y-%m-%d')}")

        # Calculate overall project completion
        total_duration = sum(task.duration for task in self.tasks.values())
        completed_duration = sum(
            task.duration - getattr(task, "remaining_duration", task.duration)
            for task in self.tasks.values()
        )

        if total_duration > 0:
            completion_pct = completed_duration / total_duration * 100
            report.append(f"Project Completion: {completion_pct:.1f}%")

        # Find projected end date
        latest_end_date = status_date
        for task_id, task in self.tasks.items():
            if hasattr(task, "new_end_date") and task.new_end_date > latest_end_date:
                latest_end_date = task.new_end_date

        # Add project buffer if exists
        if (
            hasattr(self, "project_buffer_id")
            and self.project_buffer_id in self.buffers
        ):
            project_buffer = self.buffers[self.project_buffer_id]
            if hasattr(project_buffer, "new_end_date"):
                buffer_end = project_buffer.new_end_date
                if buffer_end > latest_end_date:
                    latest_end_date = buffer_end

        report.append(f"Projected End Date: {latest_end_date.strftime('%Y-%m-%d')}")
        original_end = max(task.end_date for task in self.tasks.values())
        if (
            hasattr(self, "project_buffer_id")
            and self.project_buffer_id in self.buffers
        ):
            original_buffer_end = original_end + timedelta(
                days=self.buffers[self.project_buffer_id].size
            )
            report.append(
                f"Original End Date: {original_buffer_end.strftime('%Y-%m-%d')}"
            )

            if latest_end_date > original_buffer_end:
                delay = (latest_end_date - original_buffer_end).days
                report.append(f"Project is currently {delay} days behind schedule")
            elif latest_end_date < original_buffer_end:
                ahead = (original_buffer_end - latest_end_date).days
                report.append(f"Project is currently {ahead} days ahead of schedule")
            else:
                report.append("Project is currently on schedule")

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
                report.append(f"  Original Duration: {task.duration} days")
                report.append(f"  Remaining Duration: {task.remaining_duration} days")
                report.append(
                    f"  Progress: {((task.duration - task.remaining_duration) / task.duration * 100):.1f}%"
                )
                report.append(
                    f"  Started On: {task.actual_start_date.strftime('%Y-%m-%d')}"
                )
                report.append(
                    f"  Expected Completion: {(status_date + timedelta(days=task.remaining_duration)).strftime('%Y-%m-%d')}"
                )
                report.append("")

        # Next tasks to start
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

            # Show the next 5 tasks
            for task in not_started[:5]:
                start_date = getattr(task, "new_start_date", task.start_date)

                report.append(f"Task {task.id}: {task.name}")
                report.append(f"  Duration: {task.duration} days")
                report.append(f"  Start Date: {start_date.strftime('%Y-%m-%d')}")

                # Format the resource list
                if isinstance(task.resources, str):
                    resource_str = task.resources
                elif isinstance(task.resources, list):
                    resource_str = ", ".join(task.resources)
                else:
                    resource_str = ""

                report.append(f"  Resources: {resource_str}")
                report.append("")

        # Completed tasks
        completed = [
            task
            for task in self.tasks.values()
            if hasattr(task, "status") and task.status == "completed"
        ]

        if completed:
            report.append(f"\nCompleted Tasks: {len(completed)} of {len(self.tasks)}")

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
            Updated tasks and buffers
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
                progress_pct = progress_percentages.get(
                    task_id, 50
                )  # Default to 50% if not specified

                # Calculate remaining duration
                remaining = task.duration * (1 - progress_pct / 100)
                remaining = max(
                    0.1, remaining
                )  # Ensure some remaining work unless complete

                self.update_task_progress(task_id, remaining, simulation_date)

        # Generate report
        report = self.generate_execution_report(simulation_date)
        print(report)

        # Visualize updated schedule
        self.visualize_schedule("ccpm_execution_gantt.png")

        # Generate fever chart
        self.visualize_fever_chart("ccpm_fever_chart.png")

        return self.tasks, self.buffers if hasattr(self, "buffers") else None

    # Add a new method to explicitly set the actual start date
    def set_task_actual_start_date(self, task_id, actual_start_date):
        """
        Explicitly set the actual start date for a task.

        Args:
            task_id: The ID of the task to update
            actual_start_date: The actual date when the task started
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found in the project")

        task = self.tasks[task_id]
        task.actual_start_date = actual_start_date

        # Mark the task as in progress if it wasn't already
        if not hasattr(task, "status") or task.status not in [
            "completed",
            "in_progress",
        ]:
            task.status = "in_progress"
            task.remaining_duration = (
                task.duration
            )  # Default to full duration remaining

        return task

    def update_task_progress(self, task_id, remaining_duration, status_date=None):
        """
        Update task progress during execution phase.

        Args:
            task_id: The ID of the task to update
            remaining_duration: The remaining duration in days
            status_date: The date of this status update (defaults to today)
        """
        if status_date is None:
            status_date = datetime.now()

        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found in the project")

        task = self.tasks[task_id]

        # Store the original duration if not already tracking
        if not hasattr(task, "original_duration"):
            task.original_duration = task.duration

        # Store the previous remaining duration
        previous_remaining = getattr(task, "remaining_duration", task.duration)

        # Update the remaining duration
        task.remaining_duration = remaining_duration

        # Keep history of updates for this task if not already doing so
        if not hasattr(task, "progress_history"):
            task.progress_history = []

        # Add to history
        task.progress_history.append(
            {"date": status_date, "remaining": remaining_duration}
        )

        # Update task status
        if remaining_duration <= 0:
            task.status = "completed"
            task.actual_end_date = status_date
        else:
            task.status = "in_progress"
            # Update the expected end date based on status date and remaining duration
            task.expected_end_date = status_date + timedelta(days=remaining_duration)

        # If this is the first update, set the actual start date
        if not hasattr(task, "actual_start_date"):
            # If status_date is after the scheduled start_date, assume the task started on its scheduled start date
            if status_date > task.start_date:
                task.actual_start_date = task.start_date
            else:
                # If status update is before the scheduled start, use the status date
                task.actual_start_date = status_date

        # Recalculate the network to account for this change
        self.recalculate_network_from_progress(status_date)

        return task


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

    # Small example from Larry Leech's book
    resources = ["Red", "Green", "Magenta", "Blue"]
    # Define tasks - ID: Task(ID, Name, Duration, Dependencies, Resources)
    tasks = {
        1: Task(1, "T1.1", 30, [], ["Red"]),
        2: Task(2, "T1.2", 20, [1], ["Green"]),
        3: Task(3, "T3", 30, [5, 2], ["Magenta"]),
        4: Task(4, "T2.1", 20, [], ["Blue"]),
        5: Task(5, "T2.2", 10, [4], ["Green"]),
    }

    # # Large example from Larry Leech's book
    # resources = ["Red", "Green", "Magenta", "Blue", "Black"]
    # # Define tasks - ID: Task(ID, Name, Duration, Dependencies, Resources)
    # tasks = {
    #     1: Task(1, "A-1", 10, [], "Magenta"),
    #     2: Task(2, "A-2", 20, [1], "Black"),
    #     3: Task(3, "A-3", 30, [2], "Green"),
    #     4: Task(4, "A-4", 20, [3], "Red"),
    #     5: Task(5, "A-5", 40, [4, 9], "Magenta"),
    #     6: Task(6, "A-6", 28, [5], "Red"),
    #     7: Task(7, "B-2", 20, [], "Magenta"),
    #     8: Task(8, "B-3", 20, [7], "Blue"),
    #     9: Task(9, "B-4", 10, [8], "Red"),
    #     10: Task(10, "C-3", 30, [], "Blue"),
    #     11: Task(11, "C-4", 20, [10], "Green"),
    #     12: Task(12, "C-5", 30, [11, 15], "Red"),
    #     13: Task(13, "C-6", 10, [12], "Magenta"),
    #     14: Task(14, "D-3", 40, [], "Blue"),
    #     15: Task(15, "D-4", 10, [14], "Green"),
    #     16: Task(16, "Done", 0, [13, 6], "Black"),
    # }

    # Create scheduler with both project buffer (50%) and feeding buffer (30%)
    start_date = datetime(2025, 4, 1)  # Today
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
    scheduler.visualize_schedule("ccpm_gantt_01.png")
    scheduler.visualize_dependency_network("ccpm_network_01.png")

    # Generate and print report
    report = scheduler.generate_report()
    print(report)

    # Save report to file
    with open("ccpm_project_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    # Set the execution date to today
    current_date = datetime(2025, 4, 11)
    scheduler.set_execution_date(current_date)

    # Update task progress
    scheduler.update_task_progress(1, 10)
    scheduler.update_task_progress(4, 15)

    # Generate reports
    report = scheduler.generate_execution_report()
    print(report)

    # Visualize the current status
    scheduler.visualize_schedule("ccpm_gantt_02.png")
    scheduler.visualize_fever_chart("ccpm_fever_chart_02.png")


if __name__ == "__main__":
    create_sample_project()
