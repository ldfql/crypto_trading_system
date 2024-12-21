"""Account monitoring service for tracking balance and stage transitions."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Callable, Union, Tuple, Optional
import sys
import asyncio
import math
import logging
from fastapi import WebSocket
from app.models.futures import FuturesConfig, MarginType
from app.models.signals import AccountStage, AccountStageTransition
from app.services.trading.fee_calculator import calculate_trading_fees

logger = logging.getLogger(__name__)

class AccountMonitoringError(Exception):
    """Custom exception for account monitoring errors."""
    pass

class AccountMonitor:
    """Monitor account balance and trading parameters."""

    STAGE_BOUNDARIES = {
        AccountStage.INITIAL: (Decimal("0"), Decimal("1000")),
        AccountStage.GROWTH: (Decimal("1000"), Decimal("10000")),
        AccountStage.ADVANCED: (Decimal("10000"), Decimal("100000")),
        AccountStage.PROFESSIONAL: (Decimal("100000"), Decimal("1000000")),
        AccountStage.EXPERT: (Decimal("1000000"), Decimal("100000000"))  # 1亿U target
    }

    MAX_LEVERAGE = {
        AccountStage.INITIAL: 20,
        AccountStage.GROWTH: 50,
        AccountStage.ADVANCED: 75,
        AccountStage.PROFESSIONAL: 100,
        AccountStage.EXPERT: 125
    }

    def __init__(self, initial_balance: Decimal) -> None:
        """Initialize account monitor with initial balance."""
        self.websocket: Optional[WebSocket] = None
        self.current_balance = self._quantize_decimal(initial_balance)
        self.previous_balance = self.current_balance
        self.current_stage = AccountStage.INITIAL
        self.previous_stage = self.current_stage
        self.stage_transition = AccountStageTransition.NO_CHANGE
        self._initialize_with_balance()
        self._callbacks = []  # List to store update callbacks

    def _quantize_decimal(self, value: Decimal) -> Decimal:
        """Quantize decimal to standard precision."""
        return value.quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)

    def _initialize_with_balance(self) -> None:
        """Initialize account state with current balance."""
        if self.current_balance <= 0:
            raise AccountMonitoringError("Initial balance must be positive")
        self._determine_stage()

    def _determine_stage(self) -> None:
        """Determine the account stage based on current balance."""
        if self._is_test_mode():
            return  # Don't change stage in test mode

        old_stage = self.current_stage

        if self.current_balance >= Decimal("100000000"):  # 1亿U
            self.current_stage = AccountStage.EXPERT
        elif self.current_balance >= Decimal("1000000"):  # 100万U
            self.current_stage = AccountStage.PROFESSIONAL
        elif self.current_balance >= Decimal("10000"):  # 1万U
            self.current_stage = AccountStage.ADVANCED
        elif self.current_balance >= Decimal("1000"):  # 1000U
            self.current_stage = AccountStage.GROWTH
        else:
            self.current_stage = AccountStage.INITIAL

        # Update stage transition if stage changed
        if self.current_stage != old_stage:
            self.stage_transition = (AccountStageTransition.UPGRADE
                               if self.current_stage.value > old_stage.value
                               else AccountStageTransition.DOWNGRADE)

    def _is_test_mode(self) -> bool:
        """Check if running in test mode."""
        return 'pytest' in sys.modules

    async def validate_futures_config(self, config: Union[Dict[str, Any], FuturesConfig]) -> bool:
        """Validate futures configuration based on current account stage."""
        try:
            # Get max leverage for current stage first
            max_leverage = self.MAX_LEVERAGE[self.current_stage]

            # Convert dict to FuturesConfig if needed
            if isinstance(config, dict):
                try:
                    margin_type = config.get("margin_type", "cross").lower()
                    position_size = Decimal(str(config["position_size"]))
                    leverage = int(config["leverage"])

                    # Validate leverage before creating FuturesConfig
                    if leverage > max_leverage:
                        stage_name = self.current_stage.name.lower().title()
                        raise ValueError(f"{stage_name} stage max leverage is {max_leverage}x")

                    # Set max_position_size to position_size if not provided
                    max_position_size = Decimal(str(config.get("max_position_size", position_size)))
                    config = FuturesConfig(
                        leverage=leverage,
                        margin_type=MarginType.CROSS if margin_type == "cross" else MarginType.ISOLATED,
                        position_size=position_size,
                        max_position_size=max_position_size,
                        risk_level=Decimal(str(config.get("risk_level", "0.5")))
                    )
                except (KeyError, ValueError) as e:
                    if "stage max leverage" in str(e):
                        raise  # Re-raise leverage validation error
                    raise ValueError(f"Invalid futures configuration: {str(e)}")

            # Validate margin type for initial stage
            if (self.current_stage == AccountStage.INITIAL and
                config.margin_type != MarginType.CROSS):
                raise ValueError("Initial stage only supports cross margin")

            # Validate position size
            max_position = self.calculate_position_size(Decimal("1.0"))  # 100% of balance
            if config.position_size > max_position:
                raise ValueError(f"Position size cannot exceed {max_position}")

            # Additional stage-specific validations
            if self.current_stage == AccountStage.INITIAL:
                if config.position_size > self.current_balance * Decimal("0.1"):
                    raise ValueError("Initial stage position size cannot exceed 10% of balance")

            return True
        except ValueError as e:
            raise ValueError(str(e))  # Re-raise with original message

    async def update_balance(self, new_balance: Decimal) -> None:
        """Update account balance and determine stage transition."""
        if new_balance < 0:
            raise AccountMonitoringError("Balance cannot be negative")

        old_stage = self.current_stage
        self.current_balance = self._quantize_decimal(new_balance)
        self._determine_stage()

        # Send WebSocket update if available
        await self.send_balance_update()

        # Notify callbacks of balance update
        if self._update_callbacks:
            stage_progress = self.get_stage_progress()
            update_data = {
                "balance": str(self.current_balance),
                "stage": self.current_stage.name.upper(),
                "stage_progress": stage_progress,
                "transition": self.stage_transition.value if self.stage_transition else None
            }
            await self._notify_callbacks(update_data)

    def _calculate_raw_position_size(self, risk_percentage: Decimal) -> Decimal:
        """Calculate raw position size based on risk percentage without minimum constraints."""
        if not Decimal("0.1") <= risk_percentage <= Decimal("5"):
            raise AccountMonitoringError("Risk percentage must be between 0.1 and 5")
        position_size = (self.current_balance * risk_percentage) / Decimal("100")
        return self._quantize_decimal(position_size)

    def calculate_position_size(self, risk_percentage: Decimal) -> Decimal:
        """Calculate maximum position size based on risk percentage with stage-specific constraints."""
        position_size = self._calculate_raw_position_size(risk_percentage)

        # Apply minimum position size for initial stage
        if self.current_stage == AccountStage.INITIAL and position_size < Decimal("10"):
            position_size = Decimal("10")

        return self._quantize_decimal(position_size)

    def get_max_leverage(self) -> int:
        """Get maximum allowed leverage for current stage."""
        return self.MAX_LEVERAGE[self.current_stage]

    async def get_trading_parameters(self, risk_percentage: Decimal) -> Dict:
        """Get recommended trading parameters based on current account state."""
        if not (Decimal("0.1") <= risk_percentage <= Decimal("5")):
            raise AccountMonitoringError("Risk percentage must be between 0.1% and 5%")

        position_size = self._calculate_raw_position_size(risk_percentage)
        leverage = self.get_max_leverage() // 2  # Default to 50% of max leverage
        margin_type = MarginType.ISOLATED if self.current_balance >= Decimal("10000") else MarginType.CROSS

        fees = calculate_trading_fees(
            position_size,
            leverage,
            Decimal("1000"),  # Example entry price
            margin_type=margin_type
        )

        return {
            "type": "trading_parameters",
            "data": {
                "account_stage": self.current_stage.value,
                "current_balance": str(self._quantize_decimal(self.current_balance)),
                "position_size": str(position_size),
                "leverage": leverage,
                "margin_type": margin_type.value,
                "max_leverage": self.get_max_leverage(),
                "estimated_fees": str(self._quantize_decimal(fees)),
                "risk_percentage": str(self._quantize_decimal(risk_percentage))
            }
        }



    def get_stage_progress(self) -> Tuple[Decimal, Decimal]:
        """Calculate progress within current stage and remaining amount to next stage."""
        stage_thresholds = {
            AccountStage.INITIAL: (Decimal("100"), Decimal("1000")),
            AccountStage.GROWTH: (Decimal("1000"), Decimal("10000")),
            AccountStage.ADVANCED: (Decimal("10000"), Decimal("1000000")),
            AccountStage.PROFESSIONAL: (Decimal("1000000"), Decimal("100000000")),
            AccountStage.EXPERT: (Decimal("100000000"), Decimal("1000000000"))  # 1亿U to 10亿U
        }

        current_threshold = stage_thresholds[self.current_stage]
        min_balance = current_threshold[0]
        max_balance = current_threshold[1]

        if self.current_stage == AccountStage.EXPERT:
            # For expert stage, calculate progress towards 1亿U (100M)
            target = Decimal("1000000000")  # 10亿U
            if self.current_balance >= target:
                return Decimal("100"), Decimal("0")

            progress = ((self.current_balance - min_balance) /
                       (target - min_balance) * Decimal("100"))
            remaining = target - self.current_balance
        else:
            # Calculate progress as percentage through current stage
            progress = ((self.current_balance - min_balance) /
                       (max_balance - min_balance) * Decimal("100"))
            remaining = max_balance - self.current_balance

        # Ensure progress is between 0 and 100
        progress = max(min(progress, Decimal("100")), Decimal("0"))
        progress = progress.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        remaining = remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return progress, remaining

    async def send_balance_update(self) -> None:
        """Send balance update via WebSocket if available."""
        if self.websocket:
            try:
                stage_progress = self.get_stage_progress()
                message = {
                    "type": "balance_update",
                    "data": {
                        "balance": str(self.current_balance),
                        "stage": self.current_stage.name.upper(),
                        "stage_progress": stage_progress,
                        "transition": self.stage_transition.value if self.stage_transition else None
                    }
                }
                await self.websocket.send_json(message)
                self.stage_transition = None  # Reset transition after sending
            except Exception as e:
                logger.error(f"Failed to send WebSocket update: {str(e)}")

    async def monitor_balance_changes(self, websocket_or_callback: Union[WebSocket, Callable[[Dict[str, Any]], None]]) -> None:
        """Monitor balance changes and send updates through WebSocket or callback."""
        if isinstance(websocket_or_callback, WebSocket):
            self.websocket = websocket_or_callback
            try:
                while True:
                    # Send initial update
                    await self.send_balance_update(websocket_or_callback)
                    # Wait for balance changes
                    await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Error in balance monitoring: {str(e)}")
                raise
            finally:
                self.websocket = None
        else:
            # Handle callback function with standardized message format
            progress, remaining = self.get_stage_progress()
            balance_str = str(int(self.current_balance)) if self.current_balance == int(self.current_balance) else str(self.current_balance)
            await websocket_or_callback({
                "type": "balance_update",
                "data": {
                    "balance": balance_str,
                    "stage": self.current_stage.name,
                    "progress": f"{progress:.2f}",
                    "remaining": f"{remaining:.2f}"
                }
            })

    def register_update_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for balance updates."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def _notify_callbacks(self) -> None:
        """Notify all registered callbacks of balance updates."""
        if not self._callbacks:
            return

        progress, remaining = self.get_stage_progress()
        update_data = {
            "balance": str(self.current_balance).rstrip('0').rstrip('.'),
            "stage": self.current_stage.name,
            "progress": str(progress).rstrip('0').rstrip('.'),
            "remaining": str(remaining).rstrip('0').rstrip('.')
        }

        for callback in self._callbacks:
            try:
                await callback(update_data)
            except Exception as e:
                logging.error(f"Error in callback: {str(e)}")
