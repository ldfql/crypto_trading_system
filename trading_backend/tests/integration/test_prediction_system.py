"""Integration tests for the complete prediction system including storage and analysis."""
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from app.models.signals import TradingSignal
from app.repositories.signal_repository import SignalRepository
from app.services.monitoring.signal_monitor import SignalMonitor
from app.services.analysis.prediction_analyzer import PredictionAnalyzer
from app.services.market_analysis.market_data_service import MarketDataService


@pytest.fixture
async def market_data_service():
    """Create market data service fixture."""
    return MarketDataService()


@pytest.fixture
async def signal_repository(test_db_session):
    """Create signal repository fixture."""
    return SignalRepository(test_db_session)


@pytest.fixture
async def signal_monitor(signal_repository, market_data_service):
    """Create signal monitor fixture."""
    return SignalMonitor(signal_repository, market_data_service, testing=True)


@pytest.fixture
async def prediction_analyzer(signal_repository, signal_monitor):
    """Create prediction analyzer fixture."""
    return PredictionAnalyzer(signal_repository, signal_monitor)


@pytest.fixture
async def sample_signals(signal_repository):
    """Create sample signals for testing."""
    signals = []
    timeframes = ["1h", "4h", "1d"]
    signal_types = ["long", "short"]
    market_phases = ["accumulation", "uptrend", "distribution", "downtrend"]

    base_time = datetime.utcnow() - timedelta(days=60)

    for i in range(100):
        signal_data = {
            "symbol": "BTC/USDT",
            "signal_type": signal_types[i % 2],
            "timeframe": timeframes[i % 3],
            "entry_price": 40000 + (i * 100),
            "target_price": 41000 + (i * 100),
            "stop_loss": 39000 + (i * 100),
            "confidence": 0.85 + (i % 15) * 0.01,
            "market_cycle_phase": market_phases[i % 4],
            "market_volatility": 0.2,
            "market_volume": 1000000,
            "market_sentiment": "bullish" if i % 2 == 0 else "bearish",
            "technical_indicators": {
                "rsi": 65 if i % 2 == 0 else 35,
                "macd": "bullish" if i % 2 == 0 else "bearish",
                "ma_cross": "golden" if i % 2 == 0 else "death",
            },
            "sentiment_sources": {
                "twitter": 0.8 if i % 2 == 0 else 0.2,
                "news": 0.75 if i % 2 == 0 else 0.25,
            },
            "created_at": base_time + timedelta(hours=i),
            "validation_count": 10,
            "accuracy": 0.85 + (i % 10) * 0.01
            if i < 80
            else None,  # Leave some signals without accuracy
        }
        signal = await signal_repository.create(signal_data)
        signals.append(signal)

    return signals


async def test_long_term_signal_storage(signal_repository, sample_signals):
    """Test storage and retrieval of long-term trading signals."""
    # Test retrieval of historical predictions
    historical_signals = await signal_repository.get_historical_predictions(
        timeframe="1d", days=30
    )
    assert len(historical_signals) > 0

    # Verify signal details are stored correctly
    signal = historical_signals[0]
    assert signal.technical_indicators is not None
    assert signal.sentiment_sources is not None
    assert signal.market_cycle_phase is not None
    assert signal.validation_count >= 0


async def test_real_time_accuracy_monitoring(
    signal_monitor, signal_repository, sample_signals, market_data_service
):
    """Test real-time accuracy monitoring and updates."""
    # Get market data with testing flag
    market_data = await market_data_service.get_market_data(
        symbol="BTC/USDT", timeframe="1h", testing=True
    )
    assert market_data is not None
    assert "current_price" in market_data

    # Monitor active signals
    monitoring_results = await signal_monitor.monitor_active_signals()
    assert len(monitoring_results) > 0

    # Verify accuracy calculations
    for result in monitoring_results:
        assert "current_accuracy" in result
        assert 0 <= result["current_accuracy"] <= 1
        assert result["validation_count"] > 0


async def test_prediction_analysis_and_improvement(prediction_analyzer, sample_signals):
    """Test prediction analysis and improvement suggestions."""
    # Get performance analysis
    analysis = await prediction_analyzer.analyze_prediction_performance(days=60)

    # Verify performance metrics
    assert "performance_metrics" in analysis
    metrics = analysis["performance_metrics"]
    assert "accuracy_by_timeframe" in metrics
    assert "accuracy_by_market_phase" in metrics

    # Verify improvement suggestions
    assert "improvement_suggestions" in analysis
    suggestions = analysis["improvement_suggestions"]
    assert len(suggestions) > 0
    for suggestion in suggestions:
        assert "category" in suggestion
        assert "suggestion" in suggestion
        assert "details" in suggestion


