"""
Tests for model_selector.py - Multi-model registration and selection.

Tests cover:
- Model registration
- Model validation
- Default model handling
- Model enable/disable
"""


from src.validation.model_selector import ModelInfo, ModelSelector, get_model_selector


class TestModelSelector:
    """Test ModelSelector functionality."""

    def test_initialization_registers_default_model(self):
        """ModelSelector should register default model on init."""
        # Act
        selector = ModelSelector()

        # Assert
        assert selector.list_models() != []
        assert selector.get_default() is not None

    def test_register_model_adds_new_model(self):
        """register_model should add model to registry."""
        # Arrange
        selector = ModelSelector()

        # Act
        result = selector.register_model(
            model_id="custom_model_v1",
            model_name="Custom Model",
            model_version="1.0.0",
            description="Test model",
        )

        # Assert
        assert result is True
        models = selector.list_models()
        assert any(m.model_id == "custom_model_v1" for m in models)

    def test_register_model_rejects_duplicate_id(self):
        """register_model should reject duplicate model IDs."""
        # Arrange
        selector = ModelSelector()
        selector.register_model(
            model_id="test_model",
            model_name="Test",
            model_version="1.0",
            description="Test",
        )

        # Act
        result = selector.register_model(
            model_id="test_model",  # Duplicate
            model_name="Test 2",
            model_version="2.0",
            description="Test",
        )

        # Assert
        assert result is False

    def test_validate_model_id_returns_true_for_existing_model(self):
        """validate_model_id should return True for existing model."""
        # Arrange
        selector = ModelSelector()
        selector.register_model(
            model_id="valid_model",
            model_name="Valid",
            model_version="1.0",
            description="Test",
        )

        # Act
        result = selector.validate_model_id("valid_model")

        # Assert
        assert result is True

    def test_validate_model_id_returns_false_for_nonexistent_model(self):
        """validate_model_id should return False for nonexistent model."""
        # Arrange
        selector = ModelSelector()

        # Act
        result = selector.validate_model_id("nonexistent_model")

        # Assert
        assert result is False

    def test_validate_model_id_respects_enabled_only_flag(self):
        """validate_model_id should filter by enabled status when requested."""
        # Arrange
        selector = ModelSelector()
        selector.register_model(
            model_id="disabled_model",
            model_name="Disabled",
            model_version="1.0",
            description="Test",
            enabled=False,
        )

        # Act
        result_all = selector.validate_model_id("disabled_model", enabled_only=False)
        result_enabled = selector.validate_model_id("disabled_model", enabled_only=True)

        # Assert
        assert result_all is True  # Exists regardless of status
        assert result_enabled is False  # Not enabled

    def test_get_model_returns_model_info(self):
        """get_model should return ModelInfo for existing model."""
        # Arrange
        selector = ModelSelector()
        selector.register_model(
            model_id="test_model",
            model_name="Test Model",
            model_version="1.5.0",
            description="Test description",
        )

        # Act
        model = selector.get_model("test_model")

        # Assert
        assert model is not None
        assert model.model_id == "test_model"
        assert model.model_name == "Test Model"
        assert model.model_version == "1.5.0"

    def test_get_model_returns_none_for_nonexistent(self):
        """get_model should return None for nonexistent model."""
        # Arrange
        selector = ModelSelector()

        # Act
        model = selector.get_model("nonexistent")

        # Assert
        assert model is None

    def test_list_models_returns_all_models(self):
        """list_models should return all registered models."""
        # Arrange
        selector = ModelSelector()
        selector.register_model("model1", "Model 1", "1.0", "Test")
        selector.register_model("model2", "Model 2", "2.0", "Test")

        # Act
        models = selector.list_models()

        # Assert
        assert len(models) >= 2  # At least our 2 + default
        ids = [m.model_id for m in models]
        assert "model1" in ids
        assert "model2" in ids

    def test_list_models_filters_by_enabled(self):
        """list_models should filter by enabled status when requested."""
        # Arrange
        selector = ModelSelector()
        selector.register_model("enabled_model", "Enabled", "1.0", "Test", enabled=True)
        selector.register_model("disabled_model", "Disabled", "1.0", "Test", enabled=False)

        # Act
        all_models = selector.list_models(enabled_only=False)
        enabled_models = selector.list_models(enabled_only=True)

        # Assert
        all_ids = [m.model_id for m in all_models]
        enabled_ids = [m.model_id for m in enabled_models]

        assert "enabled_model" in all_ids
        assert "disabled_model" in all_ids
        assert "enabled_model" in enabled_ids
        assert "disabled_model" not in enabled_ids

    def test_set_default_model(self):
        """set_default should set default model."""
        # Arrange
        selector = ModelSelector()
        selector.register_model("new_default", "New Default", "1.0", "Test")

        # Act
        result = selector.set_default("new_default")

        # Assert
        assert result is True
        assert selector.get_default() == "new_default"

    def test_set_default_rejects_nonexistent_model(self):
        """set_default should reject nonexistent model."""
        # Arrange
        selector = ModelSelector()

        # Act
        result = selector.set_default("nonexistent")

        # Assert
        assert result is False

    def test_disable_model_sets_enabled_to_false(self):
        """disable_model should set enabled flag to False."""
        # Arrange
        selector = ModelSelector()
        selector.register_model("test_model", "Test", "1.0", "Test", enabled=True)

        # Act
        result = selector.disable_model("test_model")

        # Assert
        assert result is True
        model = selector.get_model("test_model")
        assert model.enabled is False

    def test_enable_model_sets_enabled_to_true(self):
        """enable_model should set enabled flag to True."""
        # Arrange
        selector = ModelSelector()
        selector.register_model("test_model", "Test", "1.0", "Test", enabled=False)

        # Act
        result = selector.enable_model("test_model")

        # Assert
        assert result is True
        model = selector.get_model("test_model")
        assert model.enabled is True

    def test_get_model_selector_returns_singleton(self):
        """get_model_selector should return same instance."""
        # Act
        selector1 = get_model_selector()
        selector2 = get_model_selector()

        # Assert
        assert selector1 is selector2


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_model_info_creation(self):
        """ModelInfo should be created with all fields."""
        # Act
        model = ModelInfo(
            model_id="test_id",
            model_name="Test Model",
            model_version="2.0.1",
            description="Test description",
            enabled=True,
        )

        # Assert
        assert model.model_id == "test_id"
        assert model.model_name == "Test Model"
        assert model.model_version == "2.0.1"
        assert model.description == "Test description"
        assert model.enabled is True

    def test_model_info_defaults_enabled_to_true(self):
        """ModelInfo should default enabled to True."""
        # Act
        model = ModelInfo(
            model_id="test",
            model_name="Test",
            model_version="1.0",
            description="Test",
        )

        # Assert
        assert model.enabled is True
