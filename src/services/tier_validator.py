"""
Tier configuration validator service.

Validates tier configurations for:
- Mathematical continuity at boundaries
- Logical consistency (ordering, ranges)
- Data integrity (positive rates, valid ranges)
"""

import logging
from decimal import Decimal
from typing import Dict, List, Tuple

from src.config.precision import ZERO
from src.models.margin_tier import MarginTier
from src.models.tier_config import TierConfiguration

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of tier configuration validation."""

    def __init__(self):
        """Initialize validation result."""
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.continuity_checks: Dict[str, bool] = {}

    def add_error(self, message: str):
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False
        logger.error(f"Validation error: {message}")

    def add_warning(self, message: str):
        """Add validation warning."""
        self.warnings.append(message)
        logger.warning(f"Validation warning: {message}")

    def add_continuity_check(self, boundary: str, is_continuous: bool):
        """Record continuity check result."""
        self.continuity_checks[boundary] = is_continuous
        if not is_continuous:
            self.add_error(f"Continuity broken at boundary: {boundary}")

    def __str__(self) -> str:
        """String representation of validation result."""
        if self.is_valid:
            return f"✓ VALID ({len(self.continuity_checks)} boundaries checked)"
        else:
            return f"✗ INVALID - {len(self.errors)} errors, {len(self.warnings)} warnings"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "continuity_checks": self.continuity_checks,
            "total_boundaries_checked": len(self.continuity_checks),
            "continuous_boundaries": sum(1 for c in self.continuity_checks.values() if c),
        }


class TierValidator:
    """
    Validator for tier configurations.

    Performs comprehensive validation including:
    - Range consistency (no gaps, no overlaps)
    - Rate ordering (increasing with tier)
    - Mathematical continuity at boundaries
    - Maintenance amount correctness
    """

    def __init__(self, continuity_threshold: Decimal = Decimal("0.01")):
        """
        Initialize tier validator.

        Args:
            continuity_threshold: Maximum allowed discontinuity in dollars
        """
        self.continuity_threshold = continuity_threshold

    def validate(self, config: TierConfiguration) -> ValidationResult:
        """
        Perform full validation of tier configuration.

        Args:
            config: TierConfiguration to validate

        Returns:
            ValidationResult with detailed findings

        Example:
            >>> validator = TierValidator()
            >>> result = validator.validate(config)
            >>> if not result.is_valid:
            ...     print(f"Errors: {result.errors}")
        """
        result = ValidationResult()

        # Basic structure validation
        self._validate_structure(config, result)

        if not config.tiers:
            result.add_error("No tiers defined in configuration")
            return result

        # Range validation
        self._validate_ranges(config.tiers, result)

        # Rate validation
        self._validate_rates(config.tiers, result)

        # Continuity validation
        self._validate_continuity(config.tiers, result)

        # Maintenance amount validation
        self._validate_maintenance_amounts(config.tiers, result)

        logger.info(f"Validated {config.symbol} v{config.version}: {result}")

        return result

    def _validate_structure(self, config: TierConfiguration, result: ValidationResult):
        """Validate basic structure of configuration."""
        if not config.symbol:
            result.add_error("Symbol is empty")

        if not config.version:
            result.add_error("Version is empty")

        if not config.tiers:
            result.add_error("No tiers defined")

    def _validate_ranges(self, tiers: List[MarginTier], result: ValidationResult):
        """Validate tier ranges for gaps and overlaps."""
        if len(tiers) < 1:
            return

        # Check first tier starts at 0
        if tiers[0].min_notional != ZERO:
            result.add_error(f"First tier should start at 0, got {tiers[0].min_notional}")

        # Check consecutive tiers are adjacent (no gaps or overlaps)
        for i in range(len(tiers) - 1):
            current_max = tiers[i].max_notional
            next_min = tiers[i + 1].min_notional

            if current_max != next_min:
                result.add_error(
                    f"Gap/overlap between tier {i + 1} and {i + 2}: "
                    f"tier {i + 1} ends at {current_max}, "
                    f"tier {i + 2} starts at {next_min}"
                )

        # Check ranges are positive
        for i, tier in enumerate(tiers):
            if tier.max_notional <= tier.min_notional:
                result.add_error(
                    f"Tier {i + 1} has invalid range: {tier.min_notional} to {tier.max_notional}"
                )

    def _validate_rates(self, tiers: List[MarginTier], result: ValidationResult):
        """Validate margin rates are increasing."""
        if len(tiers) < 2:
            return

        for i in range(len(tiers) - 1):
            current_rate = tiers[i].margin_rate
            next_rate = tiers[i + 1].margin_rate

            # Rates should be strictly increasing
            if next_rate <= current_rate:
                result.add_warning(
                    f"Margin rate not increasing from tier {i + 1} to {i + 2}: "
                    f"{current_rate} -> {next_rate}"
                )

            # Check rates are reasonable (between 0 and 100%)
            if not (ZERO < current_rate <= Decimal("1")):
                result.add_error(f"Tier {i + 1} has invalid rate: {current_rate}")

    def _validate_continuity(self, tiers: List[MarginTier], result: ValidationResult):
        """Validate mathematical continuity at tier boundaries."""
        if len(tiers) < 2:
            return

        for i in range(len(tiers) - 1):
            tier1 = tiers[i]
            tier2 = tiers[i + 1]

            boundary = tier1.max_notional

            # Calculate margin from both sides
            margin_left = boundary * tier1.margin_rate - tier1.maintenance_amount
            margin_right = boundary * tier2.margin_rate - tier2.maintenance_amount

            # Check continuity
            difference = abs(margin_left - margin_right)
            is_continuous = difference < self.continuity_threshold

            boundary_label = f"${boundary:,.0f} (T{i + 1}→T{i + 2})"
            result.add_continuity_check(boundary_label, is_continuous)

            if not is_continuous:
                logger.error(
                    f"Discontinuity at {boundary_label}: "
                    f"left=${margin_left}, right=${margin_right}, "
                    f"diff=${difference}"
                )

    def _validate_maintenance_amounts(self, tiers: List[MarginTier], result: ValidationResult):
        """Validate maintenance amounts are correct."""
        if len(tiers) < 1:
            return

        # First tier should have MA = 0
        if tiers[0].maintenance_amount != ZERO:
            result.add_error(f"First tier should have MA = 0, got {tiers[0].maintenance_amount}")

        # Subsequent tiers should follow continuity formula
        # MA[i] = MA[i-1] + boundary * (rate[i] - rate[i-1])
        for i in range(1, len(tiers)):
            prev_tier = tiers[i - 1]
            curr_tier = tiers[i]

            boundary = prev_tier.max_notional
            prev_ma = prev_tier.maintenance_amount
            curr_ma = curr_tier.maintenance_amount

            # Calculate expected MA
            expected_ma = prev_ma + boundary * (curr_tier.margin_rate - prev_tier.margin_rate)

            # Check if actual MA matches expected
            ma_difference = abs(curr_ma - expected_ma)

            if ma_difference > Decimal("0.01"):  # Allow 1 cent tolerance
                result.add_error(
                    f"Tier {i + 1} MA incorrect: "
                    f"expected ${expected_ma}, got ${curr_ma}, "
                    f"difference ${ma_difference}"
                )

    def validate_update(
        self,
        old_config: TierConfiguration,
        new_config: TierConfiguration,
    ) -> Tuple[bool, List[str]]:
        """
        Validate tier configuration update.

        Checks:
        - New configuration is valid
        - Symbol matches
        - Version is different

        Args:
            old_config: Current configuration
            new_config: Proposed new configuration

        Returns:
            Tuple of (is_valid, list of issues)

        Example:
            >>> validator = TierValidator()
            >>> is_valid, issues = validator.validate_update(old_config, new_config)
            >>> if not is_valid:
            ...     print(f"Update rejected: {issues}")
        """
        issues = []

        # Validate new configuration
        new_result = self.validate(new_config)
        if not new_result.is_valid:
            issues.extend([f"New config: {e}" for e in new_result.errors])

        # Check symbol matches
        if old_config.symbol != new_config.symbol:
            issues.append(f"Symbol mismatch: {old_config.symbol} != {new_config.symbol}")

        # Check version is different
        if old_config.version == new_config.version:
            issues.append(f"Version unchanged: {old_config.version}")

        is_valid = len(issues) == 0
        return is_valid, issues


def validate_configuration(config: TierConfiguration) -> ValidationResult:
    """
    Convenience function to validate a tier configuration.

    Args:
        config: TierConfiguration to validate

    Returns:
        ValidationResult

    Example:
        >>> result = validate_configuration(config)
        >>> assert result.is_valid
    """
    validator = TierValidator()
    return validator.validate(config)
