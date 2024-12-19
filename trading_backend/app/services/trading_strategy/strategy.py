from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.trading.pair_selector import PairSelector
from app.services.market_analysis.market_data_service import MarketDataService
import logging

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    Enhanced trading strategy that adapts based on account size and market conditions.
    Supports account growth from 100U to 100M+ U with appropriate risk management
    and position sizing strategies.
    """

    def __init__(
        self,
        account_monitor: AccountMonitor,
        pair_selector: PairSelector,
        market_data_service: MarketDataService,
        min_accuracy_threshold: float = 0.82,
    ):
        self.account_monitor = account_monitor
        self.pair_selector = pair_selector
        self.market_data_service = market_data_service
        self.min_accuracy_threshold = min_accuracy_threshold

    async def generate_signal(
        self,
        balance: Decimal,
        symbol: str,
        signal_type: str,
        confidence: float,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a trading signal with position sizing adapted to account balance
        and market conditions.

        Args:
            balance: Current account balance in USDT
            symbol: Trading pair symbol
            signal_type: Type of trading signal (e.g., 'long', 'short')
            confidence: Signal confidence level (0.0 to 1.0)
            **kwargs: Additional signal parameters

        Returns:
            Dict containing signal details and position recommendations
        """
        # Skip signals below minimum accuracy threshold
        if confidence < self.min_accuracy_threshold:
            logger.info(
                f"Signal confidence {confidence} below minimum threshold {self.min_accuracy_threshold}"
            )
            return None

        # Validate trading pair for current account stage
        is_valid, reason = await self.pair_selector.validate_pair(symbol, balance)
        if not is_valid:
            logger.warning(f"Trading pair validation failed: {reason}")
            return None

        # Get position sizing recommendation
        position_data = await self.account_monitor.calculate_position_size(
            balance=balance, symbol=symbol, volatility_adjustment=True
        )

        # Get market conditions for strategy adaptation
        market_data = await self.market_data_service.get_market_data(symbol)

        # Adjust position size based on signal confidence
        confidence_multiplier = self._calculate_confidence_multiplier(confidence)
        adjusted_size = Decimal(str(position_data["recommended_size"])) * Decimal(
            str(confidence_multiplier)
        )

        # Build signal response
        signal = {
            "symbol": symbol,
            "signal_type": signal_type,
            "position_size": float(adjusted_size),
            "account_stage": position_data["stage"],
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
            "market_conditions": {
                "volume_24h": market_data.get("volume_24h"),
                "volatility": market_data.get("volatility"),
                "trend": market_data.get("trend"),
            },
            **kwargs,
        }

        # Add staged entry points for medium and large accounts
        if position_data["stage"] in ["medium", "large"]:
            signal["entry_stages"] = [
                float(adjusted_size * Decimal("0.3")),  # First entry 30%
                float(adjusted_size * Decimal("0.3")),  # Second entry 30%
                float(adjusted_size * Decimal("0.4")),  # Final entry 40%
            ]
            signal["entry_conditions"] = self._generate_entry_conditions(
                symbol, signal_type, market_data
            )

        return signal

    async def select_trading_pairs(
        self, balance: Decimal, base_pairs: List[str], min_confidence: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Select suitable trading pairs based on account balance and market conditions.

        Args:
            balance: Current account balance in USDT
            base_pairs: List of potential trading pairs
            min_confidence: Minimum required confidence level

        Returns:
            List of suitable pairs with their metrics
        """
        # Get recommended pairs from pair selector
        suitable_pairs = await self.pair_selector.get_recommended_pairs(
            balance=balance, base_pairs=base_pairs
        )

        # Filter pairs based on minimum confidence requirement
        filtered_pairs = []
        for pair in suitable_pairs:
            market_data = await self.market_data_service.get_market_data(pair["symbol"])
            confidence = self._calculate_pair_confidence(market_data)

            if confidence >= min_confidence:
                pair["confidence"] = confidence
                filtered_pairs.append(pair)

        return filtered_pairs

    def _calculate_confidence_multiplier(self, confidence: float) -> Decimal:
        """
        Calculate position size multiplier based on signal confidence.
        """
        if confidence >= 0.95:
            return Decimal("1.0")
        elif confidence >= 0.90:
            return Decimal("0.8")
        elif confidence >= 0.85:
            return Decimal("0.6")
        else:
            return Decimal("0.4")

    def _calculate_pair_confidence(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a trading pair based on market data.
        """
        # Base confidence on market metrics
        volume_score = min(1.0, float(market_data.get("volume_24h", 0)) / 1_000_000)
        volatility_score = min(1.0, float(market_data.get("volatility", 0)) * 10)
        liquidity_score = min(1.0, float(market_data.get("liquidity_score", 0)))

        # Weight the scores
        confidence = volume_score * 0.4 + volatility_score * 0.3 + liquidity_score * 0.3

        return round(confidence, 2)

    def _generate_entry_conditions(
        self, symbol: str, signal_type: str, market_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate conditions for staged entries based on market data.
        """
        volatility = float(market_data.get("volatility", 0))
        current_price = float(market_data.get("price", 0))

        if signal_type == "long":
            return [
                {
                    "stage": 1,
                    "price": current_price,
                    "type": "market",
                    "description": "Initial entry",
                },
                {
                    "stage": 2,
                    "price": current_price * (1 - volatility * 0.5),
                    "type": "limit",
                    "description": "First dip buy",
                },
                {
                    "stage": 3,
                    "price": current_price * (1 - volatility),
                    "type": "limit",
                    "description": "Second dip buy",
                },
            ]
        else:  # short
            return [
                {
                    "stage": 1,
                    "price": current_price,
                    "type": "market",
                    "description": "Initial entry",
                },
                {
                    "stage": 2,
                    "price": current_price * (1 + volatility * 0.5),
                    "type": "limit",
                    "description": "First bounce sell",
                },
                {
                    "stage": 3,
                    "price": current_price * (1 + volatility),
                    "type": "limit",
                    "description": "Second bounce sell",
                },
            ]
