"""WebSocket router for real-time account monitoring."""
from decimal import Decimal
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional

from app.services.monitoring.account_monitor import AccountMonitor
from app.models.futures import AccountStage, AccountStageTransition

router = APIRouter()
monitor = AccountMonitor()

@router.websocket("/account/ws/monitor")
async def websocket_account_monitor(websocket: WebSocket):
    """WebSocket endpoint for real-time account monitoring."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                balance = Decimal(data.get("balance", "0"))
                if balance <= 0:
                    await websocket.send_json({
                        "error": "Balance must be positive"
                    })
                    continue

                # Update account monitor
                transition = monitor.update_balance(balance)
                stage_progress, remaining = monitor.get_stage_progress()

                # Prepare response
                response = {
                    "current_balance": str(balance),
                    "current_stage": monitor.current_stage.value,
                    "previous_stage": monitor.previous_stage.value if monitor.previous_stage else None,
                    "stage_progress": str(stage_progress),
                    "remaining_to_next_stage": str(remaining),
                    "max_leverage": monitor.get_max_leverage(),
                    "transition": transition.value if transition else None
                }

                await websocket.send_json(response)

            except (ValueError, TypeError) as e:
                await websocket.send_json({
                    "error": f"Invalid balance format: {str(e)}"
                })
            except Exception as e:
                await websocket.send_json({
                    "error": f"Error processing request: {str(e)}"
                })

    except WebSocketDisconnect:
        pass  # Client disconnected
