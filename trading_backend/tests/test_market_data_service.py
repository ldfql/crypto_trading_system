"""Tests for market data service."""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from app.services.market_analysis.market_data_service import MarketDataService
from app.models.futures import FuturesConfig, MarginType

@pytest.fixture
def market_data_service():
    """Create a market data service instance."""
    return MarketDataService()

def test_get_current_price(market_data_service):
    """Test getting current price for a symbol."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"price": "45000.00"}
        price = market_data_service.get_current_price("BTCUSDT")
        assert price == Decimal("45000.00")
        mock_get.assert_called_once()

def test_get_24h_price_range(market_data_service):
    """Test getting 24-hour price range."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "highPrice": "46000.00",
            "lowPrice": "44000.00"
        }
        high, low = market_data_service.get_24h_price_range("BTCUSDT")
        assert high == Decimal("46000.00")
        assert low == Decimal("44000.00")
        mock_get.assert_called_once()

def test_get_trading_fees(market_data_service):
    """Test getting trading fees."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "makerCommission": 10,  # 0.1%
            "takerCommission": 10   # 0.1%
        }
        maker_fee, taker_fee = market_data_service.get_trading_fees()
        assert maker_fee == Decimal("0.001")
        assert taker_fee == Decimal("0.001")
        mock_get.assert_called_once()

def test_validate_price_data(market_data_service):
    """Test price data validation."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        def mock_api_call(*args, **kwargs):
            if "ticker/price" in args[0]:
                return MagicMock(json=lambda: {"price": "45000.00"})
            elif "ticker/24hr" in args[0]:
                return MagicMock(json=lambda: {"highPrice": "46000.00", "lowPrice": "44000.00"})
            elif "depth" in args[0]:
                return MagicMock(json=lambda: {
                    "bids": [["44900.00", "1.5"]],
                    "asks": [["45100.00", "1.0"]]
                })
            return MagicMock(json=lambda: {})

        mock_get.side_effect = mock_api_call

        # Test valid price within range
        assert market_data_service.validate_price_data(Decimal("45000.00"), "BTCUSDT") is True

        # Test price outside 24h range
        assert market_data_service.validate_price_data(Decimal("47000.00"), "BTCUSDT") is False

        # Test price too far from market depth
        assert market_data_service.validate_price_data(Decimal("40000.00"), "BTCUSDT") is False

        # Test negative price
        assert market_data_service.validate_price_data(Decimal("-100.00"), "BTCUSDT") is False

        # Test zero price
        assert market_data_service.validate_price_data(Decimal("0"), "BTCUSDT") is False

        # Test order-of-magnitude error
        assert market_data_service.validate_price_data(Decimal("450000.00"), "BTCUSDT") is False

        # Test API error handling
        mock_get.side_effect = Exception("API Error")
        assert market_data_service.validate_price_data(Decimal("45000.00"), "BTCUSDT") is False

def test_calculate_fees(market_data_service):
    """Test fee calculation."""
    config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("1000"),
        max_position_size=Decimal("2000"),
        risk_level=0.1
    )

    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "makerCommission": 10,  # 0.1%
            "takerCommission": 10   # 0.1%
        }
        fees = market_data_service.calculate_fees(config)
        assert isinstance(fees, dict)
        assert "maker_fee" in fees
        assert "taker_fee" in fees
        assert fees["maker_fee"] == Decimal("0.001")
        assert fees["taker_fee"] == Decimal("0.001")

def test_error_handling(market_data_service):
    """Test error handling for API failures."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        mock_get.side_effect = Exception("API Error")
        with pytest.raises(Exception):
            market_data_service.get_current_price("BTCUSDT")

def test_validate_futures_price(market_data_service):
    """Test futures price validation."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        # Mock 24h price range
        mock_get.return_value.json.return_value = {
            "highPrice": "46000.00",
            "lowPrice": "44000.00"
        }

        # Test price within range
        assert market_data_service.validate_futures_price(Decimal("45000.00"), "BTCUSDT") is True

        # Test price above range
        assert market_data_service.validate_futures_price(Decimal("47000.00"), "BTCUSDT") is False

        # Test price below range
        assert market_data_service.validate_futures_price(Decimal("43000.00"), "BTCUSDT") is False

