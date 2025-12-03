"""DBSCAN clustering service for liquidation levels.

This module implements the core clustering algorithm using scikit-learn's DBSCAN.
"""

import time
from typing import Dict, List, Tuple

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors

from src.clustering.models import (
    ClusteringResult,
    ClusterMetadata,
    ClusterParameters,
    LiquidationCluster,
    NoisePoint,
)


class ClusteringService:
    """Service for clustering liquidation levels using DBSCAN algorithm."""

    def cluster_liquidations(
        self,
        liquidations: List[Dict[str, float]],
        symbol: str,
        timeframe_minutes: int,
        params: ClusterParameters,
    ) -> ClusteringResult:
        """Cluster liquidation levels into zones (T021).

        Args:
            liquidations: List of dicts with 'price' and 'volume' keys
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            timeframe_minutes: Data timeframe in minutes
            params: DBSCAN clustering parameters

        Returns:
            ClusteringResult with clusters, noise points, and metadata
        """
        start_time = time.perf_counter()

        # Handle empty input
        if not liquidations:
            metadata = ClusterMetadata(
                symbol=symbol,
                timeframe_minutes=timeframe_minutes,
                total_points=0,
                cluster_count=0,
                noise_count=0,
                parameters_used=params,
                computation_ms=0.0,
                auto_tuned=False,
            )
            return ClusteringResult(clusters=[], noise_points=[], metadata=metadata)

        # Prepare features
        features, prices_array = self._prepare_features(liquidations)
        volumes_array = np.array([liq["volume"] for liq in liquidations])

        # Auto-tune epsilon if requested
        epsilon = params.epsilon
        auto_tuned = False
        if params.auto_tune:
            epsilon = self._auto_epsilon(features, params.min_samples)
            auto_tuned = True

        # Run DBSCAN
        dbscan = DBSCAN(
            eps=epsilon,
            min_samples=params.min_samples,
            metric=params.distance_metric,
        )
        labels = dbscan.fit_predict(features)

        # Compute clusters
        clusters = self._compute_clusters(labels, prices_array, volumes_array, features)

        # Compute cluster centers for noise distance calculation
        cluster_centers = {}
        for cluster in clusters:
            cluster_id = cluster.cluster_id
            # Find all points in this cluster
            cluster_mask = labels == cluster_id
            cluster_features = features[cluster_mask]
            # Compute centroid in feature space
            cluster_centers[cluster_id] = np.mean(cluster_features, axis=0)

        # Compute noise points
        noise_points = self._compute_noise(
            labels, prices_array, volumes_array, features, cluster_centers
        )

        # Compute metadata
        computation_ms = (time.perf_counter() - start_time) * 1000
        metadata = ClusterMetadata(
            symbol=symbol,
            timeframe_minutes=timeframe_minutes,
            total_points=len(liquidations),
            cluster_count=len(clusters),
            noise_count=len(noise_points),
            parameters_used=params,
            computation_ms=computation_ms,
            auto_tuned=auto_tuned,
        )

        return ClusteringResult(clusters=clusters, noise_points=noise_points, metadata=metadata)

    def _prepare_features(
        self, liquidations: List[Dict[str, float]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare feature matrix for DBSCAN clustering (T019).

        Normalizes price and log(volume) to [0, 1] range for distance calculation.

        Args:
            liquidations: List of dicts with 'price' and 'volume' keys

        Returns:
            Tuple of (features_2d, prices_array)
        """
        prices = np.array([liq["price"] for liq in liquidations])
        volumes = np.array([liq["volume"] for liq in liquidations])

        # Log-transform volumes to reduce skewness
        log_volumes = np.log1p(volumes)  # log1p handles volume=0 gracefully

        # Normalize to [0, 1] range
        price_min, price_max = prices.min(), prices.max()
        if price_max > price_min:
            prices_norm = (prices - price_min) / (price_max - price_min)
        else:
            prices_norm = np.zeros_like(prices)

        vol_min, vol_max = log_volumes.min(), log_volumes.max()
        if vol_max > vol_min:
            volumes_norm = (log_volumes - vol_min) / (vol_max - vol_min)
        else:
            volumes_norm = np.zeros_like(log_volumes)

        # Stack into 2D feature matrix
        features = np.column_stack([prices_norm, volumes_norm])

        return features, prices

    def _auto_epsilon(self, features: np.ndarray, min_samples: int) -> float:
        """Auto-calculate epsilon using k-distance graph elbow method (T020).

        Args:
            features: 2D feature matrix (price, log_volume)
            min_samples: Minimum samples for DBSCAN

        Returns:
            Optimal epsilon value
        """
        # Use k-nearest neighbors to find k-distance
        k = min_samples
        nbrs = NearestNeighbors(n_neighbors=k).fit(features)
        distances, _ = nbrs.kneighbors(features)

        # Get k-th nearest neighbor distance for each point
        k_distances = distances[:, -1]

        # Sort distances
        k_distances_sorted = np.sort(k_distances)

        # Use elbow heuristic: take 90th percentile
        # (balances between too small and too large epsilon)
        epsilon = float(np.percentile(k_distances_sorted, 90))

        # Ensure epsilon is within valid range [0.01, 1.0]
        epsilon = max(0.01, min(1.0, epsilon))

        return round(epsilon, 4)

    def _compute_clusters(
        self,
        labels: np.ndarray,
        prices: np.ndarray,
        volumes: np.ndarray,
        features: np.ndarray,
    ) -> List[LiquidationCluster]:
        """Compute cluster statistics from DBSCAN labels (T022).

        Args:
            labels: DBSCAN cluster labels (-1 for noise)
            prices: Original price array
            volumes: Original volume array
            features: Normalized feature matrix

        Returns:
            List of LiquidationCluster objects
        """
        clusters = []
        unique_labels = np.unique(labels)

        for cluster_id in unique_labels:
            if cluster_id == -1:  # Skip noise points
                continue

            # Get all points in this cluster
            mask = labels == cluster_id
            cluster_prices = prices[mask]
            cluster_volumes = volumes[mask]
            cluster_features = features[mask]

            # Compute statistics
            price_min = float(cluster_prices.min())
            price_max = float(cluster_prices.max())

            # Volume-weighted centroid price
            total_volume = float(cluster_volumes.sum())
            if total_volume > 0:
                centroid_price = float(np.average(cluster_prices, weights=cluster_volumes))
            else:
                centroid_price = float(cluster_prices.mean())

            level_count = int(mask.sum())

            # Compute density: ratio of points to convex hull area
            # Simplified: use price spread as proxy
            price_spread = price_max - price_min
            if price_spread > 0:
                # Normalize density by dividing level_count by spread
                # Scale to [0, 1] range (heuristic)
                density = min(1.0, level_count / (price_spread / 100))
            else:
                density = 1.0  # All points at same price = maximum density

            cluster = LiquidationCluster(
                cluster_id=int(cluster_id),
                price_min=price_min,
                price_max=price_max,
                centroid_price=centroid_price,
                total_volume=total_volume,
                level_count=level_count,
                density=float(density),
            )
            clusters.append(cluster)

        return clusters

    def _compute_noise(
        self,
        labels: np.ndarray,
        prices: np.ndarray,
        volumes: np.ndarray,
        features: np.ndarray,
        cluster_centers: Dict[int, np.ndarray],
    ) -> List[NoisePoint]:
        """Compute noise point statistics (T023).

        Args:
            labels: DBSCAN cluster labels (-1 for noise)
            prices: Original price array
            volumes: Original volume array
            features: Normalized feature matrix
            cluster_centers: Dict mapping cluster_id to centroid coordinates

        Returns:
            List of NoisePoint objects
        """
        noise_points = []
        noise_mask = labels == -1

        if not noise_mask.any():
            return noise_points

        noise_prices = prices[noise_mask]
        noise_volumes = volumes[noise_mask]
        noise_features = features[noise_mask]

        # For each noise point, find distance to nearest cluster
        for i, (price, volume, feat) in enumerate(zip(noise_prices, noise_volumes, noise_features)):
            # Find nearest cluster center
            if cluster_centers:
                distances = [np.linalg.norm(feat - center) for center in cluster_centers.values()]
                distance_to_nearest = float(min(distances))
            else:
                # No clusters exist, use arbitrary large distance
                distance_to_nearest = 1.0

            noise_point = NoisePoint(
                price_level=float(price),
                volume=float(volume),
                distance_to_nearest=distance_to_nearest,
            )
            noise_points.append(noise_point)

        return noise_points
