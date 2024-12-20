"""Test fixtures and configuration."""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.signals import TradingSignal
from app.models.futures import AccountStage, FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor

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
