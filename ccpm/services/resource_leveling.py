import networkx as nx
from datetime import datetime, timedelta


def level_resources(tasks, resources, priority_chain=None, task_graph=None):
    """Apply resource leveling to the schedule, ensuring no resource is over-allocated."""
    # Build task graph if not provided
    if task_graph is None:
        task_graph = nx.DiGraph()

        # Add task nodes
        for task_id, task in tasks.items():
            task_graph.add_node(task_id, node_type="task", task=task)

        # Add task dependencies (edges)
        for task_id, task in tasks.items():
            for dep_id in task.dependencies:
                if dep_id in tasks:  # Ensure dependency exists
                    task_graph.add_edge(dep_id, task_id)

    # Extract priority chain tasks if provided
    priority_tasks = []
    if priority_chain is not None:
        if hasattr(priority_chain, "tasks"):
            # It's a Chain object
            priority_tasks = priority_chain.tasks
        else:
            # It's a list of task IDs
            priority_tasks = priority_chain

    # Create a conflict graph for resource conflicts
    conflict_graph = nx.Graph()

    # Add all tasks as nodes
    for task_id in tasks.keys():
        conflict_graph.add_node(task_id)

    # Add edges between tasks that share resources and would exceed capacity
    for task1_id, task1 in tasks.items():
        for task2_id, task2 in tasks.items():
            if task1_id == task2_id:
                continue  # Skip comparing task to itself

            # Check if tasks are already directly dependent based on task dependencies
            # This is more reliable than using the task graph, which might have been modified
            already_dependent = (task1_id in task2.dependencies) or (task2_id in task1.dependencies)

            if already_dependent:
                continue  # Skip if there's already a direct dependency

            # Get resource allocations for both tasks
            task1_resources = _get_task_resource_allocations(task1)
            task2_resources = _get_task_resource_allocations(task2)

            # Find shared resources between the tasks
            shared_resources = set(task1_resources.keys()) & set(task2_resources.keys())


            # If they share resources, check for conflicts
            if shared_resources:
                for resource_id in shared_resources:
                    # Get allocated amounts
                    t1_allocation = task1_resources.get(resource_id, 0.0)
                    t2_allocation = task2_resources.get(resource_id, 0.0)

                    # Default capacity is 1.0 if not specified
                    resource_capacity = 1.0
                    # If resources is a dict with capacity info, use that
                    if isinstance(resources, dict) and resource_id in resources:
                        resource_capacity = resources[resource_id].get("capacity", 1.0)

                    # If combined allocation exceeds capacity, add conflict edge
                    if t1_allocation + t2_allocation > resource_capacity:
                        conflict_graph.add_edge(task1_id, task2_id)
                        # We found a conflict, no need to check other resources
                        break

    # If no conflicts found, return tasks as is
    if not conflict_graph.edges():
        return tasks, task_graph

    # Apply graph coloring for resource allocation
    coloring = _apply_graph_coloring(conflict_graph, tasks, priority_tasks)

    # Adjust schedule based on coloring
    tasks = _adjust_schedule_based_on_coloring(tasks, coloring, task_graph, priority_tasks)

    # Add resource dependencies to the task graph
    for task1_id, task2_id in conflict_graph.edges():
        # Determine which task should come first based on coloring
        if coloring.get(task1_id, 0) < coloring.get(task2_id, 0):
            task_graph.add_edge(task1_id, task2_id, type="resource")
        else:
            task_graph.add_edge(task2_id, task1_id, type="resource")

    # Manually update dependent tasks to ensure they start after all their dependencies finish
    # This is necessary because resource leveling may have changed task start/finish times
    for task_id, task in tasks.items():
        if task.dependencies:
            # Find the maximum finish time of all dependencies
            max_finish = 0
            for dep_id in task.dependencies:
                if dep_id in tasks:
                    dep_task = tasks[dep_id]
                    if hasattr(dep_task, "early_finish") and dep_task.early_finish > max_finish:
                        max_finish = dep_task.early_finish

            # If the task starts before all dependencies finish, adjust its start time
            if task.early_start < max_finish:
                task.early_start = max_finish
                task.early_finish = max_finish + task.planned_duration

    return tasks, task_graph


def _get_task_resource_allocations(task):
    """
    Helper function to extract resource allocations from a task, handling different formats.

    Args:
        task: Task object

    Returns:
        dict: Dictionary mapping resource ID to allocation amount
    """
    # Check if task has resource_allocations attribute (new format)
    if hasattr(task, "resource_allocations") and task.resource_allocations:
        return task.resource_allocations.copy()

    # Fallback for backward compatibility
    if hasattr(task, "resources") and task.resources:
        resource_allocations = {}
        if isinstance(task.resources, str):
            resource_allocations[task.resources] = 1.0
        elif isinstance(task.resources, list):
            for resource in task.resources:
                resource_allocations[resource] = 1.0
        return resource_allocations

    # Default to empty dict if no resources found
    return {}


