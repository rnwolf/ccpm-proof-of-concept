import networkx as nx
from ..domain.chain import Chain
from ..utils.graph import find_critical_path


def identify_critical_chain(tasks, resources, task_graph=None):
    """
    Identify the critical chain considering both dependencies and resources.

    Args:
        tasks: Dictionary of Task objects keyed by ID
        resources: List of resources available for the project
        task_graph: Optional existing directed graph representing task dependencies
                   (will be built if not provided)

    Returns:
        Chain: The critical chain object
        float: Size of the project buffer
    """
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

    # Find the critical path based on task durations
    critical_path = find_critical_path(task_graph, tasks)

    # Create the critical chain object
    critical_chain = Chain("critical", "Critical Chain", type="critical")
    critical_chain.tasks = critical_path

    # Update task chain membership
    for task_id in critical_path:
        task = tasks[task_id]
        task.chain_id = "critical"
        task.chain_type = "critical"

    return critical_chain


def resolve_resource_conflicts(critical_path, tasks, resources, task_graph=None):
    """
    Resolve resource conflicts along the critical path using resource leveling.

    This method ensures that the critical chain properly accounts for resource
    dependencies, not just task dependencies.

    Args:
        critical_path: List of task IDs forming the critical path
        tasks: Dictionary of Task objects keyed by ID
        resources: List of resources available for the project
        task_graph: Optional existing directed graph

    Returns:
        list: The adjusted critical path with resource conflicts resolved
    """
    if not task_graph:
        # Build a dependency graph if not provided
        task_graph = nx.DiGraph()

        # Add task nodes
        for task_id, task in tasks.items():
            task_graph.add_node(task_id, node_type="task", task=task)

        # Add task dependencies (edges)
        for task_id, task in tasks.items():
            for dep_id in task.dependencies:
                if dep_id in tasks:
                    task_graph.add_edge(dep_id, task_id)

    # Create a conflict graph where nodes are tasks and edges represent resource conflicts
    conflict_graph = nx.Graph()

    # Add all tasks from the critical path as nodes
    for task_id in critical_path:
        conflict_graph.add_node(task_id)

    # Add edges between tasks that share resources
    for i, task1_id in enumerate(critical_path):
        task1 = tasks[task1_id]
        for j, task2_id in enumerate(critical_path[i + 1 :], i + 1):
            task2 = tasks[task2_id]

            # Check if tasks share any resources
            shared_resources = False

            # Handle different resource formats (string, list, etc.)
            t1_resources = []
            if isinstance(task1.resources, str):
                t1_resources = [task1.resources]
            elif isinstance(task1.resources, list):
                t1_resources = task1.resources

            t2_resources = []
            if isinstance(task2.resources, str):
                t2_resources = [task2.resources]
            elif isinstance(task2.resources, list):
                t2_resources = task2.resources

            # Check for shared resources
            shared_resources = bool(set(t1_resources) & set(t2_resources))

            # Check if tasks are already dependent (no need for resource conflict)
            already_dependent = nx.has_path(
                task_graph, task1_id, task2_id
            ) or nx.has_path(task_graph, task2_id, task1_id)

            if shared_resources and not already_dependent:
                conflict_graph.add_edge(task1_id, task2_id)

    # If there are no resource conflicts, return the original critical path
    if not conflict_graph.edges:
        return critical_path

    # Get tasks in topological order to establish priority
    topo_order = list(nx.topological_sort(task_graph))

    # Create a priority map for sorting (lower number = higher priority)
    task_priority = {task_id: topo_order.index(task_id) for task_id in critical_path}

    # Sort critical path tasks by priority
    sorted_critical_tasks = sorted(
        critical_path, key=lambda x: task_priority.get(x, 999)
    )

    # Apply resource leveling - add resource dependencies to the task graph
    for task1_id, task2_id in conflict_graph.edges:
        # Add the resource dependency from the higher priority task to the lower priority task
        if task_priority[task1_id] < task_priority[task2_id]:
            # task1 has higher priority, add dependency from task1 to task2
            task_graph.add_edge(task1_id, task2_id, type="resource")
        else:
            # task2 has higher priority, add dependency from task2 to task1
            task_graph.add_edge(task2_id, task1_id, type="resource")

    # Recalculate the critical path now that resource dependencies are added
    adjusted_critical_path = find_critical_path(task_graph, tasks)

    return adjusted_critical_path
