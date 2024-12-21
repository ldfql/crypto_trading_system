"""Signal repository for database operations."""
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select
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

        self.session.add(signal)
        await self.session.commit()
        await self.session.refresh(signal)
        return signal

    async def get_signal_by_id(self, signal_id: int) -> Optional[TradingSignal]:
        """Get trading signal by ID."""
        result = await self.session.execute(
            select(TradingSignal).filter(TradingSignal.id == signal_id)
        )
        return result.scalar_one_or_none()

    async def get_recent_signals(
        self,
        limit: int = 100,
        symbol: Optional[str] = None,
        direction: Optional[TradingDirection] = None,
        min_confidence: Optional[Decimal] = None
    ) -> List[TradingSignal]:
        """Get recent trading signals with optional filters."""
        query = select(TradingSignal)

        if symbol:
            query = query.filter(TradingSignal.symbol == symbol)
        if direction:
            query = query.filter(TradingSignal.direction == direction)
        if min_confidence is not None:
            query = query.filter(TradingSignal.confidence >= min_confidence)

        query = query.order_by(desc(TradingSignal.timestamp)).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """Update an existing signal."""
        if signal.id is None:
            return None

        existing = await self.get_signal_by_id(signal.id)
        if existing:
            for key, value in signal.__dict__.items():
                if not key.startswith('_') and hasattr(existing, key):
                    setattr(existing, key, value)

            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        return None

    async def delete_signal(self, signal_id: int) -> bool:
        """Delete trading signal by ID."""
        signal = await self.get_signal_by_id(signal_id)
        if signal:
            await self.session.delete(signal)
            await self.session.commit()
            return True
        return False
