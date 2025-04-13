# Refactor

Restructuring the graphbased-ccpm.py as it becoming difficult to make changes to the proof-of-concept

## How to restucture application

Separate the application into clear layers:

1. Domain Layer: Task, Buffer, Resource classes with their business logic
2. Service Layer: Schedule calculation, critical chain identification, buffer sizing
3. Visualization Layer: Pure rendering logic with no business calculations


With this enhanced model, here's how we would restructure the application:

1. Task Planning Phase

* Create tasks with aggressive and safe duration estimates
* Allow planners to adjust both estimates
* When planning is complete, finalize and lock in planned durations


2. Scheduling Phase

* Calculate the schedule using aggressive durations
* Create appropriate buffers using the difference between safe and aggressive estimates
* Determine the critical chain and feeding chains


3. Execution Phase

* Start tasks with actual start dates
* Update progress with remaining durations
* Track buffer consumption
* Generate reports and visualizations showing status against the aggressive plan


This approach properly separates the different phases of CCPM and provides a solid foundation for the visualization and reporting components to build upon.

## Migration Strategy

To migrate from the single file to this structure:

1. Create the directory structure first
2. Start with the domain model files
3. Extract the service classes one by one
4. Move visualization code to separate files
5. Update imports throughout the codebase
6. Create utility functions for shared code
7. Write integration tests to verify everything works together

This structure provides several advantages:

Clear separation of concerns between domain, services, and visualization
Easier maintenance as each file has a well-defined responsibility
Better testability of individual components
Simpler extension of functionality by adding new strategy classes or visualization types
More manageable code review as changes are isolated to specific files

Would you like me to start implementing any specific part of this structure? For example, I could show you how to extract the domain model classes or the buffer strategies into their respective files.

## Next steps for migration

Task domain model is almost done, but there are a few more elements we could address to complete it fully:

 * Validation and Error Handling: We should add comprehensive validation similar to what we did for the Resource class.
 * Duration Handling: We could enhance how the Task class handles updates to durations, especially during rescheduling.
 * Color Attribute: We properly added the color attribute for resource scheduling but should include methods for managing it.
 * Progress Calculation: We could improve the methods for calculating task progress percentages.


## Overall plan for migration

Next Steps for Migration

1. Complete domain model implementation:

The Resource class is currently a skeleton - implement the full resource functionality from the original script
Ensure all domain classes have proper validation and error handling


2. Implement service layer completely:

Finish critical_chain.py and feeding_chain.py with the algorithms from the original script
Complete resource_leveling.py with the graph coloring algorithm
Add progress tracking and execution phase functionality to scheduler.py


3. Enhance visualization components:

Complete the network.py diagram visualization
Implement fever_chart.py for buffer consumption tracking
Add resource_chart.py for resource utilization visualization


4. Add comprehensive testing:

Create unit tests for individual components
Add integration tests for the complete workflow
Include test cases for edge conditions (resource conflicts, task progress updates)


5. Improve CLI and configuration:

Enhance the CLI to support all features (execution, progress tracking)
Add configuration file support for project settings
Implement file I/O for loading/saving project data


6. Add documentation:

Complete docstrings for all classes and methods
Create usage examples
Add developer documentation for extending the system


7. Implement execution phase features:

Add functionality for task progress updates
Implement buffer consumption tracking
Create reporting for project status


8. Enhance visualization outputs:

Add interactive HTML output options
Support for exporting to common project formats
Create dashboard views for project status

## File Structure

