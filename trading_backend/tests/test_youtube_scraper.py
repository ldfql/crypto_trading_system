import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, UTC
from googleapiclient.errors import HttpError
from app.services.web_scraping.youtube_scraper import YouTubeScraper

@pytest.fixture
def mock_youtube_client(monkeypatch):
    """Create a mock YouTube API client."""
    def mock_build(*args, **kwargs):
        mock_client = Mock()

        # Configure mock responses
        mock_client.channels().list().execute.return_value = {
            'items': [{
                'id': 'test_channel_id',
                'statistics': {'subscriberCount': '100000'}
            }]
        }

        mock_client.search().list().execute.return_value = {
            'items': [{
                'id': {'videoId': 'test_video_id'},
                'snippet': {
                    'title': 'Bitcoin Trading Strategy - Strong Bullish Signals',
                    'description': 'Technical analysis shows strong support with institutional buying',
                    'publishedAt': '2024-02-18T00:00:00Z'
                }
            }]
        }

        mock_client.videos().list().execute.return_value = {
            'items': [{
                'id': 'test_video_id',
                'snippet': {
                    'title': 'Bitcoin Trading Strategy',
                    'description': 'Technical analysis shows bullish signals',
                    'publishedAt': '2024-02-18T00:00:00Z'
                },
                'statistics': {
                    'viewCount': '50000',
                    'likeCount': '5000'
                }
            }]
        }

        return mock_client

    monkeypatch.setattr('app.services.web_scraping.youtube_scraper.build', mock_build)
    return mock_build

@pytest.fixture
def youtube_scraper(monkeypatch):
    """Create a YouTube scraper instance with test credentials."""
    monkeypatch.setenv('TESTING', 'true')
    return YouTubeScraper(trading_channels=['crypto_channel'])

def create_mock_video(
    title: str,
    description: str,
    views: int,
    likes: int,
    hours_ago: int = 1
):
    return {
        'id': 'video123',
        'snippet': {
            'title': title,
            'description': description,
            'publishedAt': (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime('%Y-%m-%dT%H:%M:%SZ')
        },
        'statistics': {
            'viewCount': str(views),
            'likeCount': str(likes)
        }
    }

@pytest.mark.asyncio
async def test_get_trading_insights(youtube_scraper, mock_youtube_client):
    # Mock responses
    channel_response = {
        'items': [{
            'id': 'channel123',
            'statistics': {
                'subscriberCount': '100000'
            }
        }]
    }

    search_response = {
        'items': [{
            'id': {'videoId': 'video123'},
            'snippet': {
                'title': 'Bitcoin Trading Strategy',
                'description': 'Technical analysis of BTC',
                'publishedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        }]
    }

    videos_response = {
        'items': [
            create_mock_video(
                'Bitcoin Trading Strategy - Strong Bullish Signals',
                'Technical analysis shows strong support at current levels with institutional buying pressure. Multiple indicators suggest an upward trend continuation.',
                50000,
                5000
            )
        ]
    }

    # Configure mock responses
    mock_client = mock_youtube_client()
    mock_client.channels().list().execute.return_value = channel_response
    mock_client.search().list().execute.return_value = search_response
    mock_client.videos().list().execute.return_value = videos_response

    insights = await youtube_scraper.get_trading_insights(hours_ago=24)

    assert len(insights) == 1
    assert 'Bitcoin' in insights[0]['title']
    assert insights[0]['views'] >= 50000
    assert insights[0]['influence_weight'] > 0 and insights[0]['influence_weight'] <= 1

@pytest.mark.asyncio
async def test_get_strategy_insights(youtube_scraper, mock_youtube_client):
    channel_response = {
        'items': [{
            'id': 'channel123',
            'statistics': {
                'subscriberCount': '100000'
            }
        }]
    }

    search_response = {
        'items': [{
            'id': {'videoId': 'video123'},
            'snippet': {
                'title': 'Crypto Trading Signals',
                'description': 'Market analysis',
                'publishedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        }]
    }

    videos_response = {
        'items': [
            create_mock_video(
                'Crypto Trading Signals',
                'Market analysis',
                100000,
                10000
            )
        ]
    }

    mock_client = mock_youtube_client()
    mock_client.channels().list().execute.return_value = channel_response
    mock_client.search().list().execute.return_value = search_response
    mock_client.videos().list().execute.return_value = videos_response

    insights = await youtube_scraper.get_strategy_insights(timeframe="1h")

    assert insights['sentiment'] > 0
    assert insights['confidence'] > 0
    assert insights['sample_size'] == 1

@pytest.mark.asyncio
async def test_empty_strategy_insights(youtube_scraper, mock_youtube_client):
    mock_client = mock_youtube_client()
    mock_client.channels().list().execute.return_value = {'items': []}

    insights = await youtube_scraper.get_strategy_insights(timeframe="1h")

    assert insights['sentiment'] == 0
    assert insights['confidence'] == 0
    assert insights['sample_size'] == 0

@pytest.mark.asyncio
async def test_api_quota_exceeded(youtube_scraper, mock_youtube_client):
    error_response = Mock()
    error_response.resp.status = 403
    mock_client = mock_youtube_client()
    mock_client.channels().list().execute.side_effect = HttpError(
        error_response,
        b'Quota exceeded'
    )

    insights = await youtube_scraper.get_trading_insights(hours_ago=24)
    assert len(insights) == 0

def test_is_trading_related(youtube_scraper):
    trading_snippet = {
        'title': 'Bitcoin Trading Strategy',
        'description': 'Technical analysis and price predictions'
    }
    non_trading_snippet = {
        'title': 'My Daily Vlog',
        'description': 'A day in my life'
    }

    assert youtube_scraper._is_trading_related(trading_snippet)
    assert not youtube_scraper._is_trading_related(non_trading_snippet)

def test_calculate_influence_weight(youtube_scraper):
    # Test normal case
    weight = youtube_scraper._calculate_influence_weight(
        views=50000,
        likes=5000,
        subscribers=100000,
        comments=500
    )
    assert weight == pytest.approx(0.1, abs=0.01)

    # Test high engagement case
    high_weight = youtube_scraper._calculate_influence_weight(
        views=1000000,
        likes=100000,
        subscribers=100000,
        comments=10000
    )
    assert high_weight == pytest.approx(0.1, abs=0.01)

    # Test low engagement case
    low_weight = youtube_scraper._calculate_influence_weight(
        views=100,
        likes=10,
        subscribers=1000000,
        comments=5
    )
    assert low_weight == pytest.approx(0.1, abs=0.01)
