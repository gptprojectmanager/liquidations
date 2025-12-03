"""Tests for DBSCAN clustering module.

TDD Mode: Tests written BEFORE implementation per constitution §2.
"""

import pytest

# =============================================================================
# Phase 2: Model Tests (TDD RED - T005-T009)
# =============================================================================


class TestClusterParameters:
    """Tests for ClusterParameters model validation (T005)."""

    def test_default_values(self):
        """ClusterParameters should have correct defaults."""
        from src.clustering.models import ClusterParameters

        params = ClusterParameters()
        assert params.epsilon == 0.1
        assert params.min_samples == 3
        assert params.auto_tune is True
        assert params.distance_metric == "euclidean"

    def test_epsilon_validation_within_range(self):
        """Epsilon must be in [0.01, 1.0]."""
        from src.clustering.models import ClusterParameters

        # Valid values
        params = ClusterParameters(epsilon=0.01)
        assert params.epsilon == 0.01

        params = ClusterParameters(epsilon=1.0)
        assert params.epsilon == 1.0

        params = ClusterParameters(epsilon=0.5)
        assert params.epsilon == 0.5

    def test_epsilon_validation_out_of_range(self):
        """Epsilon outside [0.01, 1.0] should raise ValueError."""
        from pydantic import ValidationError

        from src.clustering.models import ClusterParameters

        with pytest.raises(ValidationError):
            ClusterParameters(epsilon=0.005)

        with pytest.raises(ValidationError):
            ClusterParameters(epsilon=1.5)

    def test_epsilon_rounding(self):
        """Epsilon should be rounded to 4 decimal places."""
        from src.clustering.models import ClusterParameters

        params = ClusterParameters(epsilon=0.123456)
        assert params.epsilon == 0.1235

    def test_min_samples_validation(self):
        """Min samples must be in [2, 10]."""
        from pydantic import ValidationError

        from src.clustering.models import ClusterParameters

        # Valid
        params = ClusterParameters(min_samples=2)
        assert params.min_samples == 2

        params = ClusterParameters(min_samples=10)
        assert params.min_samples == 10

        # Invalid
        with pytest.raises(ValidationError):
            ClusterParameters(min_samples=1)

        with pytest.raises(ValidationError):
            ClusterParameters(min_samples=11)

    def test_distance_metric_literal(self):
        """Distance metric must be euclidean or manhattan."""
        from pydantic import ValidationError

        from src.clustering.models import ClusterParameters

        params = ClusterParameters(distance_metric="euclidean")
        assert params.distance_metric == "euclidean"

        params = ClusterParameters(distance_metric="manhattan")
        assert params.distance_metric == "manhattan"

        with pytest.raises(ValidationError):
            ClusterParameters(distance_metric="cosine")


class TestLiquidationCluster:
    """Tests for LiquidationCluster computed properties (T006)."""

    def test_cluster_creation(self):
        """LiquidationCluster should create with required fields."""
        from src.clustering.models import LiquidationCluster

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.72,
        )
        assert cluster.cluster_id == 0
        assert cluster.price_min == 94500.0
        assert cluster.price_max == 95200.0

    def test_price_spread_computed(self):
        """Price spread should be computed as price_max - price_min."""
        from src.clustering.models import LiquidationCluster

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.72,
        )
        assert cluster.price_spread == 700.0

    def test_avg_volume_per_level_computed(self):
        """Avg volume per level should be total_volume / level_count."""
        from src.clustering.models import LiquidationCluster

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.72,
        )
        assert cluster.avg_volume_per_level == pytest.approx(333333.33, rel=0.01)

    def test_zone_strength_critical(self):
        """Zone strength should be critical for high density and level count."""
        from src.clustering.models import LiquidationCluster

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.75,
        )
        assert cluster.zone_strength == "critical"

    def test_zone_strength_significant(self):
        """Zone strength should be significant for medium density/count."""
        from src.clustering.models import LiquidationCluster

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=1000000.0,
            level_count=6,
            density=0.5,
        )
        assert cluster.zone_strength == "significant"

    def test_zone_strength_minor(self):
        """Zone strength should be minor for low density and count."""
        from src.clustering.models import LiquidationCluster

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=100000.0,
            level_count=3,
            density=0.3,
        )
        assert cluster.zone_strength == "minor"


