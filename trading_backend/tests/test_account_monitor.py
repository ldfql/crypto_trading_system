"""Tests for account monitoring functionality."""
import pytest
import asyncio
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import patch, Mock, AsyncMock, create_autospec
from app.models.signals import AccountStage, AccountStageTransition
from app.models.futures import FuturesConfig, MarginType
from app.services.monitoring.account_monitor import AccountMonitor, AccountMonitoringError
from fastapi import WebSocket
import pydantic

pytestmark = pytest.mark.asyncio  # Mark all tests as async

@pytest.mark.asyncio
async def test_init_account_monitor():
    """Test account monitor initialization."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))
    assert monitor.current_balance == Decimal("100")
    assert monitor.current_stage == AccountStage.INITIAL
    assert monitor.get_max_leverage() == 20

@pytest.mark.asyncio
async def test_determine_stage():
    """Test stage determination based on balance."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Test all stage boundaries
    test_cases = [
        (Decimal("50"), AccountStage.INITIAL),
        (Decimal("100"), AccountStage.INITIAL),
        (Decimal("999"), AccountStage.INITIAL),
        (Decimal("1000"), AccountStage.GROWTH),
        (Decimal("9999"), AccountStage.GROWTH),
        (Decimal("10000"), AccountStage.ADVANCED),
        (Decimal("99999"), AccountStage.ADVANCED),
        (Decimal("1000000"), AccountStage.PROFESSIONAL),
        (Decimal("9999999"), AccountStage.PROFESSIONAL),
        (Decimal("100000000"), AccountStage.EXPERT),
        (Decimal("500000000"), AccountStage.EXPERT)  # Path to 10亿U
    ]

    for balance, expected_stage in test_cases:
        await monitor.update_balance(balance)
        assert monitor.current_stage == expected_stage, f"Failed for balance {balance}"

@pytest.mark.asyncio
async def test_update_balance():
    """Test balance updates and stage transitions."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    # Test valid balance updates
    await monitor.update_balance(Decimal("500"))
    assert monitor.current_balance == Decimal("500")
    assert monitor.current_stage == AccountStage.INITIAL

    await monitor.update_balance(Decimal("1500"))
    assert monitor.current_balance == Decimal("1500")
    assert monitor.current_stage == AccountStage.GROWTH

    await monitor.update_balance(Decimal("15000"))
    assert monitor.current_balance == Decimal("15000")
    assert monitor.current_stage == AccountStage.ADVANCED

    # Test balance update with WebSocket notification
    mock_websocket = AsyncMock()
    monitor.websocket = mock_websocket
    await monitor.update_balance(Decimal("100000"))
    assert monitor.current_balance == Decimal("100000")
    assert monitor.current_stage == AccountStage.PROFESSIONAL

    # Verify WebSocket message
    mock_websocket.send_json.assert_awaited_once()
    call_args = mock_websocket.send_json.await_args[0][0]
    assert call_args["type"] == "balance_update"
    assert call_args["data"]["balance"] == "100000"
    assert call_args["data"]["stage"] == "PROFESSIONAL"

@pytest.mark.asyncio
async def test_calculate_position_size():
    """Test position size calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("10000"))

    # Test valid risk percentages
    assert monitor.calculate_position_size(Decimal("1")) == Decimal("100.000000000")
    assert monitor.calculate_position_size(Decimal("2.5")) == Decimal("250.000000000")

    # Test invalid risk percentages
    with pytest.raises(AccountMonitoringError, match="Risk percentage must be between 0.1 and 5"):
        monitor.calculate_position_size(Decimal("0"))
    with pytest.raises(AccountMonitoringError, match="Risk percentage must be between 0.1 and 5"):
        monitor.calculate_position_size(Decimal("6"))

