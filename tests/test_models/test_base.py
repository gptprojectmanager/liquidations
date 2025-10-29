"""Tests for abstract base liquidation model."""

import pytest
from src.liquidationheatmap.models.base import AbstractLiquidationModel


class TestAbstractLiquidationModel:
    """Tests for AbstractLiquidationModel interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AbstractLiquidationModel cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AbstractLiquidationModel()
