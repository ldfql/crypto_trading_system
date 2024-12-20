from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from app.services.analysis.prediction_analyzer import PredictionAnalyzer
from app.dependencies import get_prediction_analyzer
from datetime import datetime
from typing import Dict, Any, List
import asyncio

router = APIRouter()

@router.websocket("/ws/opportunities")
async def websocket_endpoint(
    websocket: WebSocket,
    analyzer: PredictionAnalyzer = Depends(get_prediction_analyzer)
):
    """WebSocket endpoint for real-time trading opportunities."""
    await websocket.accept()

    try:
        # Send initial opportunities
        try:
            opportunities = await analyzer.find_best_opportunities()
            if not isinstance(opportunities, list):
                opportunities = []

            message = {
                "type": "opportunities",
                "timestamp": datetime.utcnow().isoformat(),
                "data": opportunities
            }
            await websocket.send_json(message)
        except Exception as e:
            error_message = {
                "type": "error",
                "message": str(e)
            }
            await websocket.send_json(error_message)
            await websocket.close(code=1000, reason=str(e))
            return

        # Handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
                    continue

                # Send updated opportunities
                opportunities = await analyzer.find_best_opportunities()
                if not isinstance(opportunities, list):
                    opportunities = []

                message = {
                    "type": "opportunities",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": opportunities
                }
                await websocket.send_json(message)

            except WebSocketDisconnect:
                break
            except Exception as e:
                error_message = {
                    "type": "error",
                    "message": str(e)
                }
                await websocket.send_json(error_message)
                await websocket.close(code=1000, reason=str(e))
                return

    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except:
            pass
