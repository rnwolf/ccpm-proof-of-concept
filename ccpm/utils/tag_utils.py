def get_all_tags(project):
    """
    Get all tags used in the project (Resources and tasks).

    Args:
        project: CCPMScheduler instance or dict with 'resources' and 'tasks'

    Returns:
        dict: Dictionary with 'resource_tags' and 'task_tags' lists
    """
    all_tags = {"resource_tags": set(), "task_tags": set()}

    # Handle different input types
    resources = (
        getattr(project, "resources", {})
        if not isinstance(project, dict)
        else project.get("resources", {})
    )
    tasks = (
        getattr(project, "tasks", {})
        if not isinstance(project, dict)
        else project.get("tasks", {})
    )

    # Collect resource tags
    for resource in resources.values():
        if hasattr(resource, "tags") and resource.tags:
            for tag in resource.tags:
                all_tags["resource_tags"].add(tag)

    # Collect task tags
    for task in tasks.values():
        if hasattr(task, "tags") and task.tags:
            for tag in task.tags:
                all_tags["task_tags"].add(tag)

    # Convert sets to sorted lists for consistent output
    return {
        "resource_tags": sorted(list(all_tags["resource_tags"])),
        "task_tags": sorted(list(all_tags["task_tags"])),
    }


def refresh_all_tags(project):
    """
    Rebuild the all_tags set by scanning all tasks and resources.

    Args:
        project: CCPMScheduler instance or dict with 'resources' and 'tasks'

    Returns:
        dict: Updated dictionary with 'resource_tags' and 'task_tags' lists
    """
    # Force a rebuild of the tag collections
    return get_all_tags(project)


def get_resources_by_tags(resources, tags, match_all=True):
    """
    Get resources that match the specified tags.

    Args:
        resources: Dictionary of resources keyed by resource ID
        tags: List of tags to match
        match_all: If True, resource must have all tags; if False, any tag is sufficient

    Returns:
        dict: Dictionary of resources keyed by resource ID
    """
    if not tags:
        return {}

    matching_resources = {}

    for resource_id, resource in resources.items():
        if not hasattr(resource, "tags") or resource.tags is None:
            continue

        if match_all:
            # Resource must have all the specified tags
            if all(tag in resource.tags for tag in tags):
                matching_resources[resource_id] = resource
        else:
            # Resource needs just one matching tag
            if any(tag in resource.tags for tag in tags):
                matching_resources[resource_id] = resource

    return matching_resources


def get_tasks_by_tags(tasks, tags, match_all=True):
    """
    Get tasks that match the specified tags.

    Args:
        tasks: Dictionary of tasks keyed by task ID
        tags: List of tags to match
        match_all: If True, task must have all tags; if False, any tag is sufficient

    Returns:
        dict: Dictionary of tasks keyed by task ID
    """
    if not tags:
        return {}

    matching_tasks = {}

    for task_id, task in tasks.items():
        # Skip tasks without tags attribute
        if not hasattr(task, "tags") or task.tags is None:
            continue

        if match_all:
            # Task must have all the specified tags
            if all(tag in task.tags for tag in tags):
                matching_tasks[task_id] = task
        else:
            # Task needs just one matching tag
            if any(tag in task.tags for tag in tags):
                matching_tasks[task_id] = task

    return matching_tasks
