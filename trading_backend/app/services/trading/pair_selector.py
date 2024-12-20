from decimal import Decimal
from typing import List, Optional, Dict
import asyncio
from ...models.futures import FuturesConfig, MarginType, AccountStage
from ..market_analysis.market_data_service import MarketDataService
from .fee_calculator import FeeCalculator

class PairSelector:
    def __init__(self, market_data_service: MarketDataService):
        self.market_data_service = market_data_service
        self.fee_calculator = FeeCalculator()
        self.min_volume_threshold = Decimal("1000000")  # Minimum 24h volume in USDT
        self.min_confidence = 0.82  # Minimum confidence threshold

    async def select_trading_pairs(
        self,
        account_balance: Decimal,
        max_pairs: int = 3
    ) -> List[Dict]:
        """Select best trading pairs based on market conditions and account balance."""
        pairs = await self.market_data_service.get_all_trading_pairs()
        selected_pairs = []

        for pair in pairs:
            if not await self._meets_volume_requirements(pair):
                continue

            signal = await self._analyze_trading_opportunity(pair, account_balance)
            if signal and len(selected_pairs) < max_pairs:
                selected_pairs.append(signal)

        return sorted(selected_pairs, key=lambda x: x['confidence'], reverse=True)

    async def _meets_volume_requirements(self, pair: str) -> bool:
        """Check if trading pair meets minimum volume requirements."""
        volume_24h = await self.market_data_service.get_24h_volume(pair)
        return volume_24h >= self.min_volume_threshold

    def _calculate_trading_config(
        self,
        account_balance: Decimal,
        current_price: Decimal
    ) -> FuturesConfig:
        """Calculate optimal trading configuration based on account balance."""
        if account_balance <= 1000:
            leverage = 20
            risk_level = Decimal("0.1")
        elif account_balance <= 10000:
            leverage = 50
            risk_level = Decimal("0.15")
        elif account_balance <= 100000:
            leverage = 75
            risk_level = Decimal("0.2")
        else:
            leverage = 100
            risk_level = Decimal("0.25")

        position_size = account_balance * risk_level

        return FuturesConfig(
            leverage=leverage,
            margin_type=MarginType.CROSS,
            position_size=position_size,
            max_position_size=account_balance,
            risk_level=float(risk_level)
        )

    async def _analyze_trading_opportunity(
        self,
        pair: str,
        account_balance: Decimal
    ) -> Optional[Dict]:
        """Analyze trading opportunity for a specific pair."""
        current_price = await self.market_data_service.get_current_price(pair)
        if not current_price:
            return None

        volatility = await self.market_data_service.get_volatility(pair)
        if volatility < 0.01:  # Skip low volatility pairs
            return None

        config = self._calculate_trading_config(account_balance, current_price)

        # Calculate entry points and targets
        support_level = await self.market_data_service.get_support_level(pair)
        resistance_level = await self.market_data_service.get_resistance_level(pair)

        if not (support_level and resistance_level):
            return None

        # Calculate optimal entry price near support
        entry_price = support_level * Decimal("1.005")  # 0.5% above support
        take_profit = min(
            resistance_level,
            entry_price * Decimal("1.03")  # 3% profit target
        )
        stop_loss = support_level * Decimal("0.995")  # 0.5% below support

        # Calculate expected profit
        expected_profit = self.fee_calculator.estimate_profit(
            config,
            entry_price,
            take_profit
        )

        confidence = await self._calculate_signal_confidence(
            pair,
            entry_price,
            take_profit,
            stop_loss
        )

        if confidence < self.min_confidence:
            return None

        return {
            "pair": pair,
            "entry_price": entry_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "position_size": config.position_size,
            "leverage": config.leverage,
            "margin_type": config.margin_type,
            "expected_profit": expected_profit,
            "confidence": confidence
        }

    async def _calculate_signal_confidence(
        self,
        pair: str,
        entry_price: Decimal,
        take_profit: Decimal,
        stop_loss: Decimal
    ) -> float:
        """Calculate confidence level for a trading signal."""
        trend = await self.market_data_service.get_trend_strength(pair)
        volume_score = await self._calculate_volume_score(pair)

        # Risk-reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0

        # Weight factors
        trend_weight = 0.4
        volume_weight = 0.3
        rr_weight = 0.3

        # Calculate weighted confidence
        confidence = (
            trend * trend_weight +
            volume_score * volume_weight +
            min(rr_ratio / 3, 1) * rr_weight  # Cap RR contribution at 3:1
        )

        return min(confidence, 1.0)  # Ensure confidence doesn't exceed 1.0

    async def _calculate_volume_score(self, pair: str) -> float:
        """Calculate volume-based score for confidence calculation."""
        volume_24h = await self.market_data_service.get_24h_volume(pair)
        avg_volume = await self.market_data_service.get_average_volume(pair)

        if not avg_volume:
            return 0.5

        volume_ratio = float(volume_24h / avg_volume)
        return min(volume_ratio / 2, 1.0)  # Cap at 1.0, normalize to 2x average
