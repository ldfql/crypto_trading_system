from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.services.analysis.prediction_analyzer import PredictionAnalyzer
from app.repositories.signal_repository import SignalRepository
from app.services.monitoring.signal_monitor import SignalMonitor
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.monitoring.account_monitor import AccountMonitor
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///instance/trading.db")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True,
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

def get_market_data_service() -> MarketDataService:
    """Get market data service instance."""
    return MarketDataService()

async def get_signal_repository(session: AsyncSession = Depends(get_session)) -> SignalRepository:
    """Get signal repository instance."""
    repo = SignalRepository(session)
    return repo

async def get_account_monitor(
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> AccountMonitor:
    """Get account monitor instance."""
    return AccountMonitor(market_data_service)

async def get_signal_monitor(
    signal_repository: SignalRepository = Depends(get_signal_repository),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    account_monitor: AccountMonitor = Depends(get_account_monitor),
) -> SignalMonitor:
    """Get signal monitor instance."""
    return SignalMonitor(signal_repository, market_data_service, account_monitor)

async def get_prediction_analyzer(
    signal_repository: SignalRepository = Depends(get_signal_repository),
    signal_monitor: SignalMonitor = Depends(get_signal_monitor),
) -> PredictionAnalyzer:
    """Get prediction analyzer instance."""
    return PredictionAnalyzer(signal_repository, signal_monitor)
