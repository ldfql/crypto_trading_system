"""Fee calculator service for futures trading.

This module handles real-time fee calculations for different position sizes,
implementing maker/taker fee structure as per Binance futures interface.
"""
from typing import Dict, Optional, Tuple
from decimal import Decimal


class FeeCalculator:
    """Calculates trading fees for futures positions."""

    def __init__(self):
        # Default maker/taker fees (can be adjusted based on VIP level)
        self.maker_fee = Decimal('0.0002')  # 0.02%
        self.taker_fee = Decimal('0.0004')  # 0.04%

    def calculate_trading_fee(
        self,
        position_value: Decimal,
        vip_level: Optional[int] = None,
        is_maker: bool = True
    ) -> Decimal:
        """Calculate trading fee for a futures position.

        Args:
            position_value: Position value in USDT
            vip_level: Optional VIP level for fee discounts
            is_maker: Whether this is a maker order (True) or taker order (False)

        Returns:
            Calculated fee amount
        """
        maker_rate, taker_rate = self._get_fee_rates(vip_level)
        rate = maker_rate if is_maker else taker_rate
        return (position_value * rate).quantize(Decimal('0.00000001'))

    def calculate_fees(
        self,
        position_size: Decimal,
        leverage: int,
        vip_level: Optional[int] = None
    ) -> Dict[str, Decimal]:
        """Calculate trading fees for a futures position.

        Args:
            position_size: Position size in USDT
            leverage: Position leverage (1-125x)
            vip_level: Optional VIP level for fee discounts

        Returns:
            Dict containing maker_fee, taker_fee, entry_fee, exit_fee and total_fee
        """
        # Apply VIP discounts if applicable
        maker_rate, taker_rate = self._get_fee_rates(vip_level)

        # Calculate notional value
        notional_value = position_size * Decimal(str(leverage))

        # Calculate individual fees
        maker_fee = notional_value * maker_rate
        taker_fee = notional_value * taker_rate

        # Typical scenario: entry is taker, exit is maker
        entry_fee = taker_fee
        exit_fee = maker_fee

        # Total fees for round trip
        total_fee = entry_fee + exit_fee

        return {
            "maker_fee": maker_fee.quantize(Decimal('0.00000001')),
            "taker_fee": taker_fee.quantize(Decimal('0.00000001')),
            "entry_fee": entry_fee.quantize(Decimal('0.00000001')),
            "exit_fee": exit_fee.quantize(Decimal('0.00000001')),
            "total_fee": total_fee.quantize(Decimal('0.00000001'))
        }

    def _get_fee_rates(self, vip_level: Optional[int] = None) -> Tuple[Decimal, Decimal]:
        """Get fee rates based on VIP level.

        Args:
            vip_level: VIP level (0-9)

        Returns:
            Tuple of (maker_fee, taker_fee) rates
        """
        if vip_level is None:
            return self.maker_fee, self.taker_fee

        # VIP fee structure (can be expanded based on Binance's tiers)
        vip_fees = {
            0: (Decimal('0.0002'), Decimal('0.0004')),  # Regular
            1: (Decimal('0.00016'), Decimal('0.0004')), # VIP 1
            2: (Decimal('0.00014'), Decimal('0.00035')), # VIP 2
            3: (Decimal('0.00012'), Decimal('0.00032')), # VIP 3
            # Add more VIP levels as needed
        }

        return vip_fees.get(vip_level, (self.maker_fee, self.taker_fee))

    def estimate_profit(
        self,
        position_size: Decimal,
        leverage: int,
        entry_price: Decimal,
        exit_price: Decimal,
        vip_level: Optional[int] = None
    ) -> Dict[str, Decimal]:
        """Estimate profit including fees for a futures position.

        Args:
            position_size: Position size in USDT
            leverage: Position leverage (1-125x)
            entry_price: Entry price
            exit_price: Target exit price
            vip_level: Optional VIP level for fee discounts

        Returns:
            Dict containing estimated profit details
        """
        fees = self.calculate_fees(position_size, leverage, vip_level)

        # Calculate raw profit/loss
        price_change_pct = (exit_price - entry_price) / entry_price
        raw_pnl = position_size * leverage * price_change_pct

        # Subtract fees
        net_pnl = raw_pnl - fees["total_fee"]

        return {
            "raw_pnl": raw_pnl.quantize(Decimal('0.00000001')),
            "fees": fees["total_fee"],
            "net_pnl": net_pnl.quantize(Decimal('0.00000001')),
            "roi_pct": (net_pnl / position_size * Decimal('100')).quantize(Decimal('0.01'))
        }