def _apply_graph_coloring(conflict_graph, tasks, priority_tasks=None):
    """
    Apply graph coloring algorithm to assign colors (time slots) to tasks.
    For CCPM, we prioritize tasks from back to front (latest finish time first)
    with highest priority given to critical chain tasks.

    Args:
        conflict_graph: Graph where nodes are tasks and edges are resource conflicts
        tasks: Dictionary of Task objects
        priority_tasks: List of task IDs that should be prioritized (e.g., critical chain)

    Returns:
        dict: Mapping from task_id to color (time slot)
    """
    # Determine task priority - lower number means higher priority
    task_priority = {}

    # Give highest priority to tasks in the priority list (typically critical chain)
    if priority_tasks:
        for i, task_id in enumerate(priority_tasks):
            task_priority[task_id] = i

    # Next priority based on late finish time (later finish = higher priority)
    # This implements the CCPM approach of scheduling from back to front
    for task_id in conflict_graph.nodes():
        if task_id not in task_priority:
            # Default priority based on late finish time (later finish = higher priority)
            # Use degree in conflict graph as a tie-breaker
            late_finish = 0
            if task_id in tasks and hasattr(tasks[task_id], "late_finish"):
                late_finish = tasks[task_id].late_finish
            elif task_id in tasks and hasattr(tasks[task_id], "early_finish"):
                late_finish = tasks[task_id].early_finish

            # Also consider if task is part of a feeding chain
            chain_priority = 0
            if task_id in tasks and hasattr(tasks[task_id], "chain_type"):
                if tasks[task_id].chain_type == "feeding":
                    chain_priority = 500  # Priority for feeding chain tasks

            # Higher late_finish and being in a feeding chain means higher priority
            task_priority[task_id] = (
                1000 - late_finish - chain_priority
            )

    # Sort nodes by priority for coloring
    nodes_by_priority = sorted(
        conflict_graph.nodes(), key=lambda node: task_priority.get(node, 9999)
    )

    # Assign colors using greedy algorithm
    coloring = {}
    for node in nodes_by_priority:
        # Find which colors are used by neighbors
        used_colors = set()
        for neighbor in conflict_graph.neighbors(node):
            if neighbor in coloring:
                used_colors.add(coloring[neighbor])

        # Find smallest available color
        color = 0
        while color in used_colors:
            color += 1

        coloring[node] = color

    return coloring


