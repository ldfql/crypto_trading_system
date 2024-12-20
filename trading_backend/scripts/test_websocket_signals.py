import asyncio
import json
from datetime import datetime, timedelta
import websockets
from websockets.exceptions import ConnectionClosedError

async def send_test_signals():
    uri = "ws://127.0.0.1:8000/ws/opportunities"
    try:
        async with websockets.connect(uri) as websocket:
            # Send metrics
            metrics = {
                "type": "metrics",
                "data": {
                    "accuracy": 0.85,
                    "signals_today": 5,
                    "market_sentiment": "bullish",
                    "average_confidence": 0.92
                }
            }
            await websocket.send(json.dumps(metrics))
            print("Sent metrics")

            # Wait for response
            response = await websocket.recv()
            print(f"Received response: {response}")
            await asyncio.sleep(1)

            # Send current signals
            current_time = datetime.utcnow()
            current_signals = {
                "type": "current_signals",
                "data": [
                    {
                        "id": 1,
                        "symbol": "BTC/USDT",
                        "signal_type": "long",
                        "timeframe": "4h",
                        "entry_price": 45000.0,
                        "take_profit": 47000.0,
                        "stop_loss": 44000.0,
                        "confidence": 0.85,
                        "created_at": current_time.isoformat(),
                        "market_conditions": {
                            "volume_24h": 1000000,
                            "volatility": 0.02,
                            "trend": "upward"
                        }
                    }
                ]
            }
            await websocket.send(json.dumps(current_signals))
            print("Sent current signals")

            # Wait for response
            response = await websocket.recv()
            print(f"Received response: {response}")
            await asyncio.sleep(1)

            # Send historical signals
            historical_time = current_time - timedelta(hours=12)
            historical_signals = {
                "type": "historical_signals",
                "data": [
                    {
                        "id": 2,
                        "symbol": "ETH/USDT",
                        "signal_type": "short",
                        "timeframe": "1h",
                        "entry_price": 2800.0,
                        "take_profit": 2600.0,
                        "stop_loss": 2900.0,
                        "confidence": 0.78,
                        "created_at": historical_time.isoformat(),
                        "market_conditions": {
                            "volume_24h": 500000,
                            "volatility": 0.015,
                            "trend": "downward"
                        }
                    }
                ]
            }
            await websocket.send(json.dumps(historical_signals))
            print("Sent historical signals")

            # Wait for response
            response = await websocket.recv()
            print(f"Received response: {response}")

    except ConnectionClosedError as e:
        print(f"WebSocket connection closed: {e}")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(send_test_signals())
