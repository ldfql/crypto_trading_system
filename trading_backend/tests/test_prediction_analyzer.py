import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.services.analysis.prediction_analyzer import PredictionAnalyzer
from app.services.monitoring.signal_monitor import SignalMonitor
from app.repositories.signal_repository import SignalRepository
from app.models.signals import TradingSignal


@pytest.fixture
def signal_repository():
    return Mock(spec=SignalRepository)


@pytest.fixture
def signal_monitor():
    return Mock(spec=SignalMonitor)


@pytest.fixture
def prediction_analyzer(signal_repository, signal_monitor):
    return PredictionAnalyzer(signal_repository, signal_monitor)


@pytest.mark.asyncio
async def test_find_best_opportunities_ranking(prediction_analyzer, signal_repository):
    """Test that opportunities are properly ranked and filtered by confidence."""
    # Create test signals
    now = datetime.utcnow()
    signals = [
        TradingSignal(
            symbol="BTC/USDT",
            entry_price=45000.0,
            target_price=48000.0,
            stop_loss=43000.0,
            position_size=1000.0,
            confidence=0.90,
            market_volume=5000000,
            market_volatility=0.02,
            market_cycle_phase="accumulation",
            accuracy=0.88,
            created_at=now,
            technical_indicators={"rsi": 65, "macd": "bullish"},
            sentiment_sources=["social_media", "news"],
        ),
        TradingSignal(
            symbol="ETH/USDT",
            entry_price=2800.0,
            target_price=3000.0,
            stop_loss=2700.0,
            position_size=500.0,
            confidence=0.85,
            market_volume=3000000,
            market_volatility=0.015,
            market_cycle_phase="markup",
            accuracy=0.85,
            created_at=now,
            technical_indicators={"rsi": 60, "macd": "neutral"},
            sentiment_sources=["technical_analysis"],
        ),
        TradingSignal(
            symbol="SOL/USDT",
            entry_price=80.0,
            target_price=85.0,
            stop_loss=77.0,
            position_size=200.0,
            confidence=0.80,  # Below minimum threshold
            market_volume=1000000,
            market_volatility=0.025,
            market_cycle_phase="distribution",
            accuracy=0.81,
            created_at=now,
            technical_indicators={"rsi": 45, "macd": "bearish"},
            sentiment_sources=["news"],
        ),
    ]

    signal_repository.get_active_signals.return_value = signals
    opportunities = await prediction_analyzer.find_best_opportunities()

    # Verify only signals above minimum confidence are included
    assert len(opportunities) == 2
    assert all(opp["confidence"] >= 0.82 for opp in opportunities)

    # Verify ranking order (highest confidence first)
    assert opportunities[0]["pair"] == "BTC/USDT"
    assert opportunities[1]["pair"] == "ETH/USDT"

    # Verify complete trading metadata
    first_opp = opportunities[0]
    assert all(
        key in first_opp
        for key in [
            "pair",
            "entry_price",
            "take_profit",
            "stop_loss",
            "position_size",
            "confidence",
            "fees",
            "potential_profit",
            "position_type",
            "market_conditions",
            "ranking_factors",
        ]
    )

    # Verify fee calculations
    assert first_opp["fees"] == first_opp["position_size"] * 0.002  # 0.2% total fees

    # Verify market conditions
    assert all(
        key in first_opp["market_conditions"]
        for key in ["volume_24h", "volatility", "trend"]
    )

    # Verify ranking factors
    assert all(
        key in first_opp["ranking_factors"]
        for key in [
            "historical_accuracy",
            "market_volatility_score",
            "volume_factor",
            "market_phase_multiplier",
            "technical_indicators",
            "sentiment_analysis",
        ]
    )


@pytest.mark.asyncio
async def test_opportunity_score_calculation(prediction_analyzer):
    """Test the opportunity score calculation with different market conditions."""
    signal = TradingSignal(
        symbol="BTC/USDT",
        confidence=0.90,
        accuracy=0.88,
        market_volatility=0.02,  # Optimal volatility
        market_volume=5000000,
        market_cycle_phase="accumulation",
    )

    score = await prediction_analyzer._calculate_opportunity_score(signal)
    assert 0.82 <= score <= 0.95  # Score within valid range
    assert score > signal.confidence  # Score improved due to good conditions

    # Test with high volatility (should reduce score)
    signal.market_volatility = 0.06
    high_vol_score = await prediction_analyzer._calculate_opportunity_score(signal)
    assert high_vol_score < score

    # Test with accumulation phase (should increase score)
    signal.market_cycle_phase = "accumulation"
    signal.market_volatility = 0.02  # Reset to optimal
    accum_score = await prediction_analyzer._calculate_opportunity_score(signal)
    assert accum_score > high_vol_score


@pytest.mark.asyncio
async def test_empty_opportunities(prediction_analyzer, signal_repository):
    """Test handling of no available opportunities."""
    signal_repository.get_active_signals.return_value = []
    opportunities = await prediction_analyzer.find_best_opportunities()
    assert opportunities == []


@pytest.mark.asyncio
async def test_position_type_classification(prediction_analyzer, signal_repository):
    """Test correct classification of full vs partial positions."""
    signals = [
        TradingSignal(
            symbol="BTC/USDT",
            position_size=150.0,  # Full position
            confidence=0.85,
            accuracy=0.85,
        ),
        TradingSignal(
            symbol="ETH/USDT",
            position_size=50.0,  # Partial position
            confidence=0.85,
            accuracy=0.85,
        ),
    ]

    signal_repository.get_active_signals.return_value = signals
    opportunities = await prediction_analyzer.find_best_opportunities()

    assert opportunities[0]["position_type"] == "full"
    assert opportunities[1]["position_type"] == "partial"
