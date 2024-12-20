import pytest
from decimal import Decimal
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.trading.pair_selector import PairSelector
from app.services.trading_strategy.strategy import TradingStrategy
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.trading.fee_calculator import FeeCalculator


@pytest.fixture
async def market_data_service():
    """Mock market data service for testing"""

    class MockMarketDataService:
        async def get_market_data(self, symbol: str, testing: bool = False) -> dict:
            # Scale volume based on symbol to test different scenarios
            volumes = {
                "BTC/USDT": Decimal("5000000000"),  # $5B volume
                "ETH/USDT": Decimal("2000000000"),  # $2B volume
                "BNB/USDT": Decimal("1000000000"),  # $1B volume
                "SOL/USDT": Decimal("500000000"),  # $500M volume
            }
            return {
                "volume_24h": volumes.get(symbol, Decimal("50000000")),
                "price": Decimal("50000"),
                "volatility": Decimal("0.02"),
                "spread_percentage": Decimal("0.1"),
                "liquidity_score": Decimal("1.5"),
                "trend": "neutral",
            }

    return MockMarketDataService()


@pytest.fixture
async def account_monitor(market_data_service):
    """Initialize AccountMonitor with mock services"""
    return AccountMonitor(market_data_service)


@pytest.fixture
async def pair_selector(market_data_service, account_monitor):
    """Initialize PairSelector with mock services"""
    return PairSelector(market_data_service, account_monitor)


@pytest.fixture
async def fee_calculator():
    """Initialize FeeCalculator for testing"""
    return FeeCalculator()


@pytest.fixture
async def trading_strategy(account_monitor, pair_selector, market_data_service, fee_calculator):
    """Initialize TradingStrategy with mock services"""
    return TradingStrategy(
        account_monitor=account_monitor,
        pair_selector=pair_selector,
        market_data_service=market_data_service,
        fee_calculator=fee_calculator
    )


@pytest.mark.asyncio
async def test_account_stage_transitions(account_monitor):
    """Test account stage detection across different balance ranges"""
    test_cases = [
        (Decimal("50"), "micro"),  # Below minimum
        (Decimal("100"), "micro"),  # Minimum micro
        (Decimal("5000"), "micro"),  # Mid micro
        (Decimal("9999"), "micro"),  # Upper micro
        (Decimal("10000"), "small"),  # Minimum small
        (Decimal("50000"), "small"),  # Mid small
        (Decimal("99999"), "small"),  # Upper small
        (Decimal("100000"), "medium"),  # Minimum medium
        (Decimal("500000"), "medium"),  # Mid medium
        (Decimal("999999"), "medium"),  # Upper medium
        (Decimal("1000000"), "large"),  # Minimum large
        (Decimal("5000000"), "large"),  # Mid large
        (Decimal("100000000"), "large"),  # Very large
    ]

    for balance, expected_stage in test_cases:
        stage = await account_monitor.get_account_stage(balance)
        assert (
            stage == expected_stage
        ), f"Balance {balance} should be in {expected_stage} stage, got {stage}"


@pytest.mark.asyncio
async def test_position_sizing_by_stage(account_monitor):
    """Test position sizing adjustments for different account stages"""
    test_cases = [
        # (balance, expected_stage, max_position_percentage)
        (Decimal("500"), "micro", Decimal("0.02")),  # Small micro account
        (Decimal("5000"), "micro", Decimal("0.02")),  # Larger micro account
        (Decimal("20000"), "small", Decimal("0.016")),  # Small account
        (Decimal("200000"), "medium", Decimal("0.012")),  # Medium account
        (Decimal("2000000"), "large", Decimal("0.008")),  # Large account
    ]

    for balance, expected_stage, max_risk in test_cases:
        position_data = await account_monitor.calculate_position_size(
            balance=balance, symbol="BTC/USDT"
        )

        # Verify stage
        assert position_data["stage"] == expected_stage

        # Verify position size doesn't exceed maximum risk
        max_position = balance * max_risk
        assert (
            Decimal(str(position_data["recommended_size"])) <= max_position
        ), f"Position size exceeds maximum risk for {expected_stage} stage"


@pytest.mark.asyncio
async def test_pair_selection_by_stage(pair_selector):
    """Test pair selection based on account size and liquidity"""
    test_cases = [
        (Decimal("500"), 1),  # Micro account - strict requirements
        (Decimal("20000"), 2),  # Small account - moderate requirements
        (Decimal("200000"), 3),  # Medium account - relaxed requirements
        (Decimal("2000000"), 4),  # Large account - most relaxed requirements
    ]

    base_pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]

    for balance, min_expected_pairs in test_cases:
        suitable_pairs = await pair_selector.select_pairs(
            balance=balance, base_pairs=base_pairs
        )

        assert (
            len(suitable_pairs) >= min_expected_pairs
        ), f"Account with {balance} USDT should have access to at least {min_expected_pairs} pairs"

        # Verify pair requirements match account stage
        stage = await pair_selector.account_monitor.get_account_stage(balance)
        for pair in suitable_pairs:
            volume_24h = Decimal(str(pair["volume_24h"]))
            min_volume = pair_selector.min_volume_requirements[stage]
            assert (
                volume_24h >= min_volume
            ), f"Pair volume {volume_24h} below minimum {min_volume} for {stage} stage"


@pytest.mark.asyncio
async def test_strategy_adaptation(trading_strategy):
    """Test trading strategy adaptation across account stages"""
    test_cases = [
        (Decimal("500"), False),  # Micro - no staged entries
        (Decimal("20000"), False),  # Small - no staged entries
        (Decimal("200000"), True),  # Medium - uses staged entries
        (Decimal("2000000"), True),  # Large - uses staged entries
    ]

    for balance, expect_staged_entries in test_cases:
        signal = await trading_strategy.generate_signal(
            balance=balance,
            symbol="BTC/USDT",  # Use BTC/USDT which has sufficient volume
            signal_type="long",
            confidence=0.85,
            testing=True  # Enable testing mode
        )

        assert signal is not None, f"Signal should be generated for balance {balance}"

        # Verify entry conditions presence matches account stage
        has_staged_entries = len(signal.get("entry_conditions", {}).get("stages", [])) > 0
        assert has_staged_entries == expect_staged_entries, \
            f"Account with {balance} USDT should {'have' if expect_staged_entries else 'not have'} staged entries"

        if has_staged_entries:
            stages = signal["entry_conditions"]["stages"]
            assert len(stages) == 3, "Should have 3 entry stages for medium/large accounts"

            # Calculate total position size from stages
            total_staged_size = sum(stage.get("size", 0) for stage in stages)
            assert abs(total_staged_size - signal["position_size"]) < 0.0001, \
                "Sum of staged entries should equal total position size"
