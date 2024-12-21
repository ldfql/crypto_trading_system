import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from app.services.trading.pair_selector import PairSelector
from app.models.signals import AccountStage
from app.models.futures import MarginType
from app.schemas.trading import TradingSignal

@pytest.fixture
def market_data_service():
    """Create mock market data service with async methods."""
    mock = AsyncMock()
    # Setup required mock methods with async support
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
    # Test sufficient volume
    market_data_service.get_24h_volume.return_value = Decimal("2000000")
    assert await pair_selector._meets_volume_requirements("BTCUSDT") is True

    # Test insufficient volume
    market_data_service.get_24h_volume.return_value = Decimal("500000")
    assert await pair_selector._meets_volume_requirements("BTCUSDT") is False

    # Test error handling
    market_data_service.get_24h_volume.side_effect = Exception("API Error")
    assert await pair_selector._meets_volume_requirements("BTCUSDT") is False

@pytest.mark.asyncio
async def test_calculate_trading_config(pair_selector):
    """Test trading configuration calculation for different account sizes."""
    test_cases = [
        (Decimal("100"), 20, Decimal("0.1")),    # Minimum account size
        (Decimal("1000"), 15, Decimal("0.1")),   # Small account
        (Decimal("10000"), 10, Decimal("0.15")), # Medium account
        (Decimal("100000"), 5, Decimal("0.2")),  # Large account
        (Decimal("1000000"), 3, Decimal("0.25")),# Very large account
        (Decimal("10000000"), 2, Decimal("0.25")),# Huge account
        (Decimal("100000000"), 1, Decimal("0.25")) # Maximum target (1亿U)
    ]

    for balance, expected_leverage, expected_risk in test_cases:
        config = pair_selector._calculate_trading_config(balance, Decimal("50000"))
        assert config.leverage == expected_leverage
        assert config.risk_level == expected_risk
        assert config.margin_type == MarginType.CROSS
        assert config.position_size == balance * expected_risk

@pytest.mark.asyncio
async def test_analyze_trading_opportunity(pair_selector, market_data_service):
    """Test trading opportunity analysis with comprehensive parameter validation."""
    # Setup mock responses
    market_data_service.get_current_price.return_value = Decimal("45000")
    market_data_service.get_volatility.return_value = 0.02
    market_data_service.get_support_level.return_value = Decimal("44000")
    market_data_service.get_resistance_level.return_value = Decimal("46000")
    market_data_service.get_trend_strength.return_value = 0.8
    market_data_service.get_24h_volume.return_value = Decimal("2000000")
    market_data_service.get_average_volume.return_value = Decimal("1500000")

    # Test successful analysis
    signal = await pair_selector._analyze_trading_opportunity("BTCUSDT", Decimal("1000"))
    assert signal is not None
    assert signal["pair"] == "BTCUSDT"
    assert signal["entry_price"] == Decimal("44220")  # 0.5% above support
    assert signal["take_profit"] == Decimal("45546.6")  # 3% above entry
    assert signal["stop_loss"] == Decimal("43780")  # 0.5% below support
    assert signal["position_size"] == Decimal("100")  # 10% of balance
    assert signal["leverage"] == 15  # Small account leverage
    assert signal["margin_type"] == MarginType.CROSS
    assert signal["expected_profit"] > Decimal("0")
    assert 0.82 <= signal["confidence"] <= 1.0

    # Test low volatility case
    market_data_service.get_volatility.return_value = 0.005
    signal = await pair_selector._analyze_trading_opportunity("BTCUSDT", Decimal("1000"))
    assert signal is None

    # Test error handling
    market_data_service.get_current_price.side_effect = Exception("API Error")
    signal = await pair_selector._analyze_trading_opportunity("BTCUSDT", Decimal("1000"))
    assert signal is None

@pytest.mark.asyncio
async def test_select_trading_pairs(pair_selector, market_data_service):
    """Test trading pair selection with comprehensive parameter validation."""
    # Setup mock responses
    market_data_service.get_all_trading_pairs.return_value = ["BTCUSDT", "ETHUSDT"]
    market_data_service.get_24h_volume.return_value = Decimal("2000000")
    market_data_service.get_current_price.return_value = Decimal("45000")
    market_data_service.get_volatility.return_value = 0.02
    market_data_service.get_support_level.return_value = Decimal("44000")
    market_data_service.get_resistance_level.return_value = Decimal("46000")
    market_data_service.get_trend_strength.return_value = 0.8
    market_data_service.get_average_volume.return_value = Decimal("1500000")

    # Test with small account balance
    signals = await pair_selector.select_trading_pairs(Decimal("1000"), max_pairs=2)
    assert len(signals) > 0
    signal = signals[0]

    # Verify all required trading parameters
    assert isinstance(signal, TradingSignal)
    assert signal.pair == "BTCUSDT"
    assert signal.entry_price == Decimal("44220")  # 0.5% above support
    assert signal.take_profit == Decimal("45546.6")  # 3% above entry
    assert signal.stop_loss == Decimal("43780")  # 0.5% below support
    assert signal.position_size == Decimal("100")  # 10% of balance
    assert signal.leverage == 15  # Small account leverage
    assert signal.margin_type == MarginType.CROSS
    assert signal.expected_profit > Decimal("0")
    assert 0.82 <= signal.confidence <= 1.0

    # Test error handling
    market_data_service.get_all_trading_pairs.side_effect = Exception("API Error")
    signals = await pair_selector.select_trading_pairs(Decimal("1000"))
    assert len(signals) == 0

