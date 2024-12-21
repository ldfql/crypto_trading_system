"""Trading signal models."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Enum
from sqlalchemy.orm import declarative_base
from .enums import MarginType, TradingDirection

Base = declarative_base()

class TradingSignal(Base):
    """Trading signal model."""
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    entry_price = Column(Numeric(precision=20, scale=8), nullable=False)
    take_profit = Column(Numeric(precision=20, scale=8), nullable=False)
    stop_loss = Column(Numeric(precision=20, scale=8), nullable=False)
    position_size = Column(Numeric(precision=20, scale=8), nullable=False)
    leverage = Column(Integer, nullable=False)
    margin_type = Column(Enum(MarginType), nullable=False)
    direction = Column(Enum(TradingDirection), nullable=False)
    confidence = Column(Numeric(precision=5, scale=4), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    def __init__(
        self,
        symbol: str,
        entry_price: Decimal,
        take_profit: Decimal,
        stop_loss: Decimal,
        position_size: Decimal,
        leverage: int,
        margin_type: MarginType,
        direction: TradingDirection,
        confidence: Decimal,
        timestamp: Optional[datetime] = None,
        id: Optional[int] = None
    ):
        """Initialize trading signal."""
        if id is not None:
            self.id = id
        self.symbol = symbol
        self.entry_price = entry_price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.position_size = position_size
        self.leverage = leverage
        self.margin_type = margin_type
        self.direction = direction
        self.confidence = confidence
        self.timestamp = timestamp or datetime.now(timezone.utc)
