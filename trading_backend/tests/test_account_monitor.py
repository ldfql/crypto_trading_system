"""Tests for account monitoring functionality."""
import pytest
import asyncio
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import patch, Mock, AsyncMock, create_autospec
from app.models.signals import AccountStage, AccountStageTransition
from app.models.futures import FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor, AccountMonitoringError
from fastapi import WebSocket
import pydantic

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
        (Decimal("50000000"), AccountStage.EXPERT)  # Path to 1亿U
    ]

    for balance, expected_stage in test_cases:
        await monitor.update_balance(balance)
        assert monitor.current_stage == expected_stage, f"Failed for balance {balance}"

@pytest.mark.asyncio
async def test_update_balance():
    """Test balance updates and stage transitions."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Test upgrade transition
    await monitor.update_balance(Decimal("1500"))
    assert monitor.current_stage == AccountStage.GROWTH
    assert monitor.stage_transition == AccountStageTransition.UPGRADE
    assert monitor.previous_stage == AccountStage.INITIAL

    # Test no change
    await monitor.update_balance(Decimal("2000"))
    assert monitor.current_stage == AccountStage.GROWTH
    assert monitor.stage_transition == AccountStageTransition.NO_CHANGE
    assert monitor.previous_stage == AccountStage.GROWTH

    # Test downgrade
    await monitor.update_balance(Decimal("500"))
    assert monitor.current_stage == AccountStage.INITIAL
    assert monitor.stage_transition == AccountStageTransition.DOWNGRADE
    assert monitor.previous_stage == AccountStage.GROWTH

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
    """Test getting trading parameters."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))
    params = await monitor.get_trading_parameters(Decimal("1"))

    assert params["type"] == "trading_parameters"
    data = params["data"]
    assert data["account_stage"] == AccountStage.INITIAL.value
    assert Decimal(data["current_balance"]) == Decimal("100")
    assert data["margin_type"] == MarginType.CROSS.value

@pytest.mark.asyncio
async def test_validate_futures_config():
    """Test futures configuration validation."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))  # INITIAL stage

    # Test valid config for INITIAL stage
    valid_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("10"),
        max_position_size=Decimal("20"),
        risk_level=Decimal("0.5")
    )
    assert await monitor.validate_futures_config(valid_config) is True

    # Test invalid leverage
    with pytest.raises(ValueError, match="Initial stage max leverage is 20x"):
        invalid_config = FuturesConfig(
            leverage=25,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(invalid_config)

    # Test invalid margin type
    with pytest.raises(ValueError, match="Initial stage only supports cross margin"):
        invalid_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.ISOLATED,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(invalid_config)

    # Test invalid risk level
    with pytest.raises(pydantic.ValidationError, match="Input should be less than or equal to 1.0"):
        invalid_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("1.5")
        )
        await monitor.validate_futures_config(invalid_config)

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
async def test_websocket_balance_updates():
    """Test WebSocket balance updates."""
    mock_websocket = create_autospec(WebSocket, instance=True)
    mock_websocket.send_json = AsyncMock()
    mock_websocket.client_state = AsyncMock()
    mock_websocket.client_state.DISCONNECTED = False

    monitor = AccountMonitor(initial_balance=Decimal("100"))
    monitor.websocket = mock_websocket

    # Test balance update with WebSocket
    await monitor.update_balance(Decimal("1500"))

    # Verify WebSocket message
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]
    assert sent_message["type"] == "account_status"
    assert Decimal(sent_message["data"]["current_balance"]) == Decimal("1500")
    assert sent_message["data"]["stage_transition"] == AccountStageTransition.UPGRADE.value
    assert sent_message["data"]["current_stage"] == AccountStage.GROWTH.value

@pytest.mark.asyncio
async def test_real_time_monitoring():
    """Test real-time account monitoring."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Setup mock callback
    async def mock_callback(data):
        assert data["type"] == "account_status"
        assert Decimal(data["data"]["current_balance"]) == Decimal("1500")
        assert data["data"]["stage_transition"] == AccountStageTransition.UPGRADE.value

    # Start monitoring with callback
    monitor_task = asyncio.create_task(
        monitor.monitor_balance_changes(mock_callback)
    )

    try:
        # Update balance and wait for callback
        await monitor.update_balance(Decimal("1500"))
        await asyncio.sleep(0.1)  # Give time for callback to execute

        # Verify stage transition
        assert monitor.current_stage == AccountStage.GROWTH
        assert monitor.stage_transition == AccountStageTransition.UPGRADE

    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_futures_config_validation_across_stages():
    """Test futures configuration validation across different account stages."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))  # INITIAL stage

    # Test INITIAL stage restrictions
    with pytest.raises(ValueError, match="Initial stage max leverage is 20x"):
        config = FuturesConfig(
            leverage=25,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(config)

    # Move to GROWTH stage
    await monitor.update_balance(Decimal("1500"))
    assert monitor.current_stage == AccountStage.GROWTH

    # Test GROWTH stage restrictions
    with pytest.raises(ValueError, match="Growth stage only supports cross margin"):
        config = FuturesConfig(
            leverage=30,
            margin_type=MarginType.ISOLATED,
            position_size=Decimal("100"),
            max_position_size=Decimal("200"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(config)

    # Move to ADVANCED stage
    await monitor.update_balance(Decimal("15000"))
    assert monitor.current_stage == AccountStage.ADVANCED

    # Test ADVANCED stage allows both margin types
    config = FuturesConfig(
        leverage=50,
        margin_type=MarginType.ISOLATED,
        position_size=Decimal("1000"),
        max_position_size=Decimal("2000"),
        risk_level=Decimal("0.5")
    )
    assert await monitor.validate_futures_config(config) is True
