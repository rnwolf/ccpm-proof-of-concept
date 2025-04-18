import matplotlib.pyplot as plt
import networkx as nx
from datetime import datetime, timedelta


class Task:
    def __init__(
        self, id, name, duration, nominal_duration=None, predecessors="", resources=""
    ):
        self.id = id
        self.name = name
        self.duration = duration  # Optimistic duration
        self.nominal_duration = (
            nominal_duration if nominal_duration else duration * 1.5
        )  # Default to 50% buffer
        self.predecessors = predecessors.split(",") if predecessors else []
        self.predecessors = [p for p in self.predecessors if p]  # Remove empty strings
        self.resources = resources.split(",") if resources else []
        self.resources = [r for r in self.resources if r]  # Remove empty strings
        self.start = 0
        self.finish = 0
        self.type = 0  # 0=unassigned, 1=critical, 2=feeding, 3=free, 4=buffer
        self.progress = 0  # 0-100%

    def __repr__(self):
        return f"Task {self.id}: {self.name} ({self.duration} days)"


class Resource:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.tasks = []

    def __repr__(self):
        return f"Resource {self.id}: {self.name}"


class CriticalChainScheduler:
    def __init__(self):
        self.tasks = []
        self.resources = []
        self.critical_chain = []
        self.secondary_chains = []
        self.all_scheduled_tasks = []
        self.project_data = {
            "start_date": None,
            "calendar": "standard",  # standard (5 days/week) or continuous (7 days/week)
            "hours_per_day": 8,
        }

    def add_task(self, task):
        self.tasks.append(task)

    def add_resource(self, resource):
        self.resources.append(resource)

    def find_critical_chain(self):
        # Find tasks with no predecessors
        start_tasks = [t for t in self.tasks if not t.predecessors]

        if not start_tasks:
            print("Error: No starting tasks found (tasks without predecessors)")
            return

        # Find task with longest total duration path
        max_duration = 0
        best_start_task = None

        for task in start_tasks:
            total_duration = self.calculate_path_duration(task)
            if total_duration > max_duration:
                max_duration = total_duration
                best_start_task = task

        if not best_start_task:
            print("Error: Could not determine best starting task")
            return

        # Build critical chain from best starting task
        self.critical_chain = [best_start_task]
        best_start_task.type = 1
        best_start_task.start = 0
        best_start_task.finish = best_start_task.duration

        # Remove task from unassigned tasks
        self.tasks.remove(best_start_task)

        # Add subsequent tasks to critical chain
        while True:
            antecedents = self.find_antecedents(self.critical_chain[-1])
            if not antecedents:
                break

            # Find antecedent with longest duration
            next_task = max(antecedents, key=lambda t: t.duration)

            # Add to critical chain
            self.critical_chain.append(next_task)
            next_task.type = 1
            next_task.start = self.critical_chain[-2].finish
            next_task.finish = next_task.start + next_task.duration

            # Remove from unassigned tasks
            self.tasks.remove(next_task)

    def calculate_path_duration(self, task, visited=None):
        if visited is None:
            visited = set()

        if task.id in visited:
            return 0

        visited.add(task.id)

        antecedents = self.find_antecedents(task)
        if not antecedents:
            return task.duration

        max_path = 0
        for ant in antecedents:
            path_length = self.calculate_path_duration(ant, visited.copy())
            if path_length > max_path:
                max_path = path_length

        return task.duration + max_path

    def find_antecedents(self, task):
        """Find tasks that have this task as a predecessor"""
        return [t for t in self.tasks if str(task.id) in t.predecessors]

    def identify_secondary_chains(self):
        """Identify secondary (feeding) chains"""
        for cc_task in self.critical_chain:
            # Find tasks that depend on this critical chain task
            dependent_tasks = [
                t for t in self.tasks if str(cc_task.id) in t.predecessors
            ]

            for dep_task in dependent_tasks:
                chain = [dep_task]
                dep_task.type = 2  # Secondary chain
                dep_task.start = cc_task.finish
                dep_task.finish = dep_task.start + dep_task.duration
                self.tasks.remove(dep_task)

                # Check for resource conflicts and resolve them
                self.resolve_resource_conflicts(dep_task)

                # Find tasks that depend on this task
                self.build_chain_recursively(dep_task, chain)

                if chain:
                    self.secondary_chains.append(chain)

    def build_chain_recursively(self, parent_task, chain):
        """Build a chain by recursively adding dependent tasks"""
        dependent_tasks = [
            t for t in self.tasks if str(parent_task.id) in t.predecessors
        ]

        for dep_task in dependent_tasks:
            dep_task.type = 2  # Secondary chain
            dep_task.start = parent_task.finish
            dep_task.finish = dep_task.start + dep_task.duration
            chain.append(dep_task)
            self.tasks.remove(dep_task)

            # Check for resource conflicts and resolve them
            self.resolve_resource_conflicts(dep_task)

            # Continue building the chain
            self.build_chain_recursively(dep_task, chain)

    def resolve_resource_conflicts(self, task):
        """Check for and resolve resource conflicts"""
        all_scheduled_tasks = self.critical_chain + [
            t for chain in self.secondary_chains for t in chain
        ]

        for existing_task in all_scheduled_tasks:
            # Skip self comparison
            if existing_task.id == task.id:
                continue

            # Check if tasks overlap in time
            time_overlap = (
                task.start < existing_task.finish and task.finish > existing_task.start
            )

            # Check if tasks share resources
            resource_conflict = any(
                r in existing_task.resources for r in task.resources
            )

            if (
                time_overlap
                and resource_conflict
                and task.resources
                and existing_task.resources
            ):
                # Conflict detected - schedule task after the existing task
                delay = existing_task.finish - task.start
                task.start += delay
                task.finish += delay

                # Now check if this impacts other tasks and adjust them as needed
                self.adjust_dependent_tasks(task)

    def adjust_dependent_tasks(self, moved_task):
        """Adjust all tasks that depend on the moved task"""
        # Find all scheduled tasks
        all_scheduled_tasks = self.critical_chain + [
            t for chain in self.secondary_chains for t in chain
        ]

        # Find tasks that depend on the moved task
        dependent_tasks = [
            t for t in all_scheduled_tasks if str(moved_task.id) in t.predecessors
        ]

        for dep_task in dependent_tasks:
            # Only adjust if necessary
            if dep_task.start < moved_task.finish:
                delay = moved_task.finish - dep_task.start
                dep_task.start += delay
                dep_task.finish += delay

                # Recursively adjust dependent tasks
                self.adjust_dependent_tasks(dep_task)

    def generate_buffers(self):
        """Generate project buffer and feeding buffers"""
        # Project buffer based on critical chain
        if not self.critical_chain:
            print("Error: No critical chain to buffer")
            return

        buffer_size = sum(
            (t.nominal_duration - t.duration) for t in self.critical_chain
        )

        project_buffer = Task(
            id=max([t.id for t in self.critical_chain]) + 1,
            name="Project Buffer",
            duration=buffer_size,
            nominal_duration=buffer_size,
            predecessors=str(self.critical_chain[-1].id),
            resources="",
        )
        project_buffer.type = 4
        project_buffer.start = self.critical_chain[-1].finish
        project_buffer.finish = project_buffer.start + project_buffer.duration
        self.critical_chain.append(project_buffer)

        # Feeding buffers for each secondary chain
        for i, chain in enumerate(self.secondary_chains):
            if not chain:
                continue

            buffer_size = sum((t.nominal_duration - t.duration) for t in chain)

            feeding_buffer = Task(
                id=max(
                    [t.id for chain in self.secondary_chains for t in chain]
                    + [t.id for t in self.critical_chain]
                )
                + i
                + 1,
                name=f"Feeding Buffer {i+1}",
                duration=buffer_size,
                nominal_duration=buffer_size,
                predecessors=str(chain[-1].id),
                resources="",
            )
            feeding_buffer.type = 4
            feeding_buffer.start = chain[-1].finish
            feeding_buffer.finish = feeding_buffer.start + feeding_buffer.duration

            # Find the task in the critical chain that this chain feeds into
            for task in chain:
                for pred_id in task.predecessors:
                    cc_task = next(
                        (t for t in self.critical_chain if str(t.id) == pred_id), None
                    )
                    if cc_task:
                        # This is where the chain connects to the critical chain
                        # Update the feeding buffer's start time if needed
                        if feeding_buffer.finish > cc_task.start:
                            # Need to move the feeding buffer earlier
                            move_amount = feeding_buffer.finish - cc_task.start
                            feeding_buffer.start -= move_amount
                            feeding_buffer.finish -= move_amount

                            # This might require moving the entire chain earlier
                            for chain_task in reversed(chain):
                                chain_task.start -= move_amount
                                chain_task.finish -= move_amount
                        break

            chain.append(feeding_buffer)

    def schedule_remaining_tasks(self):
        """Schedule any remaining tasks"""
        while self.tasks:
            # Choose the task with fewest predecessors first
            task = min(self.tasks, key=lambda t: len(t.predecessors))

            # Get all scheduled tasks
            all_scheduled_tasks = self.critical_chain + [
                t for chain in self.secondary_chains for t in chain
            ]

            # Find earliest start time based on predecessors
            earliest_start = 0
            for pred_id in task.predecessors:
                pred = next(
                    (t for t in all_scheduled_tasks if str(t.id) == pred_id), None
                )
                if pred:
                    earliest_start = max(earliest_start, pred.finish)

            # Schedule the task
            task.type = 3  # Free task
            task.start = earliest_start
            task.finish = task.start + task.duration

            # Check for resource conflicts
            self.resolve_resource_conflicts(task)

            # Create a new chain for this "free" task
            free_chain = [task]
            self.build_chain_recursively(task, free_chain)

            if free_chain:
                self.secondary_chains.append(free_chain)

            # Remove from unassigned tasks
            if task in self.tasks:
                self.tasks.remove(task)

    def schedule(self):
        """Run the complete scheduling process"""
        # Make a copy of the original task list
        original_tasks = self.tasks.copy()

        self.find_critical_chain()
        self.identify_secondary_chains()
        self.schedule_remaining_tasks()
        self.generate_buffers()

        # Update all_scheduled_tasks
        self.all_scheduled_tasks = self.critical_chain + [
            t for chain in self.secondary_chains for t in chain
        ]

        # Reset tasks to the original list for possible rescheduling
        self.tasks = original_tasks

        return self.all_scheduled_tasks

    def visualize(self, show_resources=True):
        """Create a Gantt chart visualization"""
        all_tasks = self.critical_chain + [
            t for chain in self.secondary_chains for t in chain
        ]

        # Sort by start time
        all_tasks.sort(key=lambda t: t.start)

        colors = {
            1: "red",  # Critical chain
            2: "green",  # Secondary chain
            3: "blue",  # Free task
            4: "gray",  # Buffer
        }

        fig, ax = plt.subplots(figsize=(15, 0.5 * len(all_tasks)))

        y_labels = []
        for i, task in enumerate(all_tasks):
            # Create task label
            label = f"{task.id}: {task.name}"
            if show_resources and task.resources:
                label += f" [{','.join(task.resources)}]"
            y_labels.append(label)

            # Draw bar for task
            ax.barh(
                i,
                task.finish - task.start,
                left=task.start,
                color=colors.get(task.type, "purple"),
                edgecolor="black",
            )

            # Add task ID to the bar
            ax.text(
                task.start + (task.finish - task.start) / 2,
                i,
                f"{task.id}",
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
            )

            # Draw progress if any
            if hasattr(task, "progress") and task.progress > 0:
                progress_width = (task.finish - task.start) * (task.progress / 100)
                ax.barh(i, progress_width, left=task.start, color="darkgray", alpha=0.5)

        # Add dependencies as arrows
        for task in all_tasks:
            for pred_id in task.predecessors:
                pred = next((t for t in all_tasks if str(t.id) == pred_id), None)
                if pred:
                    # Find positions
                    pred_idx = all_tasks.index(pred)
                    task_idx = all_tasks.index(task)

                    # Draw arrow from pred end to task start
                    ax.annotate(
                        "",
                        xy=(task.start, task_idx),
                        xytext=(pred.finish, pred_idx),
                        arrowprops=dict(arrowstyle="->", color="black"),
                    )

        ax.set_yticks(range(len(all_tasks)))
        ax.set_yticklabels(y_labels)
        ax.set_xlabel("Time (days)")
        ax.set_title("Critical Chain Project Schedule")

        # Add legend
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor="red", edgecolor="black", label="Critical Chain"),
            Patch(facecolor="green", edgecolor="black", label="Secondary Chain"),
            Patch(facecolor="blue", edgecolor="black", label="Free Task"),
            Patch(facecolor="gray", edgecolor="black", label="Buffer"),
        ]
        ax.legend(handles=legend_elements, loc="upper right")

        plt.tight_layout()
        plt.grid(axis="x", linestyle="--", alpha=0.7)
        plt.show()

    def visualize_resource(self):
        """
        Create a resource loading chart visualization.

        Time (Days) along the bottom axis.
        Resources on the Y axis.
        Chart displays a count of the load caused by each task for each day.
        Zero load is blank.
        """
        # Collect all tasks from critical and secondary chains
        all_tasks = self.critical_chain + [
            t for chain in self.secondary_chains for t in chain
        ]

        if not all_tasks:
            print("No tasks to visualize")
            return

        # Find project timeline (min start to max finish)
        min_start = min(task.start for task in all_tasks)
        max_finish = max(task.finish for task in all_tasks)
        project_duration = max_finish - min_start

        # Collect all resources used in the project
        all_resources = set()
        for task in all_tasks:
            if hasattr(task, 'resources') and task.resources:
                all_resources.update(task.resources)

        # Sort resources for consistent display
        all_resources = sorted(list(all_resources))

        if not all_resources:
            print("No resources to visualize")
            return

        # Create a matrix to store resource loading
        # [resource][day] = load
        resource_loading = {resource: [0] * (project_duration + 1) for resource in all_resources}

        # Calculate resource loading for each day
        for task in all_tasks:
            if not hasattr(task, 'resources') or not task.resources:
                continue

            # For each day the task is active
            for day in range(task.start, task.finish):
                # Adjust day to be relative to project start
                relative_day = day - min_start

                # For each resource the task uses
                for resource in task.resources:
                    # Get allocation amount (default to 1.0 if not specified)
                    allocation = 1.0
                    if hasattr(task, 'get_resource_allocation'):
                        allocation = task.get_resource_allocation(resource)
                    elif hasattr(task, 'resource_allocations') and resource in task.resource_allocations:
                        allocation = task.resource_allocations[resource]

                    # Add the allocation to the resource loading
                    resource_loading[resource][relative_day] += allocation

        # Create the visualization
        fig, ax = plt.subplots(figsize=(15, 0.5 * len(all_resources)))

        # For each resource
        for i, resource in enumerate(all_resources):
            # For each day
            for day in range(project_duration + 1):
                load = resource_loading[resource][day]
                if load > 0:  # Only show non-zero loads
                    # Draw a cell with the load value
                    rect = plt.Rectangle((day + min_start, i - 0.4), 1, 0.8, 
                                        facecolor='skyblue', alpha=0.8, edgecolor='black')
                    ax.add_patch(rect)

                    # Add the load value text
                    ax.text(day + min_start + 0.5, i, f"{load:.1f}", 
                           ha='center', va='center', fontweight='bold')

        # Set up the axes
        ax.set_yticks(range(len(all_resources)))
        ax.set_yticklabels(all_resources)
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("Resources")
        ax.set_title("Resource Loading Chart")

        # Set x-axis limits
        ax.set_xlim(min_start, max_finish)

        # Set y-axis limits to add half a row of space at the bottom and top
        ax.set_ylim(-0.5, len(all_resources) - 0.5)

        # Add grid
        plt.grid(axis="x", linestyle="--", alpha=0.7)

        plt.tight_layout()
        plt.show()

    def update_progress(self, task_id, progress_percentage):
        """Update a task's progress and calculate buffer consumption"""
        # Find the task
        task = next((t for t in self.all_scheduled_tasks if t.id == task_id), None)

        if not task:
            print(f"Task {task_id} not found")
            return

        # Update progress
        task.progress = progress_percentage

        # Assume current date is based on planned progress
        current_day = int(
            task.start + (task.finish - task.start) * (progress_percentage / 100)
        )

        # Calculate theoretical vs actual progress
        if current_day > task.start:
            theoretical_progress = (
                (current_day - task.start) / (task.finish - task.start) * 100
            )
            difference = theoretical_progress - progress_percentage

            # Positive difference means behind schedule
            if difference > 0:
                # Calculate buffer consumption in days
                buffer_days = difference * (task.finish - task.start) / 100

                # Find which chain this task belongs to
                in_critical_chain = any(t.id == task.id for t in self.critical_chain)

                if in_critical_chain:
                    # Consume project buffer
                    buffer = self.critical_chain[-1]  # Last task is the project buffer
                else:
                    # Find which secondary chain
                    for chain in self.secondary_chains:
                        if any(t.id == task.id for t in chain):
                            buffer = chain[-1]  # Last task is the feeding buffer
                            break
                    else:
                        print(f"Could not find chain for task {task.id}")
                        return

                # Update buffer consumption
                if not hasattr(buffer, "consumed_days"):
                    buffer.consumed_days = 0
                buffer.consumed_days += buffer_days
                buffer.progress = min(
                    100, (buffer.consumed_days / buffer.duration) * 100
                )

                print(
                    f"Task {task.id} is behind schedule. Buffer consumption: {buffer_days:.1f} days"
                )
            else:
                print(f"Task {task.id} is ahead of schedule.")

    def generate_fever_chart(self):
        """Generate fever charts for project and feeding buffers"""
        all_buffers = []

        # Project buffer
        if self.critical_chain and self.critical_chain[-1].type == 4:
            all_buffers.append(
                (self.critical_chain[-1], self.critical_chain[:-1], "Project")
            )

        # Feeding buffers
        for i, chain in enumerate(self.secondary_chains):
            if chain and chain[-1].type == 4:
                all_buffers.append((chain[-1], chain[:-1], f"Feeding {i+1}"))

        if not all_buffers:
            print("No buffers to display")
            return

        fig, axs = plt.subplots(len(all_buffers), 1, figsize=(10, 5 * len(all_buffers)))
        if len(all_buffers) == 1:
            axs = [axs]

        for i, (buffer, chain, buffer_type) in enumerate(all_buffers):
            # Calculate percent complete for the chain
            completed_work = sum(
                t.duration * (getattr(t, "progress", 0) / 100) for t in chain
            )
            total_work = sum(t.duration for t in chain)

            if total_work == 0:
                percent_complete = 0
            else:
                percent_complete = (completed_work / total_work) * 100

            # Calculate buffer consumption percentage
            buffer_consumption_pct = getattr(buffer, "progress", 0)

            # Create fever chart with zones
            # Green zone (0-33%)
            axs[i].fill_between([0, 33], [0, 33], color="green", alpha=0.3)
            axs[i].fill_between([33, 100], [0, 33], color="green", alpha=0.3)

            # Yellow zone (33-67%)
            axs[i].fill_between([0, 67], [33, 67], color="yellow", alpha=0.3)
            axs[i].fill_between([67, 100], [33, 67], color="yellow", alpha=0.3)

            # Red zone (67-100%)
            axs[i].fill_between([0, 100], [67, 100], color="red", alpha=0.3)

            # Plot consumption point
            axs[i].plot(
                [percent_complete], [buffer_consumption_pct], "ko", markersize=10
            )

            axs[i].set_xlim(0, 100)
            axs[i].set_ylim(0, 100)
            axs[i].set_xlabel("Chain Completion %")
            axs[i].set_ylabel("Buffer Consumption %")
            axs[i].set_title(f"{buffer_type} Buffer Fever Chart")

            # Add grid
            axs[i].grid(True, linestyle="--", alpha=0.7)

            # Mark current point with coordinates
            axs[i].annotate(
                f"({percent_complete:.1f}%, {buffer_consumption_pct:.1f}%)",
                (percent_complete, buffer_consumption_pct),
                xytext=(5, 5),
                textcoords="offset points",
            )

        plt.tight_layout()
        plt.show()


