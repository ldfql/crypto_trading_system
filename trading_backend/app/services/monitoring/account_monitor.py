"""Account monitoring service for tracking balance and stage transitions."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Callable, Union, Tuple, Optional, List, Awaitable
import sys
import asyncio
import math
import logging
from fastapi.websockets import WebSocket, WebSocketDisconnect
from app.models.futures import FuturesConfig, MarginType
from app.models.enums import AccountStage, AccountStageTransition
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
        self.current_balance = Decimal("0")
        self.previous_balance = Decimal("0")
        self.current_stage = AccountStage.INITIAL
        self.stage_transition = AccountStageTransition.NO_CHANGE
        self.websocket = None  # Public attribute for WebSocket connection
        self._update_callbacks = []  # Private attribute for update callbacks
        self._initialize_with_balance(initial_balance)

    def _quantize_decimal(self, value: Decimal) -> Decimal:
        """Quantize decimal to 8 decimal places."""
        return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    def _initialize_with_balance(self, initial_balance: Decimal) -> None:
        """Initialize account with balance."""
        self.current_balance = self._quantize_decimal(initial_balance)
        self.previous_balance = self.current_balance
        self.stage_transition = AccountStageTransition.NO_CHANGE

    def _determine_stage(self, balance: Decimal) -> AccountStage:
        """Determine account stage based on balance thresholds."""
        if balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        thresholds = {
            AccountStage.INITIAL: Decimal("0"),
            AccountStage.GROWTH: Decimal("1000"),
            AccountStage.ADVANCED: Decimal("10000"),
            AccountStage.PROFESSIONAL: Decimal("1000000"),
            AccountStage.EXPERT: Decimal("100000000")
        }

        # Find the highest threshold that is less than or equal to the balance
        current_stage = AccountStage.INITIAL
        for stage, threshold in thresholds.items():
            if balance >= threshold:
                current_stage = stage
            else:
                break

        return current_stage

    async def validate_futures_config(self, config: Union[Dict[str, Any], FuturesConfig]) -> bool:
        """Validate futures configuration based on current account stage."""
        try:
            # Convert dict to FuturesConfig if needed
            if isinstance(config, dict):
                margin_type = config.get("margin_type", "cross").lower()
                position_size = Decimal(str(config["position_size"]))
                leverage = int(config["leverage"])

                # Create FuturesConfig object with account stage first
                futures_config = FuturesConfig(
                    leverage=leverage,
                    margin_type=MarginType.CROSS if margin_type == "cross" else MarginType.ISOLATED,
                    position_size=position_size,
                    max_position_size=Decimal(str(config.get("max_position_size", position_size))),
                    risk_level=Decimal(str(config.get("risk_level", "0.5"))),
                    account_stage=self.current_stage
                )
            else:
                futures_config = config
                futures_config.account_stage = self.current_stage

            # Validate leverage first
            max_leverage = futures_config.MAX_LEVERAGE[self.current_stage]
            if futures_config.leverage > max_leverage:
                raise ValueError(f"{self.current_stage.name.title()} stage max leverage is {max_leverage}x")

            # Then validate margin type for initial stage
            if self.current_stage == AccountStage.INITIAL and futures_config.margin_type != MarginType.CROSS:
                raise ValueError("Initial stage only supports cross margin")

            # Finally validate position size for initial stage
            if self.current_stage == AccountStage.INITIAL:
                max_allowed = self.current_balance * Decimal("0.1")
                if futures_config.position_size > max_allowed:
                    raise ValueError("Initial stage position size cannot exceed 10% of balance")

            return True
        except (KeyError, ValueError) as e:
            raise ValueError(str(e))

    async def update_balance(self, new_balance: Decimal) -> None:
        """Update account balance and determine stage transition."""
        if new_balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        self.previous_balance = self.current_balance
        self.current_balance = self._quantize_decimal(new_balance)
        previous_stage = self.current_stage

        # Determine new stage
        self.current_stage = self._determine_stage(self.current_balance)

        # Determine stage transition type
        if self.current_stage != previous_stage:
            stages = list(AccountStage)
            prev_idx = stages.index(previous_stage)
            curr_idx = stages.index(self.current_stage)

            if curr_idx > prev_idx:
                self.stage_transition = AccountStageTransition.UPGRADE
            else:
                self.stage_transition = AccountStageTransition.DOWNGRADE
        else:
            self.stage_transition = AccountStageTransition.NO_CHANGE

        # Send WebSocket update
        await self.send_balance_update()

        # Notify callbacks
        await self._notify_callbacks({
            "balance": str(self.current_balance),
            "stage": self.current_stage.name,
            "transition": self.stage_transition.value
        })

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
        thresholds = {
            AccountStage.INITIAL: Decimal("0"),
            AccountStage.GROWTH: Decimal("1000"),
            AccountStage.ADVANCED: Decimal("10000"),
            AccountStage.PROFESSIONAL: Decimal("1000000"),
            AccountStage.EXPERT: Decimal("100000000")
        }

        # Get current stage threshold and next stage threshold
        current_threshold = thresholds[self.current_stage]
        next_threshold = None

        stages = list(AccountStage)
        current_index = stages.index(self.current_stage)
        if current_index < len(stages) - 1:
            next_stage = stages[current_index + 1]
            next_threshold = thresholds[next_stage]

        # Calculate progress percentage
        if self.current_stage == AccountStage.EXPERT:
            # For expert stage, use a different calculation
            target = Decimal("1000000000")  # 10亿U
            progress_ratio = min(
                (self.current_balance - current_threshold) / (target - current_threshold),
                Decimal("1.0")
            )
            progress = (progress_ratio * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            remaining = max(target - self.current_balance, Decimal("0"))
        else:
            # For other stages
            stage_range = next_threshold - current_threshold if next_threshold else Decimal("0")
            progress_amount = self.current_balance - current_threshold
            if stage_range > 0:
                progress_ratio = min(progress_amount / stage_range, Decimal("1.0"))
                progress = (progress_ratio * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                progress = Decimal("0")
            remaining = max(next_threshold - self.current_balance, Decimal("0")) if next_threshold else Decimal("0")

        return progress, remaining

    async def send_balance_update(self) -> None:
        """Send balance update via WebSocket if available."""
        if self.websocket:
            stage_progress, remaining = self.get_stage_progress()
            update_data = {
                "type": "balance_update",
                "data": {
                    "balance": str(int(self.current_balance)) if self.current_balance == self.current_balance.to_integral()
                            else f"{float(self.current_balance):.2f}",
                    "stage": self.current_stage.name.upper(),
                    "progress": f"{float(stage_progress):.2f}",
                    "remaining": f"{float(remaining):.2f}"
                }
            }
            try:
                await self.websocket.send_json(update_data)
            except Exception as e:
                logger.error(f"Failed to send WebSocket update: {e}")
                # Don't re-raise as this is not critical

    async def monitor_balance_changes(self, websocket_or_callback: Union[WebSocket, Callable[[Dict[str, Any]], None]]) -> None:
        """Monitor balance changes and send updates through WebSocket or callback."""
        if isinstance(websocket_or_callback, WebSocket):
            # Store WebSocket connection
            self.websocket = websocket_or_callback
            try:
                # Send initial update
                await self.send_balance_update()
                # Keep connection alive and monitor for changes
                while True:
                    await asyncio.sleep(1)  # Prevent CPU overload
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket = None
        else:
            # Register callback function
            if not callable(websocket_or_callback):
                raise ValueError("Expected WebSocket or callable")
            self.register_update_callback(websocket_or_callback)
            try:
                # Send initial update through callback
                stage_progress, remaining = self.get_stage_progress()
                update_data = {
                    "balance": str(self.current_balance),
                    "stage": self.current_stage.name.upper(),
                    "progress": f"{stage_progress:.2f}",
                    "remaining": f"{float(remaining):.2f}"
                }
                await self._notify_callbacks(update_data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                self.remove_update_callback(websocket_or_callback)

    def register_update_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback for balance updates."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Remove a registered callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    async def _notify_callbacks(self, update_data: Dict[str, Any]) -> None:
        """Notify all registered callbacks with update data."""
        for callback in self._update_callbacks:
            try:
                await callback(update_data)
            except Exception as e:
                logger.error(f"Error in callback: {str(e)}")
