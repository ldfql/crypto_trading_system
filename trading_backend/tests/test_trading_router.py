import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.models.signals import TradingSignal
from app.repositories.signal_repository import SignalRepository

client = TestClient(app)

@pytest.fixture
def mock_signal():
    return {
        "id": 1,
        "symbol": "BTC/USDT",
        "direction": "LONG",
        "entry_price": 50000.0,
        "current_price": 51000.0,
        "confidence": 0.85,
        "status": "validated",
        "market_phase": "accumulation",
        "created_at": datetime.utcnow().isoformat(),
        "last_updated": datetime.utcnow().isoformat()
    }

@pytest.fixture
def mock_signals(mock_signal):
    signals = []
    base_time = datetime.utcnow()

    # Create signals at different times and with different statuses
    for i in range(5):
        signal = mock_signal.copy()
        signal["id"] = i + 1
        signal["created_at"] = (base_time - timedelta(hours=i*4)).isoformat()
        signal["status"] = "validated" if i % 2 == 0 else "expired"
        signal["confidence"] = 0.8 + (i * 0.03)
        signals.append(signal)

    return signals

async def test_get_24h_signals(mock_signals, monkeypatch):
    async def mock_get_signals_since(*args, **kwargs):
        return [TradingSignal(**signal) for signal in mock_signals]

    monkeypatch.setattr(SignalRepository, "get_signals_since", mock_get_signals_since)

    response = client.get("/trading/signals/24h")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 5
    assert all(isinstance(signal["id"], int) for signal in data)
    assert all(isinstance(signal["confidence"], float) for signal in data)

async def test_get_24h_signals_with_filters(mock_signals, monkeypatch):
    async def mock_get_signals_since(*args, **kwargs):
        filtered = [
            signal for signal in mock_signals
            if signal["status"] == kwargs.get("status", signal["status"]) and
            signal["confidence"] >= kwargs.get("min_confidence", 0)
        ]
        return [TradingSignal(**signal) for signal in filtered]

    monkeypatch.setattr(SignalRepository, "get_signals_since", mock_get_signals_since)

    # Test status filter
    response = client.get("/trading/signals/24h?status=validated")
    assert response.status_code == 200
    data = response.json()
    assert all(signal["status"] == "validated" for signal in data)

    # Test confidence filter
    response = client.get("/trading/signals/24h?min_confidence=0.85")
    assert response.status_code == 200
    data = response.json()
    assert all(signal["confidence"] >= 0.85 for signal in data)

    # Test time range filter
    response = client.get("/trading/signals/24h?time_range=4h")
    assert response.status_code == 200

async def test_get_current_signals(mock_signals, monkeypatch):
    async def mock_get_active_signals(*args, **kwargs):
        active = [
            signal for signal in mock_signals
            if signal["status"] != "expired"
        ]
        return [TradingSignal(**signal) for signal in active]

    monkeypatch.setattr(SignalRepository, "get_active_signals", mock_get_active_signals)

    response = client.get("/trading/signals/current")
    assert response.status_code == 200

    data = response.json()
    assert all(signal["status"] != "expired" for signal in data)

async def test_invalid_parameters():
    # Test invalid time range
    response = client.get("/trading/signals/24h?time_range=invalid")
    assert response.status_code == 422

    # Test invalid status
    response = client.get("/trading/signals/24h?status=invalid")
    assert response.status_code == 422

    # Test invalid confidence
    response = client.get("/trading/signals/24h?min_confidence=2.0")
    assert response.status_code == 422