# ==================== Test Cases ====================


def test_simple_sequential():
    """Test a simple sequential project (A -> B -> C)"""
    print("\n=== Test Case: Simple Sequential Project ===")

    scheduler = CriticalChainScheduler()

    # Add tasks
    task_a = Task(1, "Task A", 5)
    task_b = Task(2, "Task B", 3, predecessors="1")
    task_c = Task(3, "Task C", 4, predecessors="2")

    scheduler.add_task(task_a)
    scheduler.add_task(task_b)
    scheduler.add_task(task_c)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nCritical Chain:")
    for task in scheduler.critical_chain:
        print(
            f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Type: {task.type}"
        )

    # Visualize
    scheduler.visualize()

    return scheduler


def test_parallel_paths():
    """Test a project with parallel paths"""
    print("\n=== Test Case: Project with Parallel Paths ===")

    scheduler = CriticalChainScheduler()

    # Add tasks
    task_a = Task(1, "Start", 2)

    # Path 1
    task_b1 = Task(2, "Path1-Task1", 4, predecessors="1")
    task_b2 = Task(3, "Path1-Task2", 3, predecessors="2")

    # Path 2 (longer duration)
    task_c1 = Task(4, "Path2-Task1", 3, predecessors="1")
    task_c2 = Task(5, "Path2-Task2", 5, predecessors="4")

    # Final task
    task_d = Task(6, "Finish", 2, predecessors="3,5")

    scheduler.add_task(task_a)
    scheduler.add_task(task_b1)
    scheduler.add_task(task_b2)
    scheduler.add_task(task_c1)
    scheduler.add_task(task_c2)
    scheduler.add_task(task_d)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nCritical Chain:")
    for task in scheduler.critical_chain:
        print(
            f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Type: {task.type}"
        )

    print("\nSecondary Chains:")
    for i, chain in enumerate(scheduler.secondary_chains):
        print(f"Chain {i+1}:")
        for task in chain:
            print(
                f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Type: {task.type}"
            )

    # Visualize
    scheduler.visualize()

    return scheduler


