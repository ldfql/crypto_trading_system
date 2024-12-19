from fastapi import APIRouter

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except Exception:
        await websocket.close()
