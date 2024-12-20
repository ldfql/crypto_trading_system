"""Tests for account monitoring endpoints."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.futures import AccountStage, FuturesConfig, MarginType, AccountStageTransition
from app.services.monitoring.account_monitor import AccountMonitor

client = TestClient(app)

@pytest.fixture
def account_monitor():
    """Create account monitor instance for testing."""
    return AccountMonitor(initial_balance=Decimal("1000"))

def test_get_account_status():
    """Test getting account status."""
    response = client.get("/account/status", params={"balance": "1000"})
    assert response.status_code == 200
    data = response.json()
    assert data["current_stage"] == AccountStage.GROWTH.value
    assert data["current_balance"] == "1000"
    assert "stage_progress" in data
    assert "remaining_to_next_stage" in data
    assert "max_leverage" in data

def test_update_account_balance():
    """Test account balance update endpoint."""
    # Test stage transition from INITIAL to GROWTH
    response = client.post(
        "/account/update",
        json={
            "balance": "1500",
            "leverage": 20,
            "risk_percentage": "2"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_stage"] == AccountStage.GROWTH.value
    assert data["current_balance"] == "1500"
    assert "stage_progress" in data
    assert "max_leverage" in data
    assert "recommended_position_size" in data

    # Test stage transition from GROWTH to ADVANCED
    response = client.post(
        "/account/update",
        json={
            "balance": "15000",
            "leverage": 30,
            "risk_percentage": "2"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_stage"] == AccountStage.ADVANCED.value
    assert "stage_progress" in data
    assert "max_leverage" in data

def test_validate_futures_config():
    """Test futures configuration validation endpoint."""
    # Test valid configuration for GROWTH stage
    config = {
        "leverage": 20,
        "margin_type": MarginType.CROSS.value,
        "position_size": "150",
        "max_position_size": "300",
        "risk_level": 0.5
    }
    response = client.post(
        "/account/validate-config",
        params={"balance": "5000"},  # GROWTH stage (1000U-10000U)
        json=config
    )
    assert response.status_code == 200
    assert response.json()["is_valid"] is True

    # Test invalid leverage for GROWTH stage
    invalid_config = {
        "leverage": 100,  # Too high for GROWTH stage
        "margin_type": MarginType.CROSS.value,
        "position_size": "150",
        "max_position_size": "300",
        "risk_level": 0.5
    }
    response = client.post(
        "/account/validate-config",
        params={"balance": "5000"},
        json=invalid_config
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "Growth stage max leverage is 50x" in data["error"]

def test_get_trading_parameters():
    """Test getting trading parameters."""
    response = client.get(
        "/account/trading-parameters",
        params={"balance": "10000", "risk_percentage": "2"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["account_stage"] == AccountStage.ADVANCED.value
    assert data["current_balance"] == "10000"
    assert "position_size" in data
    assert "margin_type" in data
    assert "leverage" in data
    assert "estimated_fees" in data

@pytest.mark.asyncio
async def test_websocket_monitoring():
    """Test WebSocket endpoint for real-time account monitoring."""
    with client.websocket_connect("/account/ws/monitor") as websocket:
        # Test INITIAL stage
        websocket.send_json({"balance": "500"})
        data = websocket.receive_json()
        assert data["current_stage"] == AccountStage.INITIAL.value
        assert data["max_leverage"] == 20

        # Test GROWTH stage
        websocket.send_json({"balance": "5000"})
        data = websocket.receive_json()
        assert data["current_stage"] == AccountStage.GROWTH.value
        assert data["max_leverage"] == 50

        # Test ADVANCED stage
        websocket.send_json({"balance": "50000"})
        data = websocket.receive_json()
        assert data["current_stage"] == AccountStage.ADVANCED.value
        assert data["max_leverage"] == 75

        # Test PROFESSIONAL stage
        websocket.send_json({"balance": "500000"})
        data = websocket.receive_json()
        assert data["current_stage"] == AccountStage.PROFESSIONAL.value
        assert data["max_leverage"] == 100

        # Test EXPERT stage (path to 1亿U)
        websocket.send_json({"balance": "2000000"})
        data = websocket.receive_json()
        assert data["current_stage"] == AccountStage.EXPERT.value
        assert data["max_leverage"] == 125
        assert "stage_progress" in data
        assert "remaining_to_next_stage" in data

def test_error_handling():
    """Test error handling in account monitoring endpoints."""
    # Test invalid balance
    response = client.get("/account/status", params={"balance": "-1000"})
    assert response.status_code == 400

    # Test missing parameters
    response = client.get("/account/trading-parameters")
    assert response.status_code == 422

    # Test invalid risk percentage
    response = client.post(
        "/account/update",
        json={
            "balance": "1000",
            "leverage": 20,
            "risk_percentage": "10"  # Too high
        }
    )
    assert response.status_code == 400
