"""
Test script for CCPM Fever Chart visualization.
This script creates a sample project and generates fever chart visualizations.
"""

import sys
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ccpm.domain.task import Task
from ccpm.domain.buffer import Buffer
from ccpm.domain.chain import Chain
from ccpm.services.scheduler import CCPMScheduler
from ccpm.visualization.fever_chart import (
    create_fever_chart,
    generate_fever_chart_data,
    create_multi_fever_chart,
)


def create_test_project():
    """Create a test project with tasks, chains, and buffers for visualization."""
    # Create a scheduler
    scheduler = CCPMScheduler()

    # Set start date
    start_date = datetime(2025, 4, 1)
    scheduler.start_date = start_date

    # Create tasks
    task1 = Task(
        id="T1",
        name="Requirements Analysis",
        aggressive_duration=5,
        safe_duration=8,
        resources=["Business Analyst"],
    )
    task2 = Task(
        id="T2",
        name="System Design",
        aggressive_duration=10,
        safe_duration=15,
        dependencies=["T1"],
        resources=["Architect"],
    )
    task3 = Task(
        id="T3",
        name="Frontend Development",
        aggressive_duration=15,
        safe_duration=20,
        dependencies=["T2"],
        resources=["Developer A", "Developer B"],
    )
    task4 = Task(
        id="T4",
        name="Backend Development",
        aggressive_duration=12,
        safe_duration=18,
        dependencies=["T2"],
        resources=["Developer C"],
    )
    task5 = Task(
        id="T5",
        name="Database Setup",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T2"],
        resources=["DBA"],
    )
    task6 = Task(
        id="T6",
        name="Integration",
        aggressive_duration=6,
        safe_duration=10,
        dependencies=["T3", "T4", "T5"],
        resources=["Developer A", "Developer C"],
    )
    task7 = Task(
        id="T7",
        name="Testing",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T6"],
        resources=["Tester"],
    )
    task8 = Task(
        id="T8",
        name="Deployment",
        aggressive_duration=3,
        safe_duration=5,
        dependencies=["T7"],
        resources=["DevOps"],
    )

    # Additional tasks for more chains
    task9 = Task(
        id="T9",
        name="User Documentation",
        aggressive_duration=7,
        safe_duration=10,
        dependencies=["T2"],
        resources=["Technical Writer"],
    )

    task10 = Task(
        id="T10",
        name="Security Review",
        aggressive_duration=5,
        safe_duration=8,
        dependencies=["T4"],
        resources=["Security Analyst"],
    )

    task11 = Task(
        id="T11",
        name="Performance Testing",
        aggressive_duration=4,
        safe_duration=6,
        dependencies=["T6"],
        resources=["Tester"],
    )

    task12 = Task(
        id="T12",
        name="UI Design",
        aggressive_duration=8,
        safe_duration=12,
        dependencies=["T1"],
        resources=["UI Designer"],
    )

    # Add tasks to scheduler
    scheduler.add_task(task1)
    scheduler.add_task(task2)
    scheduler.add_task(task3)
    scheduler.add_task(task4)
    scheduler.add_task(task5)
    scheduler.add_task(task6)
    scheduler.add_task(task7)
    scheduler.add_task(task8)
    scheduler.add_task(task9)
    scheduler.add_task(task10)
    scheduler.add_task(task11)
    scheduler.add_task(task12)

    # Create chains - adding multiple chains of each type to demonstrate differentiation
    critical_chain = Chain(id="CC", name="Critical Chain", type="critical")
    critical_chain.add_task("T1").add_task("T2").add_task("T4").add_task("T6").add_task(
        "T7"
    ).add_task("T8")

    # Additional critical chain (parallel project or alternative path)
    critical_chain2 = Chain(id="CC2", name="Alternative Critical Path", type="critical")
    critical_chain2.add_task("T1").add_task("T2").add_task("T6").add_task(
        "T7"
    ).add_task("T8")

    feeding_chain1 = Chain(id="FC1", name="Frontend Chain", type="feeding")
    feeding_chain1.add_task("T3")
    feeding_chain1.set_connection("T6")

    feeding_chain2 = Chain(id="FC2", name="Database Chain", type="feeding")
    feeding_chain2.add_task("T5")
    feeding_chain2.set_connection("T6")

    feeding_chain3 = Chain(id="FC3", name="Documentation Chain", type="feeding")
    feeding_chain3.add_task("T9")
    feeding_chain3.set_connection("T7")

    feeding_chain4 = Chain(id="FC4", name="Security Chain", type="feeding")
    feeding_chain4.add_task("T10")
    feeding_chain4.set_connection("T7")

    feeding_chain5 = Chain(id="FC5", name="UI Chain", type="feeding")
    feeding_chain5.add_task("T12")
    feeding_chain5.set_connection("T3")

    # Add chains to scheduler
    scheduler.chains = {
        "CC": critical_chain,
        "CC2": critical_chain2,
        "FC1": feeding_chain1,
        "FC2": feeding_chain2,
        "FC3": feeding_chain3,
        "FC4": feeding_chain4,
        "FC5": feeding_chain5,
    }
    scheduler.critical_chain = critical_chain

    # Update task chain information
    for task_id in critical_chain.tasks:
        scheduler.tasks[task_id].chain_id = "CC"
        scheduler.tasks[task_id].chain_type = "critical"

    for task_id in feeding_chain1.tasks:
        scheduler.tasks[task_id].chain_id = "FC1"
        scheduler.tasks[task_id].chain_type = "feeding"

    for task_id in feeding_chain2.tasks:
        scheduler.tasks[task_id].chain_id = "FC2"
        scheduler.tasks[task_id].chain_type = "feeding"

    # Create buffers
    project_buffer = Buffer(
        id="PB", name="Project Buffer", size=20.0, buffer_type="project"
    )

    project_buffer2 = Buffer(
        id="PB2", name="Alternative Path Buffer", size=18.0, buffer_type="project"
    )

    feeding_buffer1 = Buffer(
        id="FB1",
        name="Frontend Buffer",
        size=5.0,
        buffer_type="feeding",
        connected_to="T6",
    )

    feeding_buffer2 = Buffer(
        id="FB2",
        name="Database Buffer",
        size=3.0,
        buffer_type="feeding",
        connected_to="T6",
    )

    feeding_buffer3 = Buffer(
        id="FB3",
        name="Documentation Buffer",
        size=4.0,
        buffer_type="feeding",
        connected_to="T7",
    )

    feeding_buffer4 = Buffer(
        id="FB4",
        name="Security Buffer",
        size=3.0,
        buffer_type="feeding",
        connected_to="T7",
    )

    feeding_buffer5 = Buffer(
        id="FB5",
        name="UI Buffer",
        size=4.0,
        buffer_type="feeding",
        connected_to="T3",
    )

    # Associate buffers with chains
    critical_chain.set_buffer(project_buffer)
    critical_chain2.set_buffer(project_buffer2)
    feeding_chain1.set_buffer(feeding_buffer1)
    feeding_chain2.set_buffer(feeding_buffer2)
    feeding_chain3.set_buffer(feeding_buffer3)
    feeding_chain4.set_buffer(feeding_buffer4)
    feeding_chain5.set_buffer(feeding_buffer5)

    # Add buffers to scheduler
    scheduler.buffers = {
        "PB": project_buffer,
        "PB2": project_buffer2,
        "FB1": feeding_buffer1,
        "FB2": feeding_buffer2,
        "FB3": feeding_buffer3,
        "FB4": feeding_buffer4,
        "FB5": feeding_buffer5,
    }

    # Set task schedules & chain completion
    critical_chain.completion_percentage = 0
    feeding_chain1.completion_percentage = 0
    feeding_chain2.completion_percentage = 0

    # Initial buffer consumption history (day 0)
    execution_date = start_date

    # Main critical chain
    project_buffer.consumption_history = [
        {
            "date": execution_date,
            "remaining": 20.0,
            "new_remaining": 20.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    # Alternative critical chain
    project_buffer2.consumption_history = [
        {
            "date": execution_date,
            "remaining": 18.0,
            "new_remaining": 18.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    # Original feeding chains
    feeding_buffer1.consumption_history = [
        {
            "date": execution_date,
            "remaining": 5.0,
            "new_remaining": 5.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    feeding_buffer2.consumption_history = [
        {
            "date": execution_date,
            "remaining": 3.0,
            "new_remaining": 3.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    # Additional feeding chains
    feeding_buffer3.consumption_history = [
        {
            "date": execution_date,
            "remaining": 4.0,
            "new_remaining": 4.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    feeding_buffer4.consumption_history = [
        {
            "date": execution_date,
            "remaining": 3.0,
            "new_remaining": 3.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    feeding_buffer5.consumption_history = [
        {
            "date": execution_date,
            "remaining": 4.0,
            "new_remaining": 4.0,
            "consumption_percentage": 0,
            "chain_completion": 0,
            "status": "green",
        }
    ]

    # Simulate progress at week 1
    execution_date = start_date + timedelta(days=7)
    scheduler.execution_date = execution_date

    # Update tasks
    task1.status = "in_progress"
    task1.actual_start_date = start_date
    task1.remaining_duration = 3.0  # 2 days done, 3 remaining

    task12.status = "in_progress"  # UI Design starts
    task12.actual_start_date = start_date + timedelta(days=3)
    task12.remaining_duration = 6.0  # 2 days done

    # Update chain completions
    critical_chain.completion_percentage = (
        8  # 40% of task1 done (first 8% of critical chain)
    )
    critical_chain2.completion_percentage = 9  # Similar progress, slight difference
    feeding_chain5.completion_percentage = 25  # UI Chain started

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 19.0,
            "new_remaining": 19.0,
            "consumption_percentage": 5,
            "chain_completion": 8,
            "status": "green",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 17.0,
            "new_remaining": 17.0,
            "consumption_percentage": 6,
            "chain_completion": 9,
            "status": "green",
        }
    )

    feeding_buffer5.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.8,
            "new_remaining": 3.8,
            "consumption_percentage": 5,
            "chain_completion": 25,
            "status": "green",
        }
    )

    # No change to other feeding chains yet
    feeding_chain1.completion_percentage = 0
    feeding_chain2.completion_percentage = 0
    feeding_chain3.completion_percentage = 0
    feeding_chain4.completion_percentage = 0

    # Simulate progress at week 2
    execution_date = start_date + timedelta(days=14)
    scheduler.execution_date = execution_date

    # Update tasks
    task1.status = "completed"
    task1.actual_end_date = start_date + timedelta(days=6)
    task1.remaining_duration = 0

    task2.status = "in_progress"
    task2.actual_start_date = start_date + timedelta(days=7)
    task2.remaining_duration = 6.0  # 4 days done, 6 remaining

    task12.remaining_duration = 3.0  # UI Design continuing

    task9.status = "in_progress"  # Documentation starts
    task9.actual_start_date = start_date + timedelta(days=10)
    task9.remaining_duration = 6.0  # Just started

    # Update chain completion
    critical_chain.completion_percentage = (
        28  # 100% of task1 (20%) + 40% of task2 (20%) = 28%
    )
    critical_chain2.completion_percentage = 30  # Similar progress, slight difference
    feeding_chain3.completion_percentage = 15  # Documentation chain started
    feeding_chain5.completion_percentage = 60  # UI Design continuing

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 18.0,
            "new_remaining": 18.0,
            "consumption_percentage": 10,
            "chain_completion": 28,
            "status": "green",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 16.0,
            "new_remaining": 16.0,
            "consumption_percentage": 11,
            "chain_completion": 30,
            "status": "green",
        }
    )

    feeding_buffer3.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.6,
            "new_remaining": 3.6,
            "consumption_percentage": 10,
            "chain_completion": 15,
            "status": "green",
        }
    )

    feeding_buffer5.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.2,
            "new_remaining": 3.2,
            "consumption_percentage": 20,
            "chain_completion": 60,
            "status": "green",
        }
    )

    # Update chain completion
    critical_chain.completion_percentage = (
        45  # tasks 1+2 (40%) + 25% of task4 (10%) = 45%
    )
    critical_chain2.completion_percentage = 48  # Similar progress, slightly ahead
    feeding_chain1.completion_percentage = 20  # 20% of task3
    feeding_chain2.completion_percentage = 25  # 25% of task5
    feeding_chain3.completion_percentage = 42  # Documentation progressing
    feeding_chain4.completion_percentage = 20  # Security review started
    feeding_chain5.completion_percentage = 100  # UI Design completed

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 17.0,
            "new_remaining": 17.0,
            "consumption_percentage": 15,
            "chain_completion": 45,
            "status": "green",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 14.5,
            "new_remaining": 14.5,
            "consumption_percentage": 19,
            "chain_completion": 48,
            "status": "green",
        }
    )

    feeding_buffer1.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 4.5,
            "new_remaining": 4.5,
            "consumption_percentage": 10,
            "chain_completion": 20,
            "status": "green",
        }
    )

    feeding_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 2.7,
            "new_remaining": 2.7,
            "consumption_percentage": 10,
            "chain_completion": 25,
            "status": "green",
        }
    )

    feeding_buffer3.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.2,
            "new_remaining": 3.2,
            "consumption_percentage": 20,
            "chain_completion": 42,
            "status": "green",
        }
    )

    feeding_buffer4.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 2.7,
            "new_remaining": 2.7,
            "consumption_percentage": 10,
            "chain_completion": 20,
            "status": "green",
        }
    )

    feeding_buffer5.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.2,
            "new_remaining": 3.2,
            "consumption_percentage": 20,
            "chain_completion": 100,
            "status": "green",
        }
    )

    # Simulate progress at week 4
    execution_date = start_date + timedelta(days=28)
    scheduler.execution_date = execution_date

    # Update tasks
    task4.status = "completed"
    task4.actual_end_date = start_date + timedelta(days=30)  # Delayed by 2 days
    task4.remaining_duration = 0

    task3.remaining_duration = 8.0  # 7 days done, 8 remaining (slow progress)
    task5.remaining_duration = 3.0  # 5 days done, 3 remaining
    task9.status = "completed"  # Documentation completed
    task9.actual_end_date = start_date + timedelta(days=27)
    task9.remaining_duration = 0

    task10.remaining_duration = 2.0  # Security review progressing

    # Update chain completion
    critical_chain.completion_percentage = 60  # tasks 1+2+4 (60%)
    critical_chain2.completion_percentage = 65  # Slightly ahead
    feeding_chain1.completion_percentage = 46  # 46% of task3
    feeding_chain2.completion_percentage = 62  # 62% of task5
    feeding_chain3.completion_percentage = 100  # Documentation complete
    feeding_chain4.completion_percentage = 60  # Security review progressing

    # Add to buffer consumption histories with increasing delay impact
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 15.0,
            "new_remaining": 15.0,
            "consumption_percentage": 25,
            "chain_completion": 60,
            "status": "green",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 12.0,
            "new_remaining": 12.0,
            "consumption_percentage": 33,
            "chain_completion": 65,
            "status": "yellow",
        }
    )

    feeding_buffer1.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.0,
            "new_remaining": 3.0,
            "consumption_percentage": 40,
            "chain_completion": 46,
            "status": "yellow",
        }
    )

    feeding_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 2.1,
            "new_remaining": 2.1,
            "consumption_percentage": 30,
            "chain_completion": 62,
            "status": "green",
        }
    )

    feeding_buffer3.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.0,
            "new_remaining": 3.0,
            "consumption_percentage": 25,
            "chain_completion": 100,
            "status": "green",
        }
    )

    feeding_buffer4.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 1.5,
            "new_remaining": 1.5,
            "consumption_percentage": 50,
            "chain_completion": 60,
            "status": "yellow",
        }
    )

    # Simulate progress at week 4
    execution_date = start_date + timedelta(days=28)
    scheduler.execution_date = execution_date

    # Update tasks
    task4.status = "completed"
    task4.actual_end_date = start_date + timedelta(days=30)  # Delayed by 2 days
    task4.remaining_duration = 0

    task3.remaining_duration = 8.0  # 7 days done, 8 remaining (slow progress)
    task5.remaining_duration = 3.0  # 5 days done, 3 remaining

    # Update chain completion
    critical_chain.completion_percentage = 60  # tasks 1+2+4 (60%)
    feeding_chain1.completion_percentage = 46  # 46% of task3
    feeding_chain2.completion_percentage = 62  # 62% of task5

    # Add to buffer consumption histories with increasing delay impact
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 15.0,
            "new_remaining": 15.0,
            "consumption_percentage": 25,
            "chain_completion": 60,
            "status": "green",
        }
    )

    feeding_buffer1.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.0,
            "new_remaining": 3.0,
            "consumption_percentage": 40,
            "chain_completion": 46,
            "status": "yellow",
        }
    )

    feeding_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 2.1,
            "new_remaining": 2.1,
            "consumption_percentage": 30,
            "chain_completion": 62,
            "status": "green",
        }
    )

    # Simulate progress at week 5
    execution_date = start_date + timedelta(days=35)
    scheduler.execution_date = execution_date

    # Update tasks
    task5.status = "completed"
    task5.actual_end_date = start_date + timedelta(days=33)
    task5.remaining_duration = 0

    task3.status = "completed"
    task3.actual_end_date = start_date + timedelta(days=36)  # Delayed by 2 days
    task3.remaining_duration = 0

    task6.status = "in_progress"  # Integration can start now
    task6.actual_start_date = start_date + timedelta(days=36)
    task6.remaining_duration = 6.0  # Just started

    task10.status = "completed"  # Security review completed
    task10.actual_end_date = start_date + timedelta(days=32)
    task10.remaining_duration = 0

    # Update chain completion
    critical_chain.completion_percentage = 65  # tasks 1+2+4 (60%) + small part of task6
    critical_chain2.completion_percentage = 70  # Slightly ahead
    feeding_chain1.completion_percentage = 100  # Task3 complete
    feeding_chain2.completion_percentage = 100  # Task5 complete
    feeding_chain4.completion_percentage = 100  # Security review complete

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 13.0,
            "new_remaining": 13.0,
            "consumption_percentage": 35,
            "chain_completion": 65,
            "status": "yellow",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 9.0,
            "new_remaining": 9.0,
            "consumption_percentage": 50,
            "chain_completion": 70,
            "status": "yellow",
        }
    )

    feeding_buffer1.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 2.0,
            "new_remaining": 2.0,
            "consumption_percentage": 60,
            "chain_completion": 100,
            "status": "yellow",
        }
    )

    feeding_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 1.5,
            "new_remaining": 1.5,
            "consumption_percentage": 50,
            "chain_completion": 100,
            "status": "yellow",
        }
    )

    feeding_buffer4.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 0.9,
            "new_remaining": 0.9,
            "consumption_percentage": 70,
            "chain_completion": 100,
            "status": "yellow",
        }
    )

    # Simulate progress at week 6
    execution_date = start_date + timedelta(days=42)
    scheduler.execution_date = execution_date

    # Update tasks
    task6.status = "completed"
    task6.actual_end_date = start_date + timedelta(days=44)  # Delayed by 2 days
    task6.remaining_duration = 0

    task7.status = "in_progress"
    task7.actual_start_date = start_date + timedelta(days=45)
    task7.remaining_duration = 7.0  # Just started, 1 day done

    task11.status = "in_progress"  # Performance Testing starts
    task11.actual_start_date = start_date + timedelta(days=45)
    task11.remaining_duration = 4.0

    # Update chain completion
    critical_chain.completion_percentage = 80  # tasks 1+2+4+6 + small part of task7
    critical_chain2.completion_percentage = 85  # Slightly ahead

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 10.0,
            "new_remaining": 10.0,
            "consumption_percentage": 50,
            "chain_completion": 80,
            "status": "yellow",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 7.0,
            "new_remaining": 7.0,
            "consumption_percentage": 61,
            "chain_completion": 85,
            "status": "yellow",
        }
    )

    # Simulate progress at week 7
    execution_date = start_date + timedelta(days=49)
    scheduler.execution_date = execution_date

    # Update tasks
    task7.status = "completed"
    task7.actual_end_date = start_date + timedelta(days=54)  # Major delay on testing
    task7.remaining_duration = 0

    task11.status = "completed"  # Performance Testing completed
    task11.actual_end_date = start_date + timedelta(days=50)
    task11.remaining_duration = 0

    # Task 8 not started yet but projected to be delayed
    task8.status = "in_progress"
    task8.actual_start_date = start_date + timedelta(days=55)
    task8.remaining_duration = 3.0

    # Update chain completion
    critical_chain.completion_percentage = 95  # Near completion
    critical_chain2.completion_percentage = 95  # Both paths converged

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 5.0,
            "new_remaining": 5.0,
            "consumption_percentage": 75,
            "chain_completion": 95,
            "status": "red",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 3.0,
            "new_remaining": 3.0,
            "consumption_percentage": 83,
            "chain_completion": 95,
            "status": "red",
        }
    )

    # Simulate final progress at week 8
    execution_date = start_date + timedelta(days=56)
    scheduler.execution_date = execution_date

    # Update tasks
    task8.status = "completed"
    task8.actual_end_date = start_date + timedelta(days=58)
    task8.remaining_duration = 0

    # Update chain completion
    critical_chain.completion_percentage = 100  # Complete
    critical_chain2.completion_percentage = 100  # Complete

    # Add to buffer consumption histories
    project_buffer.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 2.0,
            "new_remaining": 2.0,
            "consumption_percentage": 90,
            "chain_completion": 100,
            "status": "red",
        }
    )

    project_buffer2.consumption_history.append(
        {
            "date": execution_date,
            "remaining": 1.0,
            "new_remaining": 1.0,
            "consumption_percentage": 94,
            "chain_completion": 100,
            "status": "red",
        }
    )

    return scheduler


