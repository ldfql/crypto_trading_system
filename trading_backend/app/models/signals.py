"""Trading signal models."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Numeric, JSON
from sqlalchemy.orm import relationship
from ..database import Base
from .futures import FuturesConfig

class TradingSignal(Base):
    """Trading signal model."""
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    entry_price = Column(Numeric(precision=20, scale=8))
    take_profit = Column(Numeric(precision=20, scale=8))
    stop_loss = Column(Numeric(precision=20, scale=8))
    created_at = Column(DateTime, default=datetime.utcnow)
    futures_config = Column(JSON)

    def __init__(
        self,
        symbol: str,
        entry_price: Decimal,
        take_profit: Decimal,
        stop_loss: Decimal,
        created_at: Optional[datetime] = None,
        futures_config: Optional[FuturesConfig] = None
    ):
        """Initialize trading signal."""
        self.symbol = symbol
        self.entry_price = entry_price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.created_at = created_at or datetime.utcnow()
        if futures_config:
            self.futures_config = futures_config.dict()

    @property
    def futures_configuration(self) -> Optional[FuturesConfig]:
        """Get futures configuration as FuturesConfig object."""
        if self.futures_config:
            return FuturesConfig(**self.futures_config)
        return None