def test_resource_conflicts():
    """Test a project with resource conflicts"""
    print("\n=== Test Case: Project with Resource Conflicts ===")

    scheduler = CriticalChainScheduler()

    # Add resources
    resource_a = Resource("A", "Resource A")
    resource_b = Resource("B", "Resource B")

    scheduler.add_resource(resource_a)
    scheduler.add_resource(resource_b)

    # Add tasks
    task_1 = Task(1, "Start", 2, resources="A")

    # These tasks both need resource A but can't be done in parallel
    task_2 = Task(2, "Task 2", 4, predecessors="1", resources="A")
    task_3 = Task(3, "Task 3", 3, predecessors="1", resources="A")

    # These tasks need resource B
    task_4 = Task(4, "Task 4", 5, predecessors="2", resources="B")
    task_5 = Task(5, "Task 5", 4, predecessors="3", resources="B")

    # Final task
    task_6 = Task(6, "Finish", 2, predecessors="4,5", resources="A,B")

    scheduler.add_task(task_1)
    scheduler.add_task(task_2)
    scheduler.add_task(task_3)
    scheduler.add_task(task_4)
    scheduler.add_task(task_5)
    scheduler.add_task(task_6)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nCritical Chain:")
    for task in scheduler.critical_chain:
        print(
            f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Resources: {task.resources}"
        )

    print("\nSecondary Chains:")
    for i, chain in enumerate(scheduler.secondary_chains):
        print(f"Chain {i+1}:")
        for task in chain:
            print(
                f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Resources: {task.resources}"
            )

    # Visualize
    scheduler.visualize()

    return scheduler


