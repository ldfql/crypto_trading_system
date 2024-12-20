"""Models for futures trading configuration."""
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ValidationInfo, model_validator


class MarginType(str, Enum):
    """Margin type for futures trading."""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


class AccountStage(str, Enum):
    """Trading account stages based on balance."""
    MICRO = "micro"      # 100U - 1,000U
    SMALL = "small"      # 1,000U - 10,000U
    MEDIUM = "medium"    # 10,000U - 100,000U
    LARGE = "large"      # 100,000U - 1,000,000U
    MEGA = "mega"        # 1,000,000U+


class FuturesConfig(BaseModel):
    """Configuration for futures trading."""
    leverage: int = Field(
        default=20,
        ge=1,
        le=125,
        description="Leverage multiplier (1-125x)"
    )
    margin_type: MarginType = Field(
        default=MarginType.ISOLATED,
        description="Margin type (ISOLATED or CROSS)"
    )
    position_size: Decimal = Field(
        description="Position size in USDT"
    )
    max_position_size: Optional[Decimal] = Field(
        default=None,
        description="Maximum position size based on account balance"
    )
    risk_level: float = Field(
        default=0.02,
        ge=0.01,
        le=0.05,
        description="Risk level as percentage of account (1-5%)"
    )
    account_stage: AccountStage = Field(
        default=AccountStage.MICRO,
        description="Account stage based on balance"
    )

    @model_validator(mode='after')
    def validate_config(self) -> 'FuturesConfig':
        """Validate the entire configuration after all fields are set."""
        # Validate leverage based on account stage
        max_leverage = {
            AccountStage.MICRO: 20,   # Conservative for small accounts
            AccountStage.SMALL: 50,   # Moderate for growing accounts
            AccountStage.MEDIUM: 75,  # Higher for established accounts
            AccountStage.LARGE: 100,  # Advanced for large accounts
            AccountStage.MEGA: 125,   # Maximum for mega accounts
        }
        if self.leverage > max_leverage[self.account_stage]:
            raise ValueError(
                f"Maximum leverage for {self.account_stage.value} accounts is {max_leverage[self.account_stage]}x"
            )

        # Validate position size
        if self.max_position_size is not None and self.position_size > self.max_position_size:
            raise ValueError(
                f"Position size {self.position_size} exceeds maximum allowed size {self.max_position_size}"
            )

        # Validate minimum position size based on account stage
        min_sizes = {
            AccountStage.MICRO: Decimal("10"),    # Minimum 10 USDT for micro
            AccountStage.SMALL: Decimal("100"),   # Minimum 100 USDT for small
            AccountStage.MEDIUM: Decimal("1000"), # Minimum 1000 USDT for medium
            AccountStage.LARGE: Decimal("10000"), # Minimum 10000 USDT for large
            AccountStage.MEGA: Decimal("100000"), # Minimum 100000 USDT for mega
        }
        if self.position_size < min_sizes[self.account_stage]:
            raise ValueError(
                f"Minimum position size for {self.account_stage.value} accounts is {min_sizes[self.account_stage]} USDT"
            )

        return self


class FuturesPosition(BaseModel):
    """Model for futures trading position."""
    symbol: str = Field(description="Trading pair symbol")
    entry_price: Decimal = Field(description="Entry price")
    take_profit: Decimal = Field(description="Take profit price")
    stop_loss: Decimal = Field(description="Stop loss price")
    config: FuturesConfig = Field(description="Position configuration")

    @field_validator("take_profit")
    @classmethod
    def validate_take_profit(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        """Validate take profit price against entry price."""
        entry = info.data.get("entry_price")
        if entry is not None:
            if v <= entry:
                raise ValueError("Take profit must be higher than entry price")
        return v

    @field_validator("stop_loss")
    @classmethod
    def validate_stop_loss(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        """Validate stop loss price against entry price."""
        entry = info.data.get("entry_price")
        if entry is not None:
            if v >= entry:
                raise ValueError("Stop loss must be lower than entry price")
        return v