async def test_accuracy_requirements(prediction_analyzer, sample_signals):
    """Test that the system maintains 85%+ accuracy requirement."""
    # Get accuracy statistics
    stats = await prediction_analyzer.analyze_prediction_performance()
    metrics = stats["performance_metrics"]

    # Check overall accuracy
    accuracies = []
    for timeframe_data in metrics["accuracy_by_timeframe"].values():
        if timeframe_data["total"] > 0:
            accuracies.append(timeframe_data["accuracy"])

    if accuracies:
        average_accuracy = sum(accuracies) / len(accuracies)
        assert (
            average_accuracy >= 0.85
        ), f"Average accuracy {average_accuracy} is below 85% requirement"


async def test_historical_comparison(prediction_analyzer, sample_signals):
    """Test comparison of predictions with historical outcomes."""
    # Get two months of historical data
    analysis = await prediction_analyzer.analyze_prediction_performance(days=60)

    # Verify historical tracking
    assert "performance_metrics" in analysis
    metrics = analysis["performance_metrics"]

    # Check profit/loss tracking
    assert "profit_loss_distribution" in metrics
    profit_loss = metrics["profit_loss_distribution"]
    assert "average_profit" in profit_loss
    assert "profit_signals" in profit_loss
    assert "loss_signals" in profit_loss


async def test_continuous_improvement(prediction_analyzer, sample_signals):
    """Test system's ability to improve over time."""
    # Get improvement metrics
    improvement_report = await prediction_analyzer.generate_strategy_improvement_report(
        days=60
    )

    # Verify improvement tracking
    assert "accuracy_trend" in improvement_report
    assert "performance_analysis" in improvement_report
    assert "recommendations" in improvement_report
    assert "strategy_adjustments" in improvement_report

    # Check trend data
    trend_data = improvement_report["accuracy_trend"]
    assert len(trend_data) > 0

    # Verify recommendations
    recommendations = improvement_report["recommendations"]
    assert len(recommendations) > 0
    for rec in recommendations:
        assert "category" in rec
        assert "suggestion" in rec


async def test_market_phase_adaptation(prediction_analyzer, sample_signals):
    """Test system's ability to adapt to different market phases."""
    analysis = await prediction_analyzer.analyze_prediction_performance()

    # Verify market phase analysis
    assert "pattern_analysis" in analysis
    patterns = analysis["pattern_analysis"]
    assert "market_conditions" in patterns

    # Check performance in different market phases
    market_conditions = patterns["market_conditions"]
    for phase, data in market_conditions.items():
        assert "success_rate" in data
        assert "total" in data
        assert data["total"] > 0


async def test_signal_validation_history(signal_repository, sample_signals):
    """Test storage and retrieval of signal validation history."""
    # Get a signal with validation history
    signals = await signal_repository.get_historical_predictions(limit=1)
    assert len(signals) > 0

    signal = signals[0]
    validation_history = await signal_repository.get_validation_history(signal.id)

    if validation_history:
        for entry in validation_history:
            assert "timestamp" in entry
            assert "price" in entry
            assert "accuracy" in entry


async def test_real_time_data_validation(
    signal_monitor, market_data_service, sample_signals
):
    """Test validation against real-time market data."""
    # Get market data with testing flag
    market_data = await market_data_service.get_market_data(
        symbol="BTC/USDT", timeframe="1h", testing=True
    )
    assert market_data is not None
    assert "current_price" in market_data
    assert "market_cycle" in market_data
    assert "trend" in market_data

    # Monitor signals and validate against market data
    monitoring_results = await signal_monitor.monitor_active_signals()

    for result in monitoring_results:
        assert "market_data" in result
        market_data = result["market_data"]

        # Verify required market data fields
        assert "current_price" in market_data
        assert "volume_24h" in market_data
        assert "volatility" in market_data

        # Verify accuracy calculation
        assert "current_accuracy" in result
        assert 0 <= result["current_accuracy"] <= 1


async def test_strategy_optimization(prediction_analyzer, sample_signals):
    """Test strategy optimization based on historical performance."""
    # Generate strategy improvement report
    improvement_report = (
        await prediction_analyzer.generate_strategy_improvement_report()
    )

    # Verify strategy adjustments
    assert "strategy_adjustments" in improvement_report
    adjustments = improvement_report["strategy_adjustments"]

    for adjustment in adjustments:
        assert "type" in adjustment
        assert "adjustment" in adjustment
        assert "implementation" in adjustment
        assert isinstance(adjustment["implementation"], list)
