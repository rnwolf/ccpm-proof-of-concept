import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch
from datetime import datetime, timedelta


def create_gantt_chart(scheduler, filename=None, show=True):
    """
    Create a Gantt chart visualization of the CCPM schedule.

    Args:
        scheduler: The CCPMScheduler instance
        filename: Optional filename to save the chart
        show: Whether to display the chart (default: True)

    Returns:
        The matplotlib figure
    """
    # Get data from scheduler
    tasks = scheduler.tasks
    buffers = scheduler.buffers if hasattr(scheduler, "buffers") else {}
    critical_chain = scheduler.critical_chain
    chains = scheduler.chains if hasattr(scheduler, "chains") else {}
    status_date = getattr(scheduler, "execution_date", datetime.now())

    # Calculate the project duration for x-axis sizing
    all_end_dates = []

    # Include task end dates
    for task in tasks.values():
        end_date = task.get_end_date()
        if end_date:
            all_end_dates.append(end_date)

    # Include buffer end dates
    for buffer in buffers.values():
        end_date = buffer.get_effective_end_date()
        if end_date:
            all_end_dates.append(end_date)

    # Include status date
    all_end_dates.append(status_date)

    # Get project start date
    start_date = scheduler.start_date

    # Find the latest end date
    last_end_date = max(all_end_dates) if all_end_dates else start_date

    # Create figure with GridSpec
    fig = plt.figure(figsize=(14, 8))
    gs = gridspec.GridSpec(1, 1)

    # Gantt chart subplot
    ax_gantt = fig.add_subplot(gs[0])

    # Sort tasks by start date
    sorted_tasks = sorted(
        tasks.values(),
        key=lambda x: x.get_start_date() if x.get_start_date() else datetime.max,
    )

    # Plot each task
    for i, task in enumerate(sorted_tasks):
        # Get task dates
        start_date = task.get_start_date()
        end_date = task.get_end_date()

        if not start_date or not end_date:
            continue

        # Convert to days from project start
        project_start = scheduler.start_date
        start_day = (start_date - project_start).days
        duration = (end_date - start_date).days
        if duration <= 0:
            duration = 1  # Ensure minimum 1-day duration for visibility

        # Determine color based on chain membership
        if critical_chain and task.id in critical_chain.tasks:
            color = "red"
        elif (
            task.chain_id
            and task.chain_id in chains
            and chains[task.chain_id].type == "feeding"
        ):
            color = "orange"
        else:
            color = "blue"

        # Handle different task statuses
        if task.status == "completed":
            # Completed task - solid green
            ax_gantt.barh(i, duration, left=start_day, color="green", alpha=0.8)
        elif task.status == "in_progress":
            # In-progress task - part green, part colored with pattern
            progress_pct = task.get_progress_percentage()

            # Calculate completed portion
            completed_duration = duration * (progress_pct / 100)
            remaining_duration = duration - completed_duration

            # Draw completed portion
            if completed_duration > 0:
                ax_gantt.barh(
                    i, completed_duration, left=start_day, color="green", alpha=0.8
                )

                # Add text for completion percentage
                ax_gantt.text(
                    start_day + completed_duration / 2,
                    i,
                    f"{progress_pct:.0f}%",
                    ha="center",
                    va="center",
                    color="black",
                    fontweight="bold",
                    fontsize=8,
                )

            # Draw remaining portion
            if remaining_duration > 0:
                ax_gantt.barh(
                    i,
                    remaining_duration,
                    left=start_day + completed_duration,
                    color=color,
                    alpha=0.6,
                    hatch="///",
                )

                # Add text for remaining percentage
                ax_gantt.text(
                    start_day + completed_duration + remaining_duration / 2,
                    i,
                    f"{100 - progress_pct:.0f}%",
                    ha="center",
                    va="center",
                    color="black",
                    fontweight="bold",
                    fontsize=8,
                )
        else:
            # Not started - regular colored bar
            ax_gantt.barh(i, duration, left=start_day, color=color, alpha=0.6)

        # Format the resource list
        if hasattr(task, "resources"):
            if isinstance(task.resources, str):
                resource_str = task.resources
            elif isinstance(task.resources, list):
                resource_str = ", ".join(task.resources)
            else:
                resource_str = ""
        else:
            resource_str = ""

        # Add status indicator
        status_str = ""
        if task.status == "completed":
            status_str = " [DONE]"
        elif task.status == "in_progress":
            status_str = " [IN PROGRESS]"

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
    for buffer_id, buffer in buffers.items():
        # Skip buffers without dates
        start_date = buffer.get_effective_start_date()
        end_date = buffer.get_effective_end_date()
        if not start_date or not end_date:
            continue

        # Convert to days from project start
        project_start = scheduler.start_date
        start_day = (start_date - project_start).days
        buffer_size = (end_date - start_date).days
        if buffer_size <= 0:
            buffer_size = 1  # Ensure minimum 1-day buffer for visibility

        # Determine color based on buffer type
        color = "green" if buffer.buffer_type == "project" else "yellow"

        # Calculate consumption
        consumption_pct = buffer.get_consumption_percentage()
        consumed_size = buffer_size * (consumption_pct / 100)
        remaining_size = buffer_size - consumed_size

        # Plot consumed portion
        if consumed_size > 0:
            ax_gantt.barh(
                len(sorted_tasks) + buffer_count,
                consumed_size,
                left=start_day,
                color="red",
                alpha=0.6,
                hatch="///",
            )

        # Plot remaining portion
        if remaining_size > 0:
            ax_gantt.barh(
                len(sorted_tasks) + buffer_count,
                remaining_size,
                left=start_day + consumed_size,
                color=color,
                alpha=0.6,
            )

        # Add buffer label
        consumed_str = f" (Used: {consumption_pct:.0f}%)" if consumption_pct > 0 else ""
        ax_gantt.text(
            start_day + buffer_size / 2,
            len(sorted_tasks) + buffer_count,
            f"{buffer.name}{consumed_str}",
            ha="center",
            va="center",
            color="black",
        )

        buffer_count += 1

    # Set up the axes
    row_count = len(sorted_tasks) + buffer_count
    ax_gantt.set_yticks(range(row_count))

    # Create y-tick labels
    yticklabels = []
    for task in sorted_tasks:
        yticklabels.append(task.name)

    for buffer_id, buffer in buffers.items():
        if buffer.get_effective_start_date() and buffer.get_effective_end_date():
            yticklabels.append(buffer.name)

    # Set y-tick labels
    ax_gantt.set_yticklabels(yticklabels)

    # Add title with status date
    ax_gantt.set_title(
        f"CCPM Project Schedule (Status as of {status_date.strftime('%Y-%m-%d')})"
    )

    # Add x-axis label
    ax_gantt.set_xlabel("Days from project start")

    # Add grid lines
    ax_gantt.grid(axis="x", alpha=0.3)

    # Add legend
    legend_elements = [
        Patch(facecolor="red", alpha=0.6, label="Critical Chain Task"),
        Patch(facecolor="orange", alpha=0.6, label="Feeding Chain Task"),
        Patch(facecolor="blue", alpha=0.6, label="Regular Task"),
        Patch(facecolor="green", alpha=0.8, label="Completed Work"),
        Patch(facecolor="red", alpha=0.6, hatch="///", label="Consumed Buffer"),
        Patch(facecolor="yellow", alpha=0.6, label="Feeding Buffer"),
        Patch(facecolor="green", alpha=0.6, label="Project Buffer"),
    ]
    ax_gantt.legend(handles=legend_elements, loc="upper right", ncol=2)

    # Add vertical line for status date
    status_day = (status_date - scheduler.start_date).days
    ax_gantt.axvline(x=status_day, color="green", linestyle="--", linewidth=2)

    # Adjust layout
    plt.tight_layout()

    # Save if filename provided
    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")

    # Show if requested
    if show:
        plt.show()

    return fig


