import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import matplotlib.dates as mdates


def create_fever_chart(scheduler, filename=None, show=True, project_name=None):
    """
    Generate and display a CCPM fever chart showing buffer consumption over time relative to chain completion.

    Args:
        scheduler: The CCPMScheduler instance
        filename: Optional filename to save the chart
        show: Whether to display the chart (default: True)
        project_name: Optional project name for the chart title

    Returns:
        The matplotlib figure
    """
    if not hasattr(scheduler, "buffers") or not scheduler.buffers:
        print("No buffers found. Please run the scheduler first.")
        return None

    if not hasattr(scheduler, "chains") or not scheduler.chains:
        print("No chains found. Please run the scheduler first.")
        return None

    # Get current execution date
    status_date = getattr(scheduler, "execution_date", datetime.now())
    if status_date is None:
        status_date = datetime.now()

    # Create the figure
    fig, ax = plt.subplots(figsize=(10, 8))

    # Define the zone boundaries
    # X-axis points (chain completion %)
    x_vals = [0, 100]

    # Green-Yellow boundary (y = 10% at x = 0, y = 70% at x = 100)
    green_yellow_y = [10, 70]

    # Yellow-Red boundary (y = 30% at x = 0, y = 90% at x = 100)
    yellow_red_y = [30, 90]

    # Fill the zones
    # Red zone (top)
    ax.fill_between(x_vals, yellow_red_y, [100, 100], color="red", alpha=0.2)

    # Yellow zone (middle)
    ax.fill_between(x_vals, green_yellow_y, yellow_red_y, color="yellow", alpha=0.2)

    # Green zone (bottom)
    ax.fill_between(x_vals, [0, 0], green_yellow_y, color="green", alpha=0.2)

    # Draw the OK line (diagonal)
    ax.plot(x_vals, x_vals, "k--", alpha=0.5, label="Ideal Path")

    # Prepare to collect all chain data for legend
    legend_elements = []

    # Track maximum buffer consumption for axis scaling
    max_buffer_consumption = 0

    # Process each chain and its buffer
    for chain_id, chain in scheduler.chains.items():
        # Skip chains without buffers
        if not hasattr(chain, "buffer") or chain.buffer is None:
            continue

        buffer = chain.buffer

        # Skip buffers without consumption history
        if not hasattr(buffer, "consumption_history") or not buffer.consumption_history:
            continue

        # Get chain type for base color
        is_critical = chain.type == "critical"

        # Base colors by chain type
        base_color = "red" if is_critical else "orange"

        # Create more variety within chain types
        # Use different markers, line styles, and color variations for chains of the same type

        # Define arrays of markers, linestyles, and color variants
        markers = ["o", "s", "^", "D", "v", "<", ">", "p", "*", "h", "H", "X"]
        linestyles = ["-", "--", "-.", ":"]

        # Generate a unique identifier for this chain based on its ID
        # This ensures consistent styling each time the chart is generated
        chain_hash = hash(chain_id) % 1000

        # Select marker and linestyle based on the chain's hash
        marker_idx = chain_hash % len(markers)
        linestyle_idx = (chain_hash // len(markers)) % len(linestyles)

        marker = markers[marker_idx]
        linestyle = linestyles[linestyle_idx]

        # Create slight color variations for chains of the same type
        # For critical chains, use variations of red
        # For feeding chains, use variations of orange
        if is_critical:
            # Variations of red
            color_options = [
                "crimson",
                "darkred",
                "firebrick",
                "indianred",
                "red",
                "tomato",
            ]
            color_idx = chain_hash % len(color_options)
            color = color_options[color_idx]
        else:
            # Variations of orange/yellow
            color_options = [
                "orange",
                "darkorange",
                "coral",
                "goldenrod",
                "sandybrown",
                "chocolate",
            ]
            color_idx = chain_hash % len(color_options)
            color = color_options[color_idx]

        # Get chain name for legend
        chain_name = f"{chain.name} ({buffer.name})"

        # Extract history points
        dates = []
        consumption_pcts = []
        completion_pcts = []

        # Ensure history is sorted by date
        sorted_history = sorted(buffer.consumption_history, key=lambda x: x["date"])

        for entry in sorted_history:
            # Skip entries without proper data
            if "date" not in entry:
                continue

            # Get date
            dates.append(entry["date"])

            # Calculate buffer consumption
            if "consumption_percentage" in entry:
                consumption_pct = entry["consumption_percentage"]
            elif "remaining" in entry and hasattr(buffer, "size") and buffer.size > 0:
                original_size = buffer.size
                remaining = entry["remaining"]
                consumption_pct = ((original_size - remaining) / original_size) * 100
            else:
                # Skip if we can't calculate consumption
                continue

            consumption_pcts.append(consumption_pct)

            # Track max consumption for y-axis scaling
            max_buffer_consumption = max(max_buffer_consumption, consumption_pct)

            # Get chain completion percentage
            # First check if it's stored in the history entry
            if "chain_completion" in entry:
                completion_pct = entry["chain_completion"]
            else:
                # If not in history, use current chain completion % (approximation)
                # For historical points this is not ideal but better than nothing
                completion_pct = chain.completion_percentage

            completion_pcts.append(completion_pct)

        # Plot data points if we have any
        if dates and consumption_pcts and completion_pcts:
            # Plot the line connecting points
            ax.plot(
                completion_pcts,
                consumption_pcts,
                color=color,
                linestyle=linestyle,
                linewidth=2,
                marker=marker,
                markersize=8,
                alpha=0.7,
                label=chain_name,
            )

            # Add date labels to points
            for i, (x, y, date) in enumerate(
                zip(completion_pcts, consumption_pcts, dates)
            ):
                # Only label every Nth point to avoid clutter, and the last point
                if i == len(dates) - 1 or i % 3 == 0:
                    date_str = date.strftime("%m/%d")
                    ax.annotate(
                        date_str,
                        (x, y),
                        xytext=(5, 5),
                        textcoords="offset points",
                        fontsize=8,
                        alpha=0.8,
                        bbox=dict(
                            boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.7
                        ),
                    )

            # Add to legend with a custom Line2D element to ensure proper marker and color display
            legend_elements.append(
                Line2D(
                    [0],
                    [0],
                    color=color,
                    marker=marker,
                    linestyle=linestyle,
                    markersize=8,
                    label=chain_name,
                )
            )

            # For the final point, add a larger marker with current status
            last_x, last_y = completion_pcts[-1], consumption_pcts[-1]

            # Determine status zone
            if (
                last_y
                <= green_yellow_y[0]
                + (green_yellow_y[1] - green_yellow_y[0]) * last_x / 100
            ):
                status_color = "green"
                status_text = "Safe"
            elif (
                last_y
                <= yellow_red_y[0] + (yellow_red_y[1] - yellow_red_y[0]) * last_x / 100
            ):
                status_color = "yellow"
                status_text = "Warning"
            else:
                status_color = "red"
                status_text = "Critical"

            # Add current status point with increased visibility
            ax.scatter(
                [last_x],
                [last_y],
                s=100,
                color=status_color,
                edgecolor="black",
                zorder=10,
                marker=marker,
            )

            # Add status text (offset slightly based on marker index to avoid overlap)
            # Calculate offset based on marker index
            offset_x = 10 + (marker_idx % 3) * 5
            offset_y = 10 + (marker_idx % 3) * 5

            ax.annotate(
                f"{chain.name}\n{status_text}\n{last_x:.1f}%, {last_y:.1f}%",
                (last_x, last_y),
                xytext=(offset_x, offset_y),
                textcoords="offset points",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, alpha=0.8),
            )

    # Add zone labels
    ax.text(5, 5, "SAFE", fontsize=12, color="green", weight="bold")
    ax.text(5, 20, "WARNING", fontsize=12, color="goldenrod", weight="bold")
    ax.text(5, 60, "CRITICAL", fontsize=12, color="red", weight="bold")

    # Add legend for chain status
    ax.legend(handles=legend_elements, loc="upper left", fontsize=10)

    # Set axis labels
    ax.set_xlabel("Chain Completion (%)", fontsize=12)
    ax.set_ylabel("Buffer Consumption (%)", fontsize=12)

    # Set title
    if project_name:
        title = f"Fever Chart for {project_name} ({status_date.strftime('%Y-%m-%d')})"
    else:
        title = f"CCPM Fever Chart ({status_date.strftime('%Y-%m-%d')})"
    ax.set_title(title, fontsize=14, weight="bold")

    # Set axis limits
    ax.set_xlim(0, 105)  # Give a little extra space

    # Determine y-axis limit based on max consumption
    y_limit = max(100, max_buffer_consumption * 1.1)  # 10% margin above max
    ax.set_ylim(0, y_limit)

    # Add grid
    ax.grid(True, linestyle="--", alpha=0.7)

    # Adjust layout
    plt.tight_layout()

    # Save if filename provided
    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")

    # Show if requested
    if show:
        plt.show()

    return fig