class TestNoisePoint:
    """Tests for NoisePoint model validation (T007)."""

    def test_noise_point_creation(self):
        """NoisePoint should create with required fields."""
        from src.clustering.models import NoisePoint

        noise = NoisePoint(price_level=120000.0, volume=50000.0, distance_to_nearest=0.85)
        assert noise.price_level == 120000.0
        assert noise.volume == 50000.0
        assert noise.distance_to_nearest == 0.85

    def test_volume_validation(self):
        """Volume must be >= 0."""
        from pydantic import ValidationError

        from src.clustering.models import NoisePoint

        # Valid
        noise = NoisePoint(price_level=120000.0, volume=0.0, distance_to_nearest=0.85)
        assert noise.volume == 0.0

        # Invalid
        with pytest.raises(ValidationError):
            NoisePoint(price_level=120000.0, volume=-1.0, distance_to_nearest=0.85)

    def test_distance_validation(self):
        """Distance to nearest must be >= 0."""
        from pydantic import ValidationError

        from src.clustering.models import NoisePoint

        # Valid
        noise = NoisePoint(price_level=120000.0, volume=50000.0, distance_to_nearest=0.0)
        assert noise.distance_to_nearest == 0.0

        # Invalid
        with pytest.raises(ValidationError):
            NoisePoint(price_level=120000.0, volume=50000.0, distance_to_nearest=-0.1)


class TestClusterMetadata:
    """Tests for ClusterMetadata computation (T008)."""

    def test_metadata_creation(self):
        """ClusterMetadata should create with required fields."""
        from src.clustering.models import ClusterMetadata, ClusterParameters

        params = ClusterParameters()
        metadata = ClusterMetadata(
            symbol="BTCUSDT",
            timeframe_minutes=30,
            total_points=523,
            cluster_count=7,
            noise_count=12,
            parameters_used=params,
            computation_ms=145.3,
            auto_tuned=True,
        )
        assert metadata.symbol == "BTCUSDT"
        assert metadata.total_points == 523
        assert metadata.cluster_count == 7

    def test_timestamp_auto_generated(self):
        """Timestamp should be auto-generated if not provided."""
        from datetime import datetime

        from src.clustering.models import ClusterMetadata, ClusterParameters

        params = ClusterParameters()
        metadata = ClusterMetadata(
            symbol="BTCUSDT",
            timeframe_minutes=30,
            total_points=523,
            cluster_count=7,
            noise_count=12,
            parameters_used=params,
            computation_ms=145.3,
            auto_tuned=True,
        )
        assert isinstance(metadata.timestamp, datetime)


class TestClusteringResult:
    """Tests for ClusteringResult serialization (T009)."""

    def test_result_creation(self):
        """ClusteringResult should create with all components."""
        from src.clustering.models import (
            ClusteringResult,
            ClusterMetadata,
            ClusterParameters,
            LiquidationCluster,
            NoisePoint,
        )

        params = ClusterParameters()
        metadata = ClusterMetadata(
            symbol="BTCUSDT",
            timeframe_minutes=30,
            total_points=100,
            cluster_count=2,
            noise_count=5,
            parameters_used=params,
            computation_ms=50.0,
            auto_tuned=True,
        )

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.72,
        )

        noise = NoisePoint(price_level=120000.0, volume=50000.0, distance_to_nearest=0.85)

        result = ClusteringResult(clusters=[cluster], noise_points=[noise], metadata=metadata)
        assert len(result.clusters) == 1
        assert len(result.noise_points) == 1
        assert result.fallback_used is False

    def test_coverage_ratio_computed(self):
        """Coverage ratio should be clustered points / total points."""
        from src.clustering.models import (
            ClusteringResult,
            ClusterMetadata,
            ClusterParameters,
            LiquidationCluster,
        )

        params = ClusterParameters()
        metadata = ClusterMetadata(
            symbol="BTCUSDT",
            timeframe_minutes=30,
            total_points=100,
            cluster_count=1,
            noise_count=0,
            parameters_used=params,
            computation_ms=50.0,
            auto_tuned=True,
        )

        cluster = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.72,
        )

        result = ClusteringResult(clusters=[cluster], metadata=metadata)
        assert result.coverage_ratio == 0.45

    def test_total_clustered_volume_computed(self):
        """Total clustered volume should be sum of all cluster volumes."""
        from src.clustering.models import (
            ClusteringResult,
            ClusterMetadata,
            ClusterParameters,
            LiquidationCluster,
        )

        params = ClusterParameters()
        metadata = ClusterMetadata(
            symbol="BTCUSDT",
            timeframe_minutes=30,
            total_points=100,
            cluster_count=2,
            noise_count=0,
            parameters_used=params,
            computation_ms=50.0,
            auto_tuned=True,
        )

        cluster1 = LiquidationCluster(
            cluster_id=0,
            price_min=94500.0,
            price_max=95200.0,
            centroid_price=94850.0,
            total_volume=15000000.0,
            level_count=45,
            density=0.72,
        )

        cluster2 = LiquidationCluster(
            cluster_id=1,
            price_min=96000.0,
            price_max=96800.0,
            centroid_price=96400.0,
            total_volume=8000000.0,
            level_count=28,
            density=0.55,
        )

        result = ClusteringResult(clusters=[cluster1, cluster2], metadata=metadata)
        assert result.total_clustered_volume == 23000000.0


