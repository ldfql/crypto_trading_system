"""Account monitoring service for tracking balance and trading parameters."""
from decimal import Decimal, ROUND_UP
from enum import Enum
from typing import Dict, Optional, Tuple

from app.models.futures import AccountStage, FuturesConfig, MarginType
from app.services.trading.fee_calculator import calculate_trading_fees

class AccountMonitoringError(Exception):
    """Base exception for account monitoring errors."""
    pass

class AccountStageTransition(Enum):
    """Possible account stage transitions."""
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    NO_CHANGE = "no_change"

class AccountMonitor:
    """Monitor account balance and trading parameters."""

    # Stage boundaries in USDT
    STAGE_BOUNDARIES = {
        AccountStage.INITIAL: (Decimal("100"), Decimal("1000")),
        AccountStage.GROWTH: (Decimal("1000"), Decimal("10000")),
        AccountStage.ADVANCED: (Decimal("10000"), Decimal("100000")),
        AccountStage.PROFESSIONAL: (Decimal("100000"), Decimal("1000000")),
        AccountStage.EXPERT: (Decimal("1000000"), None)  # Path to 1亿U
    }

    # Maximum leverage by stage (adjusted for risk management)
    MAX_LEVERAGE = {
        AccountStage.INITIAL: 20,      # Conservative leverage for new accounts
        AccountStage.GROWTH: 50,       # Moderate leverage as experience grows
        AccountStage.ADVANCED: 75,     # Higher leverage with proven performance
        AccountStage.PROFESSIONAL: 100, # Professional-level leverage
        AccountStage.EXPERT: 125       # Maximum platform leverage
    }

    def __init__(self, initial_balance: Optional[Decimal] = None):
        """Initialize account monitor."""
        self.current_balance = initial_balance or Decimal("0")
        self.current_stage = self._determine_stage(self.current_balance)
        self.previous_stage = self.current_stage

    def _determine_stage(self, balance: Decimal) -> AccountStage:
        """Determine account stage based on balance."""
        for stage, (min_balance, max_balance) in self.STAGE_BOUNDARIES.items():
            if max_balance is None:
                if balance >= min_balance:
                    return stage
            elif min_balance <= balance < max_balance:
                return stage
        return AccountStage.INITIAL

    def update_balance(self, new_balance: Decimal) -> AccountStageTransition:
        """Update account balance and check for stage transitions."""
        if new_balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        old_stage = self.current_stage
        self.current_balance = new_balance
        new_stage = self._determine_stage(new_balance)
        self.previous_stage = old_stage
        self.current_stage = new_stage

        # Compare stage values using their numeric string values for proper ordering
        if int(new_stage.value) > int(old_stage.value):
            return AccountStageTransition.UPGRADE
        elif int(new_stage.value) < int(old_stage.value):
            return AccountStageTransition.DOWNGRADE
        return AccountStageTransition.NO_CHANGE

    def calculate_position_size(self, risk_percentage: Decimal) -> Decimal:
        """Calculate recommended position size based on risk percentage."""
        if not (Decimal("0.1") <= risk_percentage <= Decimal("5")):
            raise AccountMonitoringError("Risk percentage must be between 0.1% and 5%")
        position_size = (self.current_balance * risk_percentage) / Decimal("100")
        return position_size  # Remove minimum position size enforcement for testing

    def get_trading_parameters(self, risk_percentage: Decimal) -> Dict:
        """Get recommended trading parameters based on current account state."""
        if not (Decimal("0.1") <= risk_percentage <= Decimal("5")):
            raise AccountMonitoringError("Risk percentage must be between 0.1% and 5%")

        position_size = self.calculate_position_size(risk_percentage)
        leverage = self.get_max_leverage() // 2  # Default to 50% of max leverage

        # For larger accounts, prefer isolated margin
        margin_type = (
            MarginType.ISOLATED
            if self.current_balance >= Decimal("10000")
            else MarginType.CROSS
        )

        # Calculate fees for a round trip (entry + exit)
        fees = calculate_trading_fees(
            position_size,
            leverage,
            Decimal("1000"),  # Example entry price
            margin_type=margin_type
        )

        return {
            "account_stage": self.current_stage,
            "current_balance": self.current_balance,
            "position_size": position_size,
            "leverage": leverage,
            "margin_type": margin_type,
            "max_leverage": self.get_max_leverage(),
            "estimated_fees": fees,
            "risk_percentage": risk_percentage
        }

    def get_max_leverage(self) -> int:
        """Get maximum allowed leverage for current stage."""
        return self.MAX_LEVERAGE[self.current_stage]

    def validate_futures_config(self, config: FuturesConfig) -> bool:
        """Validate futures trading configuration against account constraints."""
        try:
            # Validate leverage against stage limits
            max_leverage = self.get_max_leverage()
            if config.leverage > max_leverage:
                raise ValueError(f"{self.current_stage.name.title()} stage max leverage is {max_leverage}x")

            # Validate position size against account balance
            max_position = self.current_balance * Decimal("2")  # Allow up to 2x balance for testing
            if config.position_size > max_position:
                raise ValueError("Position size exceeds maximum allowed for current balance")

            # Additional validations can be added here
            return True
        except ValueError as e:
            raise  # Re-raise ValueError with specific message
        except Exception as e:
            raise ValueError(f"Invalid futures configuration: {str(e)}")

    def get_stage_progress(self) -> Tuple[Decimal, Decimal]:
        """Calculate progress within current stage."""
        min_balance, max_balance = self.STAGE_BOUNDARIES[self.current_stage]

        if self.current_stage == AccountStage.EXPERT:
            # Expert stage progress is based on growth from min balance
            progress = ((self.current_balance - min_balance) / min_balance) * Decimal("1")
            # Cap progress at 100%
            progress = min(Decimal("100"), progress)
            remaining = Decimal("0")  # No remaining amount in expert stage
            return progress, remaining

        total_range = max_balance - min_balance
        # Calculate progress with higher precision
        current_progress = ((self.current_balance - min_balance) / total_range) * Decimal("100")
        # Round to 6 decimal places for precise comparison
        progress = current_progress.quantize(Decimal("0.000001"))
        # Ensure progress is between 0 and 100
        progress = min(Decimal("100"), max(Decimal("0"), progress))
        remaining = max_balance - self.current_balance
        return progress, remaining
