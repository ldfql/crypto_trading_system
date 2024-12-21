"""Tests for signal repository functionality."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.signal_repository import SignalRepository
from app.models.signals import TradingSignal
from app.models.enums import TradingDirection, MarginType

@pytest.fixture
async def signal_repository(db_session: AsyncSession) -> SignalRepository:
    """Create a signal repository instance."""
    return SignalRepository(db_session)

@pytest.mark.asyncio
async def test_create_signal(signal_repository: SignalRepository):
    """Test creating a new trading signal."""
    signal = TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85"),
        timestamp=datetime.now(timezone.utc)
    )

    created_signal = await signal_repository.create_signal(signal)
    assert created_signal.id is not None
    assert created_signal.symbol == "BTCUSDT"
    assert created_signal.entry_price == Decimal("50000.00")

@pytest.mark.asyncio
async def test_create_signal_default_timestamp(signal_repository: SignalRepository):
    """Test creating a signal with default timestamp."""
    signal = TradingSignal(
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

    created = await signal_repository.create_signal(signal)
    assert created.timestamp is not None
    assert created.timestamp.tzinfo == timezone.utc

@pytest.mark.asyncio
async def test_get_signal_by_id(signal_repository: SignalRepository):
    """Test retrieving a signal by ID."""
    signal = TradingSignal(
        symbol="ETHUSDT",
        entry_price=Decimal("3000.00"),
        take_profit=Decimal("3300.00"),
        stop_loss=Decimal("2800.00"),
        position_size=Decimal("1.0"),
        leverage=5,
        margin_type=MarginType.ISOLATED,
        direction=TradingDirection.SHORT,
        confidence=Decimal("0.90"),
        timestamp=datetime.now(timezone.utc)
    )

    created = await signal_repository.create_signal(signal)
    retrieved = await signal_repository.get_signal_by_id(created.id)

    assert retrieved is not None
    assert retrieved.symbol == "ETHUSDT"
    assert retrieved.leverage == 5

@pytest.mark.asyncio
async def test_get_recent_signals(signal_repository: SignalRepository):
    """Test retrieving recent trading signals."""
    signals = [
        TradingSignal(
            symbol=f"BTCUSDT",
            entry_price=Decimal("50000.00"),
            take_profit=Decimal("55000.00"),
            stop_loss=Decimal("48000.00"),
            position_size=Decimal("0.1"),
            leverage=10,
            margin_type=MarginType.CROSS,
            direction=TradingDirection.LONG,
            confidence=Decimal("0.85"),
            timestamp=datetime.now(timezone.utc)
        ) for _ in range(5)
    ]

    for signal in signals:
        await signal_repository.create_signal(signal)

    recent = await signal_repository.get_recent_signals(limit=3)
    assert len(recent) == 3
    assert all(isinstance(s, TradingSignal) for s in recent)

@pytest.mark.asyncio
async def test_get_recent_signals_with_filters(signal_repository: SignalRepository):
    """Test retrieving signals with various filters."""
    signals = [
        TradingSignal(
            symbol="BTCUSDT",
            entry_price=Decimal("50000.00"),
            take_profit=Decimal("55000.00"),
            stop_loss=Decimal("48000.00"),
            position_size=Decimal("0.1"),
            leverage=10,
            margin_type=MarginType.CROSS,
            direction=TradingDirection.LONG,
            confidence=Decimal("0.85"),
            timestamp=datetime.now(timezone.utc)
        ),
        TradingSignal(
            symbol="ETHUSDT",
            entry_price=Decimal("3000.00"),
            take_profit=Decimal("3300.00"),
            stop_loss=Decimal("2800.00"),
            position_size=Decimal("1.0"),
            leverage=5,
            margin_type=MarginType.ISOLATED,
            direction=TradingDirection.SHORT,
            confidence=Decimal("0.90"),
            timestamp=datetime.now(timezone.utc)
        )
    ]

    for signal in signals:
        await signal_repository.create_signal(signal)

    # Test symbol filter
    btc_signals = await signal_repository.get_recent_signals(symbol="BTCUSDT")
    assert len(btc_signals) == 1
    assert btc_signals[0].symbol == "BTCUSDT"

    # Test direction filter
    long_signals = await signal_repository.get_recent_signals(direction=TradingDirection.LONG)
    assert len(long_signals) == 1
    assert long_signals[0].direction == TradingDirection.LONG

    # Test confidence filter
    high_conf_signals = await signal_repository.get_recent_signals(min_confidence=Decimal("0.88"))
    assert len(high_conf_signals) == 1
    assert high_conf_signals[0].confidence >= Decimal("0.88")

@pytest.mark.asyncio
async def test_update_signal(signal_repository: SignalRepository):
    """Test updating an existing signal."""
    signal = TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85"),
        timestamp=datetime.now(timezone.utc)
    )

    created = await signal_repository.create_signal(signal)
    created.take_profit = Decimal("56000.00")
    updated = await signal_repository.update_signal(created)

    assert updated is not None
    assert updated.take_profit == Decimal("56000.00")

@pytest.mark.asyncio
async def test_update_signal_edge_cases(signal_repository: SignalRepository):
    """Test edge cases for updating signals."""
    # Test updating non-existent signal
    non_existent = TradingSignal(
        id=999,
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85"),
        timestamp=datetime.now(timezone.utc)
    )
    updated = await signal_repository.update_signal(non_existent)
    assert updated is None

    # Test updating signal without ID
    no_id = TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85"),
        timestamp=datetime.now(timezone.utc)
    )
    updated = await signal_repository.update_signal(no_id)
    assert updated is None

@pytest.mark.asyncio
async def test_delete_signal(signal_repository: SignalRepository):
    """Test deleting a trading signal."""
    signal = TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85"),
        timestamp=datetime.now(timezone.utc)
    )

    created = await signal_repository.create_signal(signal)
    assert created.id is not None

    success = await signal_repository.delete_signal(created.id)
    assert success is True

    deleted = await signal_repository.get_signal_by_id(created.id)
    assert deleted is None

@pytest.mark.asyncio
async def test_delete_signal_edge_cases(signal_repository: SignalRepository):
    """Test edge cases for deleting signals."""
    # Test deleting non-existent signal
    success = await signal_repository.delete_signal(999)
    assert success is False

    # Test deleting already deleted signal
    signal = TradingSignal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.00"),
        take_profit=Decimal("55000.00"),
        stop_loss=Decimal("48000.00"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type=MarginType.CROSS,
        direction=TradingDirection.LONG,
        confidence=Decimal("0.85"),
        timestamp=datetime.now(timezone.utc)
    )

    created = await signal_repository.create_signal(signal)
    await signal_repository.delete_signal(created.id)
    success = await signal_repository.delete_signal(created.id)
    assert success is False
