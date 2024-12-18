"""Service for fetching and analyzing market data."""
from datetime import datetime, timedelta
from typing import Dict, Optional
import aiohttp
import asyncio
import time
from collections import deque

class MarketDataService:
    """Service for retrieving and analyzing market data."""

    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self._rate_limit_window = 60  # 1 minute window
        self._max_requests = 1200  # Maximum requests per minute
        self._request_timestamps = deque(maxlen=self._max_requests)
        self._retry_count = 3
        self._retry_delay = 1  # seconds

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        testing: bool = False,
        **kwargs
    ) -> Dict:
        """Fetch market data with rate limiting and retry logic."""
        if testing:
            return self._get_mock_market_data()

        last_error = None
        for attempt in range(self._retry_count):
            try:
                await self._check_rate_limit()
                return await self._fetch_market_data(symbol, timeframe, limit, **kwargs)
            except Exception as e:
                last_error = str(e)
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue

        # If we get here, all retries failed
        raise Exception(f"Failed to fetch market data after {self._retry_count} attempts: {last_error}")

    async def _check_rate_limit(self):
        """Implement rate limiting logic"""
        now = time.time()

        # Remove timestamps older than the window
        while self._request_timestamps and self._request_timestamps[0] < now - self._rate_limit_window:
            self._request_timestamps.popleft()

        # If we've hit the limit, wait until we can make another request
        if len(self._request_timestamps) >= self._max_requests:
            sleep_time = self._request_timestamps[0] - (now - self._rate_limit_window)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self._request_timestamps.append(now)

    async def _fetch_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        **kwargs
    ) -> Dict:
        """Internal method to fetch market data"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/klines"
            params = {
                "symbol": symbol.replace("/", ""),
                "interval": timeframe,
                "limit": limit
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    processed_data = self._process_market_data(data)
                    processed_data.update(kwargs)
                    return processed_data
                else:
                    raise Exception(f"Failed to fetch market data: {response.status}")

    def _process_market_data(self, raw_data: list) -> Dict:
        """Process raw market data into analyzable format."""
        if not raw_data:
            return {}

        latest = raw_data[-1]
        volume_24h = sum(float(candle[5]) for candle in raw_data[-24:])

        prices = [float(candle[4]) for candle in raw_data]
        max_price = max(prices)
        min_price = min(prices)
        current_price = float(latest[4])

        # Calculate volatility (standard deviation of price changes)
        price_changes = [
            (prices[i] - prices[i-1]) / prices[i-1]
            for i in range(1, len(prices))
        ]
        volatility = (
            sum(x*x for x in price_changes) / len(price_changes)
        ) ** 0.5

        return {
            "current_price": current_price,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "price_range": {
                "max": max_price,
                "min": min_price
            },
            "timestamp": datetime.fromtimestamp(latest[0] / 1000)
        }

    def _get_mock_market_data(self) -> Dict:
        """Return mock market data for testing purposes."""
        now = datetime.now()
        return {
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "volatility": 0.02,
            "price_range": {
                "max": 51000.0,
                "min": 49000.0
            },
            "timestamp": now,
            "market_cycle": "accumulation",
            "trend": "bullish"
        }
