import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.routers.websocket import router
from app.services.analysis.prediction_analyzer import PredictionAnalyzer
from app.repositories.signal_repository import SignalRepository
from app.services.monitoring.signal_monitor import SignalMonitor
from app.dependencies import get_prediction_analyzer, get_session, get_market_data_service
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.signals import TradingSignal
from datetime import datetime


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_market_data_service():
    service = Mock()
    return service


@pytest.fixture
def mock_prediction_analyzer():
    mock_opportunities = [{
        "id": 1,
        "symbol": "BTC/USDT",
        "type": "LONG",
        "entry_price": 45000.0,
        "take_profit": 48000.0,
        "stop_loss": 44000.0,
        "position_size": 0.1,
        "leverage": 10,
        "margin_type": "isolated",
        "confidence": 0.85,
        "fees": 0.002,
        "expected_profit": 0.15,
        "entry_conditions": {
            "stages": [],
            "technical_indicators": {"rsi": 65},
            "market_conditions": {
                "volume_24h": 1000000,
                "volatility": 0.2,
                "trend": "bullish"
            }
        },
        "ranking_factors": {
            "historical_accuracy": 0.82,
            "market_volatility_score": 0.2,
            "volume_factor": 1000000,
            "market_phase_multiplier": 1.1,
            "technical_indicators": {"rsi": 65},
            "sentiment_analysis": 0.75
        },
        "performance_metrics": {
            "total_signals": 1,
            "accuracy_by_timeframe": {},
            "accuracy_by_market_phase": {},
            "profit_loss_distribution": {}
        },
        "market_analysis": {
            "volatility": 0.2,
            "trend": "bullish"
        }
    }]

    analyzer = MagicMock(spec=PredictionAnalyzer)
    async def mock_find_best_opportunities():
        return mock_opportunities
    analyzer.find_best_opportunities = mock_find_best_opportunities
    return analyzer


@pytest.fixture(scope="function")
def test_app(mock_db_session, mock_market_data_service, mock_prediction_analyzer):
    """Create a test FastAPI app with proper dependency injection."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_session():
        yield mock_db_session

    def override_get_market_data_service():
        return mock_market_data_service

    def override_get_prediction_analyzer():
        return mock_prediction_analyzer

    app.dependency_overrides = {
        get_session: override_get_session,
        get_market_data_service: override_get_market_data_service,
        get_prediction_analyzer: override_get_prediction_analyzer
    }

    client = TestClient(app)
    return client


def test_opportunities_websocket(test_app):
    """Test that opportunities websocket sends correctly formatted data."""
    with test_app.websocket_connect("/ws/opportunities") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "opportunities"
        assert isinstance(data["timestamp"], str)
        assert len(data["data"]) == 1
        opportunity = data["data"][0]
        assert opportunity["symbol"] == "BTC/USDT"
        assert opportunity["type"] == "LONG"


def test_opportunities_websocket_no_data(test_app, mock_prediction_analyzer):
    """Test websocket behavior when no opportunities are available."""
    async def mock_find_best_opportunities():
        return []
    mock_prediction_analyzer.find_best_opportunities = mock_find_best_opportunities

    with test_app.websocket_connect("/ws/opportunities") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "opportunities"
        assert isinstance(data["timestamp"], str)
        assert len(data["data"]) == 0


def test_opportunities_websocket_error_handling(test_app, mock_prediction_analyzer):
    """Test websocket error handling."""
    async def mock_find_best_opportunities():
        raise Exception("Test error")
    mock_prediction_analyzer.find_best_opportunities = mock_find_best_opportunities

    with test_app.websocket_connect("/ws/opportunities") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert data["message"] == "Test error"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()
        assert exc_info.value.code == 1000
        assert str(exc_info.value.reason) == "Test error"


@pytest.mark.asyncio
async def test_dependency_injection(mock_db_session):
    """Test that dependency injection works correctly."""
    signal_repository = Mock(spec=SignalRepository)
    signal_monitor = Mock(spec=SignalMonitor)

    with patch("app.dependencies.get_signal_repository", return_value=signal_repository), \
         patch("app.dependencies.get_signal_monitor", return_value=signal_monitor):
        analyzer = await get_prediction_analyzer(signal_repository, signal_monitor)
        assert isinstance(analyzer, PredictionAnalyzer)
        assert analyzer.signal_repository == signal_repository
        assert analyzer.signal_monitor == signal_monitor
