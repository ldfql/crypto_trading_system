import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import tweepy
from app.services.web_scraping.twitter_scraper import TwitterScraper

# Mock tweepy errors for testing
class MockTweepyException(Exception):
    def __init__(self, message="", api_code=None):
        self.api_code = api_code
        super().__init__(message)

@pytest.fixture
def mock_tweepy_api():
    """Create a mock Twitter API client with enhanced test data."""
    with patch('tweepy.Client') as mock_client:
        mock_api = MagicMock()
        mock_api.verify_credentials.return_value = True
        mock_api.user_timeline.return_value = []  # Will be overridden in tests
        mock_api.rate_limit_status.return_value = {
            'resources': {
                'statuses': {'/statuses/user_timeline': {'remaining': 100}}
            }
        }
        mock_client.return_value = mock_api
        return mock_client

@pytest.fixture
def twitter_scraper(mock_tweepy_api):
    """Create a TwitterScraper instance with mock API."""
    with patch.dict('os.environ', {
        'TWITTER_API_KEY': 'test_key',
        'TWITTER_API_SECRET': 'test_secret',
        'TWITTER_ACCESS_TOKEN': 'test_token',
        'TWITTER_ACCESS_SECRET': 'test_token_secret'
    }):
        scraper = TwitterScraper()
        scraper.api = mock_tweepy_api()
        return scraper

def create_mock_tweet(
    text: str,
    likes: int,
    retweets: int,
    followers: int,
    hours_ago: int = 1
):
    """Create a mock tweet with specified properties."""
    tweet = MagicMock()
    tweet.full_text = text
    tweet.favorite_count = likes
    tweet.retweet_count = retweets
    tweet.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    tweet.id = '123456'
    tweet.user = MagicMock()
    tweet.user.followers_count = followers
    return tweet

@pytest.mark.asyncio
async def test_get_influential_tweets(twitter_scraper, mock_tweepy_api):
    # Mock tweets for first account
    tweets_account1 = [
        create_mock_tweet(
            "Bitcoin looking strong at $45k support level #crypto #trading",
            1000,
            500,
            50000
        ),
        create_mock_tweet(
            "Just had coffee! Great day!",  # Non-trading tweet
            100,
            50,
            10000
        )
    ]

    # Mock tweets for second account
    tweets_account2 = [
        create_mock_tweet(
            "ETH breaking resistance, time to long! #ethereum",
            2000,
            1000,
            100000
        ),
        create_mock_tweet(
            "Beautiful weather today!",  # Non-trading tweet
            200,
            100,
            20000
        )
    ]

    # Configure mock to return different tweets for different accounts
    mock_tweepy_api.return_value.user_timeline.side_effect = [
        tweets_account1,
        tweets_account2
    ]

    results = await twitter_scraper.get_influential_tweets(hours_ago=24)

    assert len(results) == 2  # Only trading-related tweets
    assert results[0]['engagement'] > results[1]['engagement']
    assert "ETH" in results[0]['content']  # Higher engagement tweet first
    assert results[0]['sentiment_weight'] > 0 and results[0]['sentiment_weight'] <= 1

@pytest.mark.asyncio
async def test_monitor_market_sentiment(twitter_scraper, mock_tweepy_api):
    tweets = [
        create_mock_tweet(
            "Bullish on BTC with strong institutional buying. Price holding above key support levels. Technical indicators showing positive divergence. #bitcoin #trading",
            5000,
            2000,
            200000
        ),
        create_mock_tweet(
            "Market showing strength in accumulation phase. Volume increasing with positive momentum. Multiple indicators confirm uptrend. #crypto #analysis",
            3000,
            1500,
            150000
        )
    ]
    mock_tweepy_api.return_value.user_timeline.return_value = tweets

    try:
        sentiment = await twitter_scraper.monitor_market_sentiment(timeframe="1h")
        assert sentiment['sentiment'] > 0.7  # Expect bullish sentiment
        assert sentiment['confidence'] > 0.6  # Expect reasonable confidence
        assert sentiment['sample_size'] == 2
    except MockTweepyException:
        pytest.skip("Twitter API error")

@pytest.mark.asyncio
async def test_empty_market_sentiment(twitter_scraper, mock_tweepy_api):
    mock_tweepy_api.return_value.user_timeline.return_value = []

    try:
        sentiment = await twitter_scraper.monitor_market_sentiment(timeframe="1h")
        assert sentiment['sentiment'] == 0
        assert sentiment['confidence'] == 0
        assert sentiment['sample_size'] == 0
    except MockTweepyException:
        pytest.skip("Twitter API error")

def test_is_trading_related(twitter_scraper):
    assert twitter_scraper._is_trading_related("Bitcoin price analysis")
    assert twitter_scraper._is_trading_related("ETH breaking resistance")
    assert twitter_scraper._is_trading_related("Crypto market update")
    assert not twitter_scraper._is_trading_related("Having lunch")
    assert not twitter_scraper._is_trading_related("Beautiful weather today")

def test_calculate_influence_weight(twitter_scraper):
    weight = twitter_scraper._calculate_influence_weight(
        likes=1000,
        retweets=500,
        followers=10000
    )
    assert 0.1 <= weight <= 1.0

    # Test normalization
    high_weight = twitter_scraper._calculate_influence_weight(
        likes=100000,
        retweets=50000,
        followers=1000
    )
    assert high_weight == 1.0

    low_weight = twitter_scraper._calculate_influence_weight(
        likes=1,
        retweets=1,
        followers=1000000
    )
    assert low_weight == 0.1
