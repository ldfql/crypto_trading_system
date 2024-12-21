"""WebSocket endpoints for real-time account monitoring."""
from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter
from typing import Dict, Any, Optional
import json
import logging
import asyncio
from decimal import Decimal

from src.app.services.monitoring.account_monitor import AccountMonitor
from src.app.dependencies import get_account_monitor, get_market_data_service
from src.app.services.market_analysis.market_data_service import MarketDataService
from src.app.models.enums import AccountStage, AccountStageTransition

router = APIRouter()
logger = logging.getLogger(__name__)

async def handle_account_monitoring(
    websocket: WebSocket,
    account_monitor: AccountMonitor,
    data: dict
) -> None:
    """Handle account monitoring subscription and updates."""
    try:
        if "data" in data and "balance" in data["data"]:
            new_balance = Decimal(str(data["data"]["balance"]))
            # Update balance and get status
            update_data = await account_monitor.update_balance(new_balance)
            # Send update through WebSocket
            await websocket.send_json(update_data)
        else:
            # Send initial account status
            status = await account_monitor.get_account_status()
            await websocket.send_json(status)
    except Exception as e:
        logger.error(f"Error in account monitoring: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

async def handle_market_data(
    websocket: WebSocket,
    market_data_service: MarketDataService,
    data: dict
) -> None:
    """Handle market data subscription and updates."""
    try:
        market_data = await market_data_service.get_market_data()
        await websocket.send_json({
            "type": "market_data",
            "data": market_data
        })
    except Exception as e:
        logger.error(f"Error in market data handling: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    account_monitor: AccountMonitor = Depends(get_account_monitor),
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Main WebSocket endpoint for real-time monitoring."""
    await websocket.accept()
    subscriptions = set()

    try:
        # Send initial account status
        progress, remaining = account_monitor.get_stage_progress()
        await websocket.send_json({
            "type": "account_status",
            "data": {
                "current_balance": str(account_monitor.current_balance),
                "current_stage": account_monitor.current_stage.value,
                "stage_progress": float(progress),
                "remaining_to_next_stage": str(remaining) if remaining > 0 else None,
                "max_leverage": account_monitor.get_max_leverage(),
                "stage_transition": account_monitor.stage_transition.value
            }
        })

        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "subscribe":
                    channel = data.get("channel")
                    if channel == "account_monitoring":
                        await handle_account_monitoring(websocket, account_monitor, {"type": "initial"})
                        subscriptions.add(channel)
                    elif channel == "market_data":
                        await handle_market_data(websocket, market_data_service, data)
                        subscriptions.add(channel)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Invalid subscription channel: {channel}"
                        })

                elif msg_type == "update":
                    if "account_monitoring" in subscriptions:
                        await handle_account_monitoring(websocket, account_monitor, data)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Not subscribed to account monitoring"
                        })

                elif msg_type == "close":
                    await websocket.close()
                    break

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        if not websocket.client_state.DISCONNECTED:
            await websocket.close()
