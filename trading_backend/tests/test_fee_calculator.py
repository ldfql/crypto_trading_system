"""Tests for the fee calculator service."""
from decimal import Decimal
import pytest
from app.services.trading.fee_calculator import FeeCalculator


@pytest.fixture
def fee_calculator():
    return FeeCalculator()


def test_basic_fee_calculation(fee_calculator):
    """Test basic fee calculation without VIP level."""
    position_size = Decimal('100')  # 100 USDT
    leverage = 10

    fees = fee_calculator.calculate_fees(position_size, leverage)

    assert fees["maker_fee"] == Decimal('0.20')  # 0.02% of 1000
    assert fees["taker_fee"] == Decimal('0.40')  # 0.04% of 1000
    assert fees["total_fee"] == Decimal('0.60')  # Entry (taker) + Exit (maker)


def test_vip_fee_calculation(fee_calculator):
    """Test fee calculation with VIP level."""
    position_size = Decimal('100')
    leverage = 10
    vip_level = 1

    fees = fee_calculator.calculate_fees(position_size, leverage, vip_level)

    assert fees["maker_fee"] == Decimal('0.16')  # 0.016% of 1000
    assert fees["taker_fee"] == Decimal('0.40')  # 0.04% of 1000
    assert fees["total_fee"] == Decimal('0.56')  # Entry (taker) + Exit (maker)


def test_large_position_calculation(fee_calculator):
    """Test fee calculation with large position size."""
    position_size = Decimal('1000000')  # 1M USDT
    leverage = 5

    fees = fee_calculator.calculate_fees(position_size, leverage)

    assert fees["maker_fee"] == Decimal('1000')  # 0.02% of 5M
    assert fees["taker_fee"] == Decimal('2000')  # 0.04% of 5M
    assert fees["total_fee"] == Decimal('3000')  # Entry + Exit


def test_profit_estimation(fee_calculator):
    """Test profit estimation including fees."""
    position_size = Decimal('100')
    leverage = 10
    entry_price = Decimal('50000')
    exit_price = Decimal('51000')

    profit = fee_calculator.estimate_profit(
        position_size, leverage, entry_price, exit_price
    )

    # Price increase of 2% * leverage 10 * position 100 = 20 USDT raw profit
    assert profit["raw_pnl"] == Decimal('20')
    assert profit["fees"] == Decimal('0.60')
    assert profit["net_pnl"] == Decimal('19.40')
    assert profit["roi_pct"] == Decimal('19.40')  # 19.40% return on 100 USDT
