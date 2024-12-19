import asyncio
import pytest
import aiohttp
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.web_scraping.content_extractor import ContentExtractor, RateLimiter

@pytest.fixture
def mock_response():
    response = AsyncMock()
    response.status = 200
    response.text = AsyncMock()
    response.text.return_value = "Test content"
    return response

@pytest.fixture
def mock_session(mock_response):
    session = AsyncMock()
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = mock_response
    session.get.return_value = context_manager
    return session

@pytest.mark.asyncio
async def test_rate_limiter():
    limiter = RateLimiter(calls=2, period=1)

    # First two calls should be immediate
    await limiter.acquire()
    await limiter.acquire()

    # Third call should wait
    start_time = datetime.now()
    await limiter.acquire()
    elapsed = (datetime.now() - start_time).total_seconds()
    assert elapsed >= 1.0

@pytest.mark.asyncio
async def test_content_extractor_jina_success():
    mock_response = AsyncMock()
    mock_response.status = 500  # Force fallback to trafilatura
    mock_response.text = AsyncMock()
    mock_response.text.return_value = "Test content"

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_context

    async with ContentExtractor() as extractor:
        extractor.session = mock_session
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract:

            mock_fetch.return_value = "downloaded_content"
            mock_extract.return_value = "extracted_content"

            result = await extractor.extract_content("https://example.com")

            assert result["success"] is True
            assert result["source"] == "trafilatura"
            assert result["content"] == "extracted_content"

@pytest.mark.asyncio
async def test_content_extractor_fallback():
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock()
    mock_response.text.return_value = ""

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_context

    async with ContentExtractor() as extractor:
        extractor.session = mock_session
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('trafilatura.extract_metadata') as mock_metadata:

            mock_fetch.return_value = "downloaded_content"
            mock_extract.return_value = "extracted_content"
            mock_metadata.return_value = {"title": "Test"}

            result = await extractor.extract_content("https://example.com")

            assert result["success"] is True
            assert result["source"] == "trafilatura"
            assert result["content"] == "extracted_content"
            assert "metadata" in result
            assert result["metadata"]["title"] == "Test"

@pytest.mark.asyncio
async def test_content_extractor_batch():
    async with ContentExtractor() as extractor:
        with patch.object(extractor, 'extract_content', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = {
                "content": "test",
                "success": True,
                "source": "test"
            }

            urls = [f"https://example.com/{i}" for i in range(3)]
            results = await extractor.extract_batch(urls, concurrency=2)

            assert len(results) == 3
            assert all(isinstance(result, dict) for result in results)
            assert mock_extract.call_count == 3
