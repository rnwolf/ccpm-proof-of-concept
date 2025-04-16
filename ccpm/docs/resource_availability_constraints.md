# resource availability constraints

This example demonstrates how to implement various resource availability constraints:

## 1. Weekend Constraints

The create_weekday_only_calendar function creates a calendar with:

Full availability (1.0) on weekdays (Monday-Friday)
No availability (0.0) on weekends (Saturday-Sunday)

## 2. Part-time Resources

For Engineer B, I've set:

`"capacity": 0.5,  # Half-time (50%)`

This means this resource is only available at half capacity even on workdays.

## 3. Specific Unavailability Periods

For the Designer, I've added a vacation or unavailable period:

`# Designer is unavailable for 2 weeks starting May 15
add_unavailable_period(designer["calendar"],
                      datetime(2025, 5, 15),
                      datetime(2025, 5, 29))`

## 4. Holiday Constraints

For the Developer, I've added specific holidays:

`holidays = [
    datetime(2025, 5, 26),  # Memorial Day
    datetime(2025, 7, 4),   # Independence Day
]
for holiday in holidays:
    developer["calendar"][holiday.strftime("%Y-%m-%d")] = 0.0`

## 5. Varied Availability

For the Tester, I've implemented varying availability:


`# Tester is only available at 50% capacity for the first month
end_date = start_date + timedelta(days=30)
current_date = start_date
while current_date <= end_date:
    if current_date.weekday() < 5:  # Weekday
        tester["calendar"][current_date.strftime("%Y-%m-%d")] = 0.5
    current_date += timedelta(days=1)`