def test_larry_simple():
    """Test a project with resource conflicts"""
    print("\n=== Test Case: Project simple example from Larry's book  ===")

    scheduler = CriticalChainScheduler()

    #resources = ["Red", "Green", "Magenta", "Blue"]
    # Define tasks - ID: Task(ID, Name, Duration, Dependencies, Resources)
    # tasks = {
    #     1: Task(1, "T1.1", 30, [], ["Red"]),
    #     2: Task(2, "T1.2", 20, [1], ["Green"]),
    #     3: Task(3, "T3", 30, [5, 2], ["Magenta"]),
    #     4: Task(4, "T2.1", 20, [], ["Blue"]),
    #     5: Task(5, "T2.2", 10, [4], ["Green"]),
    # }

    # Add resources
    resource_r = Resource("R", "Red")
    resource_g = Resource("G", "Green")
    resource_m = Resource("M", "Magenta")
    resource_b = Resource("B", "Blue")

    scheduler.add_resource(resource_r)
    scheduler.add_resource(resource_g)
    scheduler.add_resource(resource_m)
    scheduler.add_resource(resource_b)

    # Add tasks with aggresive optimistic durations
    task_1 = Task(1, "T1.1", 30, resources="R")
    task_2 = Task(2, "T1.2", 20, predecessors="1", resources="G")

    task_3 = Task(3, "T3", 30, predecessors="2,5", resources="M")

    task_4 = Task(4, "T2.1", 20, resources="B")
    task_5 = Task(5, "T2.2", 10, predecessors="4", resources="G")


    scheduler.add_task(task_1)
    scheduler.add_task(task_2)
    scheduler.add_task(task_3)
    scheduler.add_task(task_4)
    scheduler.add_task(task_5)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nCritical Chain:")
    for task in scheduler.critical_chain:
        print(
            f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Resources: {task.resources}"
        )

    print("\nSecondary Chains:")
    for i, chain in enumerate(scheduler.secondary_chains):
        print(f"Chain {i+1}:")
        for task in chain:
            print(
                f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Resources: {task.resources}"
            )

    # Visualize
    scheduler.visualize()

    return scheduler

def test_larry_complex():
    """Test a project with resource conflicts"""
    print("\n=== Test Case: Project with Resource Conflicts ===")

    scheduler = CriticalChainScheduler()

    # Add resources
    resource_r = Resource("R", "Red")
    resource_g = Resource("G", "Green")
    resource_m = Resource("M", "Magenta")
    resource_b = Resource("B", "Blue")
    resource_k = Resource("K", "Black")

    scheduler.add_resource(resource_r)
    scheduler.add_resource(resource_g)
    scheduler.add_resource(resource_m)
    scheduler.add_resource(resource_b)
    scheduler.add_resource(resource_k)

    # Add A tasks with aggressive, optimistic durations
    task_1 = Task(1, "A-1", 5, resources="M")
    task_2 = Task(2, "A-2", 10, predecessors="1", resources="K")
    task_3 = Task(3, "A-3", 15, predecessors="2", resources="G")
    task_4 = Task(4, "A-4", 10, predecessors="3", resources="R")
    task_5 = Task(5, "A-5", 20, predecessors="4,9", resources="M")
    task_6 = Task(6, "A-6", 15, predecessors="5", resources="R")

    # Add B tasks
    task_7 = Task(7, "B-2", 10, resources="M")
    task_8 = Task(8, "B-3", 10, predecessors="7",resources="B")
    task_9 = Task(9, "B-4", 5, predecessors="8", resources="R")

    # Add C tasks
    task_10 = Task(10, "C-3", 15, resources="M")
    task_11 = Task(11, "C-4", 10, predecessors="10",resources="B")
    task_12 = Task(12, "C-5", 15, predecessors="11,15", resources="R")
    task_13 = Task(13, "C-6", 5, predecessors="12", resources="R")

    # Add D tasks
    task_14 = Task(14, "D-3", 20, resources="B")
    task_15 = Task(15, "D-4", 5, predecessors="10",resources="G")

    # End Task
    task_16 = Task(16, "End", 0, predecessors="13,6")


    scheduler.add_task(task_1)
    scheduler.add_task(task_2)
    scheduler.add_task(task_3)
    scheduler.add_task(task_4)
    scheduler.add_task(task_5)
    scheduler.add_task(task_6)
    scheduler.add_task(task_7)
    scheduler.add_task(task_8)
    scheduler.add_task(task_9)
    scheduler.add_task(task_10)
    scheduler.add_task(task_11)
    scheduler.add_task(task_12)
    scheduler.add_task(task_13)
    scheduler.add_task(task_14)
    scheduler.add_task(task_15)
    scheduler.add_task(task_16)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nCritical Chain:")
    for task in scheduler.critical_chain:
        print(
            f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Resources: {task.resources}"
        )

    print("\nSecondary Chains:")
    for i, chain in enumerate(scheduler.secondary_chains):
        print(f"Chain {i+1}:")
        for task in chain:
            print(
                f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Resources: {task.resources}"
            )

    # Visualize
    scheduler.visualize()

    return scheduler


def test_progress_tracking():
    """Test progress tracking and buffer consumption"""
    print("\n=== Test Case: Progress Tracking and Buffer Consumption ===")

    # Use the parallel paths project
    scheduler = test_parallel_paths()

    # Update progress for some tasks
    print("\nUpdating task progress:")

    # Update a critical chain task to be behind schedule
    critical_task = scheduler.critical_chain[1]  # Second task in critical chain
    print(
        f"Setting task {critical_task.id} ({critical_task.name}) to 30% complete (should be 50%)"
    )
    scheduler.update_progress(critical_task.id, 30)

    # Update a secondary chain task to be ahead of schedule
    if scheduler.secondary_chains:
        secondary_task = scheduler.secondary_chains[0][
            0
        ]  # First task in first secondary chain
        print(
            f"Setting task {secondary_task.id} ({secondary_task.name}) to 70% complete (should be 50%)"
        )
        scheduler.update_progress(secondary_task.id, 70)

    # Update a critical chain task to be on schedule
    if len(scheduler.critical_chain) > 2:
        another_critical_task = scheduler.critical_chain[
            0
        ]  # First task in critical chain
        print(
            f"Setting task {another_critical_task.id} ({another_critical_task.name}) to 100% complete (as expected)"
        )
        scheduler.update_progress(another_critical_task.id, 100)

    # Generate fever chart
    scheduler.generate_fever_chart()

    # Visualize with progress
    scheduler.visualize()

    return scheduler


def test_complex_network():
    """Test a more complex project network"""
    print("\n=== Test Case: Complex Project Network ===")

    scheduler = CriticalChainScheduler()

    # Add resources
    resource_a = Resource("A", "Engineer")
    resource_b = Resource("B", "Designer")
    resource_c = Resource("C", "Tester")

    scheduler.add_resource(resource_a)
    scheduler.add_resource(resource_b)
    scheduler.add_resource(resource_c)

    # Create tasks
    tasks = [
        Task(1, "Project Start", 0),
        Task(2, "Requirements", 5, resources="A"),
        Task(3, "Design", 7, predecessors="2", resources="B"),
        Task(4, "Prototype A", 4, predecessors="3", resources="A"),
        Task(5, "Prototype B", 6, predecessors="3", resources="B"),
        Task(6, "Develop Core", 10, predecessors="4", resources="A"),
        Task(7, "Develop UI", 8, predecessors="5", resources="B"),
        Task(8, "Quality Assurance", 6, predecessors="6,7", resources="C"),
        Task(9, "User Testing", 5, predecessors="8", resources="B,C"),
        Task(10, "Documentation", 4, predecessors="8", resources="A"),
        Task(11, "Deployment", 3, predecessors="9,10", resources="A,B"),
        Task(12, "Project End", 0, predecessors="11"),
    ]

    for task in tasks:
        scheduler.add_task(task)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nCritical Chain:")
    for task in scheduler.critical_chain:
        print(
            f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Type: {task.type}"
        )

    print("\nSecondary Chains:")
    for i, chain in enumerate(scheduler.secondary_chains):
        print(f"Chain {i+1}:")
        for task in chain:
            print(
                f"  {task.id}: {task.name} - Start: {task.start}, Finish: {task.finish}, Type: {task.type}"
            )

    # Visualize
    scheduler.visualize()

    # Update some progress
    print("\nUpdating task progress:")
    scheduler.update_progress(2, 100)  # Requirements complete
    scheduler.update_progress(3, 80)  # Design 80% complete (behind schedule)
    scheduler.update_progress(4, 20)  # Prototype A just started

    # Generate fever chart
    scheduler.generate_fever_chart()

    return scheduler


