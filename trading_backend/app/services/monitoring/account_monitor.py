from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from app.services.market_analysis.market_data_service import MarketDataService
from app.models.signals import TradingSignal
import logging

logger = logging.getLogger(__name__)


class AccountMonitor:
    """
    Monitors account balance and provides position sizing recommendations based on account stage
    and market conditions. Supports account growth from 100U to 100M+ U with appropriate
    risk management and liquidity considerations.
    """

    def __init__(self, market_data_service: MarketDataService):
        self.market_data_service = market_data_service
        # Account stages with balance ranges (in USDT)
        self.account_stages = {
            "micro": (Decimal("100"), Decimal("10000")),  # 100U - 10K U
            "small": (Decimal("10000"), Decimal("100000")),  # 10K - 100K U
            "medium": (Decimal("100000"), Decimal("1000000")),  # 100K - 1M U
            "large": (Decimal("1000000"), None),  # 1M+ U
        }

        # Risk multipliers decrease as account size increases
        self.stage_risk_multipliers = {
            "micro": Decimal("1.0"),  # Full risk for small accounts
            "small": Decimal("0.8"),  # 80% risk for growing accounts
            "medium": Decimal("0.6"),  # 60% risk for medium accounts
            "large": Decimal("0.4"),  # 40% risk for large accounts
        }

        # Maximum position size as percentage of 24h volume
        self.max_volume_percentage = {
            "micro": Decimal("0.01"),  # 1% of 24h volume
            "small": Decimal("0.02"),  # 2% of 24h volume
            "medium": Decimal("0.03"),  # 3% of 24h volume
            "large": Decimal("0.05"),  # 5% of 24h volume
        }

    async def get_account_stage(self, balance: Decimal) -> str:
        """
        Determine account stage based on current balance.

        Args:
            balance: Current account balance in USDT

        Returns:
            str: Account stage ('micro', 'small', 'medium', or 'large')
        """
        for stage, (min_bal, max_bal) in self.account_stages.items():
            if max_bal is None and balance >= min_bal:
                return stage
            if min_bal <= balance < max_bal:
                return stage
        return "micro"  # Default to micro for very small accounts

    async def calculate_position_size(
        self,
        balance: Decimal,
        symbol: str,
        risk_percentage: Decimal = Decimal("0.02"),
        volatility_adjustment: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculate recommended position size based on account balance, market conditions,
        and risk parameters.

        Args:
            balance: Current account balance in USDT
            symbol: Trading pair symbol
            risk_percentage: Base risk percentage (default 2%)
            volatility_adjustment: Whether to adjust for market volatility

        Returns:
            Dict containing position sizing recommendations and constraints
        """
        stage = await self.get_account_stage(balance)
        market_data = await self.market_data_service.get_market_data(symbol)

        # Adjust risk based on account stage
        adjusted_risk = risk_percentage * self.stage_risk_multipliers[stage]

        # Calculate base position size
        position_size = balance * adjusted_risk

        # Get market constraints
        volume_24h = Decimal(str(market_data.get("volume_24h", 0)))
        max_position = volume_24h * self.max_volume_percentage[stage]

        # Adjust for volatility if enabled
        volatility_multiplier = Decimal("1.0")
        if volatility_adjustment and "volatility" in market_data:
            volatility = Decimal(str(market_data["volatility"]))
            if volatility > Decimal("0.05"):  # High volatility
                volatility_multiplier = Decimal("0.7")
            elif volatility < Decimal("0.02"):  # Low volatility
                volatility_multiplier = Decimal("1.2")

        # Calculate final position size
        final_position_size = min(position_size * volatility_multiplier, max_position)

        # For medium and large accounts, calculate staged entries
        entry_stages = None
        if stage in ["medium", "large"]:
            entry_stages = [
                final_position_size * Decimal("0.3"),  # First entry 30%
                final_position_size * Decimal("0.3"),  # Second entry 30%
                final_position_size * Decimal("0.4"),  # Final entry 40%
            ]

        return {
            "recommended_size": float(final_position_size),
            "max_position": float(max_position),
            "stage": stage,
            "risk_level": float(adjusted_risk),
            "entry_stages": [float(x) for x in entry_stages] if entry_stages else None,
            "market_data": {
                "volume_24h": float(volume_24h),
                "volatility": market_data.get("volatility"),
                "volatility_multiplier": float(volatility_multiplier),
            },
        }

    async def validate_position_size(
        self, symbol: str, position_size: Decimal, balance: Decimal
    ) -> Tuple[bool, str]:
        """
        Validate if a proposed position size is within acceptable limits.

        Args:
            symbol: Trading pair symbol
            position_size: Proposed position size
            balance: Current account balance

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        stage = await self.get_account_stage(balance)
        market_data = await self.market_data_service.get_market_data(symbol)

        volume_24h = Decimal(str(market_data.get("volume_24h", 0)))
        max_position = volume_24h * self.max_volume_percentage[stage]

        if position_size > max_position:
            return (
                False,
                f"Position size exceeds maximum allowed ({float(max_position)} USDT) for market volume",
            )

        max_account_risk = balance * Decimal("0.05")  # Maximum 5% of account per trade
        if position_size > max_account_risk:
            return (
                False,
                f"Position size exceeds maximum account risk ({float(max_account_risk)} USDT)",
            )

        return True, "Position size is valid"

    async def log_balance_change(
        self, old_balance: Decimal, new_balance: Decimal, timestamp: datetime = None
    ) -> None:
        """
        Log significant balance changes and stage transitions.

        Args:
            old_balance: Previous account balance
            new_balance: New account balance
            timestamp: Optional timestamp for the change
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        old_stage = await self.get_account_stage(old_balance)
        new_stage = await self.get_account_stage(new_balance)

        if old_stage != new_stage:
            logger.info(
                f"Account stage transition at {timestamp}: {old_stage} -> {new_stage} "
                f"(Balance: {float(old_balance)} -> {float(new_balance)} USDT)"
            )

        # Log significant balance changes (>5%)
        change_percent = ((new_balance - old_balance) / old_balance) * Decimal("100")
        if abs(change_percent) >= Decimal("5"):
            logger.info(
                f"Significant balance change at {timestamp}: {float(change_percent)}% "
                f"({float(old_balance)} -> {float(new_balance)} USDT)"
            )
