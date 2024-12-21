"""Tests for trading router endpoints."""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.models.futures import MarginType
from app.schemas.trading import TradingSignal
from app.services.trading.pair_selector import PairSelector

client = TestClient(app)

@pytest.fixture
def mock_pair_selector():
    """Create mock pair selector for testing."""
    mock = MagicMock(spec=PairSelector)
    mock.select_trading_pairs = MagicMock()
    return mock

def test_get_trading_pairs(mock_pair_selector):
    """Test getting recommended trading pairs."""
    mock_signals = [
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("1000.00"),
            leverage=20,
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),  # Realistic profit (9% of position size)
            confidence=0.85
        )
    ]
    mock_pair_selector.select_trading_pairs.return_value = mock_signals

    with patch('app.dependencies.get_pair_selector', return_value=mock_pair_selector):
        response = client.get("/trading/pairs?account_balance=1000&max_pairs=3")
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert len(data["signals"]) == 1
        signal = data["signals"][0]
        assert signal["pair"] == "BTCUSDT"
        assert Decimal(signal["entry_price"]) == Decimal("45000.00")
        assert signal["margin_type"] == "CROSS"

def test_get_trading_pairs_invalid_balance():
    """Test getting trading pairs with invalid balance."""
    response = client.get("/trading/pairs?account_balance=-1000&max_pairs=3")
    assert response.status_code == 422

def test_get_trading_pairs_invalid_max_pairs():
    """Test getting trading pairs with invalid max_pairs."""
    response = client.get("/trading/pairs?account_balance=1000&max_pairs=11")
    assert response.status_code == 422

def test_get_trading_pairs_missing_balance():
    """Test getting trading pairs without account balance."""
    response = client.get("/trading/pairs?max_pairs=3")
    assert response.status_code == 422

def test_get_trading_pairs_with_default_max_pairs(mock_pair_selector):
    """Test getting trading pairs with default max_pairs value."""
    mock_signals = [
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("1000.00"),
            leverage=20,
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),  # Realistic profit (9% of position size)
            confidence=0.85
        )
    ]
    mock_pair_selector.select_trading_pairs.return_value = mock_signals

    with patch('app.dependencies.get_pair_selector', return_value=lambda: mock_pair_selector):
        response = client.get("/trading/pairs?account_balance=1000")
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)
        mock_pair_selector.select_trading_pairs.assert_called_once_with(
            account_balance=Decimal("1000"),
            max_pairs=3  # Default value from the router
        )
