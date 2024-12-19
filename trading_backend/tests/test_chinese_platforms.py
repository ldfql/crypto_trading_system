"""
Tests for Chinese platform scraping and sentiment analysis.
"""

import pytest
import logging
import asyncio
from app.services.web_scraping.chinese_scraper import ChineseScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestChinesePlatforms:
    @pytest.fixture
    def chinese_scraper(self):
        """Initialize Chinese scraper for testing."""
        logger.info("Initializing Chinese scraper for testing...")
        scraper = ChineseScraper()
        logger.info("Chinese scraper initialized successfully")
        return scraper

    @pytest.mark.asyncio
    async def test_sentiment_analysis(self, chinese_scraper):
        """Test Chinese sentiment analysis accuracy."""
        # Test cases with expected sentiment scores
        test_cases = [
            {
                "text": "比特币突破新高，牛市来临，建议建仓。市场看多情绪强烈。",  # Bullish case
                "expected_sentiment": 0.8,
                "min_confidence": 0.85,
            },
            {
                "text": "比特币价格暴跌，市场恐慌蔓延，建议清仓观望。",  # Bearish case
                "expected_sentiment": -0.8,
                "min_confidence": 0.85,
            },
            {
                "text": "市场横盘整理，等待方向选择。",  # Neutral case
                "expected_sentiment": 0.0,
                "min_confidence": 0.85,
            },
        ]

        try:
            async with asyncio.timeout(120):  # Overall test timeout
                for case in test_cases:
                    logger.info(
                        f"\nTesting sentiment analysis with text: {case['text']}"
                    )
                    sentiment, confidence = await chinese_scraper.analyze_sentiment(
                        case["text"]
                    )

                    logger.info(
                        f"Got sentiment score: {sentiment}, confidence: {confidence}"
                    )

                    # Verify confidence meets minimum requirement
                    assert (
                        confidence >= case["min_confidence"]
                    ), f"Confidence {confidence} below threshold {case['min_confidence']}"

                    # Verify sentiment is within expected range
                    assert (
                        abs(sentiment - case["expected_sentiment"]) <= 0.3
                    ), f"Sentiment score {sentiment} too far from expected {case['expected_sentiment']}"

                    # Verify sentiment direction is correct
                    if case["expected_sentiment"] > 0:
                        assert sentiment > 0, "Expected positive sentiment"
                    elif case["expected_sentiment"] < 0:
                        assert sentiment < 0, "Expected negative sentiment"
                    else:
                        assert abs(sentiment) < 0.3, "Expected neutral sentiment"

                logger.info("All sentiment analysis tests completed successfully")

        except asyncio.TimeoutError:
            logger.error("Test timed out after 120 seconds")
            raise
        except Exception as e:
            logger.error(f"Test failed with error: {str(e)}")
            raise
