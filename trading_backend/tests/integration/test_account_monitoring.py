"""Integration tests for account monitoring functionality."""
from decimal import Decimal
import pytest

from app.models.futures import AccountStage, FuturesConfig, MarginType
from app.services.monitoring.account_monitor import (
    AccountMonitor,
    AccountMonitoringError,
    AccountStageTransition
)

@pytest.fixture
def account_monitor():
    """Create account monitor instance for testing."""
    return AccountMonitor(Decimal("500"))  # Start in INITIAL stage

def test_stage_transitions(account_monitor):
    """Test account stage transitions based on balance changes."""
    # Test upgrade to GROWTH stage
    transition = account_monitor.update_balance(Decimal("1200"))
    assert transition == AccountStageTransition.UPGRADE
    assert account_monitor.current_stage == AccountStage.GROWTH
    assert account_monitor.previous_stage == AccountStage.INITIAL

    # Test downgrade back to INITIAL stage
    transition = account_monitor.update_balance(Decimal("800"))
    assert transition == AccountStageTransition.DOWNGRADE
    assert account_monitor.current_stage == AccountStage.INITIAL
    assert account_monitor.previous_stage == AccountStage.GROWTH

def test_trading_parameters_calculation(account_monitor):
    """Test trading parameter calculations."""
    params = account_monitor.get_trading_parameters(Decimal("1"))  # 1% risk

    assert params["account_stage"] == AccountStage.INITIAL
    assert params["current_balance"] == Decimal("500")
    assert params["position_size"] == Decimal("5")  # 1% of 500
    assert params["leverage"] <= 20  # Max leverage for INITIAL stage
    assert isinstance(params["margin_type"], MarginType)
    assert params["estimated_fees"] > 0

def test_futures_config_validation(account_monitor):
    """Test futures configuration validation."""
    # Valid configuration for INITIAL stage
    valid_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("150"),  # Valid for INITIAL stage
        max_position_size=Decimal("300"),
        risk_level=0.5  # Medium risk
    )
    assert account_monitor.validate_futures_config(valid_config) is True

    # Invalid leverage for INITIAL stage
    invalid_config = FuturesConfig(
        leverage=30,  # Exceeds INITIAL stage max of 20
        margin_type=MarginType.CROSS,
        position_size=Decimal("150"),
        max_position_size=Decimal("300"),
        risk_level=0.5
    )
    assert account_monitor.validate_futures_config(invalid_config) is False

    # Test position size validation
    large_position_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("600"),  # Too large for account balance
        max_position_size=Decimal("1000"),
        risk_level=0.5
    )
    assert account_monitor.validate_futures_config(large_position_config) is False

def test_stage_progress_calculation(account_monitor):
    """Test stage progress calculations."""
    # Set balance to middle of INITIAL stage
    account_monitor.update_balance(Decimal("500"))
    progress, remaining = account_monitor.get_stage_progress()

    assert 45 <= progress <= 55  # Should be around 50% through INITIAL stage
    assert Decimal("400") <= remaining <= Decimal("600")  # Remaining to next stage

def test_risk_percentage_validation(account_monitor):
    """Test risk percentage validation."""
    with pytest.raises(AccountMonitoringError):
        account_monitor.calculate_position_size(Decimal("6"))  # Too high risk

    with pytest.raises(AccountMonitoringError):
        account_monitor.calculate_position_size(Decimal("0.05"))  # Too low risk

def test_advanced_stage_parameters():
    """Test parameters for advanced account stages."""
    advanced_monitor = AccountMonitor(Decimal("50000"))
    params = advanced_monitor.get_trading_parameters(Decimal("2"))

    assert params["account_stage"] == AccountStage.ADVANCED
    assert params["margin_type"] == MarginType.ISOLATED  # Should prefer isolated for larger accounts
    assert params["max_leverage"] == 75  # Max leverage for ADVANCED stage

def test_expert_stage_progress():
    """Test progress calculation for expert stage."""
    expert_monitor = AccountMonitor(Decimal("2000000"))
    progress, remaining = expert_monitor.get_stage_progress()

    assert progress == Decimal("100")  # Expert stage has no upper limit
    assert remaining == Decimal("0")  # No remaining progress needed
