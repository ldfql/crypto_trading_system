from fastapi import FastAPI
from app.routers import websocket

app = FastAPI()
app.include_router(websocket.router)
