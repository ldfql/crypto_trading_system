"""Account monitoring service for tracking balance and stage transitions."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Callable, Union, Tuple, Optional, List, Awaitable
import sys
import asyncio
import math
import logging
from datetime import datetime, timezone, UTC
from fastapi.websockets import WebSocket, WebSocketDisconnect
from src.app.models.futures import FuturesConfig
from src.app.models.enums import AccountStage, AccountStageTransition, MarginType
from src.app.services.trading.fee_calculator import calculate_trading_fees

class WebSocketError(Exception):
    """Exception raised for WebSocket-related errors."""

logger = logging.getLogger(__name__)

class AccountMonitoringError(Exception):
    """Custom exception for account monitoring errors."""
    pass

class AccountMonitor:
    """Monitor account balance and trading parameters."""

    STAGE_BOUNDARIES = {
        AccountStage.INITIAL: (Decimal("0"), Decimal("999.99999999")),  # Initial stage up to but not including 1000
        AccountStage.BEGINNER: (Decimal("1000"), Decimal("9999.99999999")),  # Beginner stage from 1000 up to but not including 10000
        AccountStage.INTERMEDIATE: (Decimal("10000"), Decimal("99999.99999999")),  # Intermediate stage from 10000 up to but not including 100000
        AccountStage.ADVANCED: (Decimal("100000"), Decimal("999999.99999999")),  # Advanced stage from 100000 up to but not including 1M
        AccountStage.PROFESSIONAL: (Decimal("1000000"), Decimal("9999999.99999999")),  # Professional stage from 1M up to but not including 10M
        AccountStage.EXPERT: (Decimal("10000000"), None)  # Expert stage from 10M onwards
    }

    MAX_LEVERAGE = {
        AccountStage.INITIAL: 15,
        AccountStage.BEGINNER: 15,
        AccountStage.INTERMEDIATE: 12,
        AccountStage.ADVANCED: 10,
        AccountStage.PROFESSIONAL: 5,
        AccountStage.EXPERT: 3
    }

    # Define stage order for transitions
    STAGE_ORDER = [
        AccountStage.INITIAL,
        AccountStage.BEGINNER,
        AccountStage.INTERMEDIATE,
        AccountStage.ADVANCED,
        AccountStage.PROFESSIONAL,
        AccountStage.EXPERT
    ]

    def _quantize_decimal(self, value: Decimal) -> Decimal:
        """Quantize decimal to 8 decimal places."""
        return value.quantize(Decimal("0.00000001"))

    def __init__(self, initial_balance: Decimal):
        """Initialize account monitor with initial balance."""
        self.current_balance = self._quantize_decimal(initial_balance)
        self.previous_stage = AccountStage.INITIAL
        self.stage_transition = AccountStageTransition.NO_CHANGE
        self.websocket: Optional[WebSocket] = None
        self.update_callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []

        # Validate initial balance
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative")

        self.current_stage = self._determine_stage(self.current_balance)

    def _determine_stage(self, balance: Optional[Decimal] = None) -> AccountStage:
        """Determine account stage based on current balance."""
        if balance is None:
            balance = self.current_balance

        if balance < 0:
            raise AccountMonitoringError("Account balance cannot be negative")

        # Ensure we're using exact decimal comparison
        balance = self._quantize_decimal(balance)

        # Check stages in order from lowest to highest
        for stage in self.STAGE_ORDER:
            min_balance, max_balance = self.STAGE_BOUNDARIES[stage]
            min_balance = self._quantize_decimal(min_balance)

            if max_balance is not None:
                max_balance = self._quantize_decimal(max_balance)
                if min_balance <= balance <= max_balance:
                    return stage
            else:  # Expert stage (no upper bound)
                if min_balance <= balance:
                    return stage

        # This should never happen given our stage boundaries
        raise AccountMonitoringError("Could not determine account stage")

    async def validate_futures_config(self, config: FuturesConfig) -> None:
        """Validate futures trading configuration based on account stage."""
        if not config:
            raise AccountMonitoringError("Futures configuration is required")

        # First validate margin type is valid
        if not isinstance(config.margin_type, MarginType) or config.margin_type is None:
            raise AccountMonitoringError("Invalid margin type")

        # Validate leverage limits for current stage
        max_leverage = self.get_max_leverage()
        if config.leverage > max_leverage:
            raise AccountMonitoringError(
                f"Maximum leverage {max_leverage} exceeded for account stage {self.current_stage}"
            )

        # Validate risk levels based on stage
        if self.current_stage == AccountStage.EXPERT:
            if config.risk_level < Decimal("0.1") or config.risk_level > Decimal("0.15"):
                raise AccountMonitoringError("Expert stage risk level must be between 0.1 and 0.15")
        else:
            if config.risk_level < Decimal("0.1") or config.risk_level > Decimal("5"):
                raise AccountMonitoringError("Risk level must be between 0.1% and 5%")

        # Validate stage-specific margin type constraints
        if self.current_stage == AccountStage.INITIAL and config.margin_type != MarginType.CROSS:
            raise AccountMonitoringError("Initial stage only supports cross margin")

        # Validate position size
        min_position_size = Decimal("10") if self.current_stage == AccountStage.INITIAL else Decimal("0")
        if config.position_size < min_position_size:
            raise AccountMonitoringError(
                f"Minimum position size of {min_position_size} required for {self.current_stage} stage"
            )

        # Validate max position size based on current balance
        max_position_size = self.current_balance * Decimal("0.95")  # 95% of balance
        if config.position_size > max_position_size:
            raise AccountMonitoringError(
                f"Position size ({config.position_size}) cannot exceed 95% of current balance ({max_position_size})"
            )

        # Basic validation passed, now validate the config itself
        try:
            config.validate()
        except ValueError as e:
            raise AccountMonitoringError(str(e))

    async def update_balance(self, new_balance: Union[Decimal, str, float]) -> Dict[str, Any]:
        """Update account balance and determine stage transition."""
        # Convert input to Decimal if needed
        if isinstance(new_balance, str):
            new_balance = Decimal(new_balance)
        elif isinstance(new_balance, float):
            new_balance = Decimal(str(new_balance))

        # Validate new balance
        if new_balance < 0:
            raise AccountMonitoringError("Balance cannot be negative")

        # Store previous state
        previous_balance = self.current_balance
        previous_stage = self.current_stage

        # Update balance and determine new stage
        self.current_balance = self._quantize_decimal(new_balance)
        new_stage = self._determine_stage(self.current_balance)

        # Determine stage transition
        if new_stage == previous_stage:
            self.stage_transition = AccountStageTransition.NO_CHANGE
        elif self.STAGE_ORDER.index(new_stage) > self.STAGE_ORDER.index(previous_stage):
            self.stage_transition = AccountStageTransition.UPGRADE
        else:
            self.stage_transition = AccountStageTransition.DOWNGRADE

        self.current_stage = new_stage

        # Prepare update data
        update_data = {
            "previous_balance": str(previous_balance),
            "current_balance": str(self.current_balance),
            "previous_stage": previous_stage.value,
            "current_stage": self.current_stage.value,
            "stage_transition": self.stage_transition.value
        }

        # Send WebSocket update if available
        await self.send_balance_update()

        # Notify callbacks
        await self._notify_callbacks(update_data)

        return update_data

    def _calculate_raw_position_size(self, risk_percentage: Decimal) -> Decimal:
        """Calculate raw position size based on risk percentage."""
        if risk_percentage < Decimal("0.1") or risk_percentage > Decimal("5"):
            raise AccountMonitoringError("Risk percentage must be between 0.1% and 5%")

        # Calculate position size based on risk percentage
        position_size = self.current_balance * (risk_percentage / Decimal("100"))
        return self._quantize_decimal(position_size)

    def calculate_position_size(self, risk_percentage: Decimal) -> Decimal:
        """Calculate recommended position size based on risk percentage."""
        if risk_percentage < Decimal("0.1") or risk_percentage > Decimal("5"):
            raise AccountMonitoringError("Risk percentage must be between 0.1% and 5%")

        # For INITIAL stage, always return minimum position size of 10
        if self.current_stage == AccountStage.INITIAL:
            return self._quantize_decimal(Decimal("10"))

        # For other stages, calculate based on risk percentage
        raw_size = self._calculate_raw_position_size(risk_percentage)
        return self._quantize_decimal(raw_size)

    def get_max_leverage(self) -> int:
        """Get maximum allowed leverage based on account stage."""
        return self.MAX_LEVERAGE[self.current_stage]

    async def get_trading_parameters(self, risk_percentage: Decimal) -> Dict:
        """Get recommended trading parameters based on current account state."""
        if risk_percentage < Decimal("0.1") or risk_percentage > Decimal("5"):
            raise AccountMonitoringError("Risk percentage must be between 0.1% and 5%")

        position_size = self.calculate_position_size(risk_percentage)
        max_leverage = self.get_max_leverage()

        # Get current stage and progress
        stage_progress = self.get_stage_progress()

        # Build response
        return {
            "type": "trading_parameters",
            "data": {
                "account_stage": self.current_stage.value,
                "current_balance": str(self.current_balance),
                "stage_progress": str(stage_progress),
                "position_size": str(position_size),
                "max_leverage": max_leverage,
                "margin_type": MarginType.CROSS.value,  # Default to CROSS margin
                "risk_percentage": str(risk_percentage)
            }
        }


    def get_stage_progress(self) -> Decimal:
        """Calculate progress within current stage as decimal between 0 and 1."""
        if self.current_stage == AccountStage.EXPERT:
            # Expert stage uses specific milestones
            milestones = [
                (Decimal("10000000"), Decimal("0.00")),  # Start of expert stage
                (Decimal("32500000"), Decimal("0.25")),  # 25% through
                (Decimal("55000000"), Decimal("0.50")),  # 50% through
                (Decimal("77500000"), Decimal("0.75")),  # 75% through
                (Decimal("100000000"), Decimal("1.00"))  # Target reached (1亿U)
            ]

            # If balance is below first milestone or at first milestone, return 0%
            if self.current_balance <= milestones[0][0]:
                return Decimal("0")
            # If balance is at or above max milestone, return 100%
            if self.current_balance >= milestones[-1][0]:
                return Decimal("1")

            # Find the appropriate milestone range and interpolate
            for i in range(len(milestones) - 1):
                lower_balance, lower_progress = milestones[i]
                upper_balance, upper_progress = milestones[i + 1]
                if lower_balance <= self.current_balance < upper_balance:
                    # Linear interpolation between milestones
                    progress_range = upper_progress - lower_progress
                    balance_range = upper_balance - lower_balance
                    progress = lower_progress + (
                        (self.current_balance - lower_balance) / balance_range * progress_range
                    )
                    return self._quantize_decimal(progress)

        # For other stages, calculate linear progress within stage boundaries
        stage_bounds = self.STAGE_BOUNDARIES[self.current_stage]
        min_balance = stage_bounds[0]
        max_balance = stage_bounds[1]

        if self.current_balance <= min_balance:
            return Decimal("0")
        if self.current_balance >= max_balance:
            return Decimal("1")

        # Calculate linear progress
        progress = (self.current_balance - min_balance) / (max_balance - min_balance)
        return self._quantize_decimal(progress)

    async def send_balance_update(self) -> None:
        """Send balance update through WebSocket if available."""
        if not self.websocket:
            return

        try:
            stage_progress = self.get_stage_progress()
            update_data = {
                "type": "balance_update",
                "data": {
                    "balance": str(self.current_balance),
                    "stage": self.current_stage.value,
                    "stage_progress": str(stage_progress),
                    "stage_transition": self.stage_transition.value,
                    "max_leverage": self.get_max_leverage(),
                    "timestamp": datetime.now(UTC).isoformat()
                }
            }
            await self.websocket.send_json(update_data)
        except WebSocketDisconnect:
            logger.warning("WebSocket disconnected during balance update")
            self.websocket = None  # Clear disconnected websocket
        except Exception as e:
            logger.error(f"Error sending balance update: {str(e)}")

    async def monitor_balance_changes(self, websocket: WebSocket) -> None:
        """Monitor balance changes and send updates through WebSocket."""
        try:
            while True:
                update_data = {
                    "type": "real_time_update",
                    "data": {
                        "balance": str(self.current_balance).rstrip('0').rstrip('.'),
                        "stage": self.current_stage.value,
                        "stage_progress": str(self.get_stage_progress()[0]).rstrip('0').rstrip('.'),
                        "max_leverage": self.get_max_leverage(),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
                await websocket.send_json(update_data)
                await asyncio.sleep(5)  # Update every 5 seconds
        except WebSocketDisconnect:
            logger.warning("WebSocket disconnected during monitoring")
        except Exception as e:
            logger.error(f"Error in balance monitoring: {e}")

    def register_update_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback for balance updates."""
        self.update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Remove a registered callback."""
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)

    async def _notify_callbacks(self, update_data: Dict[str, Any]) -> None:
        """Notify all registered callbacks with update data."""
        for callback in self.update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update_data)
                else:
                    callback(update_data)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
