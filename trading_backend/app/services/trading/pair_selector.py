from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.monitoring.account_monitor import AccountMonitor
import logging

logger = logging.getLogger(__name__)


class PairSelector:
    """
    Selects suitable trading pairs based on account balance and market conditions.
    Implements dynamic pair selection that scales with account growth from 100U to 100M+ U.
    """

    def __init__(
        self, market_data_service: MarketDataService, account_monitor: AccountMonitor
    ):
        self.market_data_service = market_data_service
        self.account_monitor = account_monitor

        # Minimum 24h volume requirements by stage (in USDT)
        self.min_volume_requirements = {
            "micro": Decimal("1_000_000"),  # $1M daily volume
            "small": Decimal("5_000_000"),  # $5M daily volume
            "medium": Decimal("20_000_000"),  # $20M daily volume
            "large": Decimal("100_000_000"),  # $100M daily volume
        }

        # Maximum spread requirements by stage
        self.max_spread_percentage = {
            "micro": Decimal("0.5"),  # 0.5% max spread
            "small": Decimal("0.3"),  # 0.3% max spread
            "medium": Decimal("0.2"),  # 0.2% max spread
            "large": Decimal("0.1"),  # 0.1% max spread
        }

    async def select_pairs(
        self,
        balance: Decimal,
        base_pairs: List[str],
        min_liquidity_score: Decimal = Decimal(
            "1.2"
        ),  # Require 20% more than minimum volume
    ) -> List[Dict[str, Any]]:
        """
        Select suitable trading pairs based on account balance and market conditions.

        Args:
            balance: Current account balance in USDT
            base_pairs: List of potential trading pairs to evaluate
            min_liquidity_score: Minimum required liquidity score (1.0 = meets minimum volume)

        Returns:
            List of suitable pairs with their metrics, sorted by liquidity score
        """
        stage = await self.account_monitor.get_account_stage(balance)
        min_volume = self.min_volume_requirements[stage]
        max_spread = self.max_spread_percentage[stage]

        suitable_pairs = []
        for pair in base_pairs:
            try:
                market_data = await self.market_data_service.get_market_data(pair)
                volume_24h = Decimal(str(market_data.get("volume_24h", 0)))
                spread = Decimal(str(market_data.get("spread_percentage", 100)))

                # Skip pairs that don't meet volume or spread requirements
                if volume_24h < min_volume or spread > max_spread:
                    continue

                liquidity_score = volume_24h / min_volume
                if liquidity_score < min_liquidity_score:
                    continue

                suitable_pairs.append(
                    {
                        "symbol": pair,
                        "volume_24h": float(volume_24h),
                        "spread_percentage": float(spread),
                        "volatility": market_data.get("volatility", 0),
                        "liquidity_score": float(liquidity_score),
                        "market_cap": market_data.get("market_cap", 0),
                        "stage_requirements": {
                            "min_volume": float(min_volume),
                            "max_spread": float(max_spread),
                        },
                    }
                )

            except Exception as e:
                logger.warning(f"Error processing pair {pair}: {str(e)}")
                continue

        # Sort pairs by liquidity score (highest first)
        return sorted(suitable_pairs, key=lambda x: x["liquidity_score"], reverse=True)

    async def validate_pair(
        self,
        symbol: str,
        balance: Decimal,
        position_size: Optional[Decimal] = None,
        testing: bool = False
    ) -> Tuple[bool, str]:
        """
        Validate if a specific trading pair is suitable for the current account balance
        and optional position size.

        Args:
            symbol: Trading pair symbol
            balance: Current account balance in USDT
            position_size: Optional position size to validate
            testing: Whether to use testing mode

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        stage = await self.account_monitor.get_account_stage(balance)
        market_data = await self.market_data_service.get_market_data(
            symbol, testing=testing
        )

        volume_24h = Decimal(str(market_data.get("volume_24h", 0)))
        spread = Decimal(str(market_data.get("spread_percentage", 100)))

        # Check volume requirement
        if volume_24h < self.min_volume_requirements[stage]:
            return (
                False,
                f"Insufficient 24h volume ({float(volume_24h)} USDT) for account stage {stage}",
            )

        # Check spread requirement
        if spread > self.max_spread_percentage[stage]:
            return (
                False,
                f"Spread too high ({float(spread)}%) for account stage {stage}",
            )

        # If position size provided, validate against volume
        if position_size is not None:
            max_position = volume_24h * Decimal("0.01")  # Max 1% of 24h volume
            if position_size > max_position:
                return (
                    False,
                    f"Position size ({float(position_size)} USDT) exceeds maximum allowed ({float(max_position)} USDT) for market volume",
                )

        return True, "Trading pair is valid for current account stage"

    async def get_recommended_pairs(
        self, balance: Decimal, base_pairs: List[str], max_pairs: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get a list of recommended trading pairs optimized for the current account balance.

        Args:
            balance: Current account balance in USDT
            base_pairs: List of potential trading pairs
            max_pairs: Maximum number of pairs to return

        Returns:
            List of recommended pairs with detailed metrics
        """
        suitable_pairs = await self.select_pairs(
            balance=balance,
            base_pairs=base_pairs,
            min_liquidity_score=Decimal(
                "1.5"
            ),  # Require 50% more than minimum volume for recommendations
        )

        # Return top pairs up to max_pairs
        return suitable_pairs[:max_pairs]
