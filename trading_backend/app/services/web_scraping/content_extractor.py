import asyncio
import logging
from typing import Optional, Dict, Any
import aiohttp
import trafilatura
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, calls: int, period: int):
        self.calls = calls
        self.period = period
        self.timestamps: list[datetime] = []

    async def acquire(self):
        now = datetime.now()
        # Remove timestamps older than the period
        self.timestamps = [ts for ts in self.timestamps if now - ts < timedelta(seconds=self.period)]

        if len(self.timestamps) >= self.calls:
            # Wait until the oldest timestamp is outside the period
            wait_time = (self.timestamps[0] + timedelta(seconds=self.period) - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.timestamps.pop(0)

        self.timestamps.append(now)

class ContentExtractor:
    def __init__(self):
        self.jina_reader_url = "https://r.jina.ai/"
        # Rate limit: 100 requests per minute for Jina Reader
        self.jina_limiter = RateLimiter(calls=100, period=60)
        # Rate limit: 30 requests per minute for Trafilatura
        self.trafilatura_limiter = RateLimiter(calls=30, period=60)
        self.session = None

    async def __aenter__(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def extract_content(self, url: str) -> Dict[str, Any]:
        """
        Extract content from a URL using Jina Reader with Trafilatura as fallback.
        Returns a dictionary containing the extracted content and metadata.
        """
        result = {
            "content": "",
            "metadata": {},
            "source": "",
            "success": False,
            "error": None
        }

        # Ensure session is initialized
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            # Try Jina Reader first
            await self.jina_limiter.acquire()
            async with self.session.get(f"{self.jina_reader_url}{url}") as response:
                if response.status == 200:
                    result["content"] = await response.text()
                    result["source"] = "jina_reader"
                    result["success"] = True
                    return result
                logger.warning(f"Jina Reader failed with status {response.status} for {url}")
        except Exception as e:
            logger.error(f"Error using Jina Reader: {str(e)}")
            result["error"] = str(e)

        try:
            # Fallback to Trafilatura
            await self.trafilatura_limiter.acquire()
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                content = trafilatura.extract(downloaded)
                if content:
                    result["content"] = content
                    result["metadata"] = trafilatura.extract_metadata(downloaded) or {}
                    result["source"] = "trafilatura"
                    result["success"] = True
                    return result
        except Exception as e:
            logger.error(f"Error using Trafilatura: {str(e)}")
            if not result["error"]:
                result["error"] = str(e)

        return result

    async def extract_batch(self, urls: list[str], concurrency: int = 5) -> list[Dict[str, Any]]:
        """
        Extract content from multiple URLs concurrently.
        """
        async def process_url(url: str) -> Dict[str, Any]:
            return await self.extract_content(url)

        # Process URLs in batches to control concurrency
        results = []
        for i in range(0, len(urls), concurrency):
            batch = urls[i:i + concurrency]
            batch_results = await asyncio.gather(*[process_url(url) for url in batch])
            results.extend(batch_results)

        return results
