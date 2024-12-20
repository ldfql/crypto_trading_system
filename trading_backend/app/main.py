"""Main application module."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import websocket, trading, account

app = FastAPI(title="Crypto Trading System")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(websocket.router)
app.include_router(trading.router)
app.include_router(account.router)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
