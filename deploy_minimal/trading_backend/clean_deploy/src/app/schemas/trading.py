from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from ..models.futures import MarginType

class TradingSignal(BaseModel):
    """Trading signal response model."""
    pair: str = Field(..., description="Trading pair symbol", pattern=r"^[A-Z0-9]+USDT$")
    entry_price: Decimal = Field(..., description="Recommended entry price", gt=0)
    take_profit: Decimal = Field(..., description="Take profit target", gt=0)
    stop_loss: Decimal = Field(..., description="Stop loss level", gt=0)
    position_size: Decimal = Field(..., description="Recommended position size", gt=0)
    leverage: int = Field(..., description="Recommended leverage", ge=1, le=125)
    margin_type: MarginType = Field(..., description="Margin type (cross/isolated)")
    expected_profit: Decimal = Field(..., description="Expected profit after fees", gt=0)
    confidence: float = Field(..., ge=0.82, le=1.0, description="Signal confidence level")

    @validator('take_profit')
    def validate_take_profit(cls, v, values):
        if 'entry_price' in values and v <= values['entry_price']:
            raise ValueError("Take profit must be higher than entry price")
        return v

    @validator('stop_loss')
    def validate_stop_loss(cls, v, values):
        if 'entry_price' in values and v >= values['entry_price']:
            raise ValueError("Stop loss must be lower than entry price")
        return v

    @validator('position_size')
    def validate_position_size(cls, v):
        if v > Decimal("1000000000"):
            raise ValueError("Position size exceeds maximum allowed")
        return v

    @validator('expected_profit')
    def validate_expected_profit(cls, v, values):
        if 'position_size' in values and v > values['position_size'] * Decimal("0.1"):
            raise ValueError("Expected profit exceeds 10% of position size")
        return v

class TradingPairResponse(BaseModel):
    """Response model for trading pair selection."""
    signals: List[TradingSignal] = Field(..., description="List of trading signals")
