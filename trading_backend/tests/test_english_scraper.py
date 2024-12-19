import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from app.services.web_scraping.english_scraper import EnglishPlatformScraper
from app.services.web_scraping.sentiment_analyzer import SentimentAnalyzer
from app.services.web_scraping.account_discovery import AccountDiscovery

@pytest.fixture
def mock_twitter_api():
    with patch('tweepy.API') as mock_api:
        yield mock_api

@pytest.fixture
def mock_youtube_client():
    with patch('googleapiclient.discovery.build') as mock_build:
        yield mock_build

@pytest.fixture
def mock_sentiment_analyzer():
    analyzer = Mock(spec=SentimentAnalyzer)
    analyzer.analyze_text.return_value = 0.75
    return analyzer

@pytest.fixture
def mock_account_discovery():
    discovery = Mock(spec=AccountDiscovery)
    discovery.find_related_accounts.return_value = ['trader1', 'trader2']
    return discovery

@pytest.fixture
def scraper(mock_twitter_api, mock_youtube_client, mock_sentiment_analyzer, mock_account_discovery):
    return EnglishPlatformScraper(
        twitter_api_key='test_key',
        twitter_api_secret='test_secret',
        twitter_access_token='test_token',
        twitter_access_secret='test_token_secret',
        youtube_api_key='test_youtube_key',
        sentiment_analyzer=mock_sentiment_analyzer,
        account_discovery=mock_account_discovery
    )

@pytest.mark.asyncio
async def test_get_twitter_insights(scraper, mock_twitter_api):
    # Mock tweet data
    tweet = Mock()
    tweet.full_text = "Bitcoin looking bullish with strong support at $45k"
    tweet.created_at = datetime.now()
    tweet.id = "123456"

    mock_twitter_api.return_value.user_timeline.return_value = [tweet]

    insights = await scraper.get_twitter_insights(['crypto_trader'])

    assert len(insights) == 1
    assert insights[0]['platform'] == 'twitter'
    assert insights[0]['content'] == tweet.full_text
    assert insights[0]['sentiment'] == 0.75

@pytest.mark.asyncio
async def test_get_youtube_insights(scraper, mock_youtube_client):
    # Mock YouTube API responses
    channel_response = {
        'items': [{'id': 'channel123'}]
    }
    videos_response = {
        'items': [{
            'id': {'videoId': 'video123'},
            'snippet': {
                'title': 'Crypto Trading Strategy',
                'description': 'Analysis of BTC trends',
                'publishedAt': '2024-01-01T00:00:00Z'
            }
        }]
    }

    mock_youtube_client.return_value.channels().list().execute.return_value = channel_response
    mock_youtube_client.return_value.search().list().execute.return_value = videos_response

    insights = await scraper.get_youtube_insights(['crypto_channel'])

    assert len(insights) == 1
    assert insights[0]['platform'] == 'youtube'
    assert 'Crypto Trading Strategy' in insights[0]['content']
    assert insights[0]['sentiment'] == 0.75

@pytest.mark.asyncio
async def test_discover_related_accounts(scraper):
    related_accounts = await scraper.discover_related_accounts(['seed_trader'])
    assert len(related_accounts) == 2
    assert 'trader1' in related_accounts
    assert 'trader2' in related_accounts

def test_is_trading_related(scraper):
    assert scraper._is_trading_related("Bitcoin price analysis")
    assert scraper._is_trading_related("ETH breaking resistance")
    assert not scraper._is_trading_related("Good morning everyone!")
