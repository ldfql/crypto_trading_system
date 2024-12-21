"""Integration tests for account monitoring functionality."""
from decimal import Decimal
import pytest
import asyncio
from fastapi import WebSocket
from unittest.mock import AsyncMock, create_autospec
import pydantic

from app.models.signals import AccountStage, AccountStageTransition
from app.models.futures import FuturesConfig, MarginType
from app.services.monitoring.account_monitor import (
    AccountMonitor,
    AccountMonitoringError
)
from app.routers.websocket import websocket_endpoint

@pytest.fixture
def account_monitor():
    """Create an account monitor instance for testing."""
    return AccountMonitor(initial_balance=Decimal("100"))

@pytest.mark.asyncio
async def test_stage_transitions():
    """Test account stage transitions."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Test INITIAL to GROWTH transition
    await monitor.update_balance(Decimal("1500"))
    assert monitor.current_stage == AccountStage.GROWTH
    assert monitor.stage_transition == AccountStageTransition.UPGRADE

    # Test GROWTH to ADVANCED transition
    await monitor.update_balance(Decimal("15000"))
    assert monitor.current_stage == AccountStage.ADVANCED
    assert monitor.stage_transition == AccountStageTransition.UPGRADE

    # Test downgrade
    await monitor.update_balance(Decimal("900"))
    assert monitor.current_stage == AccountStage.INITIAL
    assert monitor.stage_transition == AccountStageTransition.DOWNGRADE

@pytest.mark.asyncio
async def test_trading_parameters_calculation():
    """Test trading parameter calculations."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))
    params = await monitor.get_trading_parameters(Decimal("1"))  # 1% risk

    assert params["type"] == "trading_parameters"
    data = params["data"]
    assert data["account_stage"] == AccountStage.INITIAL.value
    assert Decimal(data["current_balance"]) == Decimal("100")
    assert Decimal(data["position_size"]) > 0
    assert data["leverage"] <= monitor.get_max_leverage()
    assert data["margin_type"] == MarginType.CROSS.value

@pytest.mark.asyncio
async def test_futures_config_validation():
    """Test futures configuration validation."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Valid configuration for INITIAL stage
    valid_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("10"),  # Minimum valid position size
        max_position_size=Decimal("15"),  # Max position size for test
        risk_level=Decimal("0.5")  # Medium risk
    )
    assert await monitor.validate_futures_config(valid_config) is True

    # Test invalid leverage
    with pytest.raises(ValueError, match="Initial stage max leverage is 20x"):
        invalid_leverage_config = FuturesConfig(
            leverage=30,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("15"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(invalid_leverage_config)

    # Test invalid margin type for INITIAL stage
    with pytest.raises(ValueError, match="Initial stage only supports cross margin"):
        invalid_margin_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.ISOLATED,
            position_size=Decimal("10"),
            max_position_size=Decimal("15"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(invalid_margin_config)

    # Test invalid risk level
    with pytest.raises(pydantic.ValidationError, match="Input should be less than or equal to 1.0"):
        invalid_risk_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("15"),
            risk_level=Decimal("1.5")  # Invalid risk level
        )
        await monitor.validate_futures_config(invalid_risk_config)

    # Test position size exceeding max allowed (using GROWTH stage account)
    growth_monitor = AccountMonitor(initial_balance=Decimal("1500"))  # GROWTH stage
    with pytest.raises(ValueError, match="Position size cannot exceed max position size"):
        large_position_config = FuturesConfig(
            leverage=20,
            margin_type=MarginType.CROSS,
            position_size=Decimal("1600"),  # Exceeds max position size
            max_position_size=Decimal("1600"),
            risk_level=Decimal("0.5")
        )
        await growth_monitor.validate_futures_config(large_position_config)

@pytest.mark.asyncio
async def test_stage_progress_calculation():
    """Test stage progress calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Test progress in INITIAL stage
    await monitor.update_balance(Decimal("550"))  # Exactly 50% between 100 and 1000
    progress, remaining = monitor.get_stage_progress()
    assert progress >= Decimal("45")  # Allow for some decimal rounding
    assert progress <= Decimal("55")
    assert remaining == Decimal("450")  # 1000 (next stage) - 550 (current)

@pytest.mark.asyncio
async def test_expert_stage_progress():
    """Test progress calculation in expert stage."""
    monitor = AccountMonitor(initial_balance=Decimal("1000000"))  # Start in EXPERT stage
    await monitor.update_balance(Decimal("50000000"))  # Halfway to 1亿U

    progress, remaining = monitor.get_stage_progress()
    assert progress >= Decimal("45")  # Allow for some decimal rounding
    assert progress <= Decimal("55")
    assert remaining == Decimal("50000000")  # 100M - 50M
    assert monitor.current_stage == AccountStage.EXPERT

