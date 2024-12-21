"""Test cases for signal repository."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.models.signals import TradingSignal
from app.models.futures import FuturesConfig, MarginType
from app.repositories.signal_repository import SignalRepository

@pytest.mark.asyncio
async def test_create_signal(db_session):
    """Test creating a new trading signal."""
    repo = SignalRepository(db_session)
    signal_data = {
        "symbol": "BTCUSDT",
        "entry_price": Decimal("50000"),
        "take_profit": Decimal("55000"),
        "stop_loss": Decimal("48000"),
        "position_size": Decimal("0.1"),
        "leverage": 10,
        "margin_type": "isolated",
        "direction": "long",
        "confidence": Decimal("0.85"),
        "timestamp": datetime.now(timezone.utc)
    }

    created = await repo.create_signal(**signal_data)
    assert created.id is not None
    assert created.symbol == "BTCUSDT"
    assert created.leverage == 10
    assert created.margin_type == "isolated"
    assert created.direction == "long"
    assert created.confidence == Decimal("0.85")

@pytest.mark.asyncio
async def test_create_signal_default_timestamp(db_session):
    """Test creating a signal with default timestamp."""
    repo = SignalRepository(db_session)
    signal_data = {
        "symbol": "BTCUSDT",
        "entry_price": Decimal("50000"),
        "take_profit": Decimal("55000"),
        "stop_loss": Decimal("48000"),
        "position_size": Decimal("0.1"),
        "leverage": 10,
        "margin_type": "isolated",
        "direction": "long",
        "confidence": Decimal("0.85")
    }

    created = await repo.create_signal(**signal_data)
    assert created.timestamp is not None
    assert created.timestamp.tzinfo == timezone.utc  # Verify timezone

@pytest.mark.asyncio
async def test_get_signal(db_session):
    """Test retrieving a trading signal."""
    repo = SignalRepository(db_session)
    signal_data = {
        "symbol": "ETHUSDT",
        "entry_price": Decimal("3000"),
        "take_profit": Decimal("3300"),
        "stop_loss": Decimal("2800"),
        "position_size": Decimal("1.0"),
        "leverage": 5,
        "margin_type": "cross",
        "direction": "short",
        "confidence": Decimal("0.90"),
        "timestamp": datetime.now(timezone.utc)
    }

    created = await repo.create_signal(**signal_data)
    retrieved = await repo.get_signal(created.id)
    assert retrieved is not None
    assert retrieved.symbol == "ETHUSDT"
    assert retrieved.leverage == 5
    assert retrieved.margin_type == "cross"
    assert retrieved.direction == "short"
    assert retrieved.confidence == Decimal("0.90")

@pytest.mark.asyncio
async def test_update_signal(db_session):
    """Test updating a trading signal with futures config."""
    repo = SignalRepository(db_session)
    signal_data = {
        "symbol": "BNBUSDT",
        "entry_price": Decimal("400"),
        "take_profit": Decimal("440"),
        "stop_loss": Decimal("380"),
        "position_size": Decimal("2.5"),
        "leverage": 20,
        "margin_type": "isolated",
        "direction": "long",
        "confidence": Decimal("0.95"),
        "timestamp": datetime.now(timezone.utc)
    }

    created = await repo.create_signal(**signal_data)

    futures_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("100"),
        max_position_size=Decimal("1000"),
        risk_level=0.5
    )

    updated = await repo.update_signal(created.id, futures_config)
    assert updated is not None
    assert updated.futures_config["leverage"] == 10
    assert updated.futures_config["margin_type"] == MarginType.CROSS
    assert Decimal(updated.futures_config["position_size"]) == Decimal("100")

@pytest.mark.asyncio
async def test_update_signal_edge_cases(db_session):
    """Test edge cases for updating signals."""
    repo = SignalRepository(db_session)

    # Test updating non-existent signal
    futures_config = FuturesConfig(
        leverage=10,
        margin_type="cross",  # Use string instead of enum
        position_size=Decimal("100"),
        max_position_size=Decimal("1000"),
        risk_level=Decimal("0.5")
    )
    updated = await repo.update_signal(999, futures_config)
    assert updated is None

    # Test updating with invalid futures config
    signal = await repo.create_signal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000"),
        take_profit=Decimal("55000"),
        stop_loss=Decimal("48000"),
        position_size=Decimal("0.1"),
        leverage=10,
        margin_type="isolated",
        direction="long",
        confidence=Decimal("0.85")
    )

    with pytest.raises(ValueError, match="Leverage must be between 1 and 125"):
        invalid_config = FuturesConfig(
            leverage=126,  # Invalid leverage
            margin_type="cross",  # Use string instead of enum
            position_size=Decimal("100"),
            max_position_size=Decimal("1000"),
            risk_level=Decimal("0.5")
        )
        await repo.update_signal(signal.id, invalid_config)

@pytest.mark.asyncio
async def test_delete_signal(db_session):
    """Test deleting a trading signal."""
    repo = SignalRepository(db_session)
    signal_data = {
        "symbol": "SOLUSDT",
        "entry_price": Decimal("100"),
        "take_profit": Decimal("110"),
        "stop_loss": Decimal("95"),
        "position_size": Decimal("10"),
        "leverage": 15,
        "margin_type": "isolated",
        "direction": "long",
        "confidence": Decimal("0.88"),
        "timestamp": datetime.now(timezone.utc)
    }

    created = await repo.create_signal(**signal_data)
    assert await repo.delete_signal(created.id) is True
    assert await repo.get_signal(created.id) is None

@pytest.mark.asyncio
async def test_get_signals_with_filters(db_session):
    """Test retrieving multiple trading signals with filters."""
    repo = SignalRepository(db_session)
    signal_data_list = [
        {
            "symbol": "BTCUSDT",
            "entry_price": Decimal("45000.00"),
            "take_profit": Decimal("48000.00"),
            "stop_loss": Decimal("43000.00"),
            "position_size": Decimal("0.1"),
            "leverage": 10,
            "margin_type": "isolated",
            "direction": "long",
            "confidence": Decimal("0.85"),
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "symbol": "ETHUSDT",
            "entry_price": Decimal("3000.00"),
            "take_profit": Decimal("3300.00"),
            "stop_loss": Decimal("2800.00"),
            "position_size": Decimal("1.0"),
            "leverage": 5,
            "margin_type": "cross",
            "direction": "short",
            "confidence": Decimal("0.90"),
            "timestamp": datetime.now(timezone.utc)
        }
    ]

    for signal_data in signal_data_list:
        await repo.create_signal(**signal_data)

    # Test filtering by symbol
    btc_signals = await repo.get_signals(symbol="BTCUSDT")
    assert len(btc_signals) == 1
    assert all(signal.symbol == "BTCUSDT" for signal in btc_signals)

    # Test filtering by direction
    long_signals = await repo.get_signals(direction="long")
    assert len(long_signals) == 1
    assert all(signal.direction == "long" for signal in long_signals)

    # Test filtering by confidence threshold
    high_confidence_signals = await repo.get_signals(min_confidence=Decimal("0.88"))
    assert len(high_confidence_signals) == 1
    assert all(signal.confidence >= Decimal("0.88") for signal in high_confidence_signals)

@pytest.mark.asyncio
async def test_get_signals_edge_cases(db_session):
    """Test edge cases for retrieving signals."""
    repo = SignalRepository(db_session)

    # Test with no signals in database
    signals = await repo.get_signals()
    assert len(signals) == 0

    # Test with invalid symbol filter
    signals = await repo.get_signals(symbol="INVALIDPAIR")
    assert len(signals) == 0

    # Test with invalid direction filter
    signals = await repo.get_signals(direction="invalid")
    assert len(signals) == 0

    # Test with negative confidence filter
    signals = await repo.get_signals(min_confidence=Decimal("-0.1"))
    assert len(signals) == 0

    # Test limit enforcement
    for i in range(150):  # Create more signals than default limit
        await repo.create_signal(
            symbol=f"PAIR{i}USDT",
            entry_price=Decimal("1000"),
            take_profit=Decimal("1100"),
            stop_loss=Decimal("900"),
            position_size=Decimal("1"),
            leverage=10,
            margin_type="isolated",
            direction="long",
            confidence=Decimal("0.85")
        )

    signals = await repo.get_signals()  # Should respect default limit
    assert len(signals) == 100

    # Test custom limit
    signals = await repo.get_signals(limit=50)
    assert len(signals) == 50

@pytest.mark.asyncio
async def test_signal_validation(db_session):
    """Test signal validation rules."""
    repo = SignalRepository(db_session)

    # Test invalid leverage
    with pytest.raises(ValueError, match="Leverage must be between 1 and 125"):
        await repo.create_signal(
            symbol="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("48000.00"),
            stop_loss=Decimal("43000.00"),
            position_size=Decimal("0.1"),
            leverage=126,
            margin_type="isolated",
            direction="long",
            confidence=Decimal("0.85"),
            timestamp=datetime.now(timezone.utc)
        )

    # Test invalid margin type
    with pytest.raises(ValueError, match="Margin type must be either 'isolated' or 'cross'"):
        await repo.create_signal(
            symbol="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("48000.00"),
            stop_loss=Decimal("43000.00"),
            position_size=Decimal("0.1"),
            leverage=10,
            margin_type="invalid",
            direction="long",
            confidence=Decimal("0.85"),
            timestamp=datetime.now(timezone.utc)
        )

    # Test invalid direction
    with pytest.raises(ValueError, match="Direction must be either 'long' or 'short'"):
        await repo.create_signal(
            symbol="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("48000.00"),
            stop_loss=Decimal("43000.00"),
            position_size=Decimal("0.1"),
            leverage=10,
            margin_type="isolated",
            direction="invalid",
            confidence=Decimal("0.85"),
            timestamp=datetime.now(timezone.utc)
        )

    # Test invalid confidence
    with pytest.raises(ValueError, match="Confidence must be a decimal between 0 and 1"):
        await repo.create_signal(
            symbol="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("48000.00"),
            stop_loss=Decimal("43000.00"),
            position_size=Decimal("0.1"),
            leverage=10,
            margin_type="isolated",
            direction="long",
            confidence=Decimal("1.5"),
            timestamp=datetime.now(timezone.utc)
        )

@pytest.mark.asyncio
async def test_decimal_serialization(db_session):
    """Test decimal serialization in futures config updates."""
    repo = SignalRepository(db_session)
    signal = await repo.create_signal(
        symbol="BTCUSDT",
        entry_price=Decimal("50000.123456789"),
        take_profit=Decimal("55000.987654321"),
        stop_loss=Decimal("48000.111111111"),
        position_size=Decimal("0.123456789"),
        leverage=10,
        margin_type="isolated",
        direction="long",
        confidence=Decimal("0.85")
    )

    config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("123.456789123"),
        max_position_size=Decimal("1000.987654321"),
        risk_level=Decimal("0.567891234")
    )

    updated = await repo.update_signal(signal.id, config)
    assert updated is not None
    assert Decimal(updated.futures_config["position_size"]) == Decimal("123.456789123")
    assert Decimal(updated.futures_config["max_position_size"]) == Decimal("1000.987654321")
    assert Decimal(updated.futures_config["risk_level"]) == Decimal("0.567891234")