def test_fever_chart():
    """Test the CCPM fever chart visualization."""
    print("Testing CCPM Fever Chart...")

    # Create a sample project with progress history
    scheduler = create_test_project()

    # Create fever chart
    create_fever_chart(
        scheduler, filename="test_fever_chart.png", project_name="Test Project"
    )
    print("Fever chart saved as 'test_fever_chart.png'")

    # Test data generation function
    fever_data = generate_fever_chart_data(scheduler)

    # Check the data structure
    print(f"Generated data for {len(fever_data)} chains")
    for chain_id, data in fever_data.items():
        print(f"  Chain: {data['name']} ({data['type']})")
        print(f"  Buffer: {data['buffer_name']}")
        print(f"  Data points: {len(data['dates'])}")
        print(f"  Final consumption: {data['buffer_consumption'][-1]:.1f}%")
        print(f"  Final completion: {data['chain_completion'][-1]:.1f}%")
        print(f"  Status: {data['status'][-1]}")
        print()

    return scheduler, fever_data


def test_multi_fever_chart():
    """Test creating a fever chart with multiple data series."""
    print("Testing Multi-Series Fever Chart...")

    # Create two sample projects with different progress patterns
    scheduler1 = create_test_project()

    # Create a second dataset with slightly different values
    scheduler2 = create_test_project()

    # Modify some values for the second project to show contrast
    # Access the critical chain buffer
    critical_chain = scheduler2.chains["CC"]
    project_buffer = critical_chain.buffer

    # Update the consumption history to show a different pattern
    for i, entry in enumerate(project_buffer.consumption_history):
        # Make the second project perform better in the middle, worse at the end
        if i > 2 and i < 5:
            entry["consumption_percentage"] = (
                entry["consumption_percentage"] * 0.8
            )  # Better performance
        elif i >= 5:
            entry["consumption_percentage"] = min(
                100, entry["consumption_percentage"] * 1.2
            )  # Worse at the end

    # Generate fever chart data for both projects
    data1 = generate_fever_chart_data(scheduler1)
    data2 = generate_fever_chart_data(scheduler2)

    # Create a multi-series fever chart
    combined_data = {"Project 1": data1, "Project 2": data2}
    create_multi_fever_chart(
        combined_data,
        filename="test_multi_fever_chart.png",
        title="Comparison of Two Projects",
    )
    print("Multi-series fever chart saved as 'test_multi_fever_chart.png'")


def run_all_tests():
    """Run all fever chart tests."""
    scheduler, _ = test_fever_chart()
    test_multi_fever_chart()
    print("All fever chart tests completed successfully.")


if __name__ == "__main__":
    run_all_tests()
