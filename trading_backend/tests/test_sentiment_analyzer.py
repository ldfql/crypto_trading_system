import pytest
from datetime import datetime
import torch
from unittest.mock import Mock, patch
from app.services.web_scraping.sentiment_analyzer import SentimentAnalyzer


@pytest.fixture
def analyzer():
    return SentimentAnalyzer()


@pytest.mark.asyncio
async def test_analyze_content_high_confidence(analyzer):
    text = """Based on technical analysis, we're seeing a clear double bottom pattern
    with strong support at $45,000. The RSI indicates oversold conditions, and volume
    is increasing. This suggests a bullish reversal is likely."""

    sentiment, confidence = await analyzer.analyze_content(text)

    assert sentiment > 0.5  # Should be strongly bullish
    assert confidence > 0.85  # Should have high confidence


@pytest.mark.asyncio
async def test_analyze_content_low_confidence(analyzer):
    text = "Bitcoin price moved today."

    sentiment, confidence = await analyzer.analyze_content(text)

    assert confidence < 0.5  # Should have low confidence due to lack of analysis


@pytest.mark.asyncio
async def test_technical_pattern_detection(analyzer):
    bullish_text = "Clear inverse head and shoulders pattern forming with golden cross"
    bearish_text = "Double top pattern confirmed with death cross signal"

    bullish_score = analyzer._detect_technical_patterns(bullish_text)
    bearish_score = analyzer._detect_technical_patterns(bearish_text)

    assert bullish_score > 0.7  # Should be strongly bullish
    assert bearish_score < -0.7  # Should be strongly bearish


@pytest.mark.asyncio
async def test_trading_rules_analysis(analyzer):
    bullish_text = "Strong buy signal with uptrend confirmation and higher highs"
    bearish_text = "Clear sell signal in downtrend with lower lows"

    bullish_score = analyzer._apply_trading_rules(bullish_text)
    bearish_score = analyzer._apply_trading_rules(bearish_text)

    assert bullish_score > 0.6  # Should be bullish
    assert bearish_score < -0.6  # Should be bearish


@pytest.mark.asyncio
async def test_confidence_calculation(analyzer):
    high_quality_text = """Detailed technical analysis shows a strong bullish setup:
    1. Double bottom pattern confirmed
    2. RSI showing oversold conditions
    3. Volume increasing significantly
    4. Multiple higher lows forming
    Based on these indicators, a strong buy signal is present."""

    low_quality_text = "Price went up today"

    _, high_conf = await analyzer.analyze_content(high_quality_text)
    _, low_conf = await analyzer.analyze_content(low_quality_text)

    assert high_conf > 0.85  # Should have very high confidence
    assert low_conf < 0.5  # Should have low confidence


@pytest.mark.asyncio
async def test_bert_sentiment(analyzer):
    with patch("torch.nn.functional.softmax") as mock_softmax:
        # Mock BERT output probabilities [negative, neutral, positive]
        mock_softmax.return_value = torch.tensor([[0.1, 0.2, 0.7]])

        score = await analyzer._get_bert_sentiment("Test text")
        assert score == pytest.approx(0.6, abs=0.01)  # 0.7 - 0.1 = 0.6


@pytest.mark.asyncio
async def test_accuracy_tracking(analyzer):
    text = "Strong buy signal confirmed with technical analysis"
    sentiment, confidence = await analyzer.analyze_content(text)

    assert len(analyzer.accuracy_history) > 0
    entry = analyzer.accuracy_history[-1]

    assert "timestamp" in entry
    assert "sentiment" in entry
    assert "confidence" in entry
    assert isinstance(entry["timestamp"], datetime)


@pytest.mark.asyncio
async def test_error_handling(analyzer):
    # Test with None input
    sentiment, confidence = await analyzer.analyze_content(None)
    assert sentiment == 0.0
    assert confidence == 0.0

    # Test with empty string
    sentiment, confidence = await analyzer.analyze_content("")
    assert sentiment == 0.0
    assert confidence == 0.0
