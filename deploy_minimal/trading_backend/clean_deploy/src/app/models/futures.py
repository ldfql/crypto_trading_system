"""Futures trading models."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Enum
from src.app.database import Base
from src.app.models.enums import MarginType, TradingDirection, AccountStage

class FuturesConfig(Base):
    """Futures trading configuration."""
    __tablename__ = "futures_config"

    id = Column(Integer, primary_key=True)
    leverage = Column(Integer, nullable=False)
    margin_type = Column(Enum(MarginType), nullable=False, default=MarginType.CROSS)
    position_size = Column(Numeric(precision=20, scale=8), nullable=False)
    max_position_size = Column(Numeric(precision=20, scale=8), nullable=False)
    risk_level = Column(Numeric(precision=5, scale=4), nullable=False)
    account_stage = Column(Enum(AccountStage), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Stage-specific leverage limits
    MAX_LEVERAGE = {
        AccountStage.INITIAL: 15,      # Safer limit for small accounts
        AccountStage.BEGINNER: 15,     # Moderate risk for growing accounts
        AccountStage.INTERMEDIATE: 12,  # Balanced risk as account grows
        AccountStage.ADVANCED: 10,     # Conservative as stakes increase
        AccountStage.PROFESSIONAL: 5,  # Very conservative with larger capital
        AccountStage.EXPERT: 3        # Minimal leverage for largest accounts
    }

    def __init__(
        self,
        leverage: int,
        position_size: Decimal,
        max_position_size: Decimal,
        risk_level: Decimal,
        margin_type: MarginType = MarginType.CROSS,
        account_stage: AccountStage = None,
        id: int = None
    ):
        """Initialize futures configuration."""
        if id is not None:
            self.id = id
        self.leverage = leverage
        self.margin_type = margin_type
        self.position_size = position_size
        self.max_position_size = max_position_size
        self.risk_level = risk_level
        self.account_stage = account_stage
        self.validate()

    def validate(self) -> bool:
        """Validate futures configuration."""
        if self.position_size <= 0:
            raise ValueError("Position size must be greater than zero")

        if self.position_size > self.max_position_size:
            raise ValueError(
                f"Position size ({self.position_size}) cannot exceed max position size ({self.max_position_size})"
            )

        if self.leverage <= 0:
            raise ValueError("Leverage must be greater than zero")

        # Basic validation only - detailed validation happens in AccountMonitor
        if self.risk_level <= 0:
            raise ValueError("Risk level must be greater than zero")

        return True

class FuturesPosition(Base):
    """Futures trading position."""
    __tablename__ = "futures_positions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    entry_price = Column(Numeric(precision=20, scale=8), nullable=False)
    take_profit = Column(Numeric(precision=20, scale=8), nullable=True)
    stop_loss = Column(Numeric(precision=20, scale=8), nullable=True)
    direction = Column(Enum(TradingDirection), nullable=False)
    size = Column(Numeric(precision=20, scale=8), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __init__(
        self,
        symbol: str,
        entry_price: Decimal,
        direction: TradingDirection,
        size: Decimal,
        take_profit: Decimal = None,
        stop_loss: Decimal = None,
        id: int = None
    ):
        """Initialize futures position."""
        if id is not None:
            self.id = id
        self.symbol = symbol
        self.entry_price = entry_price
        self.direction = direction
        self.size = size
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.validate()

    def validate(self) -> bool:
        """Validate futures position."""
        if self.direction == TradingDirection.LONG:
            if self.take_profit is not None and self.take_profit <= self.entry_price:
                raise ValueError("Take profit must be above entry price for long positions")
            if self.stop_loss is not None and self.stop_loss >= self.entry_price:
                raise ValueError("Stop loss must be below entry price for long positions")
        else:  # SHORT
            if self.take_profit is not None and self.take_profit >= self.entry_price:
                raise ValueError("Take profit must be below entry price for short positions")
            if self.stop_loss is not None and self.stop_loss <= self.entry_price:
                raise ValueError("Stop loss must be above entry price for short positions")

        return True
