from decimal import Decimal
from typing import Optional
from ...models.futures import FuturesConfig, MarginType

class FeeCalculator:
    def __init__(self):
        self.maker_fee = Decimal('0.0002')  # 0.02%
        self.taker_fee = Decimal('0.0004')  # 0.04%

    def calculate_fees(
        self,
        position_size: Decimal,
        leverage: int,
        entry_price: Decimal,
        exit_price: Optional[Decimal] = None,
        margin_type: MarginType = MarginType.CROSS
    ) -> Decimal:
        """Calculate total fees for a futures trade including entry and exit"""
        notional_value = position_size * leverage
        entry_fee = notional_value * self.taker_fee

        if exit_price:
            exit_fee = notional_value * self.maker_fee
            return entry_fee + exit_fee

        return entry_fee

    def estimate_profit(
        self,
        config: FuturesConfig,
        entry_price: Decimal,
        take_profit: Decimal,
        position_size: Optional[Decimal] = None
    ) -> Decimal:
        """Estimate potential profit including fees"""
        pos_size = position_size or config.position_size
        notional_value = pos_size * config.leverage
        price_diff = take_profit - entry_price
        gross_profit = (price_diff / entry_price) * notional_value

        total_fees = self.calculate_fees(
            pos_size,
            config.leverage,
            entry_price,
            take_profit,
            config.margin_type
        )

        return gross_profit - total_fees
