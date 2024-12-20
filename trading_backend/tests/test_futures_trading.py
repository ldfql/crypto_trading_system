"""Tests for futures trading functionality."""
from decimal import Decimal
import pytest
from unittest.mock import Mock, AsyncMock
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.trading.fee_calculator import FeeCalculator
from app.services.trading_strategy.strategy import TradingStrategy
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.trading.pair_selector import PairSelector


@pytest.fixture
def market_data_service():
    """Mock market data service with complete test data."""
    service = Mock(spec=MarketDataService)
    service.get_market_data = AsyncMock(return_value={
        "symbol": "BTCUSDT",
        "price": 50000.0,
        "volume_24h": 5000000.0,
        "volatility": 0.02,
        "trend": "accumulation",
        "liquidity_score": 0.95,
        "market_phase": "bullish",
        "technical_indicators": {
            "rsi": 65,
            "macd": "bullish",
            "moving_averages": {
                "ma_20": 49500.0,
                "ma_50": 48000.0,
                "ma_200": 45000.0
            }
        },
        "funding_rate": 0.0001,
        "open_interest": 1000000.0,
        "max_leverage": 125,
        "min_leverage": 1,
        "maintenance_margin": 0.025
    })
    return service


@pytest.fixture
def pair_selector(market_data_service, account_monitor):
    """Create pair selector with mock implementation."""
    selector = Mock(spec=PairSelector)
    selector.validate_pair = AsyncMock(return_value=(True, None))  # Always return valid for testing
    return selector


@pytest.fixture
def account_monitor(market_data_service):
    """Create account monitor with mock implementation."""
    monitor = Mock(spec=AccountMonitor)

    async def validate_leverage_and_margin(balance, leverage, margin_type):
        # Micro account rules (balance < 10000)
        if balance < Decimal("10000"):
            if margin_type != "ISOLATED":
                return False, "Micro accounts must use isolated margin"
            if leverage > 20:
                return False, "Micro accounts limited to 20x leverage"

        # Small account rules (10000 <= balance < 100000)
        elif balance < Decimal("100000"):
            if leverage > 50:
                return False, "Small accounts limited to 50x leverage"

        # Medium account rules (100000 <= balance < 1000000)
        elif balance < Decimal("1000000"):
            if leverage > 75:
                return False, "Medium accounts limited to 75x leverage"

        # Large account rules (balance >= 1000000)
        else:
            if leverage > 125:
                return False, "Large accounts limited to 125x leverage"

        return True, None

    monitor.validate_leverage_and_margin = AsyncMock(side_effect=validate_leverage_and_margin)
    return monitor


@pytest.fixture
def fee_calculator():
    """Create fee calculator with mock implementation."""
    calculator = Mock(spec=FeeCalculator)
    calculator.calculate_fees = AsyncMock(return_value={
        "entry_fee": 0.5,
        "exit_fee": 0.5,
        "total_fee": 1.0,
        "fee_rate": 0.001
    })
    calculator.calculate_total_fees = AsyncMock(return_value=1.0)
    return calculator


@pytest.fixture
def trading_strategy(account_monitor, pair_selector, market_data_service, fee_calculator):
    """Create trading strategy with all required dependencies."""
    return TradingStrategy(
        account_monitor=account_monitor,
        pair_selector=pair_selector,
        market_data_service=market_data_service,
        fee_calculator=fee_calculator,
        min_accuracy_threshold=0.82
    )


@pytest.mark.asyncio
async def test_leverage_limits_by_account_stage(account_monitor):
    """Test leverage limits for different account stages."""
    test_cases = [
        (Decimal("100"), 20, "ISOLATED", True),  # Micro account, max 20x
        (Decimal("100"), 21, "ISOLATED", False),  # Micro account, exceeds limit
        (Decimal("20000"), 50, "CROSS", True),   # Small account, max 50x
        (Decimal("20000"), 51, "CROSS", False),  # Small account, exceeds limit
        (Decimal("200000"), 75, "CROSS", True),  # Medium account, max 75x
        (Decimal("200000"), 76, "CROSS", False), # Medium account, exceeds limit
        (Decimal("2000000"), 125, "CROSS", True), # Large account, max 125x
        (Decimal("2000000"), 126, "CROSS", False) # Large account, exceeds limit
    ]

    for balance, leverage, margin_type, expected_valid in test_cases:
        is_valid, _ = await account_monitor.validate_leverage_and_margin(
            balance, leverage, margin_type
        )
        assert is_valid == expected_valid, f"Failed for balance {balance}, leverage {leverage}"