def create_resource_gantt(scheduler, filename=None, show=True):
    """
    Create a Gantt chart showing resource allocation over time.

    Args:
        scheduler: The CCPMScheduler instance
        filename: Optional filename to save the chart
        show: Whether to display the chart (default: True)

    Returns:
        The matplotlib figure
    """
    # Get data from scheduler
    tasks = scheduler.tasks
    resources = scheduler.resources
    status_date = getattr(scheduler, "execution_date", datetime.now())

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))

    # Get unique resources from all tasks
    all_resources = set()
    for task in tasks.values():
        if hasattr(task, "resources"):
            if isinstance(task.resources, str):
                all_resources.add(task.resources)
            elif isinstance(task.resources, list):
                all_resources.update(task.resources)

    # Convert to sorted list
    all_resources = sorted(list(all_resources))

    # Create a mapping of resource to row
    resource_to_row = {resource: i for i, resource in enumerate(all_resources)}

    # Plot each task on its resource row
    for task in tasks.values():
        # Get task dates
        start_date = task.get_start_date()
        end_date = task.get_end_date()

        if not start_date or not end_date:
            continue

        # Convert to days from project start
        project_start = scheduler.start_date
        start_day = (start_date - project_start).days
        duration = (end_date - start_date).days
        if duration <= 0:
            duration = 1  # Ensure minimum 1-day duration for visibility

        # Determine color based on task status
        if task.status == "completed":
            color = "green"
            alpha = 0.8
            hatch = None
        elif task.status == "in_progress":
            color = "orange"
            alpha = 0.6
            hatch = "///"
        else:
            color = "blue"
            alpha = 0.6
            hatch = None

        # For each resource, add a bar
        task_resources = []
        if hasattr(task, "resources"):
            if isinstance(task.resources, str):
                task_resources = [task.resources]
            elif isinstance(task.resources, list):
                task_resources = task.resources

        for resource in task_resources:
            if resource in resource_to_row:
                row = resource_to_row[resource]
                bar = ax.barh(
                    row,
                    duration,
                    left=start_day,
                    color=color,
                    alpha=alpha,
                    hatch=hatch,
                    edgecolor="black",
                )

                # Add task label
                ax.text(
                    start_day + duration / 2,
                    row,
                    f"{task.id}: {task.name}",
                    ha="center",
                    va="center",
                    color="black",
                )

    # Set up the axes
    ax.set_yticks(range(len(all_resources)))
    ax.set_yticklabels(all_resources)

    # Add title
    ax.set_title(
        f"Resource Allocation (Status as of {status_date.strftime('%Y-%m-%d')})"
    )

    # Add x-axis label
    ax.set_xlabel("Days from project start")

    # Add grid lines
    ax.grid(axis="x", alpha=0.3)

    # Add vertical line for status date
    status_day = (status_date - scheduler.start_date).days
    ax.axvline(x=status_day, color="green", linestyle="--", linewidth=2)

    # Add legend
    legend_elements = [
        Patch(facecolor="green", alpha=0.8, label="Completed Task"),
        Patch(facecolor="orange", alpha=0.6, hatch="///", label="In Progress Task"),
        Patch(facecolor="blue", alpha=0.6, label="Planned Task"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")

    # Adjust layout
    plt.tight_layout()

    # Save if filename provided
    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")

    # Show if requested
    if show:
        plt.show()

    return fig


def create_buffer_chart(scheduler, filename=None, show=True):
    """
    Create a chart showing buffer consumption over time.

    Args:
        scheduler: The CCPMScheduler instance
        filename: Optional filename to save the chart
        show: Whether to display the chart (default: True)

    Returns:
        The matplotlib figure
    """
    # Get buffer data from scheduler
    buffers = scheduler.buffers if hasattr(scheduler, "buffers") else {}

    if not buffers:
        print("No buffers available to visualize")
        return None

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each buffer
    for i, (buffer_id, buffer) in enumerate(buffers.items()):
        consumption_pct = buffer.get_consumption_percentage()

        # Determine color based on consumption
        if consumption_pct < 33:
            color = "green"
        elif consumption_pct < 67:
            color = "yellow"
        else:
            color = "red"

        # Create bar
        ax.barh(i, consumption_pct, color=color, alpha=0.7, edgecolor="black")

        # Add percentage text
        ax.text(
            consumption_pct + 2,  # Offset for visibility
            i,
            f"{consumption_pct:.1f}%",
            va="center",
        )

        # Add warning lines
        ax.axvline(x=33, color="yellow", linestyle="--", alpha=0.5)
        ax.axvline(x=67, color="red", linestyle="--", alpha=0.5)

    # Set up axes
    ax.set_yticks(range(len(buffers)))
    ax.set_yticklabels(
        [f"{buffer.name} ({buffer.buffer_type})" for buffer in buffers.values()]
    )
    ax.set_xlim(0, 105)  # 0-100% with a little extra space

    # Add labels and title
    ax.set_title("Buffer Consumption")
    ax.set_xlabel("Consumption Percentage")

    # Add legend for zones
    legend_elements = [
        Patch(facecolor="green", alpha=0.7, label="Safe Zone (0-33%)"),
        Patch(facecolor="yellow", alpha=0.7, label="Warning Zone (33-67%)"),
        Patch(facecolor="red", alpha=0.7, label="Critical Zone (67-100%)"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")

    # Adjust layout
    plt.tight_layout()

    # Save if filename provided
    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")

    # Show if requested
    if show:
        plt.show()

    return fig
