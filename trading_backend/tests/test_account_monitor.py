"""Tests for account monitoring functionality."""
import pytest
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import patch, Mock, AsyncMock
from app.models.signals import AccountStage, AccountStageTransition
from app.models.futures import FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor, AccountMonitoringError
from fastapi import WebSocket

pytestmark = pytest.mark.asyncio  # Mark all tests as async

@pytest.mark.asyncio
async def test_init_account_monitor():
    """Test account monitor initialization."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))
    assert monitor.current_balance == Decimal("100")
    assert monitor.current_stage == AccountStage.INITIAL
    assert monitor.get_max_leverage() == 20

@pytest.mark.asyncio
async def test_determine_stage():
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
        (Decimal("2000000"), AccountStage.EXPERT),
    ]

    for balance, expected_stage in test_cases:
        monitor.current_balance = balance
        assert monitor._determine_stage(balance) == expected_stage

@pytest.mark.asyncio
async def test_update_balance():
    """Test balance updates and stage transitions."""
    monitor = AccountMonitor(initial_balance=Decimal("900"))
    assert monitor.current_stage == AccountStage.INITIAL

    # Test upgrade
    await monitor.update_balance(Decimal("1500"))
    assert monitor.stage_transition == AccountStageTransition.UPGRADE
    assert monitor.current_stage == AccountStage.GROWTH

    # Test downgrade
    await monitor.update_balance(Decimal("500"))
    assert monitor.stage_transition == AccountStageTransition.DOWNGRADE
    assert monitor.current_stage == AccountStage.INITIAL

    # Test no change
    await monitor.update_balance(Decimal("600"))
    assert monitor.stage_transition == AccountStageTransition.NO_CHANGE
    assert monitor.current_stage == AccountStage.INITIAL

@pytest.mark.asyncio
async def test_calculate_position_size():
    """Test position size calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("10000"))

    # Test valid risk percentages
    assert monitor.calculate_position_size(Decimal("1")) == Decimal("100.000000000")
    assert monitor.calculate_position_size(Decimal("2.5")) == Decimal("250.000000000")

    # Test invalid risk percentages
    with pytest.raises(AccountMonitoringError, match="Risk percentage must be between 0.1 and 5"):
        monitor.calculate_position_size(Decimal("0"))
    with pytest.raises(AccountMonitoringError, match="Risk percentage must be between 0.1 and 5"):
        monitor.calculate_position_size(Decimal("6"))

@pytest.mark.asyncio
async def test_get_trading_parameters():
    """Test trading parameter recommendations."""
    monitor = AccountMonitor(initial_balance=Decimal("5000"))
    params = monitor.get_trading_parameters(Decimal("2.5"))

    assert params["max_leverage"] == 50  # Growth stage max leverage
    assert isinstance(params["position_size"], Decimal)
    assert params["position_size"].quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP) == \
           Decimal("125.000000000")  # 2.5% of 5000
    assert params["margin_type"] == MarginType.CROSS