ccpm/
├── __init__.py                    # Package initialization
├── __main__.py                    # Main entry point for the package:
├── domain/                        # Domain model
│   ├── __init__.py
│   ├── task.py                    # Task class
│   ├── chain.py                   # Chain class
│   ├── buffer.py                  # Buffer class
│   └── resource.py                # Resource class
├── services/                      # Business logic
│   ├── __init__.py
│   ├── scheduler.py               # Core scheduling service
│   ├── buffer_strategies.py       # Buffer calculation strategies
│   ├── critical_chain.py          # Critical chain identification
│   ├── feeding_chain.py           # Feeding chain identification
│   └── resource_leveling.py       # Resource leveling algorithms
├── visualization/                 # Visualization components
│   ├── __init__.py
│   ├── gantt.py                   # Gantt chart visualization
│   ├── network.py                 # Network diagram visualization
│   ├── fever_chart.py             # Fever chart for buffer consumption
│   └── resource_chart.py          # Resource utilization chart
├── utils/                         # Utility functions
│   ├── __init__.py
│   ├── graph.py                   # Graph algorithms and utilities
│   └── date_utils.py              # Date manipulation helpers
├── examples/                      # Example usage
│   ├── simple_project.py
│   ├── multi_chain_project.py
│   └── buffer_strategy_comparison.py
└── tests/
    └── test_integration.py        # ensure everything works together correctly,

## Domain model

This enhanced domain model provides several advantages:

Explicit Chain Objects: Representing chains as first-class domain objects makes the relationship between tasks, chains, and buffers clearer.
Custom Buffer Ratios: Each feeding chain can have its own buffer ratio, allowing for more nuanced buffer sizing.
Clear Membership: Tasks know which chain they belong to, making it easier to track chain membership.
Better Buffer Calculation: The buffer calculation now properly accounts for the difference between aggressive and safe estimates.
Improved Traceability: With this structure, it's easier to trace the impact of task updates on chains and buffers.

### Resource Domain

This implementation provides several advantages:

* Complete Timeline View: Shows both historical performance and future projections
* Integrated Planning: Uses the scheduler's task assignments for future projections
* Resource Constraint Analysis: Helps identify which resources may become constraints
* Flow Balance Prediction: Projects future flow balance based on the plan
* "What-If" Analysis: Can be used to model different scheduling scenarios

You can visualize both actual and planned resource utilization, helping project managers balance workloads and identify potential bottlenecks before they occur.

How It Handles Historical Data

For historical data, the implementation tracks actual:

 * Arrivals (when tasks started on a resource)
 * Departures (when tasks were completed)
 * Work in progress states on each date

How It Handles Future Data

For future data, we need to predict:

 * When tasks will start
 * When tasks will finish
 * What the WIP will be on future dates


* Configuration option to allow over-allocation with allow_overallocation parameter
* Tracking of over-allocations in a dedicated dictionary
* Methods for reporting over-allocations:

    * is_overallocated() to check if over-allocation exists
    * get_overallocation_report() to get detailed information about over-allocations

The scheduler component would need to be configured to respect this over-allocation setting.

Tags support

A tags list attribute to store tags
Methods to add, remove, and filter resources by tags

Flow tracking for Cumulative Flow Diagrams

Methods to record task arrivals and departures
Tracking of work in progress with state transitions
Generation of cumulative flow diagram data
Analysis of flow balance (arrivals vs. departures)

Key Validation and Error Handling Features Added:

Input Validation:

Validates all parameters in the constructor
Checks for None values, empty strings, negative numbers
Validates data types (numbers, strings, dictionaries)
Date format validation in the calendar


Method Validation:

Validates input parameters for all methods
Type checking for dates, numbers, and other parameters
Range checking (negative values, zero values)
Date sequence validation (start date before end date)


Custom Exceptions:

Added custom ResourceOverallocationError for clarity
Provides detailed error messages with resource name and context


Data Integrity:

Maintains consistent data structures
Updates related data when changing allocations
Ensures state consistency for planned assignments


Error Recovery:

Transaction-like behavior for multi-day allocations
Rolls back partial allocations if any day fails
Updates overallocation tracking when deallocating

Validation and Error handling ensures that:

Invalid data is rejected early with clear error messages
Complex operations maintain consistency across related data structures
Errors provide sufficient context for debugging
Data structures remain in a valid state even after partial operations

## Services

### Scheduler

* Track flow events by calling the appropriate resource methods when tasks start or complete
* Provide visualization methods for cumulative flow diagrams
* Identify constraint resources by analyzing flow balance across all resources