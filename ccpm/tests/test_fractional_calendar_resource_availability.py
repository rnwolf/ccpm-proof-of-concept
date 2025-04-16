from datetime import datetime, timedelta
from ccpm.domain.task import Task
from ccpm.services.scheduler import CCPMScheduler


def create_sample_network_with_resource_constraints():
    # Create scheduler
    scheduler = CCPMScheduler()

    # Set start date
    start_date = datetime(2025, 5, 1)
    scheduler.set_start_date(start_date)

    # Define resources with availability constraints
    resources = {}

    # 1. Regular resource with weekend constraints
    engineer_a = {
        "id": "Engineer A",
        "name": "Engineer A",
        "capacity": 1.0,  # Full-time (100%)
        "calendar": create_weekday_only_calendar(
            start_date, 90
        ),  # 90 days of weekdays only
    }

    # 2. Part-time resource
    engineer_b = {
        "id": "Engineer B",
        "name": "Engineer B",
        "capacity": 0.5,  # Half-time (50%)
        "calendar": create_weekday_only_calendar(start_date, 90),
    }

    # 3. Resource with specific availability periods
    designer = {
        "id": "Designer",
        "name": "Designer",
        "capacity": 1.0,
        "calendar": create_weekday_only_calendar(start_date, 90),
    }
    # Designer is unavailable for 2 weeks starting May 15
    add_unavailable_period(
        designer["calendar"], datetime(2025, 5, 15), datetime(2025, 5, 29)
    )

    # 4. Resource with holiday constraints
    developer = {
        "id": "Developer",
        "name": "Developer",
        "capacity": 1.0,
        "calendar": create_weekday_only_calendar(start_date, 90),
    }
    # Add company holidays
    holidays = [
        datetime(2025, 5, 26),  # Memorial Day
        datetime(2025, 7, 4),  # Independence Day
    ]
    for holiday in holidays:
        developer["calendar"][holiday.strftime("%Y-%m-%d")] = 0.0

    # 5. Resource with varied availability
    tester = {
        "id": "Tester",
        "name": "Tester",
        "capacity": 1.0,
        "calendar": create_weekday_only_calendar(start_date, 90),
    }
    # Tester is only available at 50% capacity for the first month
    end_date = start_date + timedelta(days=30)
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Weekday
            tester["calendar"][current_date.strftime("%Y-%m-%d")] = 0.5
        current_date += timedelta(days=1)

    # Add all resources to the scheduler
    resources = [engineer_a, engineer_b, designer, developer, tester]
    scheduler.set_resources(resources)

    # Create tasks (similar to previous example, but with resource constraints)
    # ... [task creation code] ...

    # Schedule the project
    scheduler.schedule()

    return scheduler


def create_weekday_only_calendar(start_date, num_days):
    """Create a calendar with full availability on weekdays, none on weekends."""
    calendar = {}

    current_date = start_date
    end_date = start_date + timedelta(days=num_days)

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        # 0-4 are Monday-Friday, 5-6 are Saturday-Sunday
        if current_date.weekday() < 5:  # Weekday
            calendar[date_str] = 1.0  # Full availability
        else:  # Weekend
            calendar[date_str] = 0.0  # No availability

        current_date += timedelta(days=1)

    return calendar


def add_unavailable_period(calendar, start_date, end_date):
    """Mark a period as unavailable in the resource calendar."""
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        calendar[date_str] = 0.0  # No availability
        current_date += timedelta(days=1)

    return calendar


def add_company_holidays(calendar, holiday_list):
    """Add company holidays to the calendar."""
    for holiday_date in holiday_list:
        date_str = holiday_date.strftime("%Y-%m-%d")
        calendar[date_str] = 0.0  # No availability on holidays

    return calendar
