import pytest
from decimal import Decimal, ROUND_HALF_UP
from app.models.futures import FuturesConfig, MarginType

def test_futures_config_validation():
    config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100.123456789"),
        max_position_size=Decimal("1000.987654321"),
        risk_level=Decimal("0.1")
    )

    # Verify decimal precision
    assert config.position_size == Decimal("100.123456789").quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)
    assert config.max_position_size == Decimal("1000.987654321").quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)
    assert config.risk_level == Decimal("0.1").quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)
    assert config.leverage == 10
    assert config.margin_type == MarginType.CROSS

    # Test position size validation against max position size
    with pytest.raises(ValueError, match=r"Position size \(\d+\.?\d*\) cannot exceed max position size \(\d+\.?\d*\)"):
        FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("2000.123456789"),
            max_position_size=Decimal("1000.987654321"),
            risk_level=Decimal("0.1")
        )

def test_risk_level_validation():
    # Test invalid risk level (too high)
    with pytest.raises(ValueError):
        FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=1.5  # Invalid risk level
        )

    # Test invalid risk level (too low)
    with pytest.raises(ValueError):
        FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=Decimal("0.05")  # Invalid risk level
        )

def test_leverage_validation():
    # Test invalid leverage (too high)
    with pytest.raises(ValueError):
        FuturesConfig(
            leverage=126,  # Max allowed is 125
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=Decimal("0.5")
        )

    # Test invalid leverage (too low)
    with pytest.raises(ValueError):
        FuturesConfig(
            leverage=0,  # Min allowed is 1
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=Decimal("0.5")
        )