def generate_fever_chart_data(scheduler):
    """
    Generate data for a fever chart without creating the visualization.
    Useful for custom plotting or data analysis.

    Args:
        scheduler: The CCPMScheduler instance

    Returns:
        dict: Dictionary with fever chart data for each chain
    """
    result = {}

    # Process each chain and its buffer
    for chain_id, chain in scheduler.chains.items():
        # Skip chains without buffers
        if not hasattr(chain, "buffer") or chain.buffer is None:
            continue

        buffer = chain.buffer

        # Skip buffers without consumption history
        if not hasattr(buffer, "consumption_history") or not buffer.consumption_history:
            continue

        # Initialize chain data
        chain_data = {
            "name": chain.name,
            "buffer_name": buffer.name,
            "type": chain.type,
            "dates": [],
            "buffer_consumption": [],
            "chain_completion": [],
            "status": [],
        }

        # Ensure history is sorted by date
        sorted_history = sorted(buffer.consumption_history, key=lambda x: x["date"])

        for entry in sorted_history:
            # Skip entries without proper data
            if "date" not in entry:
                continue

            # Get date
            chain_data["dates"].append(entry["date"])

            # Calculate buffer consumption
            if "consumption_percentage" in entry:
                consumption_pct = entry["consumption_percentage"]
            elif "remaining" in entry and hasattr(buffer, "size") and buffer.size > 0:
                original_size = buffer.size
                remaining = entry["remaining"]
                consumption_pct = ((original_size - remaining) / original_size) * 100
            else:
                # Skip if we can't calculate consumption
                continue

            chain_data["buffer_consumption"].append(consumption_pct)

            # Get chain completion percentage
            # First check if it's stored in the history entry
            if "chain_completion" in entry:
                completion_pct = entry["chain_completion"]
            else:
                # If not in history, use current chain completion % (approximation)
                completion_pct = chain.completion_percentage

            chain_data["chain_completion"].append(completion_pct)

            # Determine status zone
            if consumption_pct < 33:
                status = "green"
            elif consumption_pct < 67:
                status = "yellow"
            else:
                status = "red"

            chain_data["status"].append(status)

        # Add to result if we have data
        if chain_data["dates"]:
            result[chain_id] = chain_data

    return result


