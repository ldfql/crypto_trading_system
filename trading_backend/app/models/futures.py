from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from typing import Optional

class MarginType(str, Enum):
    CROSS = "cross"
    ISOLATED = "isolated"

class AccountStage(str, Enum):
    INITIAL = "0"        # 100U - 1000U
    GROWTH = "1"         # 1000U - 10000U
    ADVANCED = "2"       # 10000U - 100000U
    PROFESSIONAL = "3"   # 100000U - 1000000U
    EXPERT = "4"         # 1000000U+ (1亿U target)

class AccountStageTransition(str, Enum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    NO_CHANGE = "no_change"

class FuturesConfig(BaseModel):
    leverage: int = Field(..., ge=1, le=125)
    margin_type: MarginType = Field(default=MarginType.CROSS)
    position_size: Decimal = Field(..., gt=0)
    max_position_size: Decimal = Field(..., gt=0)
    risk_level: float = Field(..., ge=0.01, le=1.0)

    @model_validator(mode='after')
    def validate_all(self) -> 'FuturesConfig':
        position_size = self.position_size
        max_position_size = self.max_position_size

        # Validate position size against max position size
        if position_size > max_position_size:
            raise ValueError("Position size cannot exceed max position size")

        # Validate minimum position size
        if position_size < Decimal('10'):
            raise ValueError("Position size must be at least 10U")

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
