"""Tests for trading schema validation."""
import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.trading import TradingSignal, TradingPairResponse
from app.models.futures import MarginType

def test_trading_signal_validation():
    """Test trading signal schema validation."""
    # Test valid signal
    valid_signal = TradingSignal(
        pair="BTCUSDT",
        entry_price=Decimal("45000.00"),
        take_profit=Decimal("46000.00"),
        stop_loss=Decimal("44000.00"),
        position_size=Decimal("1000.00"),
        leverage=20,
        margin_type=MarginType.CROSS,
        expected_profit=Decimal("90.00"),  # Realistic profit (9% of position size)
        confidence=0.85
    )
    assert valid_signal.pair == "BTCUSDT"
    assert valid_signal.entry_price == Decimal("45000.00")
    assert valid_signal.confidence == 0.85

    # Test invalid confidence value
    with pytest.raises(ValidationError):
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("1000.00"),
            leverage=20,
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),
            confidence=1.5  # Should be between 0 and 1
        )

    # Test invalid leverage value
    with pytest.raises(ValidationError):
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("1000.00"),
            leverage=0,  # Should be positive
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),
            confidence=0.85
        )

def test_trading_pair_response():
    """Test trading pair response schema validation."""
    signal = TradingSignal(
        pair="BTCUSDT",
        entry_price=Decimal("45000.00"),
        take_profit=Decimal("46000.00"),
        stop_loss=Decimal("44000.00"),
        position_size=Decimal("1000.00"),
        leverage=20,
        margin_type=MarginType.CROSS,
        expected_profit=Decimal("90.00"),  # Realistic profit (9% of position size)
        confidence=0.85
    )

    # Test valid response
    response = TradingPairResponse(signals=[signal])
    assert len(response.signals) == 1
    assert response.signals[0].pair == "BTCUSDT"

    # Test empty signals list
    response = TradingPairResponse(signals=[])
    assert len(response.signals) == 0

def test_trading_signal_decimal_precision():
    """Test decimal precision handling in trading signals."""
    signal = TradingSignal(
        pair="BTCUSDT",
        entry_price=Decimal("45000.123456789"),
        take_profit=Decimal("45900.987654321"),
        stop_loss=Decimal("44500.456789123"),
        position_size=Decimal("1000.123456789"),
        leverage=20,
        margin_type=MarginType.CROSS,
        expected_profit=Decimal("90.987654321"),  # Realistic profit (9% of position size)
        confidence=0.85
    )

    # Verify decimal precision is maintained
    assert signal.entry_price == Decimal("45000.123456789")
    assert signal.take_profit == Decimal("45900.987654321")
    assert signal.stop_loss == Decimal("44500.456789123")
    assert signal.position_size == Decimal("1000.123456789")
    assert signal.expected_profit == Decimal("90.987654321")

def test_trading_signal_margin_type_validation():
    """Test margin type validation in trading signals."""
    # Test CROSS margin type
    signal = TradingSignal(
        pair="BTCUSDT",
        entry_price=Decimal("45000.00"),
        take_profit=Decimal("46000.00"),
        stop_loss=Decimal("44000.00"),
        position_size=Decimal("1000.00"),
        leverage=20,
        margin_type=MarginType.CROSS,
        expected_profit=Decimal("90.00"),  # Realistic profit (9% of position size)
        confidence=0.85
    )
    assert signal.margin_type == MarginType.CROSS

    # Test ISOLATED margin type
    signal = TradingSignal(
        pair="BTCUSDT",
        entry_price=Decimal("45000.00"),
        take_profit=Decimal("46000.00"),
        stop_loss=Decimal("44000.00"),
        position_size=Decimal("1000.00"),
        leverage=20,
        margin_type=MarginType.ISOLATED,
        expected_profit=Decimal("90.00"),  # Realistic profit (9% of position size)
        confidence=0.85
    )
    assert signal.margin_type == MarginType.ISOLATED


def test_trading_signal_validation_ranges():
    """Test validation of trading signal value ranges."""
    # Test negative values
    with pytest.raises(ValidationError):
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("-45000.00"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("1000.00"),
            leverage=20,
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),
            confidence=0.85
        )

    with pytest.raises(ValidationError):
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("45000.00"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("-1000.00"),
            leverage=20,
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),
            confidence=0.85
        )

    # Test zero values
    with pytest.raises(ValidationError):
        TradingSignal(
            pair="BTCUSDT",
            entry_price=Decimal("0"),
            take_profit=Decimal("46000.00"),
            stop_loss=Decimal("44000.00"),
            position_size=Decimal("1000.00"),
            leverage=20,
            margin_type=MarginType.CROSS,
            expected_profit=Decimal("90.00"),
            confidence=0.85
        )
