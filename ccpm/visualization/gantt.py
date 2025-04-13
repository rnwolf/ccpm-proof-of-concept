import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch
from datetime import datetime, timedelta


def create_gantt_chart(scheduler, filename=None):
    """
    Create a Gantt chart visualization of the CCPM schedule.

    Args:
        scheduler: The CCPMScheduler instance
        filename: Optional filename to save the chart

    Returns:
        The matplotlib figure
    """
    # Get data from scheduler
    tasks = scheduler.tasks
    buffers = scheduler.buffers
    critical_chain = scheduler.critical_chain
    chains = scheduler.chains
    status_date = getattr(scheduler, "execution_date", datetime.now())

    # Calculate the project duration for x-axis sizing
    all_end_dates = []

    # Include task end dates
    for task in tasks.values():
        if hasattr(task, "end_date"):
            all_end_dates.append(task.end_date)
        if hasattr(task, "actual_end_date") and task.actual_end_date:
            all_end_dates.append(task.actual_end_date)

    # Include buffer end dates
    for buffer in buffers.values():
        if hasattr(buffer, "end_date"):
            all_end_dates.append(buffer.end_date)

    # Include status date
    all_end_dates.append(status_date)

    # Get project start date
    start_date = scheduler.start_date

    # Find the latest end date
    last_end_date = max(all_end_dates) if all_end_dates else start_date

    # Create figure with GridSpec to have two subplots
    fig = plt.figure(figsize=(14, 8))
    gs = gridspec.GridSpec(1, 1)  # Just one subplot for now

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

        # Determine color based on chain membership
        if critical_chain and task.id in critical_chain.tasks:
            color = "red"
        elif task.chain_id and task.chain_id != "critical":
            color = "orange"
        else:
            color = "blue"

        # Handle different task statuses
        if task.status == "completed":
            # Completed task - solid green
            ax_gantt.barh(i, duration, left=start_day, color="green", alpha=0.8)
        elif task.status == "in_progress":
            # In-progress task - part green, part colored with pattern
            if hasattr(task, "progress_history") and task.progress_history:
                latest_update = task.progress_history[-1]
                progress_pct = latest_update.get("progress_percentage", 0)

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
                # No progress history, just show as in progress
                ax_gantt.barh(i, duration, left=start_day, color=color, alpha=0.6)
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
        if not hasattr(buffer, "start_date") or not hasattr(buffer, "end_date"):
            continue

        start_date = buffer.start_date
        end_date = buffer.end_date

        # Convert to days from project start
        project_start = scheduler.start_date
        start_day = (start_date - project_start).days
        buffer_size = (end_date - start_date).days

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
        if hasattr(buffer, "start_date") and hasattr(buffer, "end_date"):
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

    return fig
