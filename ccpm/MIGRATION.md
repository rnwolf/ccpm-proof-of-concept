# Resfactor

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

1. Continue Migrating Functionality: Move more advanced features from the original code, such as resource leveling and fever charts.
2. Add Unit Tests: Create specific unit tests for each component to ensure they work correctly in isolation.
3. Improve Documentation: Add docstrings and type hints to all classes and methods.
4. Add CLI Interface: Enhance the command-line interface to allow loading projects from files, setting parameters, etc.
5. Validate Implementation: Compare the results from the new modular implementation with the original monolithic code to ensure they produce the same results.

This step-by-step approach allows us to gradually migrate the code while ensuring it continues to work correctly. Each component can be tested independently, and the integration test ensures that everything works together as expected.

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
