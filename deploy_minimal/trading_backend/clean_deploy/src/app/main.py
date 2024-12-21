"""Main application module."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.routers import websocket, trading, account, notification
from src.app.services.notification.notification_service import NotificationService

app = FastAPI(title="Crypto Trading System")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
notification_service = NotificationService()

# Include routers
app.include_router(websocket.router)
app.include_router(trading.router)
app.include_router(account.router)
app.include_router(notification.router)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