def test_get_market_depth(market_data_service):
    """Test getting market depth."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "bids": [["45000.00", "1.5"], ["44900.00", "2.0"]],
            "asks": [["45100.00", "1.0"], ["45200.00", "3.0"]]
        }
        depth = market_data_service.get_market_depth("BTCUSDT")
        assert len(depth["bids"]) == 2
        assert len(depth["asks"]) == 2
        assert depth["bids"][0][0] == Decimal("45000.00")
        assert depth["asks"][0][0] == Decimal("45100.00")

@pytest.mark.asyncio
async def test_get_market_data(market_data_service):
    """Test market data retrieval."""
    df = await market_data_service.get_market_data("BTCUSDT", interval="1h", limit=100)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 100
    assert all(col in df.columns for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    assert df['volume'].iloc[0] == 1000000
    assert df['open'].iloc[0] == 40000

@pytest.mark.asyncio
async def test_analyze_pair_metrics(market_data_service):
    """Test pair metrics analysis."""
    metrics = await market_data_service.analyze_pair_metrics("BTCUSDT")
    assert isinstance(metrics, dict)
    assert all(key in metrics for key in ['volume_24h', 'volatility', 'rsi', 'macd', 'atr'])
    assert isinstance(metrics['volume_24h'], float)
    assert isinstance(metrics['volatility'], float)
    assert isinstance(metrics['rsi'], float)
    assert isinstance(metrics['macd'], float)
    assert isinstance(metrics['atr'], float)
    assert metrics['volume_24h'] > 0
    assert metrics['volatility'] >= 0

@pytest.mark.asyncio
async def test_get_optimal_pairs(market_data_service):
    """Test optimal pairs selection based on account balance."""
    # Test small account
    pairs = await market_data_service.get_optimal_pairs(Decimal("500"))
    assert len(pairs) == 2
    assert "BTCUSDT" in pairs
    assert "ETHUSDT" in pairs

    # Test medium account
    pairs = await market_data_service.get_optimal_pairs(Decimal("5000"))
    assert len(pairs) == 3
    assert "BNBUSDT" in pairs

    # Test large account
    pairs = await market_data_service.get_optimal_pairs(Decimal("15000"))
    assert len(pairs) == 6
    assert "ADAUSDT" in pairs
    assert "SOLUSDT" in pairs
    assert "DOTUSDT" in pairs

@pytest.mark.asyncio
async def test_calculate_position_size(market_data_service):
    """Test position size calculation based on account balance."""
    # Test small account
    size, leverage = await market_data_service.calculate_position_size("BTCUSDT", Decimal("500"))
    assert size == Decimal("50")  # 10% of balance
    assert leverage == 20

    # Test medium account
    size, leverage = await market_data_service.calculate_position_size("BTCUSDT", Decimal("15000"))
    assert size == Decimal("2250")  # 15% of balance
    assert leverage == 10

    # Test large account
    size, leverage = await market_data_service.calculate_position_size("BTCUSDT", Decimal("150000"))
    assert size == Decimal("30000")  # 20% of balance
    assert leverage == 5

def test_market_depth_error_handling(market_data_service):
    """Test market depth error handling."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        # Test malformed JSON response
        mock_get.return_value.json.side_effect = ValueError("Invalid JSON")
        with pytest.raises(Exception):
            market_data_service.get_market_depth("BTCUSDT")

        # Test missing data in response
        mock_get.return_value.json.return_value = {}
        with pytest.raises(KeyError):
            market_data_service.get_market_depth("BTCUSDT")

        # Test network error
        mock_get.side_effect = Exception("Network Error")
        with pytest.raises(Exception):
            market_data_service.get_market_depth("BTCUSDT")

def test_trading_fees_error_handling(market_data_service):
    """Test trading fees error handling."""
    with patch('app.services.market_analysis.market_data_service.requests.get') as mock_get:
        # Test malformed commission data
        mock_get.return_value.json.return_value = {
            "makerCommission": "invalid",
            "takerCommission": "invalid"
        }
        with pytest.raises(Exception):
            market_data_service.get_trading_fees()

        # Test missing commission data
        mock_get.return_value.json.return_value = {}
        with pytest.raises(KeyError):
            market_data_service.get_trading_fees()
