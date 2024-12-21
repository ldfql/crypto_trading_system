from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from src.app.database import async_session_factory
from src.app.services.market_analysis.market_data_service import MarketDataService
from src.app.services.trading.pair_selector import PairSelector
from src.app.services.trading.fee_calculator import FeeCalculator
from src.app.repositories.signal_repository import SignalRepository
from src.app.services.monitoring.account_monitor import AccountMonitor
from src.app.services.notification.notification_service import NotificationService

# Singleton instances
_notification_service = NotificationService()
_account_monitor = AccountMonitor(initial_balance=Decimal("100"))

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

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

async def get_account_monitor() -> AccountMonitor:
    """Dependency for account monitor service."""
    return _account_monitor

async def get_notification_service() -> NotificationService:
    """Dependency for notification service."""
    return _notification_service
