"""Signal repository for database operations."""
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..models.signals import TradingSignal
from ..models.futures import FuturesConfig, MarginType

class SignalRepository:
    """Repository for managing trading signals."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def validate_trading_parameters(self, **kwargs) -> None:
        """Validate trading signal parameters."""
        if 'leverage' in kwargs:
            leverage = kwargs['leverage']
            if not isinstance(leverage, int) or leverage < 1 or leverage > 125:
                raise ValueError("Leverage must be between 1 and 125")

        if 'margin_type' in kwargs:
            margin_type = kwargs['margin_type']
            if margin_type not in ['isolated', 'cross']:
                raise ValueError("Margin type must be either 'isolated' or 'cross'")

        if 'direction' in kwargs:
            direction = kwargs['direction']
            if direction not in ['long', 'short']:
                raise ValueError("Direction must be either 'long' or 'short'")

        if 'confidence' in kwargs:
            confidence = kwargs['confidence']
            if not isinstance(confidence, Decimal) or confidence < 0 or confidence > 1:
                raise ValueError("Confidence must be a decimal between 0 and 1")

    async def create_signal(self, **kwargs) -> TradingSignal:
        """Create a new trading signal with validation."""
        self.validate_trading_parameters(**kwargs)

        # Set default timestamp if not provided
        if 'timestamp' not in kwargs:
            kwargs['timestamp'] = datetime.now(timezone.utc)

        signal = TradingSignal(**kwargs)
        self.session.add(signal)
        self.session.commit()
        self.session.refresh(signal)
        return signal

    async def get_signal(self, signal_id: int) -> Optional[TradingSignal]:
        """Get trading signal by ID."""
        return self.session.query(TradingSignal).filter(TradingSignal.id == signal_id).first()

    async def get_signals(self,
                         limit: int = 100,
                         symbol: Optional[str] = None,
                         direction: Optional[str] = None,
                         min_confidence: Optional[Decimal] = None) -> List[TradingSignal]:
        """Get trading signals with optional filters."""
        query = self.session.query(TradingSignal)

        if symbol:
            query = query.filter(TradingSignal.symbol == symbol)
        if direction:
            query = query.filter(TradingSignal.direction == direction)
        if min_confidence is not None:
            query = query.filter(TradingSignal.confidence >= min_confidence)

        return query.order_by(desc(TradingSignal.timestamp)).limit(limit).all()

    async def update_signal(self, signal_id: int, futures_config: FuturesConfig) -> Optional[TradingSignal]:
        """Update trading signal with futures configuration."""
        signal = await self.get_signal(signal_id)
        if signal:
            # Validate futures configuration
            self.validate_trading_parameters(
                leverage=futures_config.leverage,
                margin_type=futures_config.margin_type
            )

            # Convert Decimal values to strings for JSON serialization
            config_dict = futures_config.model_dump()
            decimal_fields = ['position_size', 'max_position_size', 'risk_level']
            for key in decimal_fields:
                if key in config_dict and config_dict[key] is not None:
                    if isinstance(config_dict[key], Decimal):
                        config_dict[key] = str(config_dict[key])

            signal.futures_config = config_dict
            self.session.commit()
            self.session.refresh(signal)
        return signal

    async def delete_signal(self, signal_id: int) -> bool:
        """Delete trading signal by ID."""
        signal = await self.get_signal(signal_id)
        if signal:
            self.session.delete(signal)
            self.session.commit()
            return True
        return False