@pytest.mark.asyncio
async def test_get_trading_parameters():
    """Test getting trading parameters."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))
    params = await monitor.get_trading_parameters(Decimal("1"))

    assert params["type"] == "trading_parameters"
    data = params["data"]
    assert data["account_stage"] == AccountStage.INITIAL.value
    assert Decimal(data["current_balance"]) == Decimal("100")
    assert data["margin_type"] == MarginType.CROSS.value

@pytest.mark.asyncio
async def test_validate_futures_config():
    """Test futures configuration validation."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))  # INITIAL stage

    # Test valid config for INITIAL stage
    valid_config = FuturesConfig(
        leverage=10,
        margin_type=MarginType.CROSS,
        position_size=Decimal("10"),
        max_position_size=Decimal("20"),
        risk_level=Decimal("0.5")
    )
    assert await monitor.validate_futures_config(valid_config) is True

    # Test invalid leverage
    with pytest.raises(ValueError, match="Initial stage max leverage is 20x"):
        invalid_config = FuturesConfig(
            leverage=25,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(invalid_config)

    # Test invalid margin type
    with pytest.raises(ValueError, match="Initial stage only supports cross margin"):
        invalid_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.ISOLATED,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("0.5")
        )
        await monitor.validate_futures_config(invalid_config)

    # Test invalid risk level
    with pytest.raises(pydantic.ValidationError, match="Input should be less than or equal to 1.0"):
        invalid_config = FuturesConfig(
            leverage=10,
            margin_type=MarginType.CROSS,
            position_size=Decimal("10"),
            max_position_size=Decimal("20"),
            risk_level=Decimal("1.5")
        )
        await monitor.validate_futures_config(invalid_config)

