"""Repository for managing trading signals with comprehensive accuracy tracking."""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.signals import TradingSignal


class SignalRepository:
    """Repository for managing trading signals with real-time accuracy monitoring."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, signal_data: Union[Dict[str, Any], TradingSignal]
    ) -> TradingSignal:
        """Create a new trading signal with comprehensive data."""
        if isinstance(signal_data, TradingSignal):
            signal = signal_data
        else:
            signal = TradingSignal(**signal_data)
        self.session.add(signal)
        await self.session.commit()
        return signal

    async def get_active_signals(
        self,
        timeframe: Optional[str] = None,
        symbol: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[TradingSignal]:
        """Get active signals with optional filtering."""
        current_time = datetime.now(timezone.utc)
        conditions = [
            or_(
                TradingSignal.expires_at.is_(None),
                TradingSignal.expires_at > current_time,
            )
        ]

        if timeframe:
            conditions.append(TradingSignal.timeframe == timeframe)
        if symbol:
            conditions.append(TradingSignal.symbol == symbol)
        if min_confidence > 0:
            conditions.append(TradingSignal.confidence >= min_confidence)

        query = (
            select(TradingSignal)
            .where(and_(*conditions))
            .order_by(desc(TradingSignal.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_historical_predictions(
        self,
        timeframe: Optional[str] = None,
        symbol: Optional[str] = None,
        min_accuracy: Optional[float] = None,
        days: Optional[int] = None,
        limit: int = 100,
    ) -> List[TradingSignal]:
        """Get historical predictions with enhanced filtering."""
        conditions = []

        if timeframe:
            conditions.append(TradingSignal.timeframe == timeframe)
        if symbol:
            conditions.append(TradingSignal.symbol == symbol)
        if min_accuracy is not None:
            conditions.append(TradingSignal.accuracy >= min_accuracy)
        if days:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            conditions.append(TradingSignal.created_at >= start_date)

        query = select(TradingSignal)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(TradingSignal.created_at)).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def find_entry_points(
        self,
        symbol: str,
        min_confidence: float = 0.85,
        min_accuracy: float = 0.85,
        timeframe: Optional[str] = None,
    ) -> List[TradingSignal]:
        """Find valid entry points with enhanced criteria."""
        current_time = datetime.now(timezone.utc)
        conditions = [
            TradingSignal.symbol == symbol,
            TradingSignal.confidence >= min_confidence,
            or_(
                TradingSignal.accuracy.is_(None), TradingSignal.accuracy >= min_accuracy
            ),
            or_(
                TradingSignal.expires_at.is_(None),
                TradingSignal.expires_at > current_time,
            ),
        ]

        if timeframe:
            conditions.append(TradingSignal.timeframe == timeframe)

        query = (
            select(TradingSignal)
            .where(and_(*conditions))
            .order_by(desc(TradingSignal.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_signal(
        self, signal_id: int, update_data: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """Update signal with new data and validation results."""
        query = select(TradingSignal).where(TradingSignal.id == signal_id)
        result = await self.session.execute(query)
        signal = result.scalar_one_or_none()

        if not signal:
            return None

        for key, value in update_data.items():
            if hasattr(signal, key):
                setattr(signal, key, value)

        await self.session.commit()
        return signal

    async def get_accuracy_statistics(
        self, timeframe: Optional[str] = None, days: Optional[int] = None
    ) -> Dict[str, float]:
        """Get accuracy statistics for signals."""
        conditions = [TradingSignal.accuracy.isnot(None)]

        if timeframe:
            conditions.append(TradingSignal.timeframe == timeframe)
        if days:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            conditions.append(TradingSignal.created_at >= start_date)

        query = select(TradingSignal).where(and_(*conditions))
        result = await self.session.execute(query)
        signals = result.scalars().all()

        if not signals:
            return {
                "average_accuracy": 0.0,
                "max_accuracy": 0.0,
                "min_accuracy": 0.0,
                "total_signals": 0,
            }

        accuracies = [s.accuracy for s in signals if s.accuracy is not None]
        return {
            "average_accuracy": sum(accuracies) / len(accuracies),
            "max_accuracy": max(accuracies),
            "min_accuracy": min(accuracies),
            "total_signals": len(signals),
        }

    async def get_validation_history(
        self, signal_id: int
    ) -> Optional[List[Dict[str, Any]]]:
        """Get validation history for a specific signal."""
        signal = await self.get_signal(signal_id)
        return signal.validation_history if signal else None

    async def get_signal(self, signal_id: int) -> Optional[TradingSignal]:
        """Get a specific signal by ID."""
        result = await self.session.execute(
            select(TradingSignal).where(TradingSignal.id == signal_id)
        )
        return result.scalar_one_or_none()

    async def validate_accuracy(
        self, signal_id: int, current_price: float, market_data: Dict[str, Any]
    ) -> TradingSignal:
        """Validate signal accuracy and update metrics."""
        signal = await self.get_signal(signal_id)
        if not signal:
            raise ValueError(f"Signal with id {signal_id} not found")

        # Calculate accuracy based on price movement
        price_diff = abs(current_price - signal.entry_price) / signal.entry_price
        accuracy_improvement = 0.0

        if signal.validation_count > 0:
            # Improve accuracy if prediction was correct
            if (
                current_price > signal.entry_price and signal.sentiment == "bullish"
            ) or (current_price < signal.entry_price and signal.sentiment == "bearish"):
                accuracy_improvement = min(0.05, price_diff)  # Cap improvement at 5%

        # Update signal metrics
        signal.last_price = current_price
        signal.last_validated_at = datetime.utcnow()
        signal.validation_count += 1
        signal.accuracy = min(0.95, signal.accuracy + accuracy_improvement)
        signal.market_volume = market_data.get("volume")
        signal.market_volatility = market_data.get("volatility")

        await self.session.commit()
        return signal
