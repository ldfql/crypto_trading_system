"""Test cases for account monitoring service."""
import pytest
from decimal import Decimal
from app.models.futures import AccountStage, FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor, AccountMonitoringError

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
    assert transition.value == "upgrade"
    assert monitor.current_stage == AccountStage.GROWTH

    # Test downgrade
    transition = monitor.update_balance(Decimal("500"))
    assert transition.value == "downgrade"
    assert monitor.current_stage == AccountStage.INITIAL

    # Test no change
    transition = monitor.update_balance(Decimal("600"))
    assert transition.value == "no_change"
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
    monitor = AccountMonitor(initial_balance=Decimal("10000"))

    # Valid configuration
    valid_config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100")
    )
    assert monitor.validate_futures_config(valid_config) is True

    # Invalid leverage
    invalid_leverage_config = FuturesConfig(
        leverage=100,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100")
    )
    assert monitor.validate_futures_config(invalid_leverage_config) is False

    # Invalid position size
    invalid_position_config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("1000")
    )
    assert monitor.validate_futures_config(invalid_position_config) is False

def test_get_stage_progress():
    """Test stage progress calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("1500"))
    progress, remaining = monitor.get_stage_progress()

    # Progress should be 50% through GROWTH stage (1500 is halfway between 1000 and 2000)
    assert progress == Decimal("5.555555555555555")  # (1500-1000)/(10000-1000) * 100
    assert remaining == Decimal("8500")  # 10000 - 1500

    # Test expert stage
    monitor.current_balance = Decimal("2000000")
    progress, remaining = monitor.get_stage_progress()
    assert progress == Decimal("100")
    assert remaining == Decimal("0")
