"""Test configuration and fixtures."""
import pytest
import asyncio
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.signals import Base
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.monitoring.accuracy_monitor import AccuracyMonitor
from app.services.monitoring.technical_indicators import TechnicalIndicators
from googleapiclient.discovery import build
import os

# Set test environment and API keys
os.environ['TESTING'] = 'true'
os.environ['TWITTER_API_KEY'] = 'test_api_key'
os.environ['TWITTER_API_SECRET'] = 'test_api_secret'
os.environ['TWITTER_ACCESS_TOKEN'] = 'test_access_token'
os.environ['TWITTER_ACCESS_SECRET'] = 'test_access_secret'
os.environ['YOUTUBE_API_KEY'] = 'test_api_key'

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_youtube_client():
    """Create a mock YouTube API client."""
    mock_client = MagicMock()
    mock_client.channels().list().execute.return_value = {'items': [{'id': 'test_channel_id', 'statistics': {'subscriberCount': '10000'}}]}
    mock_client.search().list().execute.return_value = {'items': [{'id': {'videoId': 'test_video_id'}}]}
    mock_client.videos().list().execute.return_value = {'items': [{'id': 'test_video_id', 'snippet': {'publishedAt': '2024-02-18T00:00:00Z'}}]}
    return mock_client

@pytest.fixture(scope="session")
async def db_engine():
    """Create a test database engine."""
    database_url = os.getenv("DATABASE_URL")
    if database_url is None:
        # Fallback to SQLite for local development
        database_url = "sqlite+aiosqlite:///./test.db"

    # Convert PostgreSQL URL to async format if needed
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')

    engine = create_async_engine(
        database_url,
        echo=True
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    """Create a test database session."""
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()  # Add rollback to clean up after tests

@pytest.fixture
async def test_db_session(db_session):
    """Alias for db_session to maintain compatibility."""
    yield db_session

@pytest.fixture
async def market_data_service():
    """Create a market data service instance."""
    return MarketDataService()

@pytest.fixture
def technical_indicators():
    """Create technical indicators instance for testing."""
    return TechnicalIndicators()

@pytest.fixture
async def accuracy_monitor(db_session, market_data_service, technical_indicators):
    """Create an accuracy monitor instance."""
    monitor = AccuracyMonitor(db_session, market_data_service)
    monitor.technical_indicators = technical_indicators
    return monitor