def test_manufacturing_project():
    """Test a manufacturing project with multiple resource constraints"""
    print("\n=== Test Case: Manufacturing Project ===")

    scheduler = CriticalChainScheduler()

    # Add resources
    resources = [
        Resource("D", "Designer"),
        Resource("E", "Engineer"),
        Resource("M", "Machinist"),
        Resource("A", "Assembler"),
        Resource("Q", "Quality Control"),
    ]

    for resource in resources:
        scheduler.add_resource(resource)

    # Create tasks with nominal durations (pessimistic) and optimistic durations
    tasks = [
        Task(1, "Design Product", 7, nominal_duration=10, resources="D"),
        Task(
            2,
            "Create Specifications",
            3,
            nominal_duration=5,
            predecessors="1",
            resources="E",
        ),
        Task(
            3, "Order Materials", 5, nominal_duration=8, predecessors="2", resources="E"
        ),
        Task(
            4,
            "Design Manufacturing Process",
            4,
            nominal_duration=6,
            predecessors="2",
            resources="D,E",
        ),
        Task(
            5,
            "Receive Materials",
            2,
            nominal_duration=3,
            predecessors="3",
            resources="A",
        ),
        Task(
            6,
            "Setup Production Line",
            6,
            nominal_duration=9,
            predecessors="4",
            resources="M",
        ),
        Task(
            7,
            "Create Prototype",
            4,
            nominal_duration=6,
            predecessors="5,6",
            resources="M,A",
        ),
        Task(
            8,
            "Test Prototype",
            3,
            nominal_duration=5,
            predecessors="7",
            resources="E,Q",
        ),
        Task(
            9, "Revise Design", 4, nominal_duration=6, predecessors="8", resources="D"
        ),
        Task(
            10,
            "Produce Batch",
            8,
            nominal_duration=12,
            predecessors="9",
            resources="M,A",
        ),
        Task(
            11,
            "Quality Inspection",
            3,
            nominal_duration=5,
            predecessors="10",
            resources="Q",
        ),
        Task(
            12,
            "Package Products",
            2,
            nominal_duration=3,
            predecessors="11",
            resources="A",
        ),
        Task(
            13,
            "Ship to Customer",
            1,
            nominal_duration=2,
            predecessors="12",
            resources="A",
        ),
    ]

    for task in tasks:
        scheduler.add_task(task)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nProject Duration:")
    project_duration = scheduler.critical_chain[-2].finish  # Excluding project buffer
    project_buffer = scheduler.critical_chain[-1].duration
    print(f"  Critical Chain: {project_duration} days")
    print(f"  Project Buffer: {project_buffer} days")
    print(f"  Total Duration with Buffer: {project_duration + project_buffer} days")

    # Visualize
    scheduler.visualize()

    return scheduler


def test_software_development():
    """Test a software development project with sprint structure"""
    print("\n=== Test Case: Software Development Project ===")

    scheduler = CriticalChainScheduler()

    # Add resources
    resources = [
        Resource("PM", "Project Manager"),
        Resource("BA", "Business Analyst"),
        Resource("FE", "Frontend Developer"),
        Resource("BE", "Backend Developer"),
        Resource("QA", "QA Engineer"),
        Resource("UX", "UX Designer"),
    ]

    for resource in resources:
        scheduler.add_resource(resource)

    # Create tasks for sprint-based development
    sprint_tasks = []

    # Initial planning phase
    sprint_tasks.extend(
        [
            Task(1, "Project Kickoff", 1, nominal_duration=1, resources="PM"),
            Task(
                2,
                "Requirements Gathering",
                5,
                nominal_duration=7,
                predecessors="1",
                resources="BA,PM",
            ),
            Task(
                3,
                "System Architecture",
                4,
                nominal_duration=6,
                predecessors="2",
                resources="BE",
            ),
            Task(
                4, "UX Design", 6, nominal_duration=8, predecessors="2", resources="UX"
            ),
        ]
    )

    # Sprint 1
    sprint_tasks.extend(
        [
            Task(
                5,
                "Sprint 1 Planning",
                1,
                nominal_duration=1,
                predecessors="3,4",
                resources="PM,BA,FE,BE,QA",
            ),
            Task(
                6,
                "Backend API Layer",
                8,
                nominal_duration=10,
                predecessors="5",
                resources="BE",
            ),
            Task(
                7,
                "Frontend Framework Setup",
                5,
                nominal_duration=7,
                predecessors="5",
                resources="FE",
            ),
            Task(
                8,
                "Core UI Components",
                7,
                nominal_duration=9,
                predecessors="7",
                resources="FE,UX",
            ),
            Task(
                9,
                "Sprint 1 Testing",
                3,
                nominal_duration=5,
                predecessors="6,8",
                resources="QA",
            ),
            Task(
                10,
                "Sprint 1 Review",
                1,
                nominal_duration=1,
                predecessors="9",
                resources="PM,BA,FE,BE,QA",
            ),
        ]
    )

    # Sprint 2
    sprint_tasks.extend(
        [
            Task(
                11,
                "Sprint 2 Planning",
                1,
                nominal_duration=1,
                predecessors="10",
                resources="PM,BA,FE,BE,QA",
            ),
            Task(
                12,
                "Database Optimization",
                4,
                nominal_duration=6,
                predecessors="11",
                resources="BE",
            ),
            Task(
                13,
                "Feature Development 1",
                6,
                nominal_duration=8,
                predecessors="11",
                resources="BE",
            ),
            Task(
                14,
                "User Authentication UI",
                4,
                nominal_duration=6,
                predecessors="11",
                resources="FE",
            ),
            Task(
                15,
                "Advanced Components",
                5,
                nominal_duration=7,
                predecessors="14",
                resources="FE",
            ),
            Task(
                16,
                "Sprint 2 Testing",
                4,
                nominal_duration=6,
                predecessors="12,13,15",
                resources="QA",
            ),
            Task(
                17,
                "Sprint 2 Review",
                1,
                nominal_duration=1,
                predecessors="16",
                resources="PM,BA,FE,BE,QA",
            ),
        ]
    )

    # Sprint 3
    sprint_tasks.extend(
        [
            Task(
                18,
                "Sprint 3 Planning",
                1,
                nominal_duration=1,
                predecessors="17",
                resources="PM,BA,FE,BE,QA",
            ),
            Task(
                19,
                "Backend Integration",
                7,
                nominal_duration=9,
                predecessors="18",
                resources="BE",
            ),
            Task(
                20,
                "Frontend Integration",
                6,
                nominal_duration=8,
                predecessors="18",
                resources="FE",
            ),
            Task(
                21,
                "Performance Optimization",
                5,
                nominal_duration=7,
                predecessors="19,20",
                resources="BE,FE",
            ),
            Task(
                22,
                "Sprint 3 Testing",
                4,
                nominal_duration=6,
                predecessors="21",
                resources="QA",
            ),
            Task(
                23,
                "Sprint 3 Review",
                1,
                nominal_duration=1,
                predecessors="22",
                resources="PM,BA,FE,BE,QA",
            ),
        ]
    )

    # Final Phase
    sprint_tasks.extend(
        [
            Task(
                24,
                "System Testing",
                5,
                nominal_duration=7,
                predecessors="23",
                resources="QA",
            ),
            Task(
                25,
                "User Acceptance Testing",
                5,
                nominal_duration=7,
                predecessors="24",
                resources="BA,QA",
            ),
            Task(
                26,
                "Documentation",
                4,
                nominal_duration=6,
                predecessors="23",
                resources="BA",
            ),
            Task(
                27,
                "Deployment Preparation",
                3,
                nominal_duration=5,
                predecessors="25,26",
                resources="BE",
            ),
            Task(
                28,
                "Go Live",
                2,
                nominal_duration=3,
                predecessors="27",
                resources="PM,BE",
            ),
        ]
    )

    for task in sprint_tasks:
        scheduler.add_task(task)

    # Schedule
    scheduler.schedule()

    # Print results
    print("\nProject Timeline:")
    project_duration = scheduler.critical_chain[-2].finish  # Excluding project buffer
    project_buffer = scheduler.critical_chain[-1].duration
    print(f"  Critical Chain: {project_duration} days")
    print(f"  Project Buffer: {project_buffer} days")
    print(f"  Total Duration with Buffer: {project_duration + project_buffer} days")

    # Sprint durations
    print("\nSprint Durations:")
    sprint1_start = next(t.start for t in scheduler.all_scheduled_tasks if t.id == 5)
    sprint1_end = next(t.finish for t in scheduler.all_scheduled_tasks if t.id == 10)
    print(f"  Sprint 1: {sprint1_end - sprint1_start} days")

    sprint2_start = next(t.start for t in scheduler.all_scheduled_tasks if t.id == 11)
    sprint2_end = next(t.finish for t in scheduler.all_scheduled_tasks if t.id == 17)
    print(f"  Sprint 2: {sprint2_end - sprint2_start} days")

    sprint3_start = next(t.start for t in scheduler.all_scheduled_tasks if t.id == 18)
    sprint3_end = next(t.finish for t in scheduler.all_scheduled_tasks if t.id == 23)
    print(f"  Sprint 3: {sprint3_end - sprint3_start} days")

    # Visualize
    scheduler.visualize()

    return scheduler


