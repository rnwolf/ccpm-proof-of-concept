from abc import ABC, abstractmethod
from math import sqrt


class BufferCalculationStrategy(ABC):
    @abstractmethod
    def calculate_buffer_size(self, tasks, buffer_ratio):
        """Calculate buffer size based on the list of tasks and buffer ratio"""
        pass

    def get_name(self):
        """Get the name of this strategy"""
        return self.__class__.__name__


# Cut-and-Paste Method (C&PM)
class CutAndPasteMethod(BufferCalculationStrategy):
    def calculate_buffer_size(self, tasks, buffer_ratio):
        """
        Half times sum of the aggressive scheduling path
        Buffer = buffer_ratio * sum(aggressive durations)
        """
        aggressive_sum = sum(task.aggressive_duration for task in tasks)
        return aggressive_sum * buffer_ratio

    def get_name(self):
        return "Cut-and-Paste Method (C&PM)"


# Sum of Squares Method (SSQ)
class SumOfSquaresMethod(BufferCalculationStrategy):
    def calculate_buffer_size(self, tasks, buffer_ratio):
        """
        Square root of sum of squared differences between safe and aggressive estimates
        Buffer = sqrt(sum((safe - aggressive)²))
        """
        squared_diffs = sum(
            (task.safe_duration - task.aggressive_duration) ** 2 for task in tasks
        )
        return sqrt(squared_diffs)

    def get_name(self):
        return "Sum of Squares Method (SSQ)"


# Root Square Error Method (RSEM)
class RootSquareErrorMethod(BufferCalculationStrategy):
    def calculate_buffer_size(self, tasks, buffer_ratio):
        """
        Two times square root of sum of squared differences
        Buffer = 2 * sqrt(sum((safe - aggressive)²))
        """
        squared_diffs = sum(
            (task.safe_duration - task.aggressive_duration) ** 2 for task in tasks
        )
        return 2 * sqrt(squared_diffs)

    def get_name(self):
        return "Root Square Error Method (RSEM)"


# Adaptive Buffer Method (combines approaches based on chain characteristics)
class AdaptiveBufferMethod(BufferCalculationStrategy):
    def calculate_buffer_size(self, tasks, buffer_ratio):
        """
        Adapts buffer calculation based on chain characteristics:
        - For chains with high variation between safe/aggressive, use SSQ
        - For chains with more uniform estimates, use C&PM
        - Apply a minimum buffer size based on chain length
        """
        if not tasks:
            return 0

        # Calculate variation coefficient
        aggressive_sum = sum(task.aggressive_duration for task in tasks)
        safe_sum = sum(task.safe_duration for task in tasks)

        # Calculate average ratio of safe/aggressive
        ratios = [
            (task.safe_duration / task.aggressive_duration)
            for task in tasks
            if task.aggressive_duration > 0
        ]
        avg_ratio = sum(ratios) / len(ratios) if ratios else 1.5

        # Calculate standard deviation of ratios
        variance = (
            sum((r - avg_ratio) ** 2 for r in ratios) / len(ratios) if ratios else 0
        )
        std_dev = sqrt(variance)

        # If high variation (std_dev > 0.3), use SSQ
        if std_dev > 0.3:
            squared_diffs = sum(
                (task.safe_duration - task.aggressive_duration) ** 2 for task in tasks
            )
            buffer = sqrt(squared_diffs)
        else:
            # Otherwise use C&PM
            buffer = aggressive_sum * buffer_ratio

        # Ensure minimum buffer size
        min_buffer = aggressive_sum * 0.15  # At least 15% of chain length

        return max(buffer, min_buffer)

    def get_name(self):
        return "Adaptive Buffer Method"
