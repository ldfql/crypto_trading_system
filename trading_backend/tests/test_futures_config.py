"""Tests for futures trading configuration models."""
import pytest
from decimal import Decimal
from app.models.futures import (
    FuturesConfig,
    FuturesPosition,
    MarginType,
    AccountStage
)


def test_futures_config_defaults():
    """Test default values for futures configuration."""
    config = FuturesConfig(position_size=Decimal("100"))
    assert config.leverage == 20
    assert config.margin_type == MarginType.ISOLATED
    assert config.risk_level == 0.02
    assert config.account_stage == AccountStage.MICRO


def test_leverage_limits():
    """Test leverage limits for different account stages."""
    # Test micro account leverage limit
    with pytest.raises(ValueError, match="Maximum leverage for micro accounts is 20x"):
        FuturesConfig(
            position_size=Decimal("100"),
            leverage=25,
            account_stage=AccountStage.MICRO
        )

    # Test mega account maximum leverage
    config = FuturesConfig(
        position_size=Decimal("1000000"),
        leverage=125,
        account_stage=AccountStage.MEGA
    )
    assert config.leverage == 125


def test_position_size_validation():
    """Test position size validation."""
    # Test position size exceeding maximum
    with pytest.raises(ValueError, match="Position size .* exceeds maximum allowed size"):
        FuturesConfig(
            position_size=Decimal("1000"),
            max_position_size=Decimal("500")
        )

    # Test minimum position size for each account stage
    with pytest.raises(ValueError, match="Minimum position size for micro accounts is 10 USDT"):
        FuturesConfig(
            position_size=Decimal("5"),
            account_stage=AccountStage.MICRO
        )

    with pytest.raises(ValueError, match="Minimum position size for small accounts is 100 USDT"):
        FuturesConfig(
            position_size=Decimal("50"),
            account_stage=AccountStage.SMALL
        )

    # Test valid position sizes
    config = FuturesConfig(
        position_size=Decimal("400"),
        max_position_size=Decimal("500"),
        account_stage=AccountStage.SMALL
    )
    assert config.position_size == Decimal("400")


def test_futures_position():
    """Test futures position validation."""
    config = FuturesConfig(position_size=Decimal("100"))

    # Test valid position
    position = FuturesPosition(
        symbol="BTCUSDT",
        entry_price=Decimal("50000"),
        take_profit=Decimal("55000"),
        stop_loss=Decimal("48000"),
        config=config
    )
    assert position.symbol == "BTCUSDT"
    assert position.entry_price == Decimal("50000")

    # Test invalid take profit
    with pytest.raises(ValueError):
        FuturesPosition(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            take_profit=Decimal("45000"),  # Below entry price
            stop_loss=Decimal("48000"),
            config=config
        )

    # Test invalid stop loss
    with pytest.raises(ValueError):
        FuturesPosition(
            symbol="BTCUSDT",
            entry_price=Decimal("50000"),
            take_profit=Decimal("55000"),
            stop_loss=Decimal("52000"),  # Above entry price
            config=config
        )


def test_risk_level_validation():
    """Test risk level validation."""
    # Test valid risk levels
    config = FuturesConfig(
        position_size=Decimal("100"),
        risk_level=0.03
    )
    assert config.risk_level == 0.03

    # Test risk level too high
    with pytest.raises(ValueError):
        FuturesConfig(
            position_size=Decimal("100"),
            risk_level=0.06
        )

    # Test risk level too low
    with pytest.raises(ValueError):
        FuturesConfig(
            position_size=Decimal("100"),
            risk_level=0.005
        )


def test_account_stage_position_limits():
    """Test position size limits for different account stages."""
    # Test valid position sizes for each stage
    stages = {
        AccountStage.MICRO: Decimal("10"),
        AccountStage.SMALL: Decimal("100"),
        AccountStage.MEDIUM: Decimal("1000"),
        AccountStage.LARGE: Decimal("10000"),
        AccountStage.MEGA: Decimal("100000")
    }

    for stage, min_size in stages.items():
        config = FuturesConfig(
            position_size=min_size,
            account_stage=stage
        )
        assert config.position_size == min_size