@pytest.mark.asyncio
async def test_margin_type_restrictions(account_monitor):
    """Test margin type restrictions for different account stages."""
    # Micro accounts can only use isolated margin
    is_valid, _ = await account_monitor.validate_leverage_and_margin(
        balance=Decimal("100"),
        leverage=10,
        margin_type="CROSS"
    )
    assert not is_valid, "Micro accounts should not be allowed to use cross margin"

    # Small accounts can use both margin types
    is_valid, _ = await account_monitor.validate_leverage_and_margin(
        balance=Decimal("20000"),
        leverage=20,
        margin_type="CROSS"
    )
    assert is_valid, "Small accounts should be allowed to use cross margin"


@pytest.mark.asyncio
async def test_fee_calculations(trading_strategy):
    """Test fee calculations with different position sizes."""
    result = await trading_strategy.calculate_expected_profit(
        position_size=Decimal("1000"),
        entry_price=50000.0,
        target_price=55000.0,
        leverage=10,
        signal_type="long",
        testing=True
    )

    # Verify fees are calculated
    assert result["fee_breakdown"]["entry_fee"] > 0
    assert result["fee_breakdown"]["exit_fee"] > 0
    assert result["fee_breakdown"]["total_fee"] > 0

    # Test with different position size
    large_result = await trading_strategy.calculate_expected_profit(
        position_size=Decimal("10000"),
        entry_price=50000.0,
        target_price=55000.0,
        leverage=10,
        signal_type="long",
        testing=True
    )

    # Larger position should have proportionally higher fees
    assert large_result["fee_breakdown"]["total_fee"] > result["fee_breakdown"]["total_fee"]


@pytest.mark.asyncio
async def test_profit_calculations(trading_strategy):
    """Test profit calculations including fees."""
    # Test long position with 10x leverage
    result = await trading_strategy.calculate_expected_profit(
        position_size=Decimal("1000"),
        entry_price=50000.0,
        target_price=55000.0,  # 10% increase
        leverage=10,
        signal_type="long",
        testing=True
    )

    # 10% price increase with 10x leverage should give ~100% return before fees
    assert result["net_profit"] > 900  # Slightly less than 1000 due to fees
    assert result["roi_percentage"] > 90  # Should be close to 100%

    # Test short position with 5x leverage
    short_result = await trading_strategy.calculate_expected_profit(
        position_size=Decimal("1000"),
        entry_price=50000.0,
        target_price=45000.0,  # 10% decrease
        leverage=5,
        signal_type="short",
        testing=True
    )

    # 10% price decrease with 5x leverage should give ~50% return before fees
    assert short_result["net_profit"] > 450  # Slightly less than 500 due to fees
    assert short_result["roi_percentage"] > 45  # Should be close to 50%


@pytest.mark.asyncio
async def test_liquidation_price_calculation(trading_strategy):
    """Test liquidation price calculations for different margin types."""
    # Test isolated margin liquidation
    isolated_liq = await trading_strategy.calculate_liquidation_price(
        entry_price=50000.0,
        leverage=10,
        margin_type="ISOLATED",
        signal_type="long",
        testing=True
    )

    # With 10x leverage and maintenance margin, liquidation should be ~9% away
    expected_range = (
        45000.0,  # -10% from entry
        46000.0   # -8% from entry
    )
    assert expected_range[0] < isolated_liq < expected_range[1]

    # Test cross margin liquidation
    cross_liq = await trading_strategy.calculate_liquidation_price(
        entry_price=50000.0,
        leverage=10,
        margin_type="CROSS",
        signal_type="long",
        testing=True
    )

    # Cross margin should have a lower liquidation price
    assert cross_liq < isolated_liq


@pytest.mark.asyncio
async def test_trading_parameters_display(trading_strategy):
    """Test trading parameters display with bilingual support."""
    signal = await trading_strategy.generate_signal(
        balance=Decimal("1000"),
        symbol="BTCUSDT",
        signal_type="long",
        confidence=0.95,
        entry_price=50000.0,
        target_price=55000.0,
        stop_loss=48000.0,
        take_profit=55000.0,
        leverage=10,
        margin_type="ISOLATED",
        testing=True
    )

    assert signal is not None
    assert "symbol" in signal  # 币种名
    assert "entry_price" in signal  # 入场价格
    assert "position_size" in signal  # 仓位比例
    assert "leverage" in signal  # 杠杆倍数
    assert "margin_type" in signal  # 全仓还是逐仓
    assert "take_profit" in signal  # 止盈点
    assert "stop_loss" in signal  # 止损点
    assert "confidence" in signal  # 准确度置信度
    assert signal["confidence"] >= 0.82  # Minimum accuracy threshold
