import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/opportunities"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                print(f"Received message: {json.dumps(data, indent=2)}")
            except asyncio.TimeoutError:
                print("No message received in 5 seconds")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