@pytest.mark.asyncio
async def test_risk_percentage_validation():
    """Test risk percentage validation."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    with pytest.raises(AccountMonitoringError, match="Risk percentage must be between 0.1% and 5%"):
        await monitor.get_trading_parameters(Decimal("6"))  # Too high risk

@pytest.mark.asyncio
async def test_advanced_stage_parameters():
    """Test trading parameters for advanced stage."""
    monitor = AccountMonitor(initial_balance=Decimal("15000"))  # ADVANCED stage
    params = await monitor.get_trading_parameters(Decimal("2"))

    assert params["type"] == "trading_parameters"
    data = params["data"]
    assert data["account_stage"] == AccountStage.ADVANCED.value
    assert data["margin_type"] == MarginType.ISOLATED.value  # Advanced stage uses isolated margin

@pytest.mark.asyncio
async def test_websocket_account_monitoring_updates():
    """Test WebSocket endpoint for account monitoring updates."""
    mock_websocket = create_autospec(WebSocket, instance=True)
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_json = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.close = AsyncMock()
    mock_websocket.client_state = AsyncMock()
    mock_websocket.client_state.DISCONNECTED = False

    account_monitor = AccountMonitor(initial_balance=Decimal("1000"))

    # Setup WebSocket messages
    messages = [
        {"type": "subscribe", "channel": "account_monitoring"},
        {
            "type": "update",
            "data": {"balance": "1500"}
        },
        {
            "type": "update",
            "data": {"balance": "15000"}
        },
        {"type": "close"}
    ]
    mock_websocket.receive_json.side_effect = messages

    # Track message processing
    message_count = 0
    expected_messages = len(messages) - 1  # Don't count close message
    message_processed = asyncio.Event()

    async def mock_send_json(data):
        nonlocal message_count
        message_count += 1
        if message_count >= expected_messages:
            message_processed.set()

    mock_websocket.send_json.side_effect = mock_send_json

    # Start WebSocket endpoint
    endpoint_task = asyncio.create_task(
        websocket_endpoint(mock_websocket, account_monitor=account_monitor)
    )

    try:
        # Wait for all messages to be processed with timeout
        await asyncio.wait_for(message_processed.wait(), timeout=5.0)

        # Verify stage transitions
        sent_messages = [
            call.args[0] for call in mock_websocket.send_json.call_args_list
            if isinstance(call.args[0], dict) and call.args[0].get("type") == "account_status"
        ]

        assert len(sent_messages) > 0
        last_message = sent_messages[-1]["data"]
        assert last_message["current_stage"] == AccountStage.ADVANCED.value
        assert last_message["stage_transition"] == AccountStageTransition.UPGRADE.value
        assert Decimal(last_message["current_balance"]) == Decimal("15000")

    except asyncio.TimeoutError:
        pytest.fail("WebSocket test timed out")
    finally:
        endpoint_task.cancel()
        try:
            await endpoint_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_websocket_futures_config_updates():
    """Test futures configuration updates via WebSocket."""
    mock_websocket = create_autospec(WebSocket, instance=True)
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_json = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.close = AsyncMock()
    mock_websocket.client_state = AsyncMock()
    mock_websocket.client_state.DISCONNECTED = False

    account_monitor = AccountMonitor(initial_balance=Decimal("10000"))

    # Setup WebSocket messages for futures trading updates
    messages = [
        {"type": "subscribe", "channel": "account_monitoring"},
        {
            "type": "update",
            "data": {
                "balance": "20000",
                "futures_config": {
                    "leverage": 20,
                    "margin_type": "CROSS",
                    "position_size": "1000",
                    "max_position_size": "2000",
                    "risk_level": 0.5
                }
            }
        }
    ]
    mock_websocket.receive_json.side_effect = messages

    # Start WebSocket endpoint
    endpoint_task = asyncio.create_task(
        websocket_endpoint(mock_websocket, account_monitor=account_monitor)
    )

    try:
        # Wait for messages to be processed
        await asyncio.sleep(0.1)

        # Verify futures config updates
        sent_messages = [
            call.args[0] for call in mock_websocket.send_json.call_args_list
            if isinstance(call.args[0], dict) and call.args[0].get("type") == "account_status"
        ]

        assert len(sent_messages) > 0
        last_message = sent_messages[-1]["data"]
        assert Decimal(last_message["current_balance"]) == Decimal("20000")
        assert last_message["current_stage"] == AccountStage.ADVANCED.value
        assert last_message["stage_transition"] == AccountStageTransition.UPGRADE.value

    finally:
        endpoint_task.cancel()
        try:
            await endpoint_task
        except asyncio.CancelledError:
            pass
