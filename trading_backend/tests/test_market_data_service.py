"""Tests for market data service."""
import pytest
from decimal import Decimal
from unittest.mock import patch, Mock
import requests
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
                return Mock(json=lambda: {"price": "45000.00"})
            elif "ticker/24hr" in args[0]:
                return Mock(json=lambda: {"highPrice": "46000.00", "lowPrice": "44000.00"})
            elif "depth" in args[0]:
                return Mock(json=lambda: {
                    "bids": [["44900.00", "1.5"]],
                    "asks": [["45100.00", "1.0"]]
                })
            return Mock(json=lambda: {})

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
    """Test pair metrics analysis with various market conditions."""
    # Test normal market conditions
    with patch.object(market_data_service, 'get_market_data') as mock_data:
        df = pd.DataFrame({
            'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=100, freq='H'),
            'open': [40000] * 100,
            'high': [41000] * 100,
            'low': [39000] * 100,
            'close': [40500] * 100,
            'volume': [1000000] * 100
        })
        mock_data.return_value = df
        metrics = await market_data_service.analyze_pair_metrics('BTCUSDT')
        assert isinstance(metrics, dict)
        assert all(key in metrics for key in [
            'volume_24h', 'volume_score', 'volatility', 'volatility_score',
            'rsi', 'macd', 'atr'
        ])
        assert metrics['volume_24h'] == 24000000  # 24 * 1000000
        assert 0 <= metrics['volume_score'] <= 100  # Volume score should be normalized
        assert abs(metrics['volatility'] - 0.05) < 0.01  # (41000 - 39000) / 40000
        assert 0 <= metrics['volatility_score'] <= 100  # Volatility score should be normalized
        assert 0 <= metrics['rsi'] <= 100
        assert isinstance(metrics['macd'], float)
        assert metrics['atr'] > 0

    # Test high volatility market
    with patch.object(market_data_service, 'get_market_data') as mock_data:
        df = pd.DataFrame({
            'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=100, freq='H'),
            'open': [40000] * 100,
            'high': [44000] * 100,
            'low': [36000] * 100,
            'close': [42000] * 100,
            'volume': [2000000] * 100
        })
        mock_data.return_value = df
        metrics = await market_data_service.analyze_pair_metrics('BTCUSDT')
        assert metrics['volatility'] > 0.2  # High volatility
        assert metrics['volatility_score'] > 80  # High volatility score
        assert metrics['volume_score'] > 50  # Higher volume score

    # Test low volume market
    with patch.object(market_data_service, 'get_market_data') as mock_data:
        df = pd.DataFrame({
            'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=100, freq='H'),
            'open': [40000] * 100,
            'high': [40100] * 100,
            'low': [39900] * 100,
            'close': [40050] * 100,
            'volume': [100000] * 100
        })
        mock_data.return_value = df
        metrics = await market_data_service.analyze_pair_metrics('BTCUSDT')
        assert metrics['volatility'] < 0.01  # Low volatility
        assert metrics['volatility_score'] < 20  # Low volatility score
        assert metrics['volume_score'] < 30  # Low volume score

    # Test error handling
    with patch.object(market_data_service, 'get_market_data') as mock_data:
        mock_data.side_effect = Exception("API Error")
        with pytest.raises(ValueError, match="Failed to analyze metrics"):
            await market_data_service.analyze_pair_metrics('BTCUSDT')

    # Test missing data handling
    with patch.object(market_data_service, 'get_market_data') as mock_data:
        df = pd.DataFrame({
            'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=100, freq='H'),
            'open': [40000] * 100,
            'high': [41000] * 100,
            'low': [39000] * 100,
            'close': [40500] * 100,
            'volume': [None] * 100
        })
        mock_data.return_value = df
        with pytest.raises(ValueError, match="Invalid market data"):
            await market_data_service.analyze_pair_metrics('BTCUSDT')

