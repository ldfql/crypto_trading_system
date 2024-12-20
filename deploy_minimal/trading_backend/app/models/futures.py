from enum import Enum
from pydantic import BaseModel, Field, validator
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

    @validator('leverage')
    def validate_leverage_by_account_stage(cls, v, values):
        account_balance = values.get('position_size', 0) * v
        if account_balance <= 1000:
            if v > 20:
                raise ValueError("Initial stage (100U-1000U) max leverage is 20x")
        elif account_balance <= 10000:
            if v > 50:
                raise ValueError("Growth stage (1000U-10000U) max leverage is 50x")
        elif account_balance <= 100000:
            if v > 75:
                raise ValueError("Scaling stage (10000U-100000U) max leverage is 75x")
        return v

class FuturesPosition(BaseModel):
    symbol: str
    entry_price: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None

    @validator('take_profit')
    def validate_take_profit(cls, v, values):
        if v is not None:
            entry = values.get('entry_price')
            if entry and v <= entry:
                raise ValueError("Take profit must be higher than entry price")
        return v

    @validator('stop_loss')
    def validate_stop_loss(cls, v, values):
        if v is not None:
            entry = values.get('entry_price')
            if entry and v >= entry:
                raise ValueError("Stop loss must be lower than entry price")
        return v