@pytest.mark.asyncio
async def test_get_stage_progress():
    """Test stage progress calculation."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))

    test_cases = [
        # Initial stage (100U - 1,000U)
        (Decimal("100"), Decimal("0.00"), Decimal("900")),    # Start
        (Decimal("500"), Decimal("44.44"), Decimal("500")),   # Middle
        (Decimal("900"), Decimal("88.89"), Decimal("100")),   # Near end

        # Growth stage (1,000U - 10,000U)
        (Decimal("1000"), Decimal("0.00"), Decimal("9000")),  # Start
        (Decimal("5000"), Decimal("44.44"), Decimal("5000")), # Middle
        (Decimal("9000"), Decimal("88.89"), Decimal("1000")), # Near end

        # Advanced stage (10,000U - 1,000,000U)
        (Decimal("10000"), Decimal("0.00"), Decimal("990000")),    # Start
        (Decimal("500000"), Decimal("49.49"), Decimal("500000")),  # Middle
        (Decimal("900000"), Decimal("89.90"), Decimal("100000")),  # Near end

        # Professional stage (1,000,000U - 100,000,000U)
        (Decimal("1000000"), Decimal("0.00"), Decimal("99000000")),     # Start
        (Decimal("50000000"), Decimal("49.49"), Decimal("50000000")),   # Middle
        (Decimal("90000000"), Decimal("89.90"), Decimal("10000000")),   # Near end

        # Expert stage (100,000,000U - 1,000,000,000U)
        (Decimal("100000000"), Decimal("0.00"), Decimal("900000000")),  # Start
        (Decimal("500000000"), Decimal("44.44"), Decimal("500000000")), # Middle
        (Decimal("900000000"), Decimal("88.89"), Decimal("100000000"))  # Near end
    ]

    for balance, expected_progress, expected_remaining in test_cases:
        await monitor.update_balance(balance)
        progress, remaining = monitor.get_stage_progress()
        assert abs(progress - expected_progress) < Decimal("0.01"), \
            f"Progress mismatch at balance {balance}"
        assert abs(remaining - expected_remaining) < Decimal("0.01"), \
            f"Remaining mismatch at balance {balance}"

@pytest.mark.asyncio
async def test_negative_balance_error():
    """Test error handling for negative balance."""
    monitor = AccountMonitor(initial_balance=Decimal("100"))
    with pytest.raises(AccountMonitoringError, match="Balance cannot be negative or zero"):
        await monitor.update_balance(Decimal("-100"))
    with pytest.raises(AccountMonitoringError, match="Balance cannot be negative or zero"):
        await monitor.update_balance(Decimal("0"))

@pytest.mark.asyncio
async def test_decimal_precision():
    """Test decimal precision handling in calculations."""
    monitor = AccountMonitor(initial_balance=Decimal("1234.56789"))

    # Test position size calculation precision
    position_size = monitor.calculate_position_size(Decimal("2.5"))
    assert isinstance(position_size, Decimal)
    assert position_size.as_tuple().exponent >= -9  # No more than 9 decimal places

    # Test stage progress precision
    progress, remaining = monitor.get_stage_progress()
    assert isinstance(progress, Decimal)
    assert isinstance(remaining, Decimal)
    assert progress.as_tuple().exponent >= -9
    assert remaining.as_tuple().exponent >= -9

@pytest.mark.asyncio
async def test_stage_transition_edge_cases():
    """Test edge cases in stage transitions."""
    monitor = AccountMonitor(initial_balance=Decimal("999"))

    # Test transition at exact boundary (999 -> 1000)
    await monitor.update_balance(Decimal("1000"))
    assert monitor.current_stage == AccountStage.GROWTH
    assert monitor.current_balance == Decimal("1000")

    # Test transition at upper boundary (9999 -> 10000)
    await monitor.update_balance(Decimal("9999"))
    assert monitor.current_stage == AccountStage.GROWTH
    await monitor.update_balance(Decimal("10000"))
    assert monitor.current_stage == AccountStage.ADVANCED

    # Test transition at professional boundary
    await monitor.update_balance(Decimal("999999"))
    assert monitor.current_stage == AccountStage.ADVANCED
    await monitor.update_balance(Decimal("1000000"))
    assert monitor.current_stage == AccountStage.PROFESSIONAL

    # Test transition at expert boundary
    await monitor.update_balance(Decimal("99999999"))
    assert monitor.current_stage == AccountStage.PROFESSIONAL
    await monitor.update_balance(Decimal("100000000"))
    assert monitor.current_stage == AccountStage.EXPERT

    # Test downgrade transitions
    await monitor.update_balance(Decimal("99999999"))
    assert monitor.current_stage == AccountStage.PROFESSIONAL
    await monitor.update_balance(Decimal("999999"))
    assert monitor.current_stage == AccountStage.ADVANCED
    await monitor.update_balance(Decimal("9999"))
    assert monitor.current_stage == AccountStage.GROWTH
    await monitor.update_balance(Decimal("999"))
    assert monitor.current_stage == AccountStage.INITIAL

@pytest.mark.asyncio
async def test_expert_stage_progress():
    """Test progress calculation for expert stage."""
    monitor = AccountMonitor(initial_balance=Decimal("100000000"))  # Start at expert stage

    test_cases = [
        (Decimal("100000000"), Decimal("0.00")),  # Start of expert stage
        (Decimal("200000000"), Decimal("11.11")),  # 20% through
        (Decimal("500000000"), Decimal("44.44")),  # 50% through
        (Decimal("750000000"), Decimal("72.22")),  # 75% through
        (Decimal("900000000"), Decimal("88.89")),  # 90% through
        (Decimal("1000000000"), Decimal("100.00"))  # Target reached (10亿U)
    ]

    for balance, expected_progress in test_cases:
        await monitor.update_balance(balance)
        progress, _ = monitor.get_stage_progress()
        assert abs(progress - expected_progress) < Decimal("0.01"), f"Failed for balance {balance}"

@pytest.mark.asyncio
async def test_websocket_balance_updates():
    """Test WebSocket balance update notifications."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))
    mock_websocket = AsyncMock()
    monitor.websocket = mock_websocket

    # Test balance update with stage change
    await monitor.update_balance(Decimal("10000"))

    # Verify WebSocket message
    mock_websocket.send_json.assert_awaited_once()
    call_args = mock_websocket.send_json.await_args[0][0]
    assert call_args["type"] == "balance_update"
    assert call_args["data"]["balance"] == "10000"
    assert call_args["data"]["stage"] == "ADVANCED"

    # Test balance update without stage change
    await monitor.update_balance(Decimal("15000"))
    mock_websocket.send_json.assert_awaited_with({
        "type": "balance_update",
        "data": {
            "balance": "15000",
            "stage": "ADVANCED",
            "progress": "0.51",
            "remaining": "985000.00"
        }
    })

