from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from typing import Optional

class MarginType(str, Enum):
    CROSS = "cross"
    ISOLATED = "isolated"

class AccountStage(str, Enum):
    INITIAL = "initial"  # 100U - 1000U
    GROWTH = "growth"    # 1000U - 10000U
    SCALING = "scaling"  # 10000U - 100000U
    MATURE = "mature"    # 100000U+

class FuturesConfig(BaseModel):
    leverage: int = Field(..., ge=1, le=125)
    margin_type: MarginType
    position_size: Decimal = Field(..., gt=0)
    max_position_size: Decimal = Field(..., gt=0)
    risk_level: float = Field(..., ge=0.01, le=1.0)

    @model_validator(mode='after')
    def validate_all(self) -> 'FuturesConfig':
        position_size = self.position_size
        leverage = self.leverage

        # First validate position size range
        if position_size < Decimal('100'):
            raise ValueError("Position size must be at least 100U")
        if position_size > Decimal('10000'):
            raise ValueError("Position size must not exceed 10000U")

        # Initial stage: 100U-1000U
        if Decimal('100') <= position_size < Decimal('1000'):
            if leverage > 20:
                raise ValueError("Initial stage (100U-1000U) max leverage is 20x")
        # Growth stage: 1000U-10000U
        elif Decimal('1000') <= position_size <= Decimal('10000'):
            if leverage > 50:
                raise ValueError("Growth stage (1000U-10000U) max leverage is 50x")

        return self

class FuturesPosition(BaseModel):
    symbol: str
    entry_price: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None

    @field_validator('take_profit')
    @classmethod
    def validate_take_profit(cls, v, values):
        if v is not None:
            entry = values.get('entry_price')
            if entry and v <= entry:
                raise ValueError("Take profit must be higher than entry price")
        return v

    @field_validator('stop_loss')
    @classmethod
    def validate_stop_loss(cls, v, values):
        if v is not None:
            entry = values.get('entry_price')
            if entry and v >= entry:
                raise ValueError("Stop loss must be lower than entry price")
        return v