def create_multi_fever_chart(data_dict, filename=None, show=True, title=None):
    """
    Create a fever chart from pre-generated data for multiple projects or snapshots.

    Args:
        data_dict: Dictionary of fever chart data (from generate_fever_chart_data)
        filename: Optional filename to save the chart
        show: Whether to display the chart (default: True)
        title: Optional chart title

    Returns:
        The matplotlib figure
    """
    # Create the figure
    fig, ax = plt.subplots(figsize=(10, 8))

    # Define the zone boundaries
    # X-axis points (chain completion %)
    x_vals = [0, 100]

    # Green-Yellow boundary (y = 10% at x = 0, y = 70% at x = 100)
    green_yellow_y = [10, 70]

    # Yellow-Red boundary (y = 30% at x = 0, y = 90% at x = 100)
    yellow_red_y = [30, 90]

    # Fill the zones
    # Red zone (top)
    ax.fill_between(x_vals, yellow_red_y, [100, 100], color="red", alpha=0.2)

    # Yellow zone (middle)
    ax.fill_between(x_vals, green_yellow_y, yellow_red_y, color="yellow", alpha=0.2)

    # Green zone (bottom)
    ax.fill_between(x_vals, [0, 0], green_yellow_y, color="green", alpha=0.2)

    # Draw the OK line (diagonal)
    ax.plot(x_vals, x_vals, "k--", alpha=0.5, label="Ideal Path")

    # Prepare to collect all chain data for legend
    legend_elements = []

    # Track maximum buffer consumption for axis scaling
    max_buffer_consumption = 0

    # Process each set of data
    for project_key, project_data in data_dict.items():
        # Loop through each chain in this project
        for chain_id, chain_data in project_data.items():
            # Skip if no data
            if not chain_data["dates"]:
                continue

            # Choose color and marker based on chain type
            is_critical = chain_data["type"] == "critical"

            # Base colors by chain type
            base_color = "red" if is_critical else "orange"

            # Generate a unique identifier for this chain
            chain_hash = hash(f"{project_key}_{chain_id}") % 1000

            # Define arrays of markers, linestyles, and color variants
            markers = ["o", "s", "^", "D", "v", "<", ">", "p", "*", "h", "H", "X"]
            linestyles = ["-", "--", "-.", ":"]

            # Select marker and linestyle based on the chain's hash
            marker_idx = chain_hash % len(markers)
            linestyle_idx = (chain_hash // len(markers)) % len(linestyles)

            marker = markers[marker_idx]
            linestyle = linestyles[linestyle_idx]

            # Create slight color variations
            if is_critical:
                # Variations of red
                color_options = [
                    "crimson",
                    "darkred",
                    "firebrick",
                    "indianred",
                    "red",
                    "tomato",
                ]
                color_idx = chain_hash % len(color_options)
                color = color_options[color_idx]
            else:
                # Variations of orange/yellow
                color_options = [
                    "orange",
                    "darkorange",
                    "coral",
                    "goldenrod",
                    "sandybrown",
                    "chocolate",
                ]
                color_idx = chain_hash % len(color_options)
                color = color_options[color_idx]

            # Get chain name for legend
            chain_name = f"{chain_data['name']} ({chain_data['buffer_name']})"
            if len(data_dict) > 1:
                # Add project key if comparing multiple projects
                chain_name = f"{project_key}: {chain_name}"

            # Get data points
            completion_pcts = chain_data["chain_completion"]
            consumption_pcts = chain_data["buffer_consumption"]
            dates = chain_data["dates"]

            # Update max consumption
            max_buffer_consumption = max(
                max_buffer_consumption, max(consumption_pcts, default=0)
            )

            # Plot the line connecting points
            ax.plot(
                completion_pcts,
                consumption_pcts,
                color=color,
                linestyle=linestyle,
                linewidth=2,
                marker=marker,
                markersize=8,
                alpha=0.7,
            )

            # Add date labels to points
            for i, (x, y, date) in enumerate(
                zip(completion_pcts, consumption_pcts, dates)
            ):
                # Only label every Nth point to avoid clutter, and the last point
                if i == len(dates) - 1 or i % 3 == 0:
                    date_str = date.strftime("%m/%d")
                    ax.annotate(
                        date_str,
                        (x, y),
                        xytext=(5, 5),
                        textcoords="offset points",
                        fontsize=8,
                        alpha=0.8,
                        bbox=dict(
                            boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.7
                        ),
                    )

            # Add to legend with custom Line2D object
            legend_elements.append(
                Line2D(
                    [0],
                    [0],
                    color=color,
                    marker=marker,
                    linestyle=linestyle,
                    markersize=8,
                    label=chain_name,
                )
            )

            # Add a marker for the final point with appropriate styling
            last_x, last_y = completion_pcts[-1], consumption_pcts[-1]

            # For the last point, add a larger marker to highlight current status
            # Determine which zone it's in
            if (
                last_y
                <= green_yellow_y[0]
                + (green_yellow_y[1] - green_yellow_y[0]) * last_x / 100
            ):
                status_color = "green"
            elif (
                last_y
                <= yellow_red_y[0] + (yellow_red_y[1] - yellow_red_y[0]) * last_x / 100
            ):
                status_color = "yellow"
            else:
                status_color = "red"

            ax.scatter(
                [last_x],
                [last_y],
                s=100,
                color=status_color,
                edgecolor="black",
                zorder=10,
                marker=marker,
            )

    # Add zone labels
    ax.text(5, 5, "SAFE", fontsize=12, color="green", weight="bold")
    ax.text(5, 20, "WARNING", fontsize=12, color="goldenrod", weight="bold")
    ax.text(5, 60, "CRITICAL", fontsize=12, color="red", weight="bold")

    # Add legend
    ax.legend(handles=legend_elements, loc="upper left", fontsize=10)

    # Set axis labels
    ax.set_xlabel("Chain Completion (%)", fontsize=12)
    ax.set_ylabel("Buffer Consumption (%)", fontsize=12)

    # Set title
    if title:
        ax.set_title(title, fontsize=14, weight="bold")
    else:
        ax.set_title("CCPM Fever Chart", fontsize=14, weight="bold")

    # Set axis limits
    ax.set_xlim(0, 105)  # Give a little extra space

    # Determine y-axis limit based on max consumption
    y_limit = max(100, max_buffer_consumption * 1.1)  # 10% margin above max
    ax.set_ylim(0, y_limit)

    # Add grid
    ax.grid(True, linestyle="--", alpha=0.7)

    # Adjust layout
    plt.tight_layout()

    # Save if filename provided
    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")

    # Show if requested
    if show:
        plt.show()

    return fig