@pytest.mark.asyncio
async def test_real_time_monitoring():
    """Test real-time monitoring functionality."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))
    updates_received = []

    async def mock_callback(data):
        updates_received.append(data)

    # Register callback
    monitor.register_update_callback(mock_callback)

    # Test multiple balance updates
    test_balances = [
        (Decimal("5000"), AccountStage.GROWTH),
        (Decimal("15000"), AccountStage.ADVANCED),
        (Decimal("1500000"), AccountStage.PROFESSIONAL),
        (Decimal("150000000"), AccountStage.EXPERT)
    ]

    for balance, expected_stage in test_balances:
        await monitor.update_balance(balance)
        assert len(updates_received) > 0
        latest_update = updates_received[-1]
        assert latest_update["balance"] == str(balance)
        assert latest_update["stage"] == expected_stage.name

    # Test callback removal
    monitor.remove_update_callback(mock_callback)
    await monitor.update_balance(Decimal("200000000"))
    assert len(updates_received) == len(test_balances)  # No new updates after removal

@pytest.mark.asyncio
async def test_futures_config_validation_across_stages():
    """Test futures configuration validation across different account stages."""
    monitor = AccountMonitor(initial_balance=Decimal("1000"))

    test_cases = [
        # Initial stage (max leverage: 20x)
        (Decimal("500"), {
            "leverage": 25,
            "position_size": Decimal("100"),
            "margin_type": "isolated"
        }, False, "Initial stage max leverage is 20x"),  # Should fail - leverage too high

        # Growth stage (max leverage: 50x)
        (Decimal("5000"), {
            "leverage": 45,
            "position_size": Decimal("1000"),
            "margin_type": "cross"
        }, True, None),  # Should pass

        # Advanced stage (max leverage: 75x)
        (Decimal("50000"), {
            "leverage": 70,
            "position_size": Decimal("10000"),
            "margin_type": "isolated"
        }, True, None),  # Should pass

        # Professional stage (max leverage: 100x)
        (Decimal("1500000"), {
            "leverage": 95,
            "position_size": Decimal("100000"),
            "margin_type": "cross"
        }, True, None),  # Should pass

        # Expert stage (max leverage: 125x)
        (Decimal("150000000"), {
            "leverage": 120,
            "position_size": Decimal("1000000"),
            "margin_type": "isolated"
        }, True, None),  # Should pass

        # Additional test cases for better coverage
        (Decimal("1000"), {
            "leverage": 20,
            "position_size": Decimal("200"),
            "margin_type": "isolated"
        }, False, "Initial stage only supports cross margin"),  # Should fail - wrong margin type

        (Decimal("1000"), {
            "leverage": 15,
            "position_size": Decimal("150"),
            "margin_type": "cross"
        }, False, "Initial stage position size cannot exceed 10% of balance"),  # Should fail - position size too large
    ]

    for balance, config, should_pass, expected_error in test_cases:
        await monitor.update_balance(balance)
        try:
            result = await monitor.validate_futures_config(config)
            assert should_pass, f"Expected validation to fail for balance {balance}"
            assert result is True
        except ValueError as e:
            assert not should_pass, f"Expected validation to pass for balance {balance}, but got error: {str(e)}"
            if expected_error:
                assert str(e) == expected_error, f"Expected error '{expected_error}' but got '{str(e)}'"