# =============================================================================
# Phase 3: Service Tests (TDD RED - T015-T018)
# =============================================================================


class TestClusteringService:
    """Tests for ClusteringService (T015-T018)."""

    def test_single_dense_cluster_detection(self):
        """Service should detect a single dense cluster (T015)."""
        from src.clustering.models import ClusterParameters
        from src.clustering.service import ClusteringService

        # Arrange: Dense cluster of liquidations around 95000
        liquidations = [
            {"price": 94900.0, "volume": 1000000.0},
            {"price": 94950.0, "volume": 1200000.0},
            {"price": 95000.0, "volume": 1500000.0},
            {"price": 95050.0, "volume": 1100000.0},
            {"price": 95100.0, "volume": 900000.0},
        ]

        service = ClusteringService()
        # Use epsilon=0.6 to capture normalized feature space distances
        params = ClusterParameters(epsilon=0.6, min_samples=3, auto_tune=False)

        # Act
        result = service.cluster_liquidations(liquidations, "BTCUSDT", 30, params)

        # Assert
        assert result.metadata.cluster_count == 1
        assert len(result.clusters) == 1
        assert result.clusters[0].level_count == 5
        assert result.clusters[0].price_min <= 94900.0
        assert result.clusters[0].price_max >= 95100.0
        assert result.clusters[0].total_volume == 5700000.0

    def test_multiple_cluster_detection(self):
        """Service should detect multiple distinct clusters (T016)."""
        from src.clustering.models import ClusterParameters
        from src.clustering.service import ClusteringService

        # Arrange: Two separate clusters
        liquidations = [
            # Cluster 1: around 94000
            {"price": 93900.0, "volume": 500000.0},
            {"price": 94000.0, "volume": 600000.0},
            {"price": 94100.0, "volume": 550000.0},
            # Cluster 2: around 96000 (far from cluster 1)
            {"price": 95900.0, "volume": 800000.0},
            {"price": 96000.0, "volume": 900000.0},
            {"price": 96100.0, "volume": 850000.0},
        ]

        service = ClusteringService()
        # Use epsilon=0.4 to separate two distinct clusters
        params = ClusterParameters(epsilon=0.4, min_samples=2, auto_tune=False)

        # Act
        result = service.cluster_liquidations(liquidations, "BTCUSDT", 30, params)

        # Assert
        assert result.metadata.cluster_count == 2
        assert len(result.clusters) == 2
        assert result.metadata.total_points == 6

    def test_noise_point_handling(self):
        """Service should identify noise points (outliers) correctly (T017)."""
        from src.clustering.models import ClusterParameters
        from src.clustering.service import ClusteringService

        # Arrange: Dense cluster + isolated outlier
        liquidations = [
            # Dense cluster around 95000
            {"price": 94900.0, "volume": 1000000.0},
            {"price": 94950.0, "volume": 1200000.0},
            {"price": 95000.0, "volume": 1500000.0},
            {"price": 95050.0, "volume": 1100000.0},
            # Isolated outlier far away
            {"price": 120000.0, "volume": 50000.0},
        ]

        service = ClusteringService()
        # Use epsilon=0.6 to form cluster, outlier will be noise
        params = ClusterParameters(epsilon=0.6, min_samples=3, auto_tune=False)

        # Act
        result = service.cluster_liquidations(liquidations, "BTCUSDT", 30, params)

        # Assert
        assert result.metadata.cluster_count == 1
        assert result.metadata.noise_count == 1
        assert len(result.noise_points) == 1
        assert result.noise_points[0].price_level == 120000.0
        assert result.noise_points[0].volume == 50000.0
        assert result.noise_points[0].distance_to_nearest > 0

    def test_empty_input_returns_empty_result(self):
        """Service should handle empty input gracefully (T018)."""
        from src.clustering.models import ClusterParameters
        from src.clustering.service import ClusteringService

        # Arrange
        liquidations = []
        service = ClusteringService()
        params = ClusterParameters()

        # Act
        result = service.cluster_liquidations(liquidations, "BTCUSDT", 30, params)

        # Assert
        assert result.metadata.cluster_count == 0
        assert result.metadata.noise_count == 0
        assert len(result.clusters) == 0
        assert len(result.noise_points) == 0
        assert result.metadata.total_points == 0
        assert result.fallback_used is False


