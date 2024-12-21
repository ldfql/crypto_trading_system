from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

class MarginType(str, Enum):
    CROSS = "cross"
    ISOLATED = "isolated"

class FuturesConfig(BaseModel):
    leverage: int = Field(..., ge=1, le=125)
    margin_type: MarginType = Field(default=MarginType.CROSS)
    position_size: Decimal = Field(..., gt=Decimal('0'))
    max_position_size: Decimal = Field(..., gt=Decimal('0'))
    risk_level: Decimal = Field(..., ge=Decimal('0.1'), le=Decimal('1.0'))

    def _quantize_decimal(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)

    @model_validator(mode='after')
    def validate_all(self) -> 'FuturesConfig':
        position_size = self._quantize_decimal(self.position_size)
        max_position_size = self._quantize_decimal(self.max_position_size)
        risk_level = self._quantize_decimal(Decimal(str(self.risk_level)))

        if position_size > max_position_size:
            raise ValueError(f"Position size ({position_size}) cannot exceed max position size ({max_position_size})")

        # Validate leverage based on position size
        if self.leverage > 20 and position_size > Decimal('1000'):
            raise ValueError("High leverage (>20x) not allowed for position sizes over 1000U")

        self.position_size = position_size
        self.max_position_size = max_position_size
        self.risk_level = risk_level

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
