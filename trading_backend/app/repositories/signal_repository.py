"""Signal repository for database operations."""
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select
from sqlalchemy.future import select as future_select
from ..models.signals import TradingSignal
from ..models.futures import FuturesConfig
from ..models.enums import MarginType, TradingDirection

class SignalRepository:
    """Repository for managing trading signals."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create_signal(self, signal: TradingSignal) -> TradingSignal:
        """Create a new trading signal."""
        # Set default timestamp if not provided
        if not signal.timestamp:
            signal.timestamp = datetime.now(timezone.utc)

        async with self.session.begin():
            self.session.add(signal)
            await self.session.flush()
            await self.session.refresh(signal)
            return signal

    async def get_signal_by_id(self, signal_id: int) -> Optional[TradingSignal]:
        """Get trading signal by ID."""
        stmt = future_select(TradingSignal).filter(TradingSignal.id == signal_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_signals(
        self,
        limit: int = 100,
        symbol: Optional[str] = None,
        direction: Optional[TradingDirection] = None,
        min_confidence: Optional[Decimal] = None
    ) -> List[TradingSignal]:
        """Get recent trading signals with optional filters."""
        stmt = future_select(TradingSignal)

        if symbol:
            stmt = stmt.filter(TradingSignal.symbol == symbol)
        if direction:
            stmt = stmt.filter(TradingSignal.direction == direction)
        if min_confidence is not None:
            stmt = stmt.filter(TradingSignal.confidence >= min_confidence)

        stmt = stmt.order_by(desc(TradingSignal.timestamp)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """Update an existing signal."""
        if signal.id is None:
            return None

        existing = await self.get_signal_by_id(signal.id)
        if existing:
            async with self.session.begin():
                for key, value in signal.__dict__.items():
                    if not key.startswith('_') and hasattr(existing, key):
                        setattr(existing, key, value)
                await self.session.flush()
                await self.session.refresh(existing)
                return existing
        return None

    async def delete_signal(self, signal_id: int) -> bool:
        """Delete trading signal by ID."""
        signal = await self.get_signal_by_id(signal_id)
        if signal:
            async with self.session.begin():
                await self.session.delete(signal)
                await self.session.flush()
                return True
        return False
