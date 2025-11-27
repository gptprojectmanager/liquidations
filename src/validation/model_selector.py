"""
Model selection for validation runs.

Manages model registration and selection for multi-model validation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.validation.logger import logger


@dataclass
class ModelInfo:
    """Information about a registered model."""

    model_id: str
    model_name: str
    model_version: str
    description: str
    enabled: bool = True
    config_path: Optional[str] = None


class ModelSelector:
    """
    Manages model selection for validation.

    Allows registration and selection of multiple models
    for validation runs.
    """

    def __init__(self):
        """Initialize model selector."""
        self._models: Dict[str, ModelInfo] = {}
        self._default_model: Optional[str] = None

        # Register default model
        self.register_model(
            model_id="liquidation_model_v1",
            model_name="Liquidation Model v1",
            model_version="1.0.0",
            description="Default liquidation heatmap model",
        )
        self.set_default("liquidation_model_v1")

        logger.info("ModelSelector initialized with default model")

    def register_model(
        self,
        model_id: str,
        model_name: str,
        model_version: str,
        description: str,
        enabled: bool = True,
        config_path: Optional[str] = None,
    ) -> bool:
        """
        Register a model for validation.

        Args:
            model_id: Unique model identifier
            model_name: Human-readable model name
            model_version: Model version string
            description: Model description
            enabled: Whether model is enabled for validation
            config_path: Optional path to model config file

        Returns:
            True if registration successful
        """
        if model_id in self._models:
            logger.warning(f"Model {model_id} already registered - updating")

        model_info = ModelInfo(
            model_id=model_id,
            model_name=model_name,
            model_version=model_version,
            description=description,
            enabled=enabled,
            config_path=config_path,
        )

        self._models[model_id] = model_info

        logger.info(
            f"Model registered: {model_id} ({model_name} v{model_version}), enabled={enabled}"
        )

        return True

    def unregister_model(self, model_id: str) -> bool:
        """
        Unregister a model.

        Args:
            model_id: Model ID to unregister

        Returns:
            True if unregistration successful
        """
        if model_id not in self._models:
            logger.warning(f"Model {model_id} not registered")
            return False

        # Check if it's the default
        if self._default_model == model_id:
            logger.warning(f"Unregistering default model {model_id} - clearing default")
            self._default_model = None

        del self._models[model_id]

        logger.info(f"Model unregistered: {model_id}")
        return True

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """
        Get model information.

        Args:
            model_id: Model ID

        Returns:
            ModelInfo if found, None otherwise
        """
        return self._models.get(model_id)

    def list_models(self, enabled_only: bool = False) -> List[ModelInfo]:
        """
        List all registered models.

        Args:
            enabled_only: Only return enabled models

        Returns:
            List of ModelInfo
        """
        models = list(self._models.values())

        if enabled_only:
            models = [m for m in models if m.enabled]

        return models

    def set_default(self, model_id: str) -> bool:
        """
        Set default model for validation.

        Args:
            model_id: Model ID to set as default

        Returns:
            True if successful
        """
        if model_id not in self._models:
            logger.error(f"Cannot set default - model {model_id} not registered")
            return False

        self._default_model = model_id
        logger.info(f"Default model set to: {model_id}")
        return True

    def get_default(self) -> Optional[str]:
        """
        Get default model ID.

        Returns:
            Default model ID, or None if not set
        """
        return self._default_model

    def enable_model(self, model_id: str) -> bool:
        """
        Enable model for validation.

        Args:
            model_id: Model ID to enable

        Returns:
            True if successful
        """
        model = self._models.get(model_id)
        if not model:
            logger.error(f"Cannot enable - model {model_id} not registered")
            return False

        model.enabled = True
        logger.info(f"Model enabled: {model_id}")
        return True

    def disable_model(self, model_id: str) -> bool:
        """
        Disable model for validation.

        Args:
            model_id: Model ID to disable

        Returns:
            True if successful
        """
        model = self._models.get(model_id)
        if not model:
            logger.error(f"Cannot disable - model {model_id} not registered")
            return False

        model.enabled = False
        logger.info(f"Model disabled: {model_id}")
        return True

    def validate_model_id(self, model_id: str, enabled_only: bool = True) -> bool:
        """
        Validate model ID is registered and optionally enabled.

        Args:
            model_id: Model ID to validate
            enabled_only: Only accept enabled models

        Returns:
            True if valid
        """
        model = self._models.get(model_id)

        if not model:
            logger.warning(f"Model validation failed: {model_id} not registered")
            return False

        if enabled_only and not model.enabled:
            logger.warning(f"Model validation failed: {model_id} is disabled")
            return False

        return True

    def get_model_summary(self) -> dict:
        """
        Get summary of all registered models.

        Returns:
            Dict with model statistics
        """
        total = len(self._models)
        enabled = sum(1 for m in self._models.values() if m.enabled)
        disabled = total - enabled

        return {
            "total_models": total,
            "enabled_models": enabled,
            "disabled_models": disabled,
            "default_model": self._default_model,
            "models": [
                {
                    "model_id": m.model_id,
                    "model_name": m.model_name,
                    "model_version": m.model_version,
                    "enabled": m.enabled,
                }
                for m in self._models.values()
            ],
        }


# Global selector instance
_global_selector: Optional[ModelSelector] = None


def get_model_selector() -> ModelSelector:
    """
    Get global model selector instance (singleton).

    Returns:
        ModelSelector instance
    """
    global _global_selector

    if _global_selector is None:
        _global_selector = ModelSelector()

    return _global_selector
