import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from app.services.trading.pair_selector import PairSelector
from app.services.market_analysis.market_data_service import MarketDataService
from app.models.futures import FuturesConfig, MarginType

@pytest.fixture
def market_data_service():
    mock = AsyncMock(spec=MarketDataService)
    # Setup required mock methods
    mock.get_24h_volume = AsyncMock()
    mock.get_current_price = AsyncMock()
    mock.get_volatility = AsyncMock()
    mock.get_support_level = AsyncMock()
    mock.get_resistance_level = AsyncMock()
    mock.get_trend_strength = AsyncMock()
    mock.get_average_volume = AsyncMock()
    mock.get_all_trading_pairs = AsyncMock()
    return mock

@pytest.fixture
def pair_selector(market_data_service):
    return PairSelector(market_data_service)

@pytest.mark.asyncio
async def test_meets_volume_requirements(pair_selector, market_data_service):
    """Test volume requirement checking."""
    market_data_service.get_24h_volume.return_value = Decimal("2000000")
    assert await pair_selector._meets_volume_requirements("BTCUSDT")

    market_data_service.get_24h_volume.return_value = Decimal("500000")
    assert not await pair_selector._meets_volume_requirements("BTCUSDT")

@pytest.mark.asyncio
async def test_calculate_trading_config(pair_selector):
    """Test trading configuration calculation for different account sizes."""
    test_cases = [
        (Decimal("100"), 20, Decimal("0.1")),    # Minimum account size
        (Decimal("500"), 15, Decimal("0.1")),    # Small account
        (Decimal("5000"), 10, Decimal("0.15")),  # Medium account
        (Decimal("50000"), 5, Decimal("0.2")),   # Large account
        (Decimal("500000"), 3, Decimal("0.25")), # Very large account
        (Decimal("5000000"), 2, Decimal("0.25")),# Huge account
        (Decimal("100000000"), 1, Decimal("0.25")) # Maximum target (1亿U)
    ]

    for balance, expected_leverage, expected_risk in test_cases:
        config = pair_selector._calculate_trading_config(balance, Decimal("50000"))
        assert config.leverage == expected_leverage
        assert config.risk_level == float(expected_risk)
        assert config.margin_type == MarginType.CROSS
        assert config.position_size == balance * expected_risk

@pytest.mark.asyncio
async def test_calculate_signal_confidence(pair_selector, market_data_service):
    """Test signal confidence calculation."""
    market_data_service.get_trend_strength.return_value = 0.9
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_average_volume.return_value = Decimal("2500000")

    confidence = await pair_selector._calculate_signal_confidence(
        "BTCUSDT",
        Decimal("50000"),
        Decimal("51500"),  # 3% take profit
        Decimal("49750")   # 0.5% stop loss
    )

    assert 0.82 <= confidence <= 1.0

@pytest.mark.asyncio
async def test_analyze_trading_opportunity(pair_selector, market_data_service):
    """Test complete trading opportunity analysis."""
    # Setup mock returns
    market_data_service.get_current_price.return_value = Decimal("50000")
    market_data_service.get_volatility.return_value = 0.02
    market_data_service.get_support_level.return_value = Decimal("49500")
    market_data_service.get_resistance_level.return_value = Decimal("51000")
    market_data_service.get_trend_strength.return_value = 0.9
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_average_volume.return_value = Decimal("2500000")

    signal = await pair_selector._analyze_trading_opportunity("BTCUSDT", Decimal("10000"))

    assert signal is not None
    assert signal["pair"] == "BTCUSDT"
    assert isinstance(signal["entry_price"], Decimal)
    assert isinstance(signal["take_profit"], Decimal)
    assert isinstance(signal["stop_loss"], Decimal)
    assert signal["confidence"] >= 0.82

@pytest.mark.asyncio
async def test_select_trading_pairs(pair_selector, market_data_service):
    """Test complete trading pair selection process."""
    # Setup mock returns
    market_data_service.get_all_trading_pairs.return_value = ["BTCUSDT", "ETHUSDT"]
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_current_price.return_value = Decimal("50000")
    market_data_service.get_volatility.return_value = 0.02
    market_data_service.get_support_level.return_value = Decimal("49500")
    market_data_service.get_resistance_level.return_value = Decimal("51000")
    market_data_service.get_trend_strength.return_value = 0.9
    market_data_service.get_average_volume.return_value = Decimal("2500000")

    # Test with different account sizes
    for balance in [Decimal("100"), Decimal("5000"), Decimal("50000"), Decimal("1000000"), Decimal("100000000")]:
        signals = await pair_selector.select_trading_pairs(balance, max_pairs=2)

        assert len(signals) <= 2
        assert all(0.82 <= signal["confidence"] <= 1.0 for signal in signals)
        assert all(isinstance(signal["entry_price"], Decimal) for signal in signals)
        assert all(isinstance(signal["take_profit"], Decimal) for signal in signals)
        assert all(isinstance(signal["stop_loss"], Decimal) for signal in signals)
