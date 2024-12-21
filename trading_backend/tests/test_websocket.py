"""Tests for WebSocket functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
from fastapi import WebSocket, WebSocketDisconnect
from app.routers.websocket import websocket_endpoint
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.market_analysis.market_data_service import MarketDataService
from decimal import Decimal
import asyncio

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket with necessary attributes."""
    mock = create_autospec(WebSocket, instance=True)
    mock.accept = AsyncMock()
    mock.receive_json = AsyncMock()
    mock.send_json = AsyncMock()
    mock.close = AsyncMock()
    mock.client_state = MagicMock()
    mock.client_state.DISCONNECTED = False
    return mock

@pytest.fixture
def mock_account_monitor():
    """Create a mock AccountMonitor."""
    mock = create_autospec(AccountMonitor, instance=True)
    mock.get_account_status = AsyncMock(return_value={
        "type": "account_status",
        "current_stage": "initial",
        "current_balance": "100",
        "stage_progress": "0.00",
        "remaining_to_next_stage": "900.00",
        "max_leverage": 20
    })
    mock.send_balance_update = AsyncMock()
    mock.update_balance = AsyncMock()  # Make sure this is an AsyncMock
    return mock

@pytest.fixture
def mock_market_data_service():
    """Create a mock MarketDataService."""
    mock = create_autospec(MarketDataService, instance=True)
    mock.get_market_data = AsyncMock(return_value={
        "type": "market_data",
        "data": {
            "btc_price": "50000",
            "eth_price": "3000",
            "market_sentiment": "neutral"
        }
    })
    return mock

async def test_websocket_connection(mock_websocket, mock_account_monitor):
    """Test WebSocket connection establishment."""
    mock_websocket.receive_json.side_effect = [
        {"type": "subscribe", "channel": "account_monitoring"},
        WebSocketDisconnect()
    ]

    await websocket_endpoint(
        websocket=mock_websocket,
        account_monitor=mock_account_monitor
    )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited()

async def test_websocket_account_monitoring(mock_websocket, mock_account_monitor):
    """Test account monitoring subscription."""
    mock_websocket.receive_json.side_effect = [
        {"type": "subscribe", "channel": "account_monitoring"},
        {"type": "update", "data": {"balance": "1000"}},
        WebSocketDisconnect()
    ]

    await websocket_endpoint(
        websocket=mock_websocket,
        account_monitor=mock_account_monitor
    )

    mock_websocket.accept.assert_awaited_once()
    mock_account_monitor.update_balance.assert_awaited_with(Decimal("1000"))
    mock_account_monitor.send_balance_update.assert_awaited_with(mock_websocket)

async def test_websocket_error_handling(mock_websocket, mock_account_monitor):
    """Test error handling in WebSocket endpoint."""
    mock_websocket.receive_json.side_effect = Exception("Test error")

    await websocket_endpoint(
        websocket=mock_websocket,
        account_monitor=mock_account_monitor
    )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_with({
        "type": "error",
        "message": "Test error"
    })

async def test_invalid_subscription_type(mock_websocket, mock_account_monitor):
    """Test handling of invalid subscription type."""
    mock_websocket.receive_json.return_value = {
        "type": "invalid_type"
    }

    await websocket_endpoint(
        websocket=mock_websocket,
        account_monitor=mock_account_monitor
    )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_with({
        "type": "error",
        "message": "Unknown message type: invalid_type"
    })

async def test_websocket_account_updates(mock_websocket, mock_account_monitor):
    """Test account balance updates."""
    mock_websocket.receive_json.side_effect = [
        {"type": "subscribe", "channel": "account_monitoring"},
        {"type": "update", "data": {"balance": "2000"}},
        WebSocketDisconnect()
    ]

    await websocket_endpoint(
        websocket=mock_websocket,
        account_monitor=mock_account_monitor
    )

    mock_account_monitor.update_balance.assert_awaited_with(Decimal("2000"))
    mock_account_monitor.send_balance_update.assert_awaited_with(mock_websocket)