def test_buffer_sizing_strategies():
    """Test different buffer sizing strategies"""
    print("\n=== Test Case: Buffer Sizing Strategies ===")

    # Create a simple project
    tasks = [
        Task(1, "Task A", 10, nominal_duration=15),
        Task(2, "Task B", 8, nominal_duration=12, predecessors="1"),
        Task(3, "Task C", 6, nominal_duration=9, predecessors="2"),
        Task(4, "Task D", 5, nominal_duration=8, predecessors="3"),
    ]

    # Strategy 1: Default (50% of safety removed)
    print("\nBuffer Strategy 1: Default (50% of safety removed)")
    scheduler1 = CriticalChainScheduler()
    for task in tasks:
        # Create a copy of the task
        task_copy = Task(
            task.id,
            task.name,
            task.duration,
            nominal_duration=task.nominal_duration,
            predecessors=",".join(task.predecessors),
            resources=",".join(task.resources),
        )
        scheduler1.add_task(task_copy)

    scheduler1.schedule()
    project_duration1 = scheduler1.critical_chain[-2].finish
    buffer_size1 = scheduler1.critical_chain[-1].duration
    print(f"  Critical Chain: {project_duration1} days")
    print(f"  Project Buffer: {buffer_size1} days")
    print(f"  Total Duration: {project_duration1 + buffer_size1} days")
    print(f"  Buffer Percentage: {(buffer_size1 / project_duration1) * 100:.1f}%")

    # Strategy 2: Square Root of Sum of Squares (Root Sum Square method)
    print("\nBuffer Strategy 2: Root Sum Square Method")

    class RSSCriticalChainScheduler(CriticalChainScheduler):
        def generate_buffers(self):
            """Generate project buffer and feeding buffers using Root Sum Square method"""
            # Project buffer based on critical chain
            if not self.critical_chain:
                print("Error: No critical chain to buffer")
                return

            # Calculate buffer using Root Sum Square method
            safety_margins = [
                (t.nominal_duration - t.duration) for t in self.critical_chain
            ]
            buffer_size = round(sum(margin**2 for margin in safety_margins) ** 0.5)

            project_buffer = Task(
                id=max([t.id for t in self.critical_chain]) + 1,
                name="Project Buffer (RSS)",
                duration=buffer_size,
                nominal_duration=buffer_size,
                predecessors=str(self.critical_chain[-1].id),
                resources="",
            )
            project_buffer.type = 4
            project_buffer.start = self.critical_chain[-1].finish
            project_buffer.finish = project_buffer.start + project_buffer.duration
            self.critical_chain.append(project_buffer)

            # Feeding buffers for each secondary chain
            for i, chain in enumerate(self.secondary_chains):
                if not chain:
                    continue

                # Calculate buffer using Root Sum Square method
                safety_margins = [(t.nominal_duration - t.duration) for t in chain]
                buffer_size = round(sum(margin**2 for margin in safety_margins) ** 0.5)

                feeding_buffer = Task(
                    id=max(
                        [t.id for chain in self.secondary_chains for t in chain]
                        + [t.id for t in self.critical_chain]
                    )
                    + i
                    + 1,
                    name=f"Feeding Buffer {i+1} (RSS)",
                    duration=buffer_size,
                    nominal_duration=buffer_size,
                    predecessors=str(chain[-1].id),
                    resources="",
                )
                feeding_buffer.type = 4
                feeding_buffer.start = chain[-1].finish
                feeding_buffer.finish = feeding_buffer.start + feeding_buffer.duration

                # Find the task in the critical chain that this chain feeds into
                for task in chain:
                    for pred_id in task.predecessors:
                        cc_task = next(
                            (t for t in self.critical_chain if str(t.id) == pred_id),
                            None,
                        )
                        if cc_task:
                            # This is where the chain connects to the critical chain
                            # Update the feeding buffer's start time if needed
                            if feeding_buffer.finish > cc_task.start:
                                # Need to move the feeding buffer earlier
                                move_amount = feeding_buffer.finish - cc_task.start
                                feeding_buffer.start -= move_amount
                                feeding_buffer.finish -= move_amount

                                # This might require moving the entire chain earlier
                                for chain_task in reversed(chain):
                                    chain_task.start -= move_amount
                                    chain_task.finish -= move_amount
                            break

                chain.append(feeding_buffer)

    scheduler2 = RSSCriticalChainScheduler()
    for task in tasks:
        # Create a copy of the task
        task_copy = Task(
            task.id,
            task.name,
            task.duration,
            nominal_duration=task.nominal_duration,
            predecessors=",".join(task.predecessors),
            resources=",".join(task.resources),
        )
        scheduler2.add_task(task_copy)

    scheduler2.schedule()
    project_duration2 = scheduler2.critical_chain[-2].finish
    buffer_size2 = scheduler2.critical_chain[-1].duration
    print(f"  Critical Chain: {project_duration2} days")
    print(f"  Project Buffer: {buffer_size2} days")
    print(f"  Total Duration: {project_duration2 + buffer_size2} days")
    print(f"  Buffer Percentage: {(buffer_size2 / project_duration2) * 100:.1f}%")

    # Compare the strategies
    print("\nComparison of Buffer Strategies:")
    print(
        f"  Strategy 1 (Default): Buffer = {buffer_size1} days ({(buffer_size1 / project_duration1) * 100:.1f}% of critical chain)"
    )
    print(
        f"  Strategy 2 (RSS): Buffer = {buffer_size2} days ({(buffer_size2 / project_duration2) * 100:.1f}% of critical chain)"
    )

    # Create a comparison chart
    fig, ax = plt.subplots(figsize=(10, 6))

    strategies = ["Default (50% of Safety)", "Root Sum Square"]
    durations = [project_duration1, project_duration2]
    buffers = [buffer_size1, buffer_size2]

    x = range(len(strategies))
    width = 0.35

    ax.bar(x, durations, width, label="Critical Chain")
    ax.bar(x, buffers, width, bottom=durations, label="Project Buffer")

    ax.set_ylabel("Duration (days)")
    ax.set_title("Comparison of Buffer Sizing Strategies")
    ax.set_xticks(x)
    ax.set_xticklabels(strategies)
    ax.legend()

    # Add total duration labels
    for i, total in enumerate(
        [project_duration1 + buffer_size1, project_duration2 + buffer_size2]
    ):
        ax.text(i, total + 0.5, f"Total: {total}", ha="center", va="bottom")

    # Add buffer percentage labels
    for i, (duration, buffer) in enumerate(zip(durations, buffers)):
        percentage = (buffer / duration) * 100
        ax.text(
            i, duration + buffer / 2, f"{percentage:.1f}%", ha="center", va="center"
        )

    plt.tight_layout()
    plt.show()

    return scheduler1, scheduler2


# Additional utility functions
def extract_critical_chain_path(scheduler):
    """Extract the critical chain path as a list of task IDs"""
    return [
        task.id for task in scheduler.critical_chain if task.type != 4
    ]  # Exclude buffers


