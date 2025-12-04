"""
Tests for queue_config.py - Queue overflow policies.

Tests cover:
- Overflow policy types (REJECT, DROP_OLDEST, DROP_NEWEST)
- Queue size validation
- Policy behavior
"""

import pytest

from src.validation.queue_config import OverflowPolicy, QueueConfig


class TestQueueConfig:
    """Test QueueConfig functionality."""

    def test_initialization_with_defaults(self):
        """QueueConfig should initialize with default values."""
        # Act
        config = QueueConfig()

        # Assert
        assert config.max_size == 10
        assert config.overflow_policy == OverflowPolicy.REJECT

    def test_initialization_with_custom_values(self):
        """QueueConfig should accept custom configuration."""
        # Act
        config = QueueConfig(
            max_size=20,
            overflow_policy=OverflowPolicy.DROP_OLDEST,
        )

        # Assert
        assert config.max_size == 20
        assert config.overflow_policy == OverflowPolicy.DROP_OLDEST

    def test_should_accept_returns_true_when_below_max(self):
        """should_accept should return True when queue not full."""
        # Arrange
        config = QueueConfig(max_size=5)

        # Act
        result = config.should_accept(current_size=3)

        # Assert
        assert result is True

    def test_should_accept_with_reject_policy_returns_false_when_full(self):
        """should_accept with REJECT should return False when full."""
        # Arrange
        config = QueueConfig(max_size=5, overflow_policy=OverflowPolicy.REJECT)

        # Act
        result = config.should_accept(current_size=5)

        # Assert
        assert result is False

    def test_should_accept_with_drop_oldest_returns_true_when_full(self):
        """should_accept with DROP_OLDEST should return True when full."""
        # Arrange
        config = QueueConfig(max_size=5, overflow_policy=OverflowPolicy.DROP_OLDEST)

        # Act
        result = config.should_accept(current_size=5)

        # Assert
        assert result is True

    def test_should_accept_with_drop_newest_returns_true_when_full(self):
        """should_accept with DROP_NEWEST should return True when full."""
        # Arrange
        config = QueueConfig(max_size=5, overflow_policy=OverflowPolicy.DROP_NEWEST)

        # Act
        result = config.should_accept(current_size=5)

        # Assert
        assert result is True

    def test_handle_overflow_with_drop_oldest_removes_first_items(self):
        """handle_overflow with DROP_OLDEST should remove oldest items."""
        # Arrange
        config = QueueConfig(max_size=3, overflow_policy=OverflowPolicy.DROP_OLDEST)
        items = ["item-1", "item-2", "item-3", "item-4", "item-5"]

        # Act
        result = config.handle_overflow(items)

        # Assert
        assert len(result) == 3
        assert result == ["item-3", "item-4", "item-5"]  # Oldest removed

    def test_handle_overflow_with_drop_newest_removes_last_items(self):
        """handle_overflow with DROP_NEWEST should keep oldest items."""
        # Arrange
        config = QueueConfig(max_size=3, overflow_policy=OverflowPolicy.DROP_NEWEST)
        items = ["item-1", "item-2", "item-3", "item-4", "item-5"]

        # Act
        result = config.handle_overflow(items)

        # Assert
        assert len(result) == 3
        assert result == ["item-1", "item-2", "item-3"]  # Newest removed

    def test_handle_overflow_with_reject_returns_unchanged(self):
        """handle_overflow with REJECT should return items unchanged."""
        # Arrange
        config = QueueConfig(max_size=3, overflow_policy=OverflowPolicy.REJECT)
        items = ["item-1", "item-2", "item-3"]

        # Act
        result = config.handle_overflow(items)

        # Assert
        assert result == items

    def test_max_size_validation_minimum(self):
        """max_size should enforce minimum value."""
        # Act/Assert
        with pytest.raises(ValueError):
            QueueConfig(max_size=0)

    def test_max_size_validation_maximum(self):
        """max_size should enforce maximum value."""
        # Act/Assert
        with pytest.raises(ValueError):
            QueueConfig(max_size=100)

    def test_overflow_policy_enum_values(self):
        """OverflowPolicy should have expected values."""
        # Assert
        assert OverflowPolicy.REJECT.value == "reject"
        assert OverflowPolicy.DROP_OLDEST.value == "drop_oldest"
        assert OverflowPolicy.DROP_NEWEST.value == "drop_newest"

    def test_default_constants(self):
        """QueueConfig should have expected default constants."""
        # Assert
        assert QueueConfig.DEFAULT_MAX_SIZE == 10
        assert QueueConfig.MIN_SIZE == 1
        assert QueueConfig.MAX_SIZE == 50


class TestOverflowPolicy:
    """Test OverflowPolicy enum."""

    def test_reject_policy_value(self):
        """REJECT policy should have correct value."""
        # Assert
        assert OverflowPolicy.REJECT == "reject"

    def test_drop_oldest_policy_value(self):
        """DROP_OLDEST policy should have correct value."""
        # Assert
        assert OverflowPolicy.DROP_OLDEST == "drop_oldest"

    def test_drop_newest_policy_value(self):
        """DROP_NEWEST policy should have correct value."""
        # Assert
        assert OverflowPolicy.DROP_NEWEST == "drop_newest"

    def test_policy_comparison(self):
        """Policies should be comparable."""
        # Act
        policy1 = OverflowPolicy.REJECT
        policy2 = OverflowPolicy.REJECT
        policy3 = OverflowPolicy.DROP_OLDEST

        # Assert
        assert policy1 == policy2
        assert policy1 != policy3
