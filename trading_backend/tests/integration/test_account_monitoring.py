"""Integration tests for account monitoring functionality."""
from decimal import Decimal
import pytest
import asyncio
from fastapi import WebSocket
from unittest.mock import AsyncMock, create_autospec

from app.models.signals import AccountStage, AccountStageTransition
from app.models.futures import FuturesConfig, MarginType
from app.services.monitoring.account_monitor import (
    AccountMonitor,
    AccountMonitoringError
)
from app.routers.websocket import websocket_endpoint

@pytest.fixture
def account_monitor():
    """Create account monitor instance for testing."""
    return AccountMonitor(initial_balance=Decimal("100"))  # Start with minimum balance for INITIAL stage

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
    assert params["current_balance"] == Decimal("100")
    assert params["position_size"] == Decimal("1")  # 1% of 100
    assert params["leverage"] <= 20  # Max leverage for INITIAL stage
    assert isinstance(params["margin_type"], MarginType)
    assert params["estimated_fees"] > 0

def test_futures_config_validation(account_monitor):
    """Test futures configuration validation."""
    # Valid configuration for INITIAL stage
    valid_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("10"),  # Minimum valid position size
        max_position_size=Decimal("15"),  # Max position size for test
        risk_level=Decimal("0.5")  # Medium risk
    )
    assert account_monitor.validate_futures_config(valid_config) is True

    # Test invalid leverage
    with pytest.raises(ValueError, match="Initial stage max leverage is 20x"):
        invalid_leverage_config = FuturesConfig(
            leverage=30,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("15"),
            risk_level=Decimal("0.5")
        )
        account_monitor.validate_futures_config(invalid_leverage_config)

    # Test invalid margin type for INITIAL stage
    with pytest.raises(ValueError, match="Initial stage only supports cross margin"):
        invalid_margin_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.ISOLATED,
            position_size=Decimal("10"),
            max_position_size=Decimal("15"),
            risk_level=Decimal("0.5")
        )
        account_monitor.validate_futures_config(invalid_margin_config)

    # Test invalid risk level
    with pytest.raises(ValueError) as exc_info:
        invalid_risk_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("15"),
            risk_level=Decimal("1.5")  # Invalid risk level
        )
    assert "Input should be less than or equal to 1.0" in str(exc_info.value)

    # Test position size exceeding max allowed (using GROWTH stage account)
    growth_monitor = AccountMonitor(initial_balance=Decimal("1500"))  # GROWTH stage
    with pytest.raises(ValueError, match="Position size .* exceeds maximum allowed"):
        large_position_config = FuturesConfig(
            leverage=20,
            margin_type=MarginType.CROSS,
            position_size=Decimal("100"),  # Exceeds 5% of 1500
            max_position_size=Decimal("100"),
            risk_level=Decimal("0.5")
        )
        growth_monitor.validate_futures_config(large_position_config)

def test_stage_progress_calculation(account_monitor):
    """Test stage progress calculations."""
    # Set balance to middle of INITIAL stage (100U to 1000U)
    account_monitor.update_balance(Decimal("550"))  # Exactly 50% between 100 and 1000
    progress, remaining = account_monitor.get_stage_progress()

    assert 45 <= progress <= 55  # Should be around 50% through INITIAL stage
    assert Decimal("400") <= remaining <= Decimal("500")  # Remaining to next stage

    # Test EXPERT stage progress
    account_monitor.update_balance(Decimal("150000"))  # In EXPERT stage
    progress, remaining = account_monitor.get_stage_progress()
    assert progress > 0  # Should show some progress
    assert remaining > 0  # Should show remaining amount to target

def test_expert_stage_progress(account_monitor):
    """Test progress calculation in EXPERT stage."""
    # Move to EXPERT stage
    account_monitor.update_balance(Decimal("150000"))
    assert account_monitor.current_stage == AccountStage.EXPERT

    # Calculate progress towards 1亿U target
    progress, remaining = account_monitor.get_stage_progress()
    assert progress > 0  # Should show some progress
    assert remaining == Decimal("100000000") - Decimal("150000")  # Remaining to 1亿U

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

@pytest.mark.asyncio
@pytest.mark.timeout(5)  # 5 second timeout for the entire test
async def test_websocket_account_monitoring_updates():
    """Test real-time account monitoring updates via WebSocket."""
    mock_websocket = create_autospec(WebSocket, instance=True)
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_json = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.close = AsyncMock()

    account_monitor = AccountMonitor(initial_balance=Decimal("100"))  # Start with 100U

    # Setup WebSocket connection with predefined messages
    messages = [
        {"type": "subscribe", "channel": "account_monitoring"},
        {"type": "update", "data": {"balance": "1000"}},  # Growth stage
        {"type": "update", "data": {"balance": "10000"}},  # Advanced stage
        {"type": "update", "data": {"balance": "100000"}},  # Expert stage
        {"type": "update", "data": {"balance": "1000000"}},  # Progress in expert stage
        {"type": "close"}  # Clean close
    ]
    mock_websocket.receive_json.side_effect = messages

    # Track message processing without recursion
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
        # Wait for all messages to be processed
        await asyncio.wait_for(message_processed.wait(), timeout=2.0)

        # Verify stage transitions through WebSocket updates
        sent_messages = [
            call.args[0] for call in mock_websocket.send_json.call_args_list
            if isinstance(call.args[0], dict) and "current_stage" in call.args[0]
        ]

        # Verify progression through stages
        stages = [msg["current_stage"] for msg in sent_messages]
        assert "initial" in stages
        assert "growth" in stages
        assert "advanced" in stages
        assert "expert" in stages

        # Verify progress tracking
        final_message = sent_messages[-1]
        assert Decimal(final_message["stage_progress"]) > 0
        assert Decimal(final_message["remaining_to_next_stage"]) < Decimal("99000000")

    except asyncio.TimeoutError:
        pytest.fail("WebSocket test timed out")
    finally:
        # Ensure cleanup
        if not endpoint_task.done():
            endpoint_task.cancel()
            try:
                await asyncio.wait_for(endpoint_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        await mock_websocket.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)  # 5 second timeout for the entire test
async def test_websocket_futures_config_updates():
    """Test futures configuration updates via WebSocket."""
    mock_websocket = create_autospec(WebSocket, instance=True)
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_json = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.close = AsyncMock()

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
        },
        {"type": "close"}  # Clean close
    ]
    mock_websocket.receive_json.side_effect = messages

    # Track message processing without recursion
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
        await asyncio.wait_for(message_processed.wait(), timeout=2.0)

        # Verify futures config updates
        sent_messages = [
            call.args[0] for call in mock_websocket.send_json.call_args_list
            if call.args[0]["type"] == "account_status"
        ]

        assert len(sent_messages) > 0
        last_message = sent_messages[-1]["data"]
        assert last_message["current_balance"] == Decimal("20000")
        assert last_message["futures_config"]["leverage"] == 20
        assert last_message["futures_config"]["margin_type"] == "CROSS"

    except asyncio.TimeoutError:
        pytest.fail("WebSocket test timed out")
    finally:
        # Ensure cleanup
        if not endpoint_task.done():
            endpoint_task.cancel()
            try:
                await asyncio.wait_for(endpoint_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        await mock_websocket.close()
