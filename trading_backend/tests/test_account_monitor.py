"""Test cases for account monitoring service."""
import pytest
from decimal import Decimal
from app.models.futures import AccountStage, FuturesConfig, MarginType
from app.services.monitoring.account_monitor import (
    AccountMonitor,
    AccountMonitoringError,
    AccountStageTransition
)

def test_init_account_monitor():
    """Test account monitor initialization."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))
    assert monitor.current_balance == Decimal("1000")
    assert monitor.current_stage == AccountStage.GROWTH

def test_determine_stage():
    """Test stage determination based on balance."""
    monitor = AccountMonitor()

    # Test all stage boundaries
    test_cases = [
        (Decimal("50"), AccountStage.INITIAL),
        (Decimal("100"), AccountStage.INITIAL),
        (Decimal("999"), AccountStage.INITIAL),
        (Decimal("1000"), AccountStage.GROWTH),
        (Decimal("9999"), AccountStage.GROWTH),
        (Decimal("10000"), AccountStage.ADVANCED),
        (Decimal("99999"), AccountStage.ADVANCED),
        (Decimal("100000"), AccountStage.PROFESSIONAL),
        (Decimal("999999"), AccountStage.PROFESSIONAL),
        (Decimal("1000000"), AccountStage.EXPERT),
        (Decimal("10000000"), AccountStage.EXPERT),
    ]

    for balance, expected_stage in test_cases:
        monitor.current_balance = balance
        assert monitor._determine_stage(balance) == expected_stage

def test_update_balance():
    """Test balance updates and stage transitions."""
    monitor = AccountMonitor(initial_balance=Decimal("900"))
    assert monitor.current_stage == AccountStage.INITIAL

    # Test upgrade
    transition = monitor.update_balance(Decimal("1500"))
    assert transition == AccountStageTransition.UPGRADE
    assert monitor.current_stage == AccountStage.GROWTH

    # Test downgrade
    transition = monitor.update_balance(Decimal("500"))
    assert transition == AccountStageTransition.DOWNGRADE
    assert monitor.current_stage == AccountStage.INITIAL

    # Test no change
    transition = monitor.update_balance(Decimal("600"))
    assert transition == AccountStageTransition.NO_CHANGE
    assert monitor.current_stage == AccountStage.INITIAL

def test_calculate_position_size():
    """Test position size calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("10000"))

    # Test valid risk percentages
    assert monitor.calculate_position_size(Decimal("1")) == Decimal("100")
    assert monitor.calculate_position_size(Decimal("2.5")) == Decimal("250")

    # Test invalid risk percentages
    with pytest.raises(AccountMonitoringError):
        monitor.calculate_position_size(Decimal("0"))
    with pytest.raises(AccountMonitoringError):
        monitor.calculate_position_size(Decimal("6"))

def test_get_trading_parameters():
    """Test trading parameter recommendations."""
    monitor = AccountMonitor(initial_balance=Decimal("5000"))
    params = monitor.get_trading_parameters(Decimal("2"))

    assert params["account_stage"] == AccountStage.GROWTH
    assert params["current_balance"] == Decimal("5000")
    assert params["position_size"] == Decimal("100")  # 2% of 5000
    assert params["margin_type"] == MarginType.CROSS
    assert params["leverage"] == 25  # 50% of max leverage for GROWTH stage
    assert "estimated_fees" in params
    assert params["risk_percentage"] == Decimal("2")

def test_validate_futures_config():
    """Test futures configuration validation."""
    monitor = AccountMonitor(initial_balance=Decimal("5000"))  # Growth stage (1000U-10000U)

    # Valid configuration
    valid_config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100"),
        max_position_size=Decimal("1000"),
        risk_level=0.1
    )
    assert monitor.validate_futures_config(valid_config) is True

    # Invalid leverage
    with pytest.raises(ValueError, match="Growth stage max leverage is 50x"):
        invalid_leverage_config = FuturesConfig(
            leverage=100,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=0.1
        )
        monitor.validate_futures_config(invalid_leverage_config)

    # Invalid position size
    with pytest.raises(ValueError, match="Position size exceeds maximum allowed"):
        invalid_position_config = FuturesConfig(
            leverage=20,
            margin_type=MarginType.CROSS,
            position_size=Decimal("1000"),
            max_position_size=Decimal("2000"),
            risk_level=0.1
        )
        monitor.validate_futures_config(invalid_position_config)

def test_get_stage_progress():
    """Test stage progress calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("1500"))
    progress, remaining = monitor.get_stage_progress()

    # Progress should be ~5.56% through GROWTH stage (1500-1000)/(10000-1000) * 100
    assert abs(progress - Decimal("5.555555555555555")) < Decimal("0.000001")
    assert remaining == Decimal("8500")  # 10000 - 1500

    # Test expert stage
    transition = monitor.update_balance(Decimal("2000000"))
    assert transition == AccountStageTransition.UPGRADE
    progress, remaining = monitor.get_stage_progress()
    # Progress should be ~1.01% through expert stage (2000000-1000000)/(100000000-1000000)
    expected_progress = ((Decimal("2000000") - Decimal("1000000")) / (Decimal("100000000") - Decimal("1000000"))) * Decimal("100")
    print(f"\nDebug values:")
    print(f"Expected progress: {expected_progress}")
    print(f"Actual progress: {progress}")
    print(f"Difference: {abs(progress - expected_progress)}")
    assert abs(progress - expected_progress) < Decimal("0.000001")
    assert remaining == Decimal("98000000")  # 100000000 - 2000000
