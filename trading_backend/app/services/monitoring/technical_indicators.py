"""Technical indicators and pattern recognition for market analysis."""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC
from app.models.signals import TradingSignal

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Technical analysis indicators and patterns."""

    def __init__(self):
        """Initialize technical indicators."""
        self.patterns = {
            "bullish": {
                "golden_cross": {"weight": 0.8, "confidence": 0.85},
                "double_bottom": {"weight": 0.75, "confidence": 0.8},
                "ascending_triangle": {"weight": 0.7, "confidence": 0.75},
                "cup_and_handle": {"weight": 0.7, "confidence": 0.75},
                "bullish_engulfing": {"weight": 0.65, "confidence": 0.7},
                "pennant": {"weight": 0.65, "confidence": 0.7},
                "flag": {"weight": 0.65, "confidence": 0.7},
                "rectangle_breakout": {"weight": 0.6, "confidence": 0.7},
            },
            "bearish": {
                "death_cross": {"weight": 0.8, "confidence": 0.85},
                "double_top": {"weight": 0.75, "confidence": 0.8},
                "descending_triangle": {"weight": 0.7, "confidence": 0.75},
                "head_and_shoulders": {"weight": 0.7, "confidence": 0.75},
                "bearish_engulfing": {"weight": 0.65, "confidence": 0.7},
                "falling_wedge": {"weight": 0.65, "confidence": 0.7},
                "rectangle_breakdown": {"weight": 0.6, "confidence": 0.7},
            },
        }

    def analyze_pattern(self, pattern_name: str) -> Dict[str, Any]:
        """Analyze a specific technical pattern."""
        for sentiment, patterns in self.patterns.items():
            if pattern_name in patterns:
                return {
                    "sentiment": sentiment,
                    "weight": patterns[pattern_name]["weight"],
                    "confidence": patterns[pattern_name]["confidence"],
                }
        return {"sentiment": "neutral", "weight": 0.1, "confidence": 0.3}

    def validate_technical_indicators(
        self, signal: TradingSignal, market_data: Dict
    ) -> float:
        """Validate accuracy based on technical indicators"""
        if (
            not hasattr(signal, "technical_indicators")
            or not signal.technical_indicators
        ):
            return 0.85  # Base accuracy if no indicators

        indicators = signal.technical_indicators
        accuracy = 0.85
        total_weight = 0

        # RSI validation
        if "rsi" in indicators and "rsi" in market_data:
            rsi = float(indicators["rsi"])
            current_rsi = float(market_data["rsi"])
            if (signal.signal_type.upper() == "LONG" and current_rsi < 30) or (
                signal.signal_type.upper() == "SHORT" and current_rsi > 70
            ):
                accuracy += 0.08
            total_weight += 1

        # MACD validation
        if "macd" in indicators and "macd" in market_data:
            if indicators["macd"] == market_data["macd"]:
                accuracy += 0.08
            total_weight += 1

        # Moving average validation
        if "ma_cross" in indicators and "ma_cross" in market_data:
            if indicators["ma_cross"] == market_data["ma_cross"]:
                accuracy += 0.08
            total_weight += 1

        # Normalize accuracy based on available indicators
        if total_weight > 0:
            normalized_accuracy = (accuracy - 0.85) / total_weight + 0.85
            return min(0.99, normalized_accuracy)

        return accuracy
