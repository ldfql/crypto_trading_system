"""Test cases for signal repository."""
import pytest
from decimal import Decimal
from datetime import datetime
from app.models.signals import TradingSignal
from app.models.futures import FuturesConfig, MarginType
from app.repositories.signal_repository import SignalRepository

def test_create_signal(db_session):
    """Test creating a new trading signal."""
    repo = SignalRepository(db_session)
    signal = TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000"),
        take_profit=Decimal("55000"),
        stop_loss=Decimal("48000"),
        created_at=datetime.utcnow()
    )
    created = repo.create_signal(signal)
    assert created.id is not None
    assert created.symbol == "BTCUSDT"

def test_get_signal(db_session):
    """Test retrieving a trading signal."""
    repo = SignalRepository(db_session)
    signal = TradingSignal(
        symbol="ETHUSDT",
        entry_price=Decimal("3000"),
        take_profit=Decimal("3300"),
        stop_loss=Decimal("2800"),
        created_at=datetime.utcnow()
    )
    created = repo.create_signal(signal)
    retrieved = repo.get_signal(created.id)
    assert retrieved is not None
    assert retrieved.symbol == "ETHUSDT"

def test_update_signal(db_session):
    """Test updating a trading signal with futures config."""
    repo = SignalRepository(db_session)
    signal = TradingSignal(
        symbol="BNBUSDT",
        entry_price=Decimal("400"),
        take_profit=Decimal("440"),
        stop_loss=Decimal("380"),
        created_at=datetime.utcnow()
    )
    created = repo.create_signal(signal)

    futures_config = FuturesConfig(
        leverage=20,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100"),
        max_position_size=Decimal("1000"),
        risk_level=0.5
    )

    updated = repo.update_signal(created.id, futures_config)
    assert updated is not None
    assert updated.futures_configuration.leverage == 20
    assert updated.futures_configuration.margin_type == MarginType.CROSS

def test_delete_signal(db_session):
    """Test deleting a trading signal."""
    repo = SignalRepository(db_session)
    signal = TradingSignal(
        symbol="SOLUSDT",
        entry_price=Decimal("100"),
        take_profit=Decimal("110"),
        stop_loss=Decimal("95"),
        created_at=datetime.utcnow()
    )
    created = repo.create_signal(signal)
    assert repo.delete_signal(created.id) is True
    assert repo.get_signal(created.id) is None

def test_get_signals(db_session):
    """Test retrieving multiple trading signals."""
    repo = SignalRepository(db_session)
    signals = [
        TradingSignal(
            symbol=f"TEST{i}USDT",
            entry_price=Decimal("100"),
            take_profit=Decimal("110"),
            stop_loss=Decimal("95"),
            created_at=datetime.utcnow()
        )
        for i in range(5)
    ]
    for signal in signals:
        repo.create_signal(signal)

    retrieved = repo.get_signals(limit=3)
    assert len(retrieved) == 3
    assert all(isinstance(s, TradingSignal) for s in retrieved)
