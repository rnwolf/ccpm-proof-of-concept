import networkx as nx


def build_dependency_graph(tasks):
    """Build a directed graph representing task dependencies"""
    G = nx.DiGraph()

    # Add task nodes
    for task_id, task in tasks.items():
        G.add_node(task_id, node_type="task", task=task)

    # Add task dependencies (edges)
    for task_id, task in tasks.items():
        for dep_id in task.dependencies:
            if dep_id in tasks:  # Ensure dependency exists
                G.add_edge(dep_id, task_id)

    # Check for cycles
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Task dependencies contain cycles!")

    return G


def forward_pass(graph, tasks):
    """Calculate early start and early finish times"""
    # Topological sort to get tasks in order
    task_order = list(nx.topological_sort(graph))

    # Initialize start task
    for task_id in task_order:
        if task_id not in tasks:
            continue

        task = tasks[task_id]
        if not task.dependencies:  # Start task
            task.early_start = 0
            task.early_finish = task.planned_duration
        else:
            # Find maximum early finish of all predecessors
            max_finish = 0
            for dep_id in task.dependencies:
                if dep_id not in tasks:
                    continue

                dep_task = tasks[dep_id]
                if (
                    hasattr(dep_task, "early_finish")
                    and dep_task.early_finish > max_finish
                ):
                    max_finish = dep_task.early_finish

            task.early_start = max_finish
            task.early_finish = max_finish + task.planned_duration

    return tasks


def backward_pass(graph, tasks):
    """Calculate late start and late finish times"""
    # Reverse topological sort
    task_order = list(reversed(list(nx.topological_sort(graph))))

    # Find project duration
    project_duration = max(
        task.early_finish for task in tasks.values() if hasattr(task, "early_finish")
    )

    # Initialize end tasks
    for task_id in task_order:
        if task_id not in tasks:
            continue

        task = tasks[task_id]
        successors = list(graph.successors(task_id))

        # Filter out successors that aren't tasks
        successors = [succ_id for succ_id in successors if succ_id in tasks]

        if not successors:  # End task
            task.late_finish = project_duration
            task.late_start = task.late_finish - task.planned_duration
        else:
            # Find minimum late start of all successors
            min_start = float("inf")
            for succ_id in successors:
                succ_task = tasks[succ_id]
                if (
                    hasattr(succ_task, "late_start")
                    and succ_task.late_start < min_start
                ):
                    min_start = succ_task.late_start

            task.late_finish = min_start
            task.late_start = min_start - task.planned_duration

        # Calculate slack
        task.slack = task.late_start - task.early_start
        task.is_critical = task.slack == 0

    return tasks


def find_critical_path(graph, tasks):
    """Find the critical path (zero slack) in the graph"""
    critical_path = [
        task_id
        for task_id in graph.nodes()
        if task_id in tasks
        and hasattr(tasks[task_id], "is_critical")
        and tasks[task_id].is_critical
    ]

    # Sort critical path in topological order
    subgraph = graph.subgraph(critical_path)
    return list(nx.topological_sort(subgraph))