@pytest.mark.asyncio
async def test_validate_futures_config():
    """Test futures configuration validation."""
    monitor = AccountMonitor(initial_balance=Decimal("5000"))

    # Valid configuration
    valid_config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100"),
        max_position_size=Decimal("250"),  # 5% of 5000
        risk_level=Decimal("0.5")
    )
    assert monitor.validate_futures_config(valid_config) is True

    # Invalid leverage
    with pytest.raises(ValueError, match="Growth stage max leverage is 50x"):
        invalid_leverage_config = FuturesConfig(
            leverage=100,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),
            max_position_size=Decimal("250"),
            risk_level=Decimal("0.5")
        )
        monitor.validate_futures_config(invalid_leverage_config)

    # Invalid position size
    with pytest.raises(ValueError) as exc_info:
        invalid_position_config = FuturesConfig(
            leverage=20,
            margin_type=MarginType.CROSS,
            position_size=Decimal("1000"),
            max_position_size=Decimal("250"),
            risk_level=Decimal("0.5")
        )
        monitor.validate_futures_config(invalid_position_config)
    assert "Position size" in str(exc_info.value)
    assert "cannot exceed max position size" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_stage_progress():
    """Test stage progress calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("1500"))
    progress, remaining = monitor.get_stage_progress()

    # Progress should be ~5.56% through GROWTH stage (1500-1000)/(10000-1000) * 100
    current_progress = (Decimal("1500") - Decimal("1000"))
    stage_range = (Decimal("10000") - Decimal("1000"))
    expected_progress = (current_progress * Decimal("100") / stage_range).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    assert abs(progress - expected_progress) < Decimal("0.01"), \
        f"Progress {progress} differs from expected {expected_progress}"

    # Remaining amount should be 8500 (10000 - 1500)
    expected_remaining = (Decimal("10000") - Decimal("1500")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert abs(remaining - expected_remaining) < Decimal("0.01"), \
        f"Remaining {remaining} differs from expected {expected_remaining}"

    # Test expert stage
    await monitor.update_balance(Decimal("2000000"))  # Make async call properly awaited
    progress, remaining = monitor.get_stage_progress()

    # Progress should be ~2% through expert stage (2000000-1000000)/(100000000-1000000)
    current_progress = (Decimal("2000000") - Decimal("1000000")).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_UP
    )
    total_range = (Decimal("100000000") - Decimal("1000000")).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_UP
    )
    expected_progress = ((current_progress * Decimal("100")) / total_range).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_UP
    )

    assert abs(progress - expected_progress) < Decimal("0.000000001"), \
        f"Expert stage progress {progress} differs from expected {expected_progress}"
    assert abs(remaining - Decimal("98000000")) < Decimal("0.000000001"), \
        f"Expert stage remaining {remaining} differs from expected 98000000"

@pytest.mark.asyncio
async def test_negative_balance_error():
    """Test error handling for negative balance updates."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))
    with pytest.raises(AccountMonitoringError, match="Balance must be positive"):
        await monitor.update_balance(Decimal("-100"))
    with pytest.raises(AccountMonitoringError, match="Balance must be positive"):
        await monitor.update_balance(Decimal("0"))

@pytest.mark.asyncio
async def test_decimal_precision():
    """Test decimal precision handling in calculations."""
    monitor = AccountMonitor(initial_balance=Decimal("1234.56789"))

    # Test position size calculation precision
    position_size = monitor.calculate_position_size(Decimal("2.5"))
    assert isinstance(position_size, Decimal)
    assert position_size.as_tuple().exponent >= -9  # No more than 9 decimal places

    # Test stage progress precision
    progress, remaining = monitor.get_stage_progress()
    assert isinstance(progress, Decimal)
    assert isinstance(remaining, Decimal)
    assert progress.as_tuple().exponent >= -9
    assert remaining.as_tuple().exponent >= -9

@pytest.mark.asyncio
async def test_stage_transition_edge_cases():
    """Test stage transitions at boundary values."""
    monitor = AccountMonitor()

    # Test exact boundary transitions
    transitions = [
        (Decimal("999.99"), AccountStage.INITIAL),
        (Decimal("1000"), AccountStage.GROWTH),
        (Decimal("9999.99"), AccountStage.GROWTH),
        (Decimal("10000"), AccountStage.ADVANCED),
        (Decimal("99999.99"), AccountStage.ADVANCED),
        (Decimal("100000"), AccountStage.PROFESSIONAL),
        (Decimal("999999.99"), AccountStage.PROFESSIONAL),
        (Decimal("1000000"), AccountStage.EXPERT),
    ]

    for balance, expected_stage in transitions:
        monitor.current_balance = balance
        assert monitor._determine_stage(balance) == expected_stage, \
            f"Balance {balance} should be in {expected_stage} stage"

