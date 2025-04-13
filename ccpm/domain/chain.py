class Chain:
    def __init__(self, id, name, type="feeding", buffer_ratio=0.3):
        # Core identification
        self.id = id
        self.name = name

        # Chain type and properties
        self.type = type  # "critical" or "feeding"
        self.buffer_ratio = buffer_ratio  # Default ratio for buffer calculation

        # Tasks in this chain (ordered)
        self.tasks = []

        # Connected to (for feeding chains)
        self.connects_to_task_id = None
        self.connects_to_chain_id = None

        # Associated buffer
        self.buffer = None
        self.buffer_strategy = None  # Set by the scheduler

    def add_task(self, task_id):
        """Add a task to this chain"""
        if task_id not in self.tasks:
            self.tasks.append(task_id)
        return self

    def remove_task(self, task_id):
        """Remove a task from this chain"""
        if task_id in self.tasks:
            self.tasks.remove(task_id)
        return self

    def set_connection(self, task_id, chain_id=None):
        """Set where this feeding chain connects to"""
        self.connects_to_task_id = task_id
        self.connects_to_chain_id = chain_id
        return self

    def get_tasks(self):
        """Get the list of task IDs in this chain"""
        return self.tasks
