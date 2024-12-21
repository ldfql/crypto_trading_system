```python
"""Notification service for trading signals."""
import asyncio
import logging
from typing import Set, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class SignalNotification(BaseModel):
    """Trading signal notification model."""
    pair: str
    entry_price: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    leverage: int = Field(gt=0)
    margin_type: str
    direction: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

class ValidationResult(BaseModel):
    """Validation result model."""
    is_valid: bool
    error: Optional[str] = None

class NotificationService:
    """Service for managing WebSocket notifications."""
    def __init__(self, cooldown_minutes: int = 40):
        """Initialize notification service."""
        self.active_clients: Dict[str, WebSocket] = {}
        self.client_last_disconnect: Dict[str, datetime] = {}
        self.cooldown_minutes = cooldown_minutes
        logger.info("Notification service initialized with %d minute cooldown", cooldown_minutes)

    async def register_client(self, client_id: str, websocket: WebSocket) -> ValidationResult:
        """Register a new WebSocket client."""
        try:
            if client_id in self.client_last_disconnect:
                last_disconnect = self.client_last_disconnect[client_id]
                cooldown_period = timedelta(minutes=self.cooldown_minutes)
                if datetime.now() - last_disconnect < cooldown_period:
                    remaining = cooldown_period - (datetime.now() - last_disconnect)
                    return ValidationResult(
                        is_valid=False,
                        error=f"Please wait {remaining.seconds // 60} minutes before reconnecting"
                    )

            await websocket.accept()
            self.active_clients[client_id] = websocket
            logger.info("Client %s registered successfully", client_id)
            return ValidationResult(is_valid=True)
        except Exception as e:
            logger.error("Error registering client %s: %s", client_id, str(e))
            return ValidationResult(is_valid=False, error=str(e))

    async def remove_client(self, client_id: str) -> None:
        """Remove a WebSocket client."""
        try:
            if client_id in self.active_clients:
                websocket = self.active_clients[client_id]
                if not websocket.client_state.DISCONNECTED:
                    await websocket.close()
                del self.active_clients[client_id]
                self.client_last_disconnect[client_id] = datetime.now()
                logger.info("Client %s removed successfully", client_id)
        except Exception as e:
            logger.error("Error removing client %s: %s", client_id, str(e))

    async def broadcast_notification(self, signal: SignalNotification) -> None:
        """Broadcast notification to all active clients."""
        notification_data = signal.dict()
        disconnected_clients = set()

        for client_id, websocket in self.active_clients.items():
            try:
                await websocket.send_json({
                    "type": "signal",
                    "data": notification_data
                })
                logger.debug("Notification sent to client %s", client_id)
            except WebSocketDisconnect:
                disconnected_clients.add(client_id)
                logger.info("Client %s disconnected during broadcast", client_id)
            except Exception as e:
                logger.error("Error sending notification to client %s: %s", client_id, str(e))
                disconnected_clients.add(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.remove_client(client_id)

    async def validate_signal(self, signal: Dict[str, Any]) -> ValidationResult:
        """Validate trading signal data."""
        try:
            required_fields = ["pair", "entry_price", "leverage", "margin_type", "direction"]
            missing_fields = [field for field in required_fields if field not in signal]

            if missing_fields:
                return ValidationResult(
                    is_valid=False,
                    error=f"Missing required fields: {', '.join(missing_fields)}"
                )

            if not isinstance(signal.get("leverage"), (int, float)) or signal["leverage"] <= 0:
                return ValidationResult(
                    is_valid=False,
                    error="Invalid leverage value"
                )

            if "confidence" in signal:
                confidence = float(signal["confidence"])
                if not 0 <= confidence <= 1:
                    return ValidationResult(
                        is_valid=False,
                        error="Confidence must be between 0 and 1"
                    )


            return ValidationResult(is_valid=True)
        except Exception as e:
            logger.error("Error validating signal: %s", str(e))
            return ValidationResult(is_valid=False, error=str(e))

    async def send_error(self, client_id: str, error: str) -> None:
        """Send error message to specific client."""
        try:
            if client_id in self.active_clients:
                websocket = self.active_clients[client_id]
                await websocket.send_json({
                    "type": "error",
                    "message": error
                })
        except Exception as e:
            logger.error("Error sending error message to client %s: %s", client_id, str(e))
```
