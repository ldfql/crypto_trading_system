import pytest
from decimal import Decimal
from app.models.futures import FuturesConfig, MarginType, AccountStage

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

def test_leverage_limits_by_account_stage():
    # Initial stage test (100U-1000U)
    with pytest.raises(ValueError, match="Initial stage.*max leverage is 20x"):
        FuturesConfig(
            leverage=25,
            margin_type=MarginType.CROSS,
            position_size=Decimal("50"),
            max_position_size=Decimal("1000"),
            risk_level=0.1
        )

    # Growth stage test (1000U-10000U)
    with pytest.raises(ValueError, match="Growth stage.*max leverage is 50x"):
        FuturesConfig(
            leverage=60,
            margin_type=MarginType.CROSS,
            position_size=Decimal("200"),
            max_position_size=Decimal("10000"),
            risk_level=0.1
        )

def test_risk_level_validation():
    with pytest.raises(ValueError):
        FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=1.5
        )
