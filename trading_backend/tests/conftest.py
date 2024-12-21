"""Test fixtures and configuration."""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket

from app.models.signals import TradingSignal
from app.models.enums import MarginType, TradingDirection, AccountStage
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.market_analysis.market_data_service import MarketDataService

# Use SQLite for testing with async support
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=True
    )

    async with engine.begin() as conn:
        await conn.run_sync(TradingSignal.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(TradingSignal.metadata.drop_all)
        await engine.dispose()

@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Create database session for testing."""
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture
def account_monitor():
    """Create mock account monitor."""
    return MagicMock(spec=AccountMonitor)

@pytest.fixture
def futures_config():
    """Create sample futures configuration."""
    return {
        "margin_type": MarginType.CROSS,
        "leverage": 10,
        "position_size": Decimal("0.1")
    }

@pytest.fixture
def trading_signal():
    """Create sample trading signal."""
    return TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85")
    )

@pytest.fixture
def mock_websocket():
    """Create mock websocket."""
    ws = MagicMock(spec=WebSocket)
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    return ws

@pytest.fixture
def mock_market_data_service():
    """Create mock market data service."""
    service = MagicMock(spec=MarketDataService)
    service.get_current_price = AsyncMock(return_value=Decimal("50000.00"))
    service.get_24h_volume = AsyncMock(return_value=Decimal("1000000.00"))
    service.get_order_book_depth = AsyncMock(return_value={
        "bids": [(Decimal("49900.00"), Decimal("1.0"))],
        "asks": [(Decimal("50100.00"), Decimal("1.0"))]
    })
    return service

@pytest.fixture
def mock_account_monitor():
    """Create mock account monitor."""
    monitor = MagicMock(spec=AccountMonitor)
    monitor.get_current_stage = AsyncMock(return_value=AccountStage.INITIAL)
    monitor.get_balance = AsyncMock(return_value=Decimal("1000.00"))
    monitor.get_unrealized_pnl = AsyncMock(return_value=Decimal("0.00"))
    monitor.get_margin_ratio = AsyncMock(return_value=Decimal("0.50"))
    monitor.get_position_value = AsyncMock(return_value=Decimal("5000.00"))
    monitor.get_available_margin = AsyncMock(return_value=Decimal("500.00"))
    return monitor
