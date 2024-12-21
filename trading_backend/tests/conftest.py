"""Test fixtures and configuration."""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, create_autospec, MagicMock
from fastapi import WebSocket

from app.database import Base
from app.models.signals import TradingSignal, AccountStage
from app.models.futures import FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.market_analysis.market_data_service import MarketDataService

@pytest.fixture
def db_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def db_session(db_engine):
    """Create database session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def account_monitor():
    """Create account monitor instance for testing."""
    return AccountMonitor(initial_balance=Decimal("1000"))

@pytest.fixture
def futures_config():
    """Create futures configuration for testing."""
    return FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100")
    )

@pytest.fixture
def trading_signal():
    """Create trading signal for testing."""
    return TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000"),
        take_profit=Decimal("55000"),
        stop_loss=Decimal("48000")
    )

@pytest.fixture
def mock_websocket():
    """Create mock websocket for testing."""
    mock = MagicMock(spec=WebSocket)
    mock.accept = AsyncMock()
    mock.receive_json = AsyncMock()
    mock.send_json = AsyncMock()
    mock.receive_text = AsyncMock()
    mock.send_text = AsyncMock()
    mock.close = AsyncMock()
    return mock

@pytest.fixture
def mock_market_data_service():
    """Create mock market data service for testing."""
    mock = MagicMock(spec=MarketDataService)
    mock.get_market_data = AsyncMock(return_value={
        "price": Decimal("50000"),
        "volume": Decimal("1000000"),
        "timestamp": "2024-01-01T00:00:00Z",
        "market_depth": {
            "bids": [(Decimal("49999"), Decimal("1.5")), (Decimal("49998"), Decimal("2.0"))],
            "asks": [(Decimal("50001"), Decimal("1.0")), (Decimal("50002"), Decimal("2.5"))]
        }
    })
    return mock

@pytest.fixture
def mock_account_monitor():
    """Create mock account monitor for testing."""
    mock = MagicMock(spec=AccountMonitor)
    mock.get_account_status = AsyncMock(return_value={
        "current_balance": Decimal("1000"),
        "current_stage": AccountStage.INITIAL.value,
        "max_leverage": 20,
        "progress": Decimal("50.0"),
        "remaining": Decimal("1000"),
        "margin_type": MarginType.CROSS.value,
        "recommended_position_size": Decimal("50"),
        "estimated_fees": Decimal("0.1")
    })
    mock.update_balance = AsyncMock()
    mock.get_stage_progress = AsyncMock(return_value=(Decimal("50.0"), Decimal("1000")))
    mock.get_max_leverage = AsyncMock(return_value=20)
    mock.validate_futures_config = AsyncMock(return_value=True)
    return mock