@pytest.mark.asyncio
async def test_get_optimal_pairs(market_data_service):
    """Test optimal pair selection with different market conditions."""
    # Test normal market conditions
    with patch.object(market_data_service, 'get_all_trading_pairs') as mock_pairs, \
         patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
        mock_pairs.return_value = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
        mock_metrics.side_effect = [
            {'volume_score': 90, 'volatility_score': 85},  # BTCUSDT
            {'volume_score': 85, 'volatility_score': 80},  # ETHUSDT
            {'volume_score': 75, 'volatility_score': 70},  # BNBUSDT
            {'volume_score': 60, 'volatility_score': 65},  # ADAUSDT
            {'volume_score': 55, 'volatility_score': 60}   # SOLUSDT
        ]
        pairs = await market_data_service.get_optimal_pairs(Decimal("1000"))
        assert len(pairs) == 3
        assert pairs == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    # Test when some pairs fail validation
    with patch.object(market_data_service, 'get_all_trading_pairs') as mock_pairs, \
         patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
        mock_pairs.return_value = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        mock_metrics.side_effect = [
            {'volume_score': 90, 'volatility_score': 85},  # BTCUSDT
            ValueError("API Error"),                        # ETHUSDT fails
            {'volume_score': 75, 'volatility_score': 70}   # BNBUSDT
        ]
        pairs = await market_data_service.get_optimal_pairs(Decimal("1000"))
        assert len(pairs) == 2
        assert pairs == ["BTCUSDT", "BNBUSDT"]

    # Test error handling when all pairs fail
    with patch.object(market_data_service, 'get_all_trading_pairs') as mock_pairs, \
         patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
        mock_pairs.return_value = ["BTCUSDT", "ETHUSDT"]
        mock_metrics.side_effect = [ValueError("API Error"), ValueError("API Error")]
        with pytest.raises(ValueError, match="Failed to analyze any trading pairs"):
            await market_data_service.get_optimal_pairs(Decimal("1000"))

    # Test with empty pairs list
    with patch.object(market_data_service, 'get_all_trading_pairs') as mock_pairs:
        mock_pairs.return_value = []
        with pytest.raises(ValueError, match="No valid pairs found"):
            await market_data_service.get_optimal_pairs(Decimal("1000"))

@pytest.mark.asyncio
async def test_calculate_position_size(market_data_service):
    """Test position size calculation for different account stages."""
    # Mock trading fees
    with patch.object(market_data_service, 'get_trading_fees') as mock_fees:
        mock_fees.return_value = (Decimal('0.001'), Decimal('0.001'))  # 0.1% maker/taker fees

        # Test small account (< 10000)
        with patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
            mock_metrics.return_value = {'volatility': 0.03}
            position_size, leverage = await market_data_service.calculate_position_size('BTCUSDT', Decimal('1000'))
            assert position_size == Decimal('100')  # 10% of balance
            assert leverage == 20

        # Test medium account (10000-100000)
        with patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
            mock_metrics.return_value = {'volatility': 0.03}
            position_size, leverage = await market_data_service.calculate_position_size('BTCUSDT', Decimal('50000'))
            assert position_size == Decimal('7500')  # 15% of balance
            assert leverage == 10

        # Test large account (>100000)
        with patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
            mock_metrics.return_value = {'volatility': 0.03}
            position_size, leverage = await market_data_service.calculate_position_size('BTCUSDT', Decimal('200000'))
            assert position_size == Decimal('40000')  # 20% of balance
            assert leverage == 5

        # Test high volatility adjustment
        with patch.object(market_data_service, 'analyze_pair_metrics') as mock_metrics:
            mock_metrics.return_value = {'volatility': 0.06}
            position_size, leverage = await market_data_service.calculate_position_size('BTCUSDT', Decimal('1000'))
            assert position_size == Decimal('80')  # 8% of balance (reduced due to high volatility)
            assert leverage == 20

    # Test error handling
    with pytest.raises(ValueError, match="Account balance must be positive"):
        await market_data_service.calculate_position_size('BTCUSDT', Decimal('0'))

    # Test missing commission data
    with patch.object(market_data_service, 'get_trading_fees') as mock_fees:
        mock_fees.side_effect = KeyError("Missing commission data")
        with pytest.raises(KeyError, match="Missing commission data"):
            await market_data_service.calculate_position_size('BTCUSDT', Decimal('1000'))

@pytest.mark.asyncio
async def test_get_all_trading_pairs_error_handling():
    """Test error handling in trading pairs retrieval."""
    service = MarketDataService()

    # Test API error
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("API Error")
        pairs = await service.get_all_trading_pairs()
        assert pairs == service.trading_pairs  # Should return default pairs

    # Test invalid response format
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {}  # Missing symbols data
        pairs = await service.get_all_trading_pairs()
        assert pairs == service.trading_pairs

    # Test successful response
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING"},
                {"symbol": "ETHUSDT", "status": "TRADING"},
                {"symbol": "XRPUSDT", "status": "HALT"},  # Should be excluded
                {"symbol": "BNBUSDT", "status": "TRADING"}
            ]
        }
        pairs = await service.get_all_trading_pairs()
        assert len(pairs) == 3
        assert all(pair in pairs for pair in ["BTCUSDT", "ETHUSDT", "BNBUSDT"])
        assert "XRPUSDT" not in pairs

@pytest.mark.asyncio
async def test_get_24h_volume_error_handling():
    """Test error handling in 24h volume retrieval."""
    service = MarketDataService()

    # Test API error
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("API Error")
        volume = await service.get_24h_volume("BTCUSDT")
        assert volume == Decimal("0")  # Should return 0 on error

    # Test invalid response format
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {}  # Missing volume data
        volume = await service.get_24h_volume("BTCUSDT")
        assert volume == Decimal("0")

    # Test successful response
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"volume": "1000.50"}
        volume = await service.get_24h_volume("BTCUSDT")
        assert volume == Decimal("1000.50")
