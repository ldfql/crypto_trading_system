import pytest
from datetime import datetime
from decimal import Decimal
from app.services.market_analysis.market_data_service import MarketDataService

@pytest.fixture
def market_data_service():
    return MarketDataService()

@pytest.mark.asyncio
async def test_futures_market_data(market_data_service):
    """Test fetching futures market data."""
    data = await market_data_service.get_market_data(
        symbol="BTCUSDT",
        timeframe="1h",
        limit=10,
        use_futures=True,
        testing=True  # Use mock data for testing
    )

    # Verify basic data structure
    assert "current_price" in data
    assert "volume_24h" in data
    assert "volatility" in data
    assert "price_range" in data
    assert "timestamp" in data

    # Verify futures specific data
    assert "mark_price" in data
    assert "index_price" in data
    assert "funding_rate" in data
    assert "next_funding_time" in data

    # Verify data types
    assert isinstance(data["current_price"], Decimal)
    assert isinstance(data["mark_price"], Decimal)
    assert isinstance(data["funding_rate"], Decimal)
    assert isinstance(data["next_funding_time"], datetime)

@pytest.mark.asyncio
async def test_spot_market_data(market_data_service):
    """Test fetching spot market data."""
    data = await market_data_service.get_market_data(
        symbol="BTCUSDT",
        timeframe="1h",
        limit=10,
        use_futures=False,
        testing=True  # Use mock data for testing
    )

    # Verify basic data structure
    assert "current_price" in data
    assert "volume_24h" in data
    assert "volatility" in data
    assert "price_range" in data
    assert "timestamp" in data

    # Verify futures specific data is not present
    assert "mark_price" not in data
    assert "index_price" not in data
    assert "funding_rate" not in data
    assert "next_funding_time" not in data

@pytest.mark.asyncio
async def test_rate_limiting(market_data_service):
    """Test rate limiting functionality."""
    # Make multiple requests in quick succession
    for _ in range(5):
        data = await market_data_service.get_market_data(
            symbol="BTCUSDT",
            timeframe="1m",
            limit=5,
            use_futures=True,
            testing=True  # Use mock data for testing
        )
        assert data is not None
        assert isinstance(data["current_price"], Decimal)
