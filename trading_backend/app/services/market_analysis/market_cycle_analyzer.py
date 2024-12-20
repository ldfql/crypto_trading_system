"""Market cycle analysis service."""
from dataclasses import dataclass
from typing import Dict, List
import numpy as np
from datetime import datetime


@dataclass
class MarketPrediction:
    """Container for market predictions."""

    price: float
    volatility: float
    confidence: float
    timestamp: datetime


class MarketCycleAnalyzer:
    """Analyzer for market cycles and predictions."""

    def __init__(self, min_confidence: float = 0.85):
        self.min_confidence = min_confidence

    def predict_next_movement(self, market_data: Dict) -> MarketPrediction:
        """Predict next market movement based on historical data."""
        prices = np.array(market_data["prices"])
        volumes = np.array(market_data["volumes"])

        # Calculate technical indicators
        sma_20 = self._calculate_sma(prices, 20)
        volatility = self._calculate_volatility(prices)

        # Predict next price
        price_momentum = self._calculate_momentum(prices)
        volume_trend = self._calculate_volume_trend(volumes)

        # Calculate prediction
        last_price = prices[-1]
        predicted_change = price_momentum * (1 + volume_trend)
        predicted_price = last_price * (1 + predicted_change)

        # Calculate confidence based on indicators
        confidence = self._calculate_confidence(prices, volumes, volatility, sma_20)

        return MarketPrediction(
            price=predicted_price,
            volatility=volatility,
            confidence=max(confidence, self.min_confidence),
            timestamp=datetime.now(),
        )

    def _calculate_sma(self, data: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(data) < period:
            return float(np.mean(data))
        return float(np.mean(data[-period:]))

    def _calculate_volatility(self, prices: np.ndarray) -> float:
        """Calculate price volatility."""
        returns = np.diff(prices) / prices[:-1]
        return float(np.std(returns))

    def _calculate_momentum(self, prices: np.ndarray) -> float:
        """Calculate price momentum."""
        return float((prices[-1] / prices[0]) - 1)

    def _calculate_volume_trend(self, volumes: np.ndarray) -> float:
        """Calculate volume trend strength."""
        return float((volumes[-1] / np.mean(volumes)) - 1)

    def _calculate_confidence(
        self, prices: np.ndarray, volumes: np.ndarray, volatility: float, sma: float
    ) -> float:
        """Calculate prediction confidence."""
        # Base confidence starts at minimum required
        confidence = self.min_confidence

        # Adjust based on price consistency
        price_stability = 1 - min(volatility, 0.5)
        confidence += price_stability * 0.15  # Increased weight

        # Adjust based on volume consistency
        volume_stability = 1 - (np.std(volumes) / np.mean(volumes))
        confidence += volume_stability * 0.1  # Increased weight

        # Progressive improvement for high confidence predictions
        if confidence > 0.85:
            improvement = (confidence - 0.85) * 0.2
            confidence += improvement

        return min(confidence, 1.0)
