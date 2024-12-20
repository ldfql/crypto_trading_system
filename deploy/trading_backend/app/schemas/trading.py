from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from ..models.futures import MarginType

class TradingSignal(BaseModel):
    """Trading signal response model."""
    pair: str = Field(..., description="Trading pair symbol")
    entry_price: Decimal = Field(..., description="Recommended entry price")
    take_profit: Decimal = Field(..., description="Take profit target")
    stop_loss: Decimal = Field(..., description="Stop loss level")
    position_size: Decimal = Field(..., description="Recommended position size")
    leverage: int = Field(..., description="Recommended leverage")
    margin_type: MarginType = Field(..., description="Margin type (cross/isolated)")
    expected_profit: Decimal = Field(..., description="Expected profit after fees")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Signal confidence level")

class TradingPairResponse(BaseModel):
    """Response model for trading pair selection."""
    signals: List[TradingSignal] = Field(..., description="List of trading signals")
