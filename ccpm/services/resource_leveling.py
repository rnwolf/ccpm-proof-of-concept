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
            if task1_id != task2_id:
                # Check if tasks share any resources
                shared_resources = set(task1.resource_allocations.keys()) & set(
                    task2.resource_allocations.keys()
                )

                # If tasks share resources and are not already dependent
                if shared_resources:
                    # Check if there's already a path in the dependency graph
                    already_dependent = nx.has_path(
                        task_graph, task1_id, task2_id
                    ) or nx.has_path(task_graph, task2_id, task1_id)

                    if not already_dependent:
                        # For each shared resource, check if combined allocation exceeds capacity
                        for resource_id in shared_resources:
                            t1_allocation = task1.resource_allocations.get(
                                resource_id, 0.0
                            )
                            t2_allocation = task2.resource_allocations.get(
                                resource_id, 0.0
                            )

                            # Default capacity is 1.0 if not specified
                            resource_capacity = 1.0
                            # If resources is a dict with capacity info, use that
                            if isinstance(resources, dict) and resource_id in resources:
                                resource_capacity = resources[resource_id].get(
                                    "capacity", 1.0
                                )

                            # If combined allocation exceeds capacity, add conflict edge
                            if t1_allocation + t2_allocation > resource_capacity:
                                conflict_graph.add_edge(task1_id, task2_id)
                                # We only need one resource conflict to necessitate sequencing
                                break

    # Apply graph coloring for resource allocation
    coloring = _apply_graph_coloring(conflict_graph, tasks, priority_tasks)

    # Adjust schedule based on coloring
    _adjust_schedule_based_on_coloring(tasks, coloring)

    # Add resource dependencies to the task graph
    for task1_id, task2_id in conflict_graph.edges():
        # Determine which task should come first based on coloring
        if coloring.get(task1_id, 0) < coloring.get(task2_id, 0):
            task_graph.add_edge(task1_id, task2_id, type="resource")
        else:
            task_graph.add_edge(task2_id, task1_id, type="resource")

    return tasks, task_graph


def _get_task_resources(task):
    """
    Helper function to extract resource list from a task, handling different formats.

    Args:
        task: Task object

    Returns:
        list: List of resource names
    """
    if not hasattr(task, "resources"):
        return []

    if isinstance(task.resources, str):
        return [task.resources]
    elif isinstance(task.resources, list):
        return task.resources
    else:
        return []


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

    # This branch is likely unnecessary now, but kept for backward compatibility
    # with any old code that might still be setting resources directly
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

    # Next priority based on number of successors in original task graph
    for task_id in conflict_graph.nodes():
        if task_id not in task_priority:
            # Default priority based on task dependencies (more successors = higher priority)
            successors = list(nx.descendants(conflict_graph, task_id))
            task_priority[task_id] = 1000 + len(successors)

    # Sort nodes by priority for coloring
    nodes_by_priority = sorted(
        conflict_graph.nodes(),
        key=lambda node: (task_priority.get(node, 9999), -conflict_graph.degree(node)),
    )

    # Assign colors manually using our priority order
    coloring = {}
    for node in nodes_by_priority:
        # Find smallest available color (time slot) for this node
        used_colors = {
            coloring.get(nbr)
            for nbr in conflict_graph.neighbors(node)
            if nbr in coloring
        }

        color = 0
        while color in used_colors:
            color += 1

        coloring[node] = color

    return coloring


def _adjust_schedule_based_on_coloring(tasks, coloring):
    """
    Adjust task schedule based on graph coloring results.

    Args:
        tasks: Dictionary of Task objects
        coloring: Dictionary mapping task_id to color (time slot)

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

    # Assign start dates based on colors and dependencies
    for color in sorted_colors:
        tasks_in_color = color_groups[color]

        # Process each task in this color group
        for task_id in tasks_in_color:
            task = tasks[task_id]

            # Calculate earliest start based on dependencies
            earliest_start = None
            for dep_id in task.dependencies:
                if dep_id in tasks:
                    dep_task = tasks[dep_id]

                    # Get dependency end date
                    dep_end = None
                    if (
                        hasattr(dep_task, "actual_end_date")
                        and dep_task.actual_end_date
                    ):
                        dep_end = dep_task.actual_end_date
                    elif hasattr(dep_task, "new_end_date") and dep_task.new_end_date:
                        dep_end = dep_task.new_end_date
                    elif hasattr(dep_task, "end_date") and dep_task.end_date:
                        dep_end = dep_task.end_date

                    # Update earliest start if this dependency ends later
                    if dep_end:
                        if earliest_start is None or dep_end > earliest_start:
                            earliest_start = dep_end

            # If no dependencies or already started, use existing dates
            if earliest_start is None:
                if hasattr(task, "actual_start_date") and task.actual_start_date:
                    # Task already started
                    continue
                elif hasattr(task, "start_date") and task.start_date:
                    earliest_start = task.start_date
                else:
                    # No date available, use current date
                    earliest_start = datetime.now()

            # Update task dates
            if hasattr(task, "new_start_date"):
                task.new_start_date = earliest_start
                duration = (
                    task.remaining_duration
                    if hasattr(task, "remaining_duration")
                    else task.duration
                )
                task.new_end_date = earliest_start + timedelta(days=duration)
            else:
                task.start_date = earliest_start
                task.end_date = earliest_start + timedelta(days=task.duration)

    return tasks
