import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from ..utils.graph import build_dependency_graph


def create_network_diagram(scheduler, filename=None, show=True, layout="spring"):
    """
    Visualize the task dependency network with critical chain and feeding chains highlighted.

    Args:
        scheduler: The CCPMScheduler instance
        filename: Optional filename to save the diagram
        show: Whether to display the diagram (default: True)
        layout: Network layout type ('spring', 'dot', 'circular', 'shell', or 'spectral')

    Returns:
        The matplotlib figure
    """
    # Get data from scheduler
    tasks = scheduler.tasks
    buffers = scheduler.buffers if hasattr(scheduler, "buffers") else {}
    critical_chain = scheduler.critical_chain
    chains = scheduler.chains if hasattr(scheduler, "chains") else {}

    # Get or build the task graph
    if hasattr(scheduler, "task_graph") and scheduler.task_graph:
        G = scheduler.task_graph
    else:
        G = build_dependency_graph(tasks)

    # Create the figure
    plt.figure(figsize=(12, 8))

    # Prepare node attributes
    node_colors = []
    node_shapes = []
    node_sizes = []

    for node in G.nodes():
        if node in buffers:
            # Node is a buffer
            buffer = buffers[node]
            if buffer.buffer_type == "project":
                node_colors.append("green")
            else:  # feeding buffer
                node_colors.append("yellow")
            node_shapes.append("s")  # square for buffers
            node_sizes.append(700)
        elif node in tasks:
            # Node is a task
            task = tasks[node]

            # Check task status for shape and size
            if task.status == "completed":
                node_shapes.append("o")  # circle for completed tasks
                node_sizes.append(500)
            elif task.status == "in_progress":
                node_shapes.append("o")  # circle for in-progress tasks
                node_sizes.append(600)
            else:
                node_shapes.append("o")  # circle for planned tasks
                node_sizes.append(500)

            # Check chain membership for color
            if critical_chain and task.id in critical_chain.tasks:
                node_colors.append("red")
            elif (
                task.chain_id
                and task.chain_id in chains
                and chains[task.chain_id].type == "feeding"
            ):
                node_colors.append("orange")
            else:
                node_colors.append("skyblue")
        else:
            # Default for unknown nodes
            node_colors.append("gray")
            node_shapes.append("o")
            node_sizes.append(300)

    # Prepare edge attributes
    edge_colors = []
    edge_widths = []

    for u, v in G.edges():
        # Check if edge is part of the critical chain
        is_critical_edge = (
            critical_chain
            and u in critical_chain.tasks
            and v in critical_chain.tasks
            and critical_chain.tasks.index(u) + 1 == critical_chain.tasks.index(v)
        )

        # Check if edge is between a feeding chain and a buffer
        is_feeding_to_buffer = (
            v in buffers and buffers[v].buffer_type == "feeding" and u in tasks
        )

        # Check if edge is from a buffer to a task
        is_buffer_to_task = u in buffers and v in tasks

        # Check if edge is part of a feeding chain
        is_feeding_chain_edge = False
        for chain_id, chain in chains.items():
            if chain.type == "feeding" and u in chain.tasks and v in chain.tasks:
                # Check if they're adjacent in the chain
                try:
                    u_idx = chain.tasks.index(u)
                    v_idx = chain.tasks.index(v)
                    if abs(u_idx - v_idx) == 1:
                        is_feeding_chain_edge = True
                        break
                except (ValueError, IndexError):
                    pass

        # Assign edge color and width based on type
        if is_critical_edge:
            edge_colors.append("red")
            edge_widths.append(2.5)
        elif is_feeding_to_buffer:
            edge_colors.append("yellow")
            edge_widths.append(2.0)
        elif is_buffer_to_task:
            if buffers[u].buffer_type == "project":
                edge_colors.append("green")
            else:
                edge_colors.append("yellow")
            edge_widths.append(2.0)
        elif is_feeding_chain_edge:
            edge_colors.append("orange")
            edge_widths.append(2.0)
        else:
            edge_colors.append("gray")
            edge_widths.append(1.0)

    # Choose layout algorithm
    if layout == "spring":
        pos = nx.spring_layout(G, seed=42)
    elif layout == "dot":
        try:
            pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
        except ImportError:
            print("Graphviz not available. Using spring layout instead.")
            pos = nx.spring_layout(G, seed=42)
    elif layout == "circular":
        pos = nx.circular_layout(G)
    elif layout == "shell":
        pos = nx.shell_layout(G)
    elif layout == "spectral":
        pos = nx.spectral_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42)

    # Draw nodes with different shapes
    # First, split nodes by shape
    circles = [n for n, s in zip(G.nodes(), node_shapes) if s == "o"]
    squares = [n for n, s in zip(G.nodes(), node_shapes) if s == "s"]

    # Get the corresponding colors and sizes
    circle_colors = [node_colors[list(G.nodes()).index(n)] for n in circles]
    square_colors = [node_colors[list(G.nodes()).index(n)] for n in squares]
    circle_sizes = [node_sizes[list(G.nodes()).index(n)] for n in circles]
    square_sizes = [node_sizes[list(G.nodes()).index(n)] for n in squares]

    # Draw circles (tasks)
    nx.draw_networkx_nodes(
        G,
        pos,
        nodelist=circles,
        node_color=circle_colors,
        node_size=circle_sizes,
        node_shape="o",
        edgecolors="black",
    )

    # Draw squares (buffers)
    nx.draw_networkx_nodes(
        G,
        pos,
        nodelist=squares,
        node_color=square_colors,
        node_size=square_sizes,
        node_shape="s",
        edgecolors="black",
    )

    # Draw edges
    nx.draw_networkx_edges(
        G,
        pos,
        edge_color=edge_colors,
        width=edge_widths,
        arrowsize=15,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.1",
    )

    # Create node labels
    labels = {}
    for node in G.nodes():
        if node in buffers:
            # Label for buffer
            buffer = buffers[node]
            labels[node] = f"{buffer.name}\n({buffer.size}d)"
        elif node in tasks:
            # Label for task
            task = tasks[node]
            status_info = ""
            if task.status == "completed":
                status_info = " [✓]"
            elif task.status == "in_progress":
                progress = task.get_progress_percentage()
                status_info = f" [{progress:.0f}%]"

            # Include resources if available
            resource_info = ""
            if hasattr(task, "resources") and task.resources:
                if isinstance(task.resources, list) and len(task.resources) > 0:
                    resource_info = f"\n[{task.resources[0]}]"
                elif isinstance(task.resources, str):
                    resource_info = f"\n[{task.resources}]"

            labels[node] = f"{task.id}: {task.name}{status_info}{resource_info}"
        else:
            labels[node] = str(node)

    # Draw node labels with background for better readability
    label_pos = {
        k: (v[0], v[1] - 0.02) for k, v in pos.items()
    }  # Slightly adjust position for better alignment

    bbox_props = dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8)
    for node, label in labels.items():
        plt.text(
            label_pos[node][0],
            label_pos[node][1],
            label,
            horizontalalignment="center",
            bbox=bbox_props,
            fontsize=9,
        )

    # Create legend
    legend_elements = [
        Patch(facecolor="red", edgecolor="black", label="Critical Chain Task"),
        Patch(facecolor="orange", edgecolor="black", label="Feeding Chain Task"),
        Patch(facecolor="skyblue", edgecolor="black", label="Regular Task"),
        Line2D([0], [0], color="red", lw=2.5, label="Critical Chain"),
        Line2D([0], [0], color="orange", lw=2, label="Feeding Chain"),
        Patch(facecolor="green", edgecolor="black", label="Project Buffer"),
        Patch(facecolor="yellow", edgecolor="black", label="Feeding Buffer"),
    ]

    plt.legend(handles=legend_elements, loc="best", fontsize=10)

    # Set title and remove axis
    plt.title("Critical Chain Project Network Diagram", fontsize=14)
    plt.axis("off")

    # Make layout tight
    plt.tight_layout()

    # Save if filename provided
    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")

    # Show if requested
    if show:
        plt.show()

    return plt.gcf()
