"""Service for fetching and analyzing market data."""
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from decimal import Decimal
import aiohttp
import asyncio
import time
from collections import deque


class MarketDataService:
    """Service for retrieving and analyzing market data."""

    def __init__(self):
        self.spot_base_url = "https://api.binance.com/api/v3"
        self.futures_base_url = "https://fapi.binance.com/fapi/v1"
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
        use_futures: bool = True,
        **kwargs,
    ) -> Dict:
        """Fetch market data with rate limiting and retry logic."""
        if testing:
            return self._get_mock_market_data()

        last_error = None
        for attempt in range(self._retry_count):
            try:
                await self._check_rate_limit()
                return await self._fetch_market_data(symbol, timeframe, limit, use_futures, **kwargs)
            except Exception as e:
                last_error = str(e)
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue

        # If we get here, all retries failed
        raise Exception(
            f"Failed to fetch market data after {self._retry_count} attempts: {last_error}"
        )

    async def _check_rate_limit(self):
        """Implement rate limiting logic"""
        now = time.time()

        # Remove timestamps older than the window
        while (
            self._request_timestamps
            and self._request_timestamps[0] < now - self._rate_limit_window
        ):
            self._request_timestamps.popleft()

        # If we've hit the limit, wait until we can make another request
        if len(self._request_timestamps) >= self._max_requests:
            sleep_time = self._request_timestamps[0] - (now - self._rate_limit_window)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self._request_timestamps.append(now)

    async def _fetch_market_data(
        self, symbol: str, timeframe: str, limit: int, use_futures: bool = True, **kwargs
    ) -> Dict:
        """Internal method to fetch market data"""
        base_url = self.futures_base_url if use_futures else self.spot_base_url

        async with aiohttp.ClientSession() as session:
            # Get klines data
            klines_url = f"{base_url}/klines"
            params = {
                "symbol": symbol.replace("/", ""),
                "interval": timeframe,
                "limit": limit,
            }

            async with session.get(klines_url, params=params) as response:
                if response.status == 200:
                    klines_data = await response.json()

                    # If using futures, get additional contract info
                    if use_futures:
                        contract_info = await self._get_futures_contract_info(session, symbol)
                        processed_data = self._process_market_data(klines_data, contract_info)
                    else:
                        processed_data = self._process_market_data(klines_data)

                    processed_data.update(kwargs)
                    return processed_data
                else:
                    raise Exception(f"Failed to fetch market data: {response.status}")

    async def _get_futures_contract_info(
        self, session: aiohttp.ClientSession, symbol: str
    ) -> Dict:
        """Get futures contract specific information."""
        url = f"{self.futures_base_url}/premiumIndex"
        params = {"symbol": symbol.replace("/", "")}

        async with session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch futures info: {response.status}")

    def _process_market_data(self, raw_data: list, futures_info: Optional[Dict] = None) -> Dict:
        """Process raw market data into analyzable format."""
        if not raw_data:
            return {}

        latest = raw_data[-1]
        volume_24h = Decimal(str(sum(float(candle[5]) for candle in raw_data[-24:])))

        prices = [Decimal(str(candle[4])) for candle in raw_data]
        max_price = max(prices)
        min_price = min(prices)
        current_price = Decimal(str(latest[4]))

        # Calculate volatility (standard deviation of price changes)
        price_changes = [
            (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
        ]
        volatility = Decimal(str((sum(x * x for x in price_changes) / len(price_changes)) ** 0.5))

        result = {
            "current_price": current_price,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "price_range": {"max": max_price, "min": min_price},
            "timestamp": datetime.fromtimestamp(latest[0] / 1000),
        }

        # Add futures specific data if available
        if futures_info:
            result.update({
                "mark_price": Decimal(str(futures_info.get("markPrice", "0"))),
                "index_price": Decimal(str(futures_info.get("indexPrice", "0"))),
                "funding_rate": Decimal(str(futures_info.get("lastFundingRate", "0"))),
                "next_funding_time": datetime.fromtimestamp(
                    futures_info.get("nextFundingTime", 0) / 1000
                ),
            })

        return result

    def _get_mock_market_data(self) -> Dict:
        """Return mock market data for testing purposes."""
        now = datetime.now()
        return {
            "current_price": Decimal("50000.0"),
            "volume_24h": Decimal("5000000.0"),
            "volatility": Decimal("0.02"),
            "price_range": {
                "max": Decimal("51000.0"),
                "min": Decimal("49000.0")
            },
            "timestamp": now,
            "market_cycle": "accumulation",
            "trend": "bullish",
            "spread_percentage": Decimal("0.1"),
            "liquidity_score": Decimal("2.0"),
            "market_cap": Decimal("1000000000.0"),
            "price": Decimal("50000.0"),
            "mark_price": Decimal("50000.0"),
            "index_price": Decimal("50000.0"),
            "funding_rate": Decimal("0.0001"),
            "next_funding_time": now + timedelta(hours=8)
        }