@pytest.mark.asyncio
async def test_expert_stage_progress():
    """Test expert stage progress calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("1000000"))  # Start in expert stage

    test_balances = [
        (Decimal("2000000"), Decimal("1.0")),   # 1% progress
        (Decimal("10000000"), Decimal("9.1")),  # ~9.1% progress
        (Decimal("50000000"), Decimal("49.5")), # ~49.5% progress
    ]

    for balance, expected_progress in test_balances:
        monitor.current_balance = balance
        progress, _ = monitor.get_stage_progress()
        assert abs(progress - expected_progress) < Decimal("0.1"), \
            f"Expert stage progress {progress} differs from expected {expected_progress}"

@pytest.mark.asyncio
async def test_websocket_balance_updates(mock_websocket):
    """Test WebSocket balance updates."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))

    # Test initial balance update
    await monitor.send_balance_update(mock_websocket)
    mock_websocket.send_json.assert_awaited_with({
        "balance": "1000.000000000",
        "stage": "INITIAL",
        "previous_stage": None,
        "stage_transition": "NO_CHANGE",
        "stage_progress": "0.00"
    })

    # Test stage transition
    await monitor.update_balance(Decimal("1500"))
    await monitor.send_balance_update(mock_websocket)
    mock_websocket.send_json.assert_awaited_with({
        "balance": "1500.000000000",
        "stage": "GROWTH",
        "previous_stage": "INITIAL",
        "stage_transition": "UPGRADE",
        "stage_progress": "5.56"  # (1500-1000)/(10000-1000) * 100
    })

@pytest.mark.asyncio
async def test_real_time_monitoring():
    """Test real-time monitoring functionality."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))
    updates = []

    async def mock_callback(data):
        updates.append(data)

    # Monitor balance changes
    await monitor.update_balance(Decimal("1500"))
    await monitor.monitor_balance_changes(mock_callback)
    assert len(updates) == 1
    assert updates[0]["balance"] == "1500.000000000"
    assert updates[0]["stage_transition"] == "UPGRADE"
    assert updates[0]["stage"] == "GROWTH"

    # Test stage transition monitoring
    await monitor.update_balance(Decimal("11000"))
    await monitor.monitor_balance_changes(mock_callback)
    assert len(updates) == 2
    assert updates[1]["balance"] == "11000.000000000"
    assert updates[1]["stage_transition"] == "UPGRADE"
    assert updates[1]["stage"] == "ADVANCED"

    # Test parameter updates monitoring
    params_before = monitor.get_trading_parameters(Decimal("1"))
    await monitor.update_balance(Decimal("150000"))
    await monitor.monitor_balance_changes(mock_callback)
    params_after = monitor.get_trading_parameters(Decimal("1"))
    assert params_before["max_leverage"] != params_after["max_leverage"]

@pytest.mark.asyncio
async def test_futures_config_validation_across_stages():
    """Test futures configuration validation across different account stages."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))

    # Test INITIAL stage restrictions
    config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("10"),
        max_position_size=Decimal("50"),
        risk_level=Decimal("0.5")
    )
    assert monitor.validate_futures_config(config) is True

    # Test GROWTH stage
    await monitor.update_balance(Decimal("5000"))
    config.leverage = 30
    with pytest.raises(ValueError, match="Maximum leverage for growth stage is 50x"):
        monitor.validate_futures_config(config)

    # Test ADVANCED stage
    await monitor.update_balance(Decimal("50000"))
    config.margin_type = MarginType.ISOLATED
    assert monitor.validate_futures_config(config) is True

    # Test PROFESSIONAL stage
    await monitor.update_balance(Decimal("500000"))
    config.leverage = 50
    assert monitor.validate_futures_config(config) is True

    # Test EXPERT stage
    await monitor.update_balance(Decimal("2000000"))
    config.leverage = 100
    assert monitor.validate_futures_config(config) is True