def visualize_network(scheduler):
    """Visualize the project as a network diagram"""
    import networkx as nx

    # Create directed graph
    G = nx.DiGraph()

    # Add all tasks as nodes
    all_tasks = scheduler.critical_chain + [
        t for chain in scheduler.secondary_chains for t in chain
    ]

    # Create a mapping of task ID to task object
    task_map = {str(t.id): t for t in all_tasks}

    # Add nodes with attributes
    for task in all_tasks:
        if task.type == 4:  # Buffer
            node_color = "lightgray"
        elif task.type == 1:  # Critical chain
            node_color = "lightcoral"
        elif task.type == 2:  # Secondary chain
            node_color = "lightgreen"
        else:  # Other
            node_color = "lightblue"

        G.add_node(
            str(task.id),
            label=f"{task.id}: {task.name}",
            duration=task.duration,
            start=task.start,
            finish=task.finish,
            color=node_color,
        )

    # Add edges based on predecessors
    for task in all_tasks:
        for pred_id in task.predecessors:
            if pred_id in task_map:
                G.add_edge(pred_id, str(task.id))

    # Create positions for nodes - use hierarchical layout
    pos = nx.nx_agraph.graphviz_layout(G, prog="dot", args="-Grankdir=LR")

    # Draw the graph
    plt.figure(figsize=(14, 10))

    # Draw nodes
    node_colors = [G.nodes[n]["color"] for n in G.nodes()]

    # Draw edges
    nx.draw_networkx_edges(G, pos, arrowsize=15, width=1.5, edge_color="gray")

    # Get critical chain nodes
    critical_chain_nodes = [
        str(task_id) for task_id in extract_critical_chain_path(scheduler)
    ]

    # Draw critical chain edges with special formatting
    critical_edges = [
        (u, v)
        for u, v in G.edges()
        if u in critical_chain_nodes and v in critical_chain_nodes
    ]
    nx.draw_networkx_edges(
        G, pos, edgelist=critical_edges, width=3, edge_color="red", arrowsize=20
    )

    # Draw nodes on top of edges
    nx.draw_networkx_nodes(
        G, pos, node_size=2000, node_color=node_colors, edgecolors="black"
    )

    # Draw labels with task information
    labels = {}
    for node in G.nodes():
        task = task_map.get(node)
        if task:
            if task.type == 4:  # Buffer
                labels[node] = f"{task.id}: {task.name}\n({task.duration}d)"
            else:
                labels[node] = f"{task.id}: {task.name}\n({task.duration}d)"

    nx.draw_networkx_labels(G, pos, labels=labels, font_size=9)

    plt.title("Project Network Diagram (Critical Chain in Red)")
    plt.axis("off")
    plt.tight_layout()
    plt.show()

    return G


