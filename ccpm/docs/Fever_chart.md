# CCPM Fever Chart Implementation

## Overview

The CCPM Fever Chart is a critical visualization tool for monitoring project health in the Critical Chain Project Management methodology. This document explains the implementation details and usage of the fever chart module that I've designed for the CCPM package.

## Key Components

The implementation consists of three main functions:

1. **create_fever_chart()** - The primary function that creates a visualization of buffer consumption vs. chain completion.

2. **generate_fever_chart_data()** - A utility function that extracts data from the scheduler without generating a visualization, useful for custom analysis.

3. **create_multi_fever_chart()** - A function that allows comparison of multiple projects or scenarios on a single chart.

## Technical Details

### 1. Fever Chart Structure

The fever chart visualizes:

- **X-axis**: Chain completion percentage (0-100%)
- **Y-axis**: Buffer consumption percentage (0-100%)
- **Three zones**:
  - Green zone: Safe zone (0-10% consumption at 0% completion, 0-70% at 100% completion)
  - Yellow zone: Warning zone (10-30% consumption at 0% completion, 70-90% at 100% completion)
  - Red zone: Critical zone (above the yellow zone)

### 2. Data Model

The implementation captures several key data points for each chain/buffer pair:

- **Dates**: When status updates occurred
- **Buffer consumption percentage**: How much of the buffer has been used
- **Chain completion percentage**: How much of the chain has been completed
- **Status**: Color-coded status (green, yellow, red)

### 3. Algorithm for Zone Determination

The algorithm for determining which zone a data point falls into:

```python
# For a point (x, y) where x is completion % and y is buffer consumption %
green_yellow_lower = 10 + (70 - 10) * (x / 100)  # Linear interpolation from (0,10) to (100,70)
yellow_red_lower = 30 + (90 - 30) * (x / 100)    # Linear interpolation from (0,30) to (100,90)

if y < green_yellow_lower:
    status = "green"  # Safe zone
elif y < yellow_red_lower:
    status = "yellow"  # Warning zone
else:
    status = "red"     # Critical zone
```

### 4. Buffer Consumption Calculation

Buffer consumption is calculated as:

```
consumption_percentage = ((original_size - remaining) / original_size) * 100
```

Where:
- `original_size` is the initial buffer size
- `remaining` is the current remaining buffer size

## Usage Examples

### Basic Usage

```python
from ccpm.visualization.fever_chart import create_fever_chart

# Assuming you have a scheduler object with project data
create_fever_chart(scheduler, filename="project_fever_chart.png", project_name="Project Alpha")
```

This generates a fever chart showing all chains in the project with their buffer consumption and chain completion status.

### Generating Data for Custom Analysis

```python
from ccpm.visualization.fever_chart import generate_fever_chart_data

# Get the raw data for further analysis
fever_data = generate_fever_chart_data(scheduler)

# Example: Find which chains are in the critical zone
critical_chains = []
for chain_id, data in fever_data.items():
    if data['status'][-1] == 'red':
        critical_chains.append(chain_id)

print(f"Chains in critical status: {critical_chains}")
```

### Comparing Multiple Projects

```python
from ccpm.visualization.fever_chart import generate_fever_chart_data, create_multi_fever_chart

# Generate data for multiple projects
data1 = generate_fever_chart_data(scheduler1)
data2 = generate_fever_chart_data(scheduler2)

# Create a comparison chart
combined_data = {"Project A": data1, "Project B": data2}
create_multi_fever_chart(
    combined_data,
    filename="projects_comparison.png",
    title="Performance Comparison: Project A vs Project B"
)
```

## Integration with CCPM System

The fever chart functionality is designed to integrate with the existing CCPM system, particularly:

1. It requires the `Chain` objects to have:
   - A `completion_percentage` property
   - A reference to a `buffer` object

2. It expects the `Buffer` objects to have:
   - A `consumption_history` list containing records of buffer consumption
   - Each record should have `date`, `remaining`, and ideally `consumption_percentage` fields

## Display Customizations

The fever chart visualization includes several usability features:

1. **Date annotations**: Each data point shows its date, with some points skipped to avoid overcrowding
2. **Status indicators**: The current status point is highlighted with its zone color
3. **Legend**: Clear legend showing which line corresponds to which chain
4. **Zone labels**: The zones are clearly labeled as SAFE, WARNING, and CRITICAL

## Key Functions Reference

### `create_fever_chart(scheduler, filename=None, show=True, project_name=None)`

**Parameters:**
- `scheduler`: The CCPMScheduler instance containing project data
- `filename`: Optional path to save the chart image
- `show`: Boolean to control whether to display the chart
- `project_name`: Optional project name for the chart title

**Returns:**
- The matplotlib figure object

### `generate_fever_chart_data(scheduler)`

**Parameters:**
- `scheduler`: The CCPMScheduler instance

**Returns:**
- Dictionary with keys as chain IDs and values as dictionaries containing:
  - `name`: Chain name
  - `buffer_name`: Buffer name
  - `type`: Chain type (critical or feeding)
  - `dates`: List of date objects
  - `buffer_consumption`: List of consumption percentages
  - `chain_completion`: List of completion percentages
  - `status`: List of status values ("green", "yellow", "red")

### `create_multi_fever_chart(data_dict, filename=None, show=True, title=None)`

**Parameters:**
- `data_dict`: Dictionary with keys as project names and values as fever chart data
- `filename`: Optional path to save the chart image
- `show`: Boolean to control whether to display the chart
- `title`: Optional chart title

**Returns:**
- The matplotlib figure object

## Best Practices

1. **Regular Updates**: Update buffer consumption and chain completion data regularly to maintain an accurate fever chart.

2. **Consistent Tracking**: Ensure that both the buffer consumption and chain completion percentages are updated simultaneously.

3. **Historical Data**: Maintain the full history of buffer consumption to see trends over time.

4. **Comparative Analysis**: Use the multi-chart feature to compare:
   - Current project against similar past projects
   - Different scenarios within the same project
   - Performance across multiple concurrent projects

## Implementation Notes

1. The implementation handles missing data gracefully by:
   - Skipping entries without date information
   - Calculating consumption percentage from remaining values if not provided
   - Using current completion percentage for historical points if not recorded

2. The visualization automatically scales the y-axis based on the maximum buffer consumption.

3. Date labels are selectively displayed to prevent overcrowding.

4. The implementation is designed to work seamlessly with the existing CCPM package structure.

## Technical Requirements

The implementation uses:
- matplotlib for visualization
- datetime for date handling
- Standard Python data structures (lists, dictionaries)

## Future Enhancements

Potential future enhancements to the fever chart implementation:

1. Interactive visualization using libraries like Plotly
2. Hover tooltips with detailed information about each data point
3. Trend prediction based on historical consumption rates
4. Time-based analysis showing buffer consumption rate over time
5. Integration with risk management systems to highlight high-risk chain segments