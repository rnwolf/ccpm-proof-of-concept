import unittest
from datetime import datetime, timedelta
from ccpm.domain.buffer import Buffer, BufferError


class BufferTestCase(unittest.TestCase):
    """Test cases for the enhanced Buffer class."""

    def setUp(self):
        """Set up test cases with sample buffers."""
        # Project buffer
        self.project_buffer = Buffer(
            id="PB", name="Project Buffer", size=10, buffer_type="project"
        )

        # Feeding buffer
        self.feeding_buffer = Buffer(
            id="FB1",
            name="Feeding Buffer 1",
            size=5,
            buffer_type="feeding",
            connected_to="task1",
            strategy_name="SumOfSquaresMethod",
        )

    def test_initialization_validation(self):
        """Test validation during buffer initialization."""
        # Invalid ID
        with self.assertRaises(BufferError):
            Buffer(id=None, name="Invalid Buffer", size=5, buffer_type="project")

        # Invalid name
        with self.assertRaises(BufferError):
            Buffer(id="b1", name="", size=5, buffer_type="project")

        # Invalid size
        with self.assertRaises(BufferError):
            Buffer(id="b1", name="Invalid Size", size=-1, buffer_type="project")

        with self.assertRaises(BufferError):
            Buffer(id="b1", name="Invalid Size", size="5", buffer_type="project")

        # Invalid buffer type
        with self.assertRaises(BufferError):
            Buffer(id="b1", name="Invalid Type", size=5, buffer_type="invalid")

        # Feeding buffer without connected_to
        with self.assertRaises(BufferError):
            Buffer(id="fb1", name="Invalid Feeding", size=5, buffer_type="feeding")

        # Valid buffers
        pb = Buffer(id="pb1", name="Valid Project", size=10, buffer_type="project")
        self.assertEqual(pb.id, "pb1")
        self.assertEqual(pb.size, 10)

        fb = Buffer(
            id="fb1",
            name="Valid Feeding",
            size=5,
            buffer_type="feeding",
            connected_to="task1",
        )
        self.assertEqual(fb.id, "fb1")
        self.assertEqual(fb.connected_to, "task1")

    def test_consumption(self):
        """Test buffer consumption functionality."""
        # Initial state
        self.assertEqual(self.project_buffer.size, 10)
        self.assertEqual(self.project_buffer.remaining_size, 10)
        self.assertEqual(self.project_buffer.get_consumption_percentage(), 0)

        # Consume some buffer
        now = datetime.now()
        consumed = self.project_buffer.consume(3, now, "Task delay")

        # Check consumption
        self.assertEqual(consumed, 3)
        self.assertEqual(self.project_buffer.remaining_size, 7)
        self.assertEqual(self.project_buffer.get_consumption_percentage(), 30)

        # Check history
        self.assertEqual(len(self.project_buffer.consumption_history), 1)
        entry = self.project_buffer.consumption_history[0]
        self.assertEqual(entry["date"], now)
        self.assertEqual(entry["consumed"], 3)
        self.assertEqual(entry["new_remaining"], 7)
        self.assertEqual(entry["reason"], "Task delay")

        # Consume more
        consumed = self.project_buffer.consume(
            4, now + timedelta(days=1), "Further delay"
        )

        # Check updated state
        self.assertEqual(consumed, 4)
        self.assertEqual(self.project_buffer.remaining_size, 3)
        self.assertEqual(self.project_buffer.get_consumption_percentage(), 70)

        # Status should now be "red" (>67% consumed)
        self.assertEqual(self.project_buffer.status, "red")

        # Try consuming negative amount
        with self.assertRaises(BufferError):
            self.project_buffer.consume(-1, now)

        # Consume more than remaining
        consumed = self.project_buffer.consume(
            5, now + timedelta(days=2), "Complete consumption"
        )
        self.assertEqual(consumed, 3)  # Only 3 remained
        self.assertEqual(self.project_buffer.remaining_size, 0)
        self.assertEqual(self.project_buffer.get_consumption_percentage(), 100)

    def test_add_size(self):
        """Test adding to buffer size."""
        # Consume some buffer first
        now = datetime.now()
        self.project_buffer.consume(5, now, "Initial consumption")

        # Add to buffer
        new_size = self.project_buffer.add(
            3, now + timedelta(days=1), "Buffer extension"
        )

        # Check new state
        self.assertEqual(new_size, 13)
        self.assertEqual(self.project_buffer.size, 13)
        self.assertEqual(self.project_buffer.remaining_size, 8)

        # Consumption percentage is now 5/13
        expected_pct = (5 / 13) * 100
        self.assertAlmostEqual(
            self.project_buffer.get_consumption_percentage(), expected_pct, delta=0.1
        )

        # Check history
        self.assertEqual(len(self.project_buffer.consumption_history), 2)
        entry = self.project_buffer.consumption_history[1]
        self.assertEqual(entry["action"], "add")
        self.assertEqual(entry["amount"], 3)

        # Try adding negative amount
        with self.assertRaises(BufferError):
            self.project_buffer.add(-1, now)

    def test_reset(self):
        """Test resetting buffer consumption."""
        # Consume some buffer first
        now = datetime.now()
        self.project_buffer.consume(7, now, "Heavy consumption")

        # Reset buffer
        restored = self.project_buffer.reset(now + timedelta(days=1), "Replanning")

        # Check state after reset
        self.assertEqual(restored, 7)
        self.assertEqual(self.project_buffer.remaining_size, 10)
        self.assertEqual(self.project_buffer.get_consumption_percentage(), 0)
        self.assertEqual(self.project_buffer.status, "green")

        # Check history
        self.assertEqual(len(self.project_buffer.consumption_history), 2)
        entry = self.project_buffer.consumption_history[1]
        self.assertEqual(entry["action"], "reset")
        self.assertEqual(entry["restored"], 7)

    def test_date_functions(self):
        """Test date-related functionality."""
        # Set dates
        start_date = datetime(2025, 4, 1)
        end_date = datetime(2025, 4, 11)  # 10 days later

        self.project_buffer.start_date = start_date
        self.project_buffer.end_date = end_date

        # Get effective dates (should be same as original if no new dates)
        self.assertEqual(self.project_buffer.get_effective_start_date(), start_date)
        self.assertEqual(self.project_buffer.get_effective_end_date(), end_date)

        # Set new dates
        new_start = datetime(2025, 4, 5)
        new_end = datetime(2025, 4, 15)

        self.project_buffer.new_start_date = new_start
        self.project_buffer.new_end_date = new_end

        # Get effective dates (should be new dates now)
        self.assertEqual(self.project_buffer.get_effective_start_date(), new_start)
        self.assertEqual(self.project_buffer.get_effective_end_date(), new_end)

    def test_notes(self):
        """Test notes functionality."""
        # Add notes
        now = datetime.now()

        note1 = self.project_buffer.add_note("First note", now - timedelta(days=2))
        note2 = self.project_buffer.add_note("Second note", now - timedelta(days=1))
        note3 = self.project_buffer.add_note("Today's note", now)

        # Check note structure
        self.assertEqual(note1["text"], "First note")
        self.assertEqual(note1["date"], now - timedelta(days=2))

        # Get all notes
        all_notes = self.project_buffer.get_notes()
        self.assertEqual(len(all_notes), 3)

        # Filter by date
        recent_notes = self.project_buffer.get_notes(start_date=now - timedelta(days=1))
        self.assertEqual(len(recent_notes), 2)
        self.assertEqual(recent_notes[0]["text"], "Second note")

        old_notes = self.project_buffer.get_notes(end_date=now - timedelta(days=1))
        self.assertEqual(len(old_notes), 2)
        self.assertEqual(old_notes[1]["text"], "Second note")

        # Test validation
        with self.assertRaises(BufferError):
            self.project_buffer.add_note(123)  # Not a string

    def test_flow_data(self):
        """Test cumulative flow data generation."""
        # Set dates and consume buffer over time
        now = datetime.now()
        start_date = now - timedelta(days=10)

        # Record consumption at various points
        self.project_buffer.consume(2, start_date + timedelta(days=2), "Initial delay")
        self.project_buffer.consume(1, start_date + timedelta(days=4), "Small delay")
        self.project_buffer.consume(4, start_date + timedelta(days=7), "Major delay")

        # Get flow data
        flow_data = self.project_buffer.get_cumulative_flow_data(start_date, now)

        # Check data structure
        self.assertEqual(len(flow_data["dates"]), 11)  # 10 days + today
        self.assertEqual(len(flow_data["remaining"]), 11)
        self.assertEqual(len(flow_data["consumed"]), 11)
        self.assertEqual(len(flow_data["status"]), 11)

        # Check key values
        # Day 0: 10 remaining, 0 consumed
        self.assertEqual(flow_data["remaining"][0], 10)
        self.assertEqual(flow_data["consumed"][0], 0)

        # Day 2: 8 remaining, 2 consumed
        self.assertEqual(flow_data["remaining"][2], 8)
        self.assertEqual(flow_data["consumed"][2], 2)

        # Day 7: 3 remaining, 7 consumed
        self.assertEqual(flow_data["remaining"][7], 3)
        self.assertEqual(flow_data["consumed"][7], 7)

        # Status should change from green to yellow to red
        self.assertEqual(flow_data["status"][0], "green")
        self.assertEqual(flow_data["status"][7], "red")

    def test_fever_chart_data(self):
        """Test fever chart data generation."""
        # Consume some buffer
        now = datetime.now()
        self.project_buffer.consume(4, now, "40% consumption")

        # Get fever chart data at 50% project completion
        fever_data = self.project_buffer.get_fever_chart_data(50)

        # Check data structure
        self.assertEqual(fever_data["current_point"]["project_completion"], 50)
        self.assertEqual(fever_data["current_point"]["buffer_consumption"], 40)
        self.assertEqual(fever_data["zone"], "yellow")
        self.assertEqual(fever_data["performance_ratio"], 50 / 40)  # 1.25

        # Check history points
        self.assertEqual(len(fever_data["history_points"]), 1)

    def test_serialization(self):
        """Test to_dict and from_dict methods."""
        # Set up a complex buffer state
        now = datetime.now()

        self.project_buffer.start_date = now - timedelta(days=10)
        self.project_buffer.end_date = now + timedelta(days=10)

        self.project_buffer.consume(3, now - timedelta(days=5), "First consumption")
        self.project_buffer.consume(3, now, "Second consumption")
        self.project_buffer.add_note("Important note", now)

        # Convert to dictionary
        buffer_dict = self.project_buffer.to_dict()

        # Verify key attributes
        self.assertEqual(buffer_dict["id"], "PB")
        self.assertEqual(buffer_dict["name"], "Project Buffer")
        self.assertEqual(buffer_dict["size"], 10)
        self.assertEqual(buffer_dict["buffer_type"], "project")
        self.assertEqual(buffer_dict["remaining_size"], 4)
        self.assertEqual(buffer_dict["status"], "yellow")

        # Verify dates
        self.assertEqual(buffer_dict["start_date"], self.project_buffer.start_date)
        self.assertEqual(buffer_dict["end_date"], self.project_buffer.end_date)

        # Verify consumption history is included
        self.assertIn("consumption_history", buffer_dict)
        self.assertEqual(len(buffer_dict["consumption_history"]), 2)

        # Create new buffer from dictionary
        new_buffer = Buffer.from_dict(buffer_dict)

        # Verify attributes match
        self.assertEqual(new_buffer.id, self.project_buffer.id)
        self.assertEqual(new_buffer.name, self.project_buffer.name)
        self.assertEqual(new_buffer.size, self.project_buffer.size)
        self.assertEqual(new_buffer.buffer_type, self.project_buffer.buffer_type)
        self.assertEqual(new_buffer.remaining_size, self.project_buffer.remaining_size)
        self.assertEqual(new_buffer.status, self.project_buffer.status)

    def test_buffer_cfd_with_none_dates(self):
        """Test generating cumulative flow data with None dates and empty history."""
        # Create a buffer with no consumption history
        buffer = Buffer(
            id="test_buffer", name="Test Buffer", size=10, buffer_type="project"
        )

        # Test with no dates set
        cfd = buffer.get_cumulative_flow_data()

        # Should return valid data structure even with no dates
        self.assertIn("dates", cfd)
        self.assertIn("remaining", cfd)
        self.assertIn("consumed", cfd)
        self.assertIn("status", cfd)

        # Test with only start_date set
        buffer.start_date = datetime.now() - timedelta(days=5)
        cfd = buffer.get_cumulative_flow_data()

        # Should have at least 5 days of data
        self.assertGreaterEqual(len(cfd["dates"]), 5)

        # Test with consumption history but no end_date
        now = datetime.now()
        buffer.consume(2, now - timedelta(days=3), "Test consumption")
        cfd = buffer.get_cumulative_flow_data()

        # Should include the consumption
        self.assertEqual(cfd["consumed"][-1], 2)

        # Test with None values in consumption history (shouldn't happen normally)
        buffer.consumption_history.append(
            {
                "date": None,  # Invalid date
                "consumed": 1,
                "old_remaining": 8,
                "new_remaining": 7,
            }
        )

        # Should still work without errors
        try:
            cfd = buffer.get_cumulative_flow_data()
            # Success if no exception raised
            self.assertTrue(True)
        except TypeError:
            self.fail(
                "get_cumulative_flow_data raised TypeError with None date in history"
            )


if __name__ == "__main__":
    unittest.main()
