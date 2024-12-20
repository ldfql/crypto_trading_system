from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_session
from .services.market_analysis.market_data_service import MarketDataService
from .services.trading.pair_selector import PairSelector
from .services.trading.fee_calculator import FeeCalculator
from .repositories.signal_repository import SignalRepository

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session

async def get_market_data_service() -> MarketDataService:
    """Dependency for market data service."""
    return MarketDataService()

async def get_fee_calculator() -> FeeCalculator:
    """Dependency for fee calculator service."""
    return FeeCalculator()

async def get_pair_selector(
    market_data_service: MarketDataService = Depends(get_market_data_service)
) -> PairSelector:
    """Dependency for pair selector service."""
    return PairSelector(market_data_service)

async def get_signal_repository(
    db: AsyncSession = Depends(get_db)
) -> SignalRepository:
    """Dependency for signal repository."""
    return SignalRepository(db)
