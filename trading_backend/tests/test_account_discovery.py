import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from app.services.web_scraping.account_discovery import AccountDiscovery, RateLimiter


@pytest.fixture
def mock_twitter_api():
    with patch("tweepy.API") as mock_api:
        yield mock_api


@pytest.fixture
def mock_youtube_client():
    with patch("googleapiclient.discovery.build") as mock_build:
        yield mock_build


@pytest.fixture
def discovery(mock_twitter_api, mock_youtube_client):
    return AccountDiscovery(
        twitter_api_key="test_key",
        twitter_api_secret="test_secret",
        twitter_access_token="test_token",
        twitter_access_secret="test_token_secret",
        youtube_api_key="test_youtube_key",
    )


def create_mock_twitter_user(
    name: str,
    description: str,
    followers_count: int,
    friends_count: int,
    statuses_count: int,
    verified: bool = False,
    created_at: datetime = None,
):
    user = Mock()
    user.name = name
    user.description = description
    user.followers_count = followers_count
    user.friends_count = friends_count
    user.statuses_count = statuses_count
    user.verified = verified
    user.screen_name = name.lower().replace(" ", "_")
    user.created_at = created_at or (datetime.now() - timedelta(days=365))
    user.listed_count = followers_count // 100  # Approximate listed count
    user.url = "https://example.com" if followers_count > 100000 else None
    return user


@pytest.mark.asyncio
async def test_discover_twitter_accounts(discovery, mock_twitter_api):
    # Mock influential trader accounts
    trader1 = create_mock_twitter_user(
        "Crypto Analyst",
        "Professional crypto trader and technical analysis expert. #Bitcoin #Trading",
        followers_count=100000,
        friends_count=1000,
        statuses_count=5000,
        verified=True,
        created_at=datetime.now() - timedelta(days=730),
    )
    trader2 = create_mock_twitter_user(
        "Institutional Trader",
        "Head of Crypto Trading at Major Financial Institution. Market analysis and blockchain.",
        followers_count=75000,
        friends_count=500,
        statuses_count=3000,
        verified=True,
        created_at=datetime.now() - timedelta(days=1095),
    )
    non_influential = create_mock_twitter_user(
        "Small Trader",
        "Crypto enthusiast and trader",
        followers_count=5000,
        friends_count=1000,
        statuses_count=500,
        verified=False,
    )

    mock_twitter_api.return_value.get_followers.return_value = [
        trader1,
        non_influential,
    ]
    mock_twitter_api.return_value.get_friends.return_value = [trader2]

    discovered = await discovery._discover_twitter_accounts(["seed_account"])

    assert len(discovered) == 2
    assert any(acc["username"] == "crypto_analyst" for acc in discovered)
    assert any(acc["username"] == "institutional_trader" for acc in discovered)

    # Verify metrics for discovered accounts
    for account in discovered:
        metrics = account["metrics"]
        assert metrics["followers_count"] >= discovery.min_follower_count
        assert metrics["engagement_rate"] >= discovery.min_engagement_rate
        assert metrics["activity_rate"] >= 0.5
        assert metrics["verified"] is True


@pytest.mark.asyncio
async def test_discover_youtube_channels(discovery, mock_youtube_client):
    # Mock YouTube API responses
    search_response = {
        "items": [
            {
                "snippet": {
                    "channelId": "channel123",
                    "channelTitle": "Professional Trading Analysis",
                    "title": "Technical Trading Strategies",
                    "description": "Expert cryptocurrency market analysis and trading strategies",
                }
            }
        ]
    }

    channels_response = {
        "items": [
            {
                "brandingSettings": {
                    "channel": {"featuredChannelsUrls": ["related_channel"]}
                }
            }
        ]
    }

    related_channels_response = {
        "items": [
            {
                "snippet": {
                    "title": "Institutional Crypto Trading",
                    "description": "Professional cryptocurrency trading and market analysis",
                }
            }
        ]
    }

    mock_youtube_client.return_value.search().list().execute.return_value = (
        search_response
    )
    mock_youtube_client.return_value.channels().list().execute.side_effect = [
        channels_response,
        related_channels_response,
    ]

    discovered = await discovery._discover_youtube_channels(["seed_account"])

    assert len(discovered) == 2
    assert "Professional Trading Analysis" in discovered
    assert "Institutional Crypto Trading" in discovered


@pytest.mark.asyncio
async def test_rate_limiter():
    limiter = RateLimiter(max_requests=2, time_window=1)

    # First two requests should be immediate
    start_time = datetime.now()
    await limiter.acquire()
    await limiter.acquire()
    first_duration = (datetime.now() - start_time).total_seconds()
    assert first_duration < 0.1  # Should be near-instant

    # Third request should wait
    await limiter.acquire()
    total_duration = (datetime.now() - start_time).total_seconds()
    assert total_duration >= 1.0


@pytest.mark.asyncio
async def test_influential_trader_detection(discovery):
    # Test highly influential verified trader
    influential = create_mock_twitter_user(
        "Major Trader",
        "Professional crypto trader, technical analysis expert, and blockchain investor",
        followers_count=200000,
        friends_count=1000,
        statuses_count=10000,
        verified=True,
        created_at=datetime.now() - timedelta(days=1460),
    )
    assert await discovery._is_influential_trader(influential) is True

    # Test institutional account
    institution = create_mock_twitter_user(
        "Crypto Exchange",
        "Leading cryptocurrency exchange. Trading, market analysis, and blockchain solutions",
        followers_count=500000,
        friends_count=1000,
        statuses_count=50000,
        verified=True,
        created_at=datetime.now() - timedelta(days=2190),
    )
    assert await discovery._is_influential_trader(institution) is True

    # Test non-influential account
    non_influential = create_mock_twitter_user(
        "Small Trader",
        "Crypto trader and enthusiast",
        followers_count=10000,
        friends_count=5000,
        statuses_count=100,
        verified=False,
    )
    assert await discovery._is_influential_trader(non_influential) is False

    # Test unverified but large account
    unverified_large = create_mock_twitter_user(
        "Popular Unverified",
        "Cryptocurrency trading signals and analysis",
        followers_count=100000,
        friends_count=1000,
        statuses_count=5000,
        verified=False,
    )
    assert await discovery._is_influential_trader(unverified_large) is False


@pytest.mark.asyncio
async def test_trader_metrics(discovery):
    trader = create_mock_twitter_user(
        "Pro Trader",
        "Institutional crypto trader and market analyst",
        followers_count=150000,
        friends_count=1000,
        statuses_count=8000,
        verified=True,
        created_at=datetime.now() - timedelta(days=1095),
    )

    metrics = await discovery._calculate_trader_metrics(trader)

    assert metrics["followers_count"] == 150000
    assert metrics["engagement_rate"] == 150.0  # 150000/1000
    assert metrics["activity_rate"] > 2  # Approximately 8000/1095
    assert metrics["verified"] is True
    assert metrics["account_age_days"] == 1095
    assert metrics["avg_tweets_per_day"] > 7  # Approximately 8000/1095
    assert metrics["listed_count"] == 1500
    assert metrics["has_website"] is True