# =============================================================================
# Phase 5: Caching Tests (TDD RED - T034-T035)
# =============================================================================


class TestClusterCaching:
    """Tests for cluster caching behavior (T034-T035)."""

    def test_cluster_cache_with_ttl(self):
        """Cache should store results and expire after TTL (T034)."""
        import time

        from src.clustering.cache import ClusterCache


        # Arrange
        cache = ClusterCache(ttl_seconds=2)  # 2 second TTL
        cache_key = "BTCUSDT_30_test"
        mock_result = {"clusters": [], "metadata": {}}

        # Act - Set cache
        cache.set(cache_key, mock_result)

        # Assert - Should be cached immediately
        cached = cache.get(cache_key)
        assert cached is not None
        assert cached == mock_result

        # Wait for TTL to expire
        time.sleep(2.1)

        # Assert - Cache should be expired
        expired = cache.get(cache_key)
        assert expired is None

    def test_cache_invalidation_on_data_refresh(self):
        """Cache should be invalidated when data is refreshed (T035)."""
        from src.clustering.cache import ClusterCache

        # Arrange
        cache = ClusterCache(ttl_seconds=60)
        cache_key = "BTCUSDT_30_test"
        old_result = {"clusters": [], "version": 1}
        new_result = {"clusters": [{"cluster_id": 0}], "version": 2}

        # Act - Set initial cache
        cache.set(cache_key, old_result)
        assert cache.get(cache_key) == old_result

        # Invalidate cache (simulating data refresh)
        cache.invalidate(cache_key)

        # Assert - Cache should be cleared
        assert cache.get(cache_key) is None

        # Set new data
        cache.set(cache_key, new_result)
        assert cache.get(cache_key) == new_result

    def test_cache_key_generation(self):
        """Cache keys should be unique per symbol/timeframe/params."""
        from src.clustering.cache import ClusterCache

        from src.clustering.models import ClusterParameters

        # Arrange
        cache = ClusterCache(ttl_seconds=60)
        params1 = ClusterParameters(epsilon=0.1, min_samples=3)
        params2 = ClusterParameters(epsilon=0.2, min_samples=3)

        # Act - Generate keys
        key1 = cache.generate_key("BTCUSDT", 30, params1)
        key2 = cache.generate_key("BTCUSDT", 30, params2)
        key3 = cache.generate_key("ETHUSDT", 30, params1)
        key4 = cache.generate_key("BTCUSDT", 15, params1)

        # Assert - Keys should be different
        assert key1 != key2  # Different params
        assert key1 != key3  # Different symbol
        assert key1 != key4  # Different timeframe

        # Same inputs should generate same key
        key1_dup = cache.generate_key("BTCUSDT", 30, params1)
        assert key1 == key1_dup


# =============================================================================
# Phase 6: Performance Tests (T040-T041)
# =============================================================================


class TestClusteringPerformance:
    """Performance benchmark tests (T040-T041)."""

    pass  # Tests to be implemented