@pytest.mark.asyncio
async def test_calculate_signal_confidence(pair_selector, market_data_service):
    """Test signal confidence calculation with different market conditions."""
    # Setup mock responses
    market_data_service.get_trend_strength.return_value = 0.8
    market_data_service.get_24h_volume.return_value = Decimal("2000000")
    market_data_service.get_average_volume.return_value = Decimal("1500000")

    # Test strong trend, high volume
    confidence = await pair_selector._calculate_signal_confidence(
        "BTCUSDT",
        Decimal("45000"),  # Entry
        Decimal("46350"),  # Take profit (3% above entry)
        Decimal("44325")   # Stop loss (1.5% below entry)
    )
    assert 0.85 <= confidence <= 1.0

    # Test weak trend
    market_data_service.get_trend_strength.return_value = 0.3
    confidence = await pair_selector._calculate_signal_confidence(
        "BTCUSDT",
        Decimal("45000"),
        Decimal("46350"),
        Decimal("44325")
    )
    assert confidence < 0.85

    # Test error handling
    market_data_service.get_trend_strength.side_effect = Exception("API Error")
    confidence = await pair_selector._calculate_signal_confidence(
        "BTCUSDT",
        Decimal("45000"),
        Decimal("46350"),
        Decimal("44325")
    )
    assert confidence == 0.0

@pytest.mark.asyncio
async def test_volume_score_calculation(pair_selector, market_data_service):
    """Test volume score calculation with various scenarios."""
    # Test normal volume case
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_average_volume.return_value = Decimal("2500000")
    score = await pair_selector._calculate_volume_score("BTCUSDT")
    assert score == 1.0  # 2x average volume should give max score

    # Test low volume case
    market_data_service.get_24h_volume.return_value = Decimal("1000000")
    market_data_service.get_average_volume.return_value = Decimal("2500000")
    score = await pair_selector._calculate_volume_score("BTCUSDT")
    assert score == 0.2  # 0.4x average volume should give 0.2 score

    # Test extremely high volume case
    market_data_service.get_24h_volume.return_value = Decimal("10000000")
    market_data_service.get_average_volume.return_value = Decimal("2500000")
    score = await pair_selector._calculate_volume_score("BTCUSDT")
    assert score == 1.0  # Score should be capped at 1.0

    # Test missing average volume
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_average_volume.return_value = None
    score = await pair_selector._calculate_volume_score("BTCUSDT")
    assert score == 0.5  # Default score when average volume is missing

    # Test API error
    market_data_service.get_24h_volume.side_effect = Exception("API Error")
    score = await pair_selector._calculate_volume_score("BTCUSDT")
    assert score == 0.0  # Zero score on error

@pytest.mark.asyncio
async def test_edge_case_trading_configs(pair_selector):
    """Test trading configuration calculation with edge case account balances."""
    # Test minimum viable account
    config = pair_selector._calculate_trading_config(Decimal("10"), Decimal("50000"))
    assert config.leverage == 20
    assert config.risk_level == Decimal("0.1")
    assert config.position_size == Decimal("1")

    # Test exactly at tier boundaries
    config = pair_selector._calculate_trading_config(Decimal("1000"), Decimal("50000"))
    assert config.leverage == 15
    assert config.risk_level == Decimal("0.1")

    config = pair_selector._calculate_trading_config(Decimal("10000"), Decimal("50000"))
    assert config.leverage == 10
    assert config.risk_level == Decimal("0.15")

    # Test extremely large account
    config = pair_selector._calculate_trading_config(Decimal("100000000"), Decimal("50000"))
    assert config.leverage == 1
    assert config.risk_level == Decimal("0.25")
    assert config.margin_type == MarginType.CROSS

@pytest.mark.asyncio
async def test_market_condition_pair_selection(pair_selector, market_data_service):
    """Test pair selection under different market conditions."""
    # Setup base mock data
    market_data_service.get_all_trading_pairs.return_value = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_current_price.return_value = Decimal("50000")
    market_data_service.get_volatility.return_value = 0.02
    market_data_service.get_support_level.return_value = Decimal("49000")
    market_data_service.get_resistance_level.return_value = Decimal("51000")
    market_data_service.get_trend_strength.return_value = 0.85
    market_data_service.get_average_volume.return_value = Decimal("2500000")

    # Test high volatility market
    market_data_service.get_volatility.return_value = 0.05
    pairs = await pair_selector.select_trading_pairs(Decimal("10000"))
    assert len(pairs) > 0
    assert all(p["confidence"] >= pair_selector.min_confidence for p in pairs)

    # Test low volume market
    market_data_service.get_24h_volume.return_value = Decimal("500000")
    pairs = await pair_selector.select_trading_pairs(Decimal("10000"))
    assert len(pairs) == 0  # Should skip low volume pairs

    # Test weak trend market
    market_data_service.get_24h_volume.return_value = Decimal("5000000")
    market_data_service.get_trend_strength.return_value = 0.3
    pairs = await pair_selector.select_trading_pairs(Decimal("10000"))
    assert len(pairs) == 0  # Should skip weak trend pairs

    # Test API errors for some pairs
    async def mock_volume(pair):
        if pair == "BTCUSDT":
            return Decimal("5000000")
        raise Exception("API Error")

    market_data_service.get_24h_volume.side_effect = mock_volume
    market_data_service.get_trend_strength.return_value = 0.85
    pairs = await pair_selector.select_trading_pairs(Decimal("10000"))
    assert len(pairs) <= 1  # Should only include BTCUSDT if it passes all checks
