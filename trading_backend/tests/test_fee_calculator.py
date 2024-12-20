import pytest
from decimal import Decimal
from app.services.trading.fee_calculator import FeeCalculator
from app.models.futures import FuturesConfig, MarginType

def test_fee_calculation():
    calculator = FeeCalculator()

    fees = calculator.calculate_fees(
        position_size=Decimal("100"),
        leverage=10,
        entry_price=Decimal("50000"),
        exit_price=Decimal("51000"),
        margin_type=MarginType.CROSS
    )

    # Entry fee (0.04%) + Exit fee (0.02%) = 0.06% of notional value
    expected_fees = (Decimal("100") * 10) * (Decimal("0.0006"))
    assert fees == expected_fees

def test_profit_estimation():
    calculator = FeeCalculator()

    config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100"),
        max_position_size=Decimal("1000"),
        risk_level=0.1
    )

    profit = calculator.estimate_profit(
        config=config,
        entry_price=Decimal("50000"),
        take_profit=Decimal("51000")
    )

    # Calculate expected profit
    notional_value = Decimal("100") * 10
    price_change_pct = (Decimal("51000") - Decimal("50000")) / Decimal("50000")
    gross_profit = notional_value * price_change_pct
    fees = calculator.calculate_fees(
        Decimal("100"),
        10,
        Decimal("50000"),
        Decimal("51000"),
        MarginType.CROSS
    )
    expected_profit = gross_profit - fees

    assert profit == expected_profit