def _adjust_schedule_based_on_coloring(tasks, coloring, task_graph=None, priority_chain=None):
    """
    Adjust task schedule based on graph coloring results.
    For CCPM, we schedule critical chain tasks as early as possible (ASAP)
    and feeding chain tasks as late as possible (ALAP) while still respecting
    their logical and resource dependencies.

    Args:
        tasks: Dictionary of Task objects
        coloring: Dictionary mapping task_id to color (time slot)
        task_graph: Optional directed graph representing task dependencies
        priority_chain: Optional list of task IDs that should be prioritized (e.g., critical chain)

    Returns:
        dict: Updated tasks with adjusted schedules
    """
    # Group tasks by color (time slot)
    color_groups = {}
    for task_id, color in coloring.items():
        if color not in color_groups:
            color_groups[color] = []
        color_groups[color].append(task_id)

    # Sort colors (time slots)
    sorted_colors = sorted(color_groups.keys())

    # Set for tasks that have already been adjusted
    adjusted_tasks = set()

    # We need to adjust schedules in topological order within each color group
    # First, build a task graph to establish dependencies
    task_graph = nx.DiGraph()
    for task_id, task in tasks.items():
        task_graph.add_node(task_id)
        for dep_id in task.dependencies:
            if dep_id in tasks:
                task_graph.add_edge(dep_id, task_id)

    # Track the latest finish time for each task
    task_finish_times = {}

    # Identify critical chain and feeding chain tasks
    critical_tasks = set()
    feeding_tasks = set()

    # First, identify tasks that are explicitly marked as critical or feeding
    for task_id, task in tasks.items():
        if hasattr(task, "chain_type"):
            if task.chain_type == "critical":
                critical_tasks.add(task_id)
            elif task.chain_type == "feeding":
                feeding_tasks.add(task_id)

    # If priority_chain is provided, use it to identify critical tasks
    if priority_chain:
        critical_tasks.update(priority_chain)

    # Identify potential feeding chain tasks based on dependencies
    # A feeding chain task is one that is not in the critical chain
    # but has a path to a critical chain task
    potential_feeding_tasks = set()
    for task_id in tasks:
        if task_id not in critical_tasks:
            # Check if this task has a path to a critical chain task
            for critical_task_id in critical_tasks:
                if nx.has_path(task_graph, task_id, critical_task_id):
                    potential_feeding_tasks.add(task_id)
                    break

    # Add potential feeding tasks to feeding_tasks
    feeding_tasks.update(potential_feeding_tasks)

    # First pass: Schedule critical chain tasks as early as possible (ASAP)
    # For each color (time slot), adjust critical chain tasks within that group
    for color in sorted_colors:
        tasks_in_color = [t for t in color_groups[color] if t in critical_tasks]
        if not tasks_in_color:
            continue

        # Sort tasks in this color group topologically (within the group)
        try:
            sorted_tasks = list(
                nx.topological_sort(task_graph.subgraph(tasks_in_color))
            )
        except nx.NetworkXUnfeasible:
            # If there's a cycle, fall back to simple list
            sorted_tasks = tasks_in_color

        # Process each critical chain task in this color group
        for task_id in sorted_tasks:
            task = tasks[task_id]
            adjusted_tasks.add(task_id)

            # Calculate earliest start based on dependencies and resource conflicts
            earliest_start = 0  # Default start time

            # Check explicit dependencies first - always respect dependencies
            for dep_id in task.dependencies:
                if dep_id in tasks:
                    dep_task = tasks[dep_id]

                    # Always use the most up-to-date finish time for dependencies
                    if dep_id in task_finish_times:
                        dep_end = task_finish_times[dep_id]
                        if dep_end > earliest_start:
                            earliest_start = dep_end
                    elif hasattr(dep_task, "adjusted_early_finish"):
                        # If dependency has been adjusted, use that time
                        dep_end = dep_task.adjusted_early_finish
                        if dep_end > earliest_start:
                            earliest_start = dep_end
                    elif hasattr(dep_task, "early_finish"):
                        # Otherwise use the original early finish time
                        dep_end = dep_task.early_finish
                        if dep_end > earliest_start:
                            earliest_start = dep_end

            # Check resource conflicts - tasks with the same color can run in parallel
            # Tasks with different colors that share resources must be sequential
            if color > 0:
                # Find tasks in lower color groups that share resources with this task
                task_resources = _get_task_resource_allocations(task)
                for prev_color in range(color):
                    if prev_color in color_groups:
                        for prev_task_id in color_groups[prev_color]:
                            if prev_task_id in tasks and prev_task_id in adjusted_tasks:
                                prev_task = tasks[prev_task_id]
                                prev_task_resources = _get_task_resource_allocations(prev_task)

                                # Check if they share resources
                                shared_resources = set(task_resources.keys()) & set(prev_task_resources.keys())
                                if shared_resources:
                                    # They share resources, so this task must start after the previous task finishes
                                    if prev_task_id in task_finish_times:
                                        prev_finish = task_finish_times[prev_task_id]
                                        if prev_finish > earliest_start:
                                            earliest_start = prev_finish

            # Set new schedule
            task.adjusted_early_start = earliest_start
            task.adjusted_early_finish = earliest_start + task.planned_duration

            # Update task's early_start and early_finish properties
            task.early_start = task.adjusted_early_start
            task.early_finish = task.adjusted_early_finish

            # Store the finish time for this task
            task_finish_times[task_id] = task.adjusted_early_finish

    # Second pass: Schedule non-critical, non-feeding tasks
    # These are tasks that are not part of any chain
    # For tasks that can run in parallel with critical chain tasks, schedule them to start at the same time
    # For other tasks, schedule them as early as possible (ASAP)
    for color in sorted_colors:
        tasks_in_color = [t for t in color_groups[color] if t not in critical_tasks and t not in feeding_tasks]
        if not tasks_in_color:
            continue

        # Sort tasks in this color group topologically (within the group)
        try:
            sorted_tasks = list(
                nx.topological_sort(task_graph.subgraph(tasks_in_color))
            )
        except nx.NetworkXUnfeasible:
            # If there's a cycle, fall back to simple list
            sorted_tasks = tasks_in_color

        # Process each non-chain task in this color group
        for task_id in sorted_tasks:
            task = tasks[task_id]
            adjusted_tasks.add(task_id)

            # Calculate earliest start based on dependencies and resource conflicts
            earliest_start = 0  # Default start time

            # Check explicit dependencies first - always respect dependencies
            for dep_id in task.dependencies:
                if dep_id in tasks:
                    dep_task = tasks[dep_id]

                    # Always use the most up-to-date finish time for dependencies
                    if dep_id in task_finish_times:
                        dep_end = task_finish_times[dep_id]
                        if dep_end > earliest_start:
                            earliest_start = dep_end
                    elif hasattr(dep_task, "adjusted_early_finish"):
                        # If dependency has been adjusted, use that time
                        dep_end = dep_task.adjusted_early_finish
                        if dep_end > earliest_start:
                            earliest_start = dep_end
                    elif hasattr(dep_task, "early_finish"):
                        # Otherwise use the original early finish time
                        dep_end = dep_task.early_finish
                        if dep_end > earliest_start:
                            earliest_start = dep_end

            # Check resource conflicts - tasks with the same color can run in parallel
            # Tasks with different colors that share resources must be sequential
            if color > 0:
                # Find tasks in lower color groups that share resources with this task
                task_resources = _get_task_resource_allocations(task)
                for prev_color in range(color):
                    if prev_color in color_groups:
                        for prev_task_id in color_groups[prev_color]:
                            if prev_task_id in tasks and prev_task_id in adjusted_tasks:
                                prev_task = tasks[prev_task_id]
                                prev_task_resources = _get_task_resource_allocations(prev_task)

                                # Check if they share resources
                                shared_resources = set(task_resources.keys()) & set(prev_task_resources.keys())
                                if shared_resources:
                                    # They share resources, so this task must start after the previous task finishes
                                    if prev_task_id in task_finish_times:
                                        prev_finish = task_finish_times[prev_task_id]
                                        if prev_finish > earliest_start:
                                            earliest_start = prev_finish

            # Check if this task can be scheduled in parallel with any critical chain tasks
            # If so, delay it to start at the same time as the critical chain task
            parallel_critical_start = None
            for critical_task_id in critical_tasks:
                if critical_task_id in parallel_tasks[task_id]:
                    critical_task = tasks[critical_task_id]
                    if hasattr(critical_task, "early_start") and critical_task.early_start >= earliest_start:
                        # Find the earliest critical task that starts after this task's earliest possible start
                        if parallel_critical_start is None or critical_task.early_start < parallel_critical_start:
                            parallel_critical_start = critical_task.early_start

            # If this task can be scheduled in parallel with a critical chain task,
            # delay it to start at the same time as the critical chain task
            if parallel_critical_start is not None:
                earliest_start = parallel_critical_start

            # Set new schedule
            task.adjusted_early_start = earliest_start
            task.adjusted_early_finish = earliest_start + task.planned_duration

            # Update task's early_start and early_finish properties
            task.early_start = task.adjusted_early_start
            task.early_finish = task.adjusted_early_finish

            # Store the finish time for this task
            task_finish_times[task_id] = task.adjusted_early_finish

    # Third pass: Schedule feeding chain tasks as late as possible (ALAP)
    # First, we need to find the latest possible start time for each feeding chain task
    # based on its successors and resource constraints

    # Build a reverse graph for backward pass
    reverse_graph = task_graph.reverse()

    # Find the maximum project duration based on current schedule
    project_duration = max(
        task.early_finish for task in tasks.values() if hasattr(task, "early_finish")
    )

    # Initialize latest finish times for all tasks
    latest_finish = {}
    for task_id in tasks:
        if task_id in feeding_tasks:
            # For feeding tasks, start with project duration
            latest_finish[task_id] = project_duration
        elif task_id in adjusted_tasks:
            # For already adjusted tasks, use their current finish time
            latest_finish[task_id] = tasks[task_id].early_finish

    # Create a dictionary to track which tasks can be scheduled in parallel
    # based on lack of resource conflicts and logical dependencies
    parallel_tasks = {}
    for task1_id in tasks:
        parallel_tasks[task1_id] = set()
        for task2_id in tasks:
            if task1_id == task2_id:
                continue

            # Check if tasks have logical dependencies
            task1 = tasks[task1_id]
            task2 = tasks[task2_id]
            has_dependency = (task1_id in task2.dependencies) or (task2_id in task1.dependencies)

            # Check if tasks have resource conflicts
            task1_resources = _get_task_resource_allocations(task1)
            task2_resources = _get_task_resource_allocations(task2)
            shared_resources = set(task1_resources.keys()) & set(task2_resources.keys())

            # If no logical dependencies and no resource conflicts, they can be scheduled in parallel
            if not has_dependency and not shared_resources:
                parallel_tasks[task1_id].add(task2_id)

    # Perform backward pass to find latest finish times for feeding chain tasks
    # Process feeding tasks in reverse topological order
    feeding_tasks_list = list(feeding_tasks)
    try:
        sorted_feeding_tasks = list(nx.topological_sort(reverse_graph.subgraph(feeding_tasks_list)))
    except nx.NetworkXUnfeasible:
        # If there's a cycle, fall back to simple list
        sorted_feeding_tasks = feeding_tasks_list

    for task_id in sorted_feeding_tasks:
        task = tasks[task_id]

        # Find the minimum latest start time of all successors
        min_successor_start = project_duration

        # Check explicit successors
        for succ_id in reverse_graph.neighbors(task_id):
            if succ_id in tasks and succ_id in latest_finish:
                succ_task = tasks[succ_id]
                succ_start = latest_finish[succ_id] - succ_task.planned_duration
                if succ_start < min_successor_start:
                    min_successor_start = succ_start

        # Check resource conflicts - tasks with the same color can run in parallel
        # Tasks with different colors that share resources must be sequential
        task_color = coloring.get(task_id, 0)
        task_resources = _get_task_resource_allocations(task)

        for other_task_id, other_color in coloring.items():
            if other_task_id == task_id or other_color <= task_color:
                continue  # Skip self and tasks with lower or same color

            if other_task_id in tasks and other_task_id in latest_finish:
                other_task = tasks[other_task_id]
                other_resources = _get_task_resource_allocations(other_task)

                # Check if they share resources
                shared_resources = set(task_resources.keys()) & set(other_resources.keys())
                if shared_resources:
                    # They share resources, so this task must finish before the other task starts
                    other_start = latest_finish[other_task_id] - other_task.planned_duration
                    if other_start < min_successor_start:
                        min_successor_start = other_start

        # Calculate latest finish time for this task
        latest_finish_time = min_successor_start

        # Update latest finish time
        latest_finish[task_id] = latest_finish_time

    # Now schedule feeding chain tasks based on their latest finish times
    for task_id in feeding_tasks:
        if task_id in latest_finish:
            task = tasks[task_id]

            # Calculate latest start time
            latest_start = latest_finish[task_id] - task.planned_duration

            # Ensure the task doesn't start before its dependencies finish
            earliest_possible_start = 0
            for dep_id in task.dependencies:
                if dep_id in tasks:
                    dep_task = tasks[dep_id]
                    if dep_id in task_finish_times:
                        dep_end = task_finish_times[dep_id]
                        if dep_end > earliest_possible_start:
                            earliest_possible_start = dep_end
                    elif hasattr(dep_task, "early_finish"):
                        dep_end = dep_task.early_finish
                        if dep_end > earliest_possible_start:
                            earliest_possible_start = dep_end

            # Check if this feeding task can be scheduled in parallel with any critical chain tasks
            can_parallel_with_critical = False
            for critical_task_id in critical_tasks:
                if critical_task_id in parallel_tasks[task_id]:
                    critical_task = tasks[critical_task_id]
                    # If the critical task is already scheduled and this feeding task can run in parallel with it,
                    # schedule this feeding task to start at the same time as the critical task
                    if hasattr(critical_task, "early_start") and critical_task.early_start >= earliest_possible_start:
                        earliest_possible_start = critical_task.early_start
                        can_parallel_with_critical = True
                        break

            # If this feeding task can be scheduled in parallel with a critical chain task,
            # use the earliest possible start time instead of the latest start time
            if can_parallel_with_critical:
                start_time = earliest_possible_start
            else:
                # Use the later of earliest_possible_start and latest_start
                # This ensures we schedule ALAP while respecting dependencies
                start_time = max(earliest_possible_start, latest_start)

            # Set new schedule
            task.adjusted_early_start = start_time
            task.adjusted_early_finish = start_time + task.planned_duration

            # Update task's early_start and early_finish properties
            task.early_start = task.adjusted_early_start
            task.early_finish = task.adjusted_early_finish

            # Store the finish time for this task
            task_finish_times[task_id] = task.adjusted_early_finish

            # If task has start dates, update those too (for scheduler's use)
            if hasattr(task, "start_date") and task.start_date is not None:
                if hasattr(task, "new_start_date"):
                    task.new_start_date = task.start_date + timedelta(
                        days=task.early_start
                    )
                    if hasattr(task, "new_end_date"):
                        task.new_end_date = task.new_start_date + timedelta(
                            days=task.planned_duration
                        )

    return tasks
