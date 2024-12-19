import pytest
import torch
from unittest.mock import Mock, patch
from app.services.web_scraping.ensemble_analyzer import EnsembleSentimentAnalyzer


@pytest.fixture
def analyzer():
    return EnsembleSentimentAnalyzer(language="english")


def test_ensemble_analyzer_initialization(analyzer):
    assert analyzer.language == "english"
    assert analyzer.label_map == {"bearish": 0, "neutral": 1, "bullish": 2}
    assert analyzer.device == torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )


@pytest.mark.parametrize(
    "text,expected_sentiment",
    [
        (
            "Strong breakout above resistance with increasing volume and institutional buying",
            "bullish",
        ),
        (
            "Death cross forming with heavy distribution and bearish divergence",
            "bearish",
        ),
        (
            "Market consolidating in range with mixed signals from institutions",
            "neutral",
        ),
    ],
)
@pytest.mark.asyncio
async def test_bert_sentiment_analysis(analyzer, text, expected_sentiment):
    result = await analyzer.analyze_sentiment(text)
    assert result["sentiment"] == expected_sentiment
    assert 0 <= result["confidence"] <= 1


@pytest.mark.parametrize(
    "text,expected_sentiment",
    [
        ("Golden cross forming with strong volume", "bullish"),
        ("Death cross with increasing selling pressure", "bearish"),
        ("Price moving sideways with balanced volume", "neutral"),
    ],
)
@pytest.mark.asyncio
async def test_technical_rules_analysis(analyzer, text, expected_sentiment):
    result = await analyzer.analyze_sentiment(text)
    assert result["sentiment"] == expected_sentiment
    assert 0 <= result["confidence"] <= 1


@pytest.mark.parametrize(
    "text,expected_sentiment",
    [
        (
            "Institutional investors increasing Bitcoin holdings significantly",
            "bullish",
        ),
        ("Large miners selling Bitcoin holdings amid uncertainty", "bearish"),
        ("Market awaiting key economic data with balanced positions", "neutral"),
    ],
)
@pytest.mark.asyncio
async def test_market_context_analysis(analyzer, text, expected_sentiment):
    result = await analyzer.analyze_sentiment(text)
    assert result["sentiment"] == expected_sentiment
    assert 0 <= result["confidence"] <= 1


@pytest.mark.asyncio
async def test_ensemble_voting_agreement():
    analyzer = EnsembleSentimentAnalyzer()
    text = "Strong institutional buying confirmed by technical breakout above resistance with increasing volume and positive market sentiment"
    result = await analyzer.analyze_sentiment(text)
    assert result["sentiment"] == "bullish"
    assert result["confidence"] > 0.8


@pytest.mark.asyncio
async def test_ensemble_voting_disagreement():
    analyzer = EnsembleSentimentAnalyzer()
    text = "Technical indicators show bearish trend but institutional buying is increasing while volume remains neutral"
    result = await analyzer.analyze_sentiment(text)
    assert result["confidence"] < 0.8


@pytest.mark.asyncio
async def test_batch_analysis():
    analyzer = EnsembleSentimentAnalyzer()
    texts = [
        "Strong breakout with institutional buying",
        "Death cross forming with heavy distribution",
        "Market consolidating with mixed signals",
    ]
    results = await analyzer.batch_analyze(texts)
    assert len(results) == 3
    for result in results:
        assert result["sentiment"] in ["bullish", "bearish", "neutral"]
        assert 0 <= result["confidence"] <= 1


@pytest.mark.asyncio
async def test_error_handling():
    analyzer = EnsembleSentimentAnalyzer()
    with patch.object(
        analyzer, "_get_bert_sentiment", side_effect=Exception("BERT error")
    ):
        result = await analyzer.analyze_sentiment("test text")
        assert result["sentiment"] == "neutral"
        assert result["confidence"] == 0.33


@pytest.mark.asyncio
async def test_chinese_language_support():
    analyzer = EnsembleSentimentAnalyzer(language="chinese")
    text = "突破重要阻力位，成交量显著放大，机构持续买入"
    result = await analyzer.analyze_sentiment(text)
    assert result["sentiment"] in ["bullish", "bearish", "neutral"]
    assert 0 <= result["confidence"] <= 1


@pytest.mark.asyncio
async def test_confidence_calculation():
    analyzer = EnsembleSentimentAnalyzer()

    with patch.object(
        analyzer, "_get_bert_sentiment", return_value=("bullish", 0.9)
    ), patch.object(
        analyzer, "_apply_technical_rules", return_value=("bullish", 0.85)
    ), patch.object(
        analyzer, "_analyze_market_context", return_value=("bullish", 0.88)
    ):
        result = await analyzer.analyze_sentiment("test text")
        assert result["confidence"] > 0.85

    with patch.object(
        analyzer, "_get_bert_sentiment", return_value=("bullish", 0.4)
    ), patch.object(
        analyzer, "_apply_technical_rules", return_value=("bearish", 0.35)
    ), patch.object(
        analyzer, "_analyze_market_context", return_value=("neutral", 0.33)
    ):
        result = await analyzer.analyze_sentiment("test text")
        assert result["confidence"] < 0.5
