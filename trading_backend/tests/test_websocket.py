"""Tests for WebSocket functionality."""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.models.futures import AccountStage, AccountStageTransition, FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor

def test_websocket_connection():
    """Test WebSocket connection establishment."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        data = websocket.receive_json()
        assert "current_balance" in data or "error" in data

def test_websocket_account_monitoring():
    """Test real-time account monitoring via WebSocket."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Test initial stage (100U)
        websocket.send_json({"balance": "100"})
        response = websocket.receive_json()
        assert response["current_balance"] == "100"
        assert response["current_stage"] == "initial"
        assert float(response["stage_progress"]) >= 0.0
        assert response["max_leverage"] == 20

        # Test growth stage (1500U)
        websocket.send_json({"balance": "1500"})
        response = websocket.receive_json()
        assert response["current_balance"] == "1500"
        assert response["current_stage"] == "growth"
        assert float(response["stage_progress"]) > 0
        assert response["max_leverage"] == 50

        # Test advanced stage (15000U)
        websocket.send_json({"balance": "15000"})
        response = websocket.receive_json()
        assert response["current_balance"] == "15000"
        assert response["current_stage"] == "advanced"
        assert response["max_leverage"] == 75

def test_websocket_invalid_balance():
    """Test WebSocket handling of invalid balance."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Test negative balance
        websocket.send_json({"balance": "-100"})
        response = websocket.receive_json()
        assert "error" in response
        assert "Balance must be positive" in response["error"]

        # Test zero balance
        websocket.send_json({"balance": "0"})
        response = websocket.receive_json()
        assert "error" in response
        assert "Balance must be positive" in response["error"]

        # Test invalid format
        websocket.send_json({"balance": "invalid"})
        response = websocket.receive_json()
        assert "error" in response

@pytest.mark.asyncio
async def test_websocket_connection_error():
    """Test WebSocket connection error handling."""
    client = TestClient(app)
    with patch("fastapi.WebSocket.accept", side_effect=Exception("Connection error")):
        with pytest.raises(Exception):
            with client.websocket_connect("/account/ws/monitor"):
                pass

def test_websocket_futures_config():
    """Test WebSocket handling of futures configuration."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Set initial balance
        websocket.send_json({"balance": "1500"})
        response = websocket.receive_json()
        assert response["current_stage"] == "growth"

        # Send futures configuration
        futures_config = {
            "balance": "1500",
            "futures_config": {
                "leverage": 30,
                "margin_type": "cross",
                "position_size": "150",
                "max_position_size": "300",
                "risk_level": 0.5
            }
        }
        websocket.send_json(futures_config)
        response = websocket.receive_json()
        assert "current_balance" in response
        assert "max_leverage" in response
        assert response["max_leverage"] == 50  # Max leverage for growth stage

def test_websocket_stage_transition_notification():
    """Test WebSocket notifications for stage transitions."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Initial stage
        websocket.send_json({"balance": "800"})
        response = websocket.receive_json()
        assert response["current_stage"] == "initial"
        assert response["transition"] is None

        # Upgrade to growth stage
        websocket.send_json({"balance": "1200"})
        response = websocket.receive_json()
        assert response["current_stage"] == "growth"
        assert response["transition"] == "UPGRADE"
        assert response["previous_stage"] == "initial"

        # Downgrade back to initial stage
        websocket.send_json({"balance": "800"})
        response = websocket.receive_json()
        assert response["current_stage"] == "initial"
        assert response["transition"] == "DOWNGRADE"
        assert response["previous_stage"] == "growth"

def test_websocket_malformed_json():
    """Test WebSocket handling of malformed JSON data."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Send malformed JSON
        websocket.send_text("invalid json")
        response = websocket.receive_json()
        assert "error" in response
        assert "Invalid JSON format" in response["error"]

        # Send JSON with missing required fields
        websocket.send_json({})
        response = websocket.receive_json()
        assert "error" in response
        assert "Missing balance field" in response["error"]

def test_websocket_expert_stage():
    """Test WebSocket handling of expert stage accounts."""
    client = TestClient(app)
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Move to expert stage
        websocket.send_json({"balance": "2000000"})
        response = websocket.receive_json()
        assert response["current_stage"] == "expert"
        assert response["stage_progress"] == "100"
        assert response["max_leverage"] == 125

        # Test position size calculation in expert stage
        futures_config = {
            "balance": "2000000",
            "futures_config": {
                "leverage": 100,
                "margin_type": "isolated",
                "position_size": "200000",
                "max_position_size": "400000",
                "risk_level": 0.75
            }
        }
        websocket.send_json(futures_config)
        response = websocket.receive_json()
        assert "current_balance" in response
        assert response["max_leverage"] == 125
