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

    def __init__(self, initial_balance: Union[Decimal, str, float] = Decimal("100")):
        """Initialize account monitor with initial balance."""
        if isinstance(initial_balance, (str, float)):
            initial_balance = Decimal(str(initial_balance))

        if initial_balance <= 0:
            raise AccountMonitoringError("Initial balance must be positive")

        # Initialize with quantized balance
        self.current_balance = self._quantize_decimal(initial_balance)
        self.previous_balance = self.current_balance
        self.update_callbacks = []

        # Set initial stage based on balance
        self.current_stage = self._determine_stage(self.current_balance)
        self.previous_stage = self.current_stage
        self.stage_transition = AccountStageTransition.NO_CHANGE

    def _determine_stage(self, balance: Decimal) -> AccountStage:
        """Determine account stage based on balance."""
        # Quantize balance for consistent comparisons
        balance = self._quantize_decimal(balance)

        # Define stage thresholds
        thresholds = {
            AccountStage.EXPERT: Decimal("1000000"),      # 1M USDT
            AccountStage.PROFESSIONAL: Decimal("100000"),  # 100K USDT
            AccountStage.ADVANCED: Decimal("10000"),       # 10K USDT
            AccountStage.GROWTH: Decimal("1000"),         # 1K USDT
            AccountStage.INITIAL: Decimal("100")          # 100 USDT
        }

        # Determine stage based on balance thresholds
        for stage, threshold in thresholds.items():
            if balance >= threshold:
                return stage

        # Default to INITIAL stage if balance is below all thresholds
        return AccountStage.INITIAL

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

    async def update_balance(self, new_balance: Union[Decimal, str, float]) -> Dict[str, Any]:
        """Update account balance and determine stage transition."""
        if isinstance(new_balance, (str, float)):
            new_balance = Decimal(str(new_balance))

        if new_balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        # Update balances with quantized values
        self.previous_balance = self.current_balance
        self.current_balance = self._quantize_decimal(new_balance)

        # Update stages
        self.previous_stage = self.current_stage
        self.current_stage = self._determine_stage(self.current_balance)

        # Determine stage transition
        if self.current_stage > self.previous_stage:
            self.stage_transition = AccountStageTransition.UPGRADE
        elif self.current_stage < self.previous_stage:
            self.stage_transition = AccountStageTransition.DOWNGRADE
        else:
            self.stage_transition = AccountStageTransition.NO_CHANGE

        # Calculate stage progress
        progress, remaining = self.get_stage_progress()

        # Prepare update data
        update_data = {
            "type": "account_status",
            "data": {
                "current_balance": str(self.current_balance),
                "previous_balance": str(self.previous_balance),
                "current_stage": self.current_stage.value,
                "stage_transition": self.stage_transition.value,
                "progress": str(progress),
                "remaining": str(remaining)
            }
        }

        # Notify callbacks of update
        await self._notify_callbacks(update_data)
        return update_data

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
        # Define stage thresholds
        thresholds = {
            AccountStage.INITIAL: (Decimal("100"), Decimal("1000")),      # 100U - 1K
            AccountStage.GROWTH: (Decimal("1000"), Decimal("10000")),     # 1K - 10K
            AccountStage.ADVANCED: (Decimal("10000"), Decimal("100000")), # 10K - 100K
            AccountStage.PROFESSIONAL: (Decimal("100000"), Decimal("1000000")), # 100K - 1M
            AccountStage.EXPERT: (Decimal("1000000"), Decimal("100000000"))  # 1M - 100M (1亿)
        }

        current_balance = self._quantize_decimal(self.current_balance)
        current_stage = self.current_stage

        # Get current stage thresholds
        start_threshold, end_threshold = thresholds[current_stage]

        # Calculate progress percentage
        if current_stage == AccountStage.EXPERT:
            # For expert stage, calculate progress towards 1亿U (100M)
            total_range = end_threshold - start_threshold
            current_progress = current_balance - start_threshold
            progress = (current_progress / total_range) * Decimal("100")
            remaining = end_threshold - current_balance
        else:
            # For other stages, calculate progress towards next stage
            stage_range = end_threshold - start_threshold
            current_progress = current_balance - start_threshold
            progress = (current_progress / stage_range) * Decimal("100")
            remaining = end_threshold - current_balance

        # Ensure progress is between 0 and 100
        progress = max(Decimal("0"), min(Decimal("100"), progress))

        # Round progress to 2 decimal places
        progress = self._quantize_decimal(progress)
        remaining = self._quantize_decimal(remaining)

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