def export_to_csv(scheduler, filename="ccpm_schedule.csv", start_date=None):
    """Export the schedule to a CSV file with calendar dates"""
    import pandas as pd
    from datetime import datetime, timedelta

    # Set default start date if not provided
    if start_date is None:
        start_date = datetime.now()

    # Create a list of all scheduled tasks
    all_tasks = scheduler.critical_chain + [
        t for chain in scheduler.secondary_chains for t in chain
    ]

    # Prepare data for DataFrame
    data = []

    for task in all_tasks:
        # Skip task id 0 (usually a dummy start node)
        if task.id == 0:
            continue

        # Calculate calendar dates based on working days
        if scheduler.project_data.get("calendar") == "continuous":
            # 7 days a week
            start_date_cal = start_date + timedelta(days=task.start)
            finish_date_cal = start_date + timedelta(days=task.finish)
        else:
            # 5 days a week (skip weekends)
            start_date_cal = start_date + timedelta(
                days=task.start + (task.start // 5) * 2
            )
            finish_date_cal = start_date + timedelta(
                days=task.finish + (task.finish // 5) * 2
            )

            # Adjust if landing on weekend
            while start_date_cal.weekday() >= 5:  # 5=Saturday, 6=Sunday
                start_date_cal += timedelta(days=1)
            while finish_date_cal.weekday() >= 5:
                finish_date_cal += timedelta(days=1)

        # Determine chain type
        if task.type == 1:
            chain_type = "Critical Chain"
        elif task.type == 2:
            chain_type = "Secondary Chain"
        elif task.type == 4:
            chain_type = "Buffer"
        else:
            chain_type = "Other"

        # Create row data
        row = {
            "ID": task.id,
            "Name": task.name,
            "Duration": task.duration,
            "Start (Days)": task.start,
            "Finish (Days)": task.finish,
            "Start Date": start_date_cal.strftime("%Y-%m-%d"),
            "Finish Date": finish_date_cal.strftime("%Y-%m-%d"),
            "Predecessors": ",".join(task.predecessors),
            "Resources": ",".join(task.resources),
            "Chain Type": chain_type,
            "Progress (%)": getattr(task, "progress", 0),
        }

        data.append(row)

    # Create DataFrame and export to CSV
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"Schedule exported to {filename}")

    return df


def set_working_calendar(scheduler, calendar_type="standard", start_date=None):
    """Set the working calendar for the project

    calendar_type: 'standard' (5 day work week) or 'continuous' (7 day work week)
    start_date: datetime object for project start
    """
    scheduler.project_data["calendar"] = calendar_type

    if start_date:
        scheduler.project_data["start_date"] = start_date
    elif not scheduler.project_data["start_date"]:
        scheduler.project_data["start_date"] = datetime.now()

    print(f"Working calendar set to {calendar_type}")
    print(
        f"Project start date: {scheduler.project_data['start_date'].strftime('%Y-%m-%d')}"
    )


def test_export_functionality():
    """Test the schedule export functionality"""
    print("\n=== Test Case: Export Functionality ===")

    # Create a simple project
    scheduler = test_complex_network()

    # Set working calendar and start date
    from datetime import datetime

    set_working_calendar(
        scheduler, "standard", datetime(2025, 1, 6)
    )  # Start on a Monday

    # Export to CSV
    df = export_to_csv(scheduler, "project_schedule.csv")

    # Display the exported data
    print("\nExported Schedule Data (first 5 rows):")
    print(df.head())

    return scheduler, df


def test_monte_carlo_simulation():
    """Test Monte Carlo simulation for buffer sizing and risk analysis"""
    print("\n=== Test Case: Monte Carlo Simulation ===")

    import numpy as np

    # Create a simple project
    tasks = [
        Task(1, "Task A", 10, nominal_duration=15),
        Task(2, "Task B", 8, nominal_duration=12, predecessors="1"),
        Task(3, "Task C", 6, nominal_duration=9, predecessors="2"),
        Task(4, "Task D", 5, nominal_duration=8, predecessors="3"),
    ]

    # Function to run one Monte Carlo simulation
    def run_simulation():
        # Create copies of tasks with random durations
        sim_tasks = []
        for task in tasks:
            # Use triangular distribution (min, mode, max)
            min_duration = task.duration * 0.8  # 20% less than optimistic
            mode_duration = (task.duration + task.nominal_duration) / 2
            max_duration = task.nominal_duration * 1.2  # 20% more than pessimistic

            random_duration = np.random.triangular(
                min_duration, mode_duration, max_duration
            )

            sim_task = Task(
                task.id,
                task.name,
                round(random_duration),
                nominal_duration=task.nominal_duration,
                predecessors=",".join(task.predecessors),
                resources=",".join(task.resources),
            )
            sim_tasks.append(sim_task)

        # Create scheduler and run
        scheduler = CriticalChainScheduler()
        for task in sim_tasks:
            scheduler.add_task(task)

        scheduler.schedule()

        # Return the project duration (excluding buffer)
        return scheduler.critical_chain[-2].finish

    # Run 1000 simulations
    print("Running 1000 Monte Carlo simulations...")
    simulation_results = [run_simulation() for _ in range(1000)]

    # Analyze results
    mean_duration = np.mean(simulation_results)
    std_dev = np.std(simulation_results)
    min_duration = np.min(simulation_results)
    max_duration = np.max(simulation_results)

    # Calculate percentiles for confidence levels
    p50 = np.percentile(simulation_results, 50)
    p80 = np.percentile(simulation_results, 80)
    p90 = np.percentile(simulation_results, 90)
    p95 = np.percentile(simulation_results, 95)

    print("\nMonte Carlo Simulation Results:")
    print(f"  Minimum Duration: {min_duration:.1f} days")
    print(f"  Mean Duration: {mean_duration:.1f} days")
    print(f"  Maximum Duration: {max_duration:.1f} days")
    print(f"  Standard Deviation: {std_dev:.1f} days")
    print("\nCompletion Probability:")
    print(f"  50% Confidence (P50): {p50:.1f} days")
    print(f"  80% Confidence (P80): {p80:.1f} days")
    print(f"  90% Confidence (P90): {p90:.1f} days")
    print(f"  95% Confidence (P95): {p95:.1f} days")

    # Run standard CCPM to compare
    standard_scheduler = CriticalChainScheduler()
    for task in tasks:
        task_copy = Task(
            task.id,
            task.name,
            task.duration,
            nominal_duration=task.nominal_duration,
            predecessors=",".join(task.predecessors),
            resources=",".join(task.resources),
        )
        standard_scheduler.add_task(task_copy)

    standard_scheduler.schedule()
    project_duration = standard_scheduler.critical_chain[-2].finish
    buffer_size = standard_scheduler.critical_chain[-1].duration
    total_duration = project_duration + buffer_size

    print("\nComparison with Standard CCPM:")
    print(f"  Critical Chain Duration: {project_duration} days")
    print(f"  Project Buffer: {buffer_size} days")
    print(f"  Total Duration: {total_duration} days")

    # Calculate what confidence level the standard buffer provides
    buffer_confidence = (
        sum(1 for duration in simulation_results if duration <= total_duration)
        / len(simulation_results)
        * 100
    )
    print(f"  Standard CCPM Buffer Provides: {buffer_confidence:.1f}% confidence")

    # Visualize the results
    plt.figure(figsize=(12, 8))

    # Histogram of simulation results
    plt.hist(
        simulation_results, bins=30, alpha=0.7, color="lightblue", edgecolor="black"
    )

    # Add lines for key percentiles
    plt.axvline(
        p50, color="green", linestyle="--", linewidth=2, label=f"P50: {p50:.1f} days"
    )
    plt.axvline(
        p80, color="orange", linestyle="--", linewidth=2, label=f"P80: {p80:.1f} days"
    )
    plt.axvline(
        p90, color="red", linestyle="--", linewidth=2, label=f"P90: {p90:.1f} days"
    )

    # Add line for standard CCPM
    plt.axvline(
        total_duration,
        color="purple",
        linestyle="-",
        linewidth=2,
        label=f"Standard CCPM: {total_duration} days ({buffer_confidence:.1f}%)",
    )

    plt.xlabel("Project Duration (days)")
    plt.ylabel("Frequency")
    plt.title("Monte Carlo Simulation Results for Project Duration")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    return simulation_results, standard_scheduler

    # Run 1000 simulations
    print("Running 1000 Monte Carlo simulations...")
    simulation_results = [run_simulation() for _ in range(1000)]

    # Analyze results
    mean_duration = np.mean(simulation_results)
    std_dev = np.std(simulation_results)
    min_duration = np.min(simulation_results)
    max_duration = np.max(simulation_results)

    # Calculate percentiles for confidence levels
    p50 = np.percentile(simulation_results, 50)
    p80 = np.percentile(simulation_results, 80)
    p90 = np.percentile(simulation_results, 90)
    p95 = np.percentile(simulation_results, 95)

    print("\nMonte Carlo Simulation Results:")
    print(f"  Minimum Duration: {min_duration:.1f} days")
    print(f"  Mean Duration: {mean_duration:.1f} days")
    print(f"  Maximum Duration: {max_duration:.1f} days")
    print(f"  Standard Deviation: {std_dev:.1f} days")
    print("\nCompletion Probability:")
    print(f"  50% Confidence (P50): {p50:.1f} days")
    print(f"  80% Confidence (P80): {p80:.1f} days")
    print(f"  90% Confidence (P90): {p90:.1f} days")
    print(f"  95% Confidence (P95): {p95:.1f} days")

    # Run standard CCPM to compare
    standard_scheduler = CriticalChainScheduler()
    for task in tasks:
        task_copy = Task(
            task.id,
            task.name,
            task.duration,
            nominal_duration=task.nominal_duration,
            predecessors=",".join(task.predecessors),
            resources=",".join(task.resources),
        )
        standard_scheduler.add_task(task_copy)

    standard_scheduler.schedule()
    project_duration = standard_scheduler.critical_chain[-2].finish
    buffer_size = standard_scheduler.critical_chain[-1].duration
    total_duration = project_duration + buffer_size

    print("\nComparison with Standard CCPM:")
    print(f"  Critical Chain Duration: {project_duration} days")
    print(f"  Project Buffer: {buffer_size} days")
    print(f"  Total Duration: {total_duration} days")

    # Calculate what confidence level the standard buffer provides
    buffer_confidence = (
        sum(1 for duration in simulation_results if duration <= total_duration)
        / len(simulation_results)
        * 100
    )
    print(f"  Standard CCPM Buffer Provides: {buffer_confidence:.1f}% confidence")

    # Visualize the results
    plt.figure(figsize=(12, 8))

    # Histogram of simulation results
    plt.hist(
        simulation_results, bins=30, alpha=0.7, color="lightblue", edgecolor="black"
    )

    # Add lines for key percentiles
    plt.axvline(
        p50, color="green", linestyle="--", linewidth=2, label=f"P50: {p50:.1f} days"
    )
    plt.axvline(
        p80, color="orange", linestyle="--", linewidth=2, label=f"P80: {p80:.1f} days"
    )
    plt.axvline(
        p90, color="red", linestyle="--", linewidth=2, label=f"P90: {p90:.1f} days"
    )

    # Add line for standard CCPM
    plt.axvline(
        total_duration,
        color="purple",
        linestyle="-",
        linewidth=2,
        label=f"Standard CCPM: {total_duration} days ({buffer_confidence:.1f}%)",
    )

    plt.xlabel("Project Duration (days)")
    plt.ylabel("Frequency")
    plt.title("Monte Carlo Simulation Results for Project Duration")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    return simulation_results, standard_scheduler


# Run the tests
if __name__ == "__main__":
    print("========== Critical Chain Project Management Demo ==========")
    print("Select a test to run:")
    print("1. Simple Sequential Project")
    print("2. Project with Parallel Paths")
    print("3. Project with Resource Conflicts")
    print("4. Progress Tracking Example")
    print("5. Complex Project Network")
    print("6. Manufacturing Project Example")
    print("7. Software Development Project")
    print("8. Buffer Sizing Strategies Comparison")
    print("9. Export Schedule to CSV")
    print("10. Monte Carlo Simulation")
    print("11. Network Diagram Visualization")
    print("12. Run All Tests")
    print("13. test_larry_simple")
    print("14. test_larry_complex")

    try:
        choice = int(input("\nEnter your choice (1-14): "))

        if choice == 1:
            scheduler = test_simple_sequential()
        elif choice == 2:
            scheduler = test_parallel_paths()
        elif choice == 3:
            scheduler = test_resource_conflicts()
        elif choice == 4:
            scheduler = test_progress_tracking()
        elif choice == 5:
            scheduler = test_complex_network()
        elif choice == 6:
            scheduler = test_manufacturing_project()
        elif choice == 7:
            scheduler = test_software_development()
        elif choice == 8:
            test_buffer_sizing_strategies()
        elif choice == 9:
            test_export_functionality()
        elif choice == 10:
            test_monte_carlo_simulation()
        elif choice == 11:
            # Run complex network and visualize
            scheduler = test_complex_network()
            G = visualize_network(scheduler)
        elif choice == 12:
            print("\nRunning all tests sequentially...")
            test_simple_sequential()
            test_parallel_paths()
            test_resource_conflicts()
            test_progress_tracking()
            test_complex_network()
            test_manufacturing_project()
            test_software_development()
            test_buffer_sizing_strategies()
            test_export_functionality()
            test_monte_carlo_simulation()
            scheduler = test_complex_network()
            G = visualize_network(scheduler)
        elif choice == 13:
            scheduler = test_larry_simple()
        elif choice == 14:
            scheduler = test_larry_complex()
        else:
            print("Invalid choice. Please enter a number between 1 and 12.")
    except ValueError:
        print("Please enter a valid number.")

    print(
        "\nDemo completed. Thank you for exploring Critical Chain Project Management!"
    )
    print("============================================================")
