"""Trading signal models."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Numeric, JSON
from sqlalchemy.orm import relationship
from ..database import Base
from .futures import FuturesConfig

class AccountStage(str, Enum):
    INITIAL = "initial"        # 100U - 1000U
    GROWTH = "growth"         # 1000U - 10000U
    ADVANCED = "advanced"     # 10000U - 100000U
    PROFESSIONAL = "professional"  # 100000U - 1000000U
    EXPERT = "expert"         # 1000000U+ (1亿U target)

    def __lt__(self, other):
        stages = [
            AccountStage.INITIAL,
            AccountStage.GROWTH,
            AccountStage.ADVANCED,
            AccountStage.PROFESSIONAL,
            AccountStage.EXPERT
        ]
        return stages.index(self) < stages.index(other)

    def __gt__(self, other):
        stages = [
            AccountStage.INITIAL,
            AccountStage.GROWTH,
            AccountStage.ADVANCED,
            AccountStage.PROFESSIONAL,
            AccountStage.EXPERT
        ]
        return stages.index(self) > stages.index(other)

class AccountStageTransition(str, Enum):
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    NO_CHANGE = "NO_CHANGE"

class TradingSignal(Base):
    """Trading signal model."""
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    entry_price = Column(Numeric(precision=20, scale=8))
    take_profit = Column(Numeric(precision=20, scale=8))
    stop_loss = Column(Numeric(precision=20, scale=8))
    position_size = Column(Numeric(precision=20, scale=8))
    leverage = Column(Integer)
    margin_type = Column(String)  # 'isolated' or 'cross'
    direction = Column(String)  # 'long' or 'short'
    confidence = Column(Numeric(precision=5, scale=4))
    timestamp = Column(DateTime, index=True)
    futures_config = Column(JSON, nullable=True)

    def __init__(
        self,
        symbol: str,
        entry_price: Decimal,
        take_profit: Decimal,
        stop_loss: Decimal,
        position_size: Decimal,
        leverage: int,
        margin_type: str,
        direction: str,
        confidence: Decimal,
        timestamp: Optional[datetime] = None,
        futures_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize trading signal."""
        self.symbol = symbol
        self.entry_price = entry_price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.position_size = position_size
        self.leverage = leverage
        self.margin_type = margin_type
        self.direction = direction
        self.confidence = confidence
        self.timestamp = timestamp or datetime.utcnow()
        self.futures_config = futures_config

    @property
    def futures_configuration(self) -> Optional[FuturesConfig]:
        """Get futures configuration as FuturesConfig object."""
        if self.futures_config:
            return FuturesConfig(**self.futures_config)
        return None
