"""Tests for dependency injection functions."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_market_data_service,
    get_fee_calculator,
    get_pair_selector,
    get_signal_repository
)
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.trading.fee_calculator import FeeCalculator
from app.services.trading.pair_selector import PairSelector
from app.repositories.signal_repository import SignalRepository

@pytest.mark.asyncio
async def test_get_db():
    """Test database session dependency."""
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        break

@pytest.mark.asyncio
async def test_get_market_data_service():
    """Test market data service dependency."""
    service = await get_market_data_service()
    assert isinstance(service, MarketDataService)

@pytest.mark.asyncio
async def test_get_fee_calculator():
    """Test fee calculator dependency."""
    calculator = await get_fee_calculator()
    assert isinstance(calculator, FeeCalculator)

@pytest.mark.asyncio
async def test_get_pair_selector():
    """Test pair selector dependency."""
    market_data_service = AsyncMock(spec=MarketDataService)
    selector = await get_pair_selector(market_data_service)
    assert isinstance(selector, PairSelector)
    assert selector.market_data_service == market_data_service

@pytest.mark.asyncio
async def test_get_signal_repository():
    """Test signal repository dependency."""
    db = AsyncMock(spec=AsyncSession)
    repo = await get_signal_repository(db)
    assert isinstance(repo, SignalRepository)
    assert repo.session == db
