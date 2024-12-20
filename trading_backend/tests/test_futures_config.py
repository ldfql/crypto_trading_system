import pytest
from decimal import Decimal
from app.models.futures import FuturesConfig, MarginType

def test_futures_config_validation():
    config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100"),
        max_position_size=Decimal("1000"),
        risk_level=0.1
    )
    assert config.leverage == 10
    assert config.margin_type == MarginType.CROSS
    assert config.position_size == Decimal("100")
    assert config.max_position_size == Decimal("1000")
    assert config.risk_level == 0.1

    # Test position size validation
    with pytest.raises(ValueError, match="Position size cannot exceed max position size"):
        FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("2000"),
            max_position_size=Decimal("1000"),
            risk_level=0.1
        )

def test_risk_level_validation():
    with pytest.raises(ValueError):
        FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=1.5  # Invalid risk level
        )
