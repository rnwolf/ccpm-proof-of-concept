import networkx as nx
from ..domain.chain import Chain


def identify_feeding_chains(tasks, critical_chain, task_graph=None):
    """
    Identify feeding chains - paths that feed into the critical chain.

    Args:
        tasks: Dictionary of Task objects keyed by ID
        critical_chain: The critical chain object or list of task IDs
        task_graph: Optional existing directed graph representing task dependencies
                  (will be built if not provided)

    Returns:
        list: List of Chain objects representing the feeding chains
    """
    # Extract critical chain task IDs if a Chain object was provided
    if isinstance(critical_chain, Chain):
        critical_task_ids = critical_chain.tasks
    else:
        critical_task_ids = critical_chain

    # Create a set of critical chain tasks for faster lookup
    critical_set = set(critical_task_ids)

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

    # Identify feeding points - where non-critical tasks connect to the critical chain
    feeding_points = {}  # Maps critical chain task to list of feeding tasks

    # For each critical task, find its non-critical predecessors
    for critical_task_id in critical_task_ids:
        predecessors = list(task_graph.predecessors(critical_task_id))
        for pred_id in predecessors:
            if pred_id not in critical_set and pred_id in tasks:
                if critical_task_id not in feeding_points:
                    feeding_points[critical_task_id] = []
                feeding_points[critical_task_id].append(pred_id)

    # Create feeding chains
    feeding_chains = []
    chain_id = 1

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
                    for pred in task_graph.predecessors(current_task)
                    if pred not in critical_set and pred in tasks
                ]

                if not preds:
                    # No more predecessors, chain is complete
                    break

                # For simplicity, take the "longest" predecessor path
                if len(preds) > 1:
                    # Sort predecessors by their duration (longest first)
                    preds.sort(
                        key=lambda x: tasks[x].planned_duration
                        if hasattr(tasks[x], "planned_duration")
                        else tasks[x].duration,
                        reverse=True,
                    )

                # Add the predecessor to our chain and continue
                current_task = preds[0]
                chain.append(current_task)

            # Reverse the chain so it's in topological order
            chain.reverse()

            # Create the chain object with a unique ID
            chain_name = f"Feeding Chain {chain_id}"
            feeding_chain = Chain(f"feeding_{chain_id}", chain_name, type="feeding")
            feeding_chain.tasks = chain
            feeding_chain.set_connection(critical_task_id)

            # Mark tasks as part of this feeding chain
            for task_id in chain:
                tasks[task_id].chain_id = feeding_chain.id
                tasks[task_id].chain_type = "feeding"

            # Add to result list
            feeding_chains.append(feeding_chain)
            chain_id += 1

    return feeding_chains
