"""WebSocket router for real-time account monitoring."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from decimal import Decimal
from typing import Dict, List
from ..services.monitoring.account_monitor import AccountMonitor

router = APIRouter()
connected_clients: List[WebSocket] = []

@router.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time account monitoring."""
    await websocket.accept()
    connected_clients.append(websocket)
    monitor = AccountMonitor()

    try:
        while True:
            data = await websocket.receive_json()
            balance = Decimal(data.get("balance", "0"))

            # Update account status
            monitor.update_balance(balance)

            # Get current trading parameters
            params = monitor.get_trading_parameters(Decimal("2"))  # Default 2% risk

            # Calculate stage progress
            progress, remaining = monitor.get_stage_progress()

            # Send response
            response = {
                "current_stage": params["account_stage"].value,
                "current_balance": str(balance),
                "max_leverage": params["leverage"],
                "margin_type": params["margin_type"].value,
                "stage_progress": str(progress),
                "remaining_to_next_stage": str(remaining),
                "position_size": str(params["position_size"]),
                "estimated_fees": str(params["estimated_fees"])
            }
            await websocket.send_json(response)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
        if websocket in connected_clients:
            connected_clients.remove(websocket)

@router.websocket("/ws/broadcast")
async def broadcast_endpoint(websocket: WebSocket):
    """WebSocket endpoint for broadcasting account updates."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Broadcast to all connected clients
            for client in connected_clients:
                if client.client_state.state.value == 1:  # Check if client is connected
                    await client.send_json(data)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
        if websocket in connected_clients:
            connected_clients.remove(websocket)
