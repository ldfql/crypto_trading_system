import pytest
from decimal import Decimal
from app.services.trading_strategy.strategy import TradingStrategy
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.trading.pair_selector import PairSelector
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.trading.fee_calculator import FeeCalculator
from unittest.mock import AsyncMock

@pytest.fixture
def trading_strategy(mocker):
    account_monitor = mocker.Mock(spec=AccountMonitor)
    pair_selector = mocker.Mock(spec=PairSelector)
    market_data_service = mocker.Mock(spec=MarketDataService)
    fee_calculator = mocker.Mock(spec=FeeCalculator)

    # Configure account monitor mock
    account_monitor.max_leverage = {
        "micro": 20,
        "small": 50,
        "medium": 75,
        "large": 125
    }

    return TradingStrategy(
        account_monitor=account_monitor,
        pair_selector=pair_selector,
        market_data_service=market_data_service,
        fee_calculator=fee_calculator
    )

@pytest.mark.asyncio
async def test_calculate_optimal_leverage_high_volatility(trading_strategy):
    """Test leverage reduction in high volatility conditions."""
    # Setup
    balance = Decimal("5000")  # Micro account
    market_data = {
        "volatility": 0.06,  # High volatility
        "trend": "neutral"
    }
    trading_strategy.account_monitor.get_account_stage.return_value = "micro"

    # Execute
    result = await trading_strategy.calculate_optimal_leverage(
        symbol="BTCUSDT",
        balance=balance,
        market_data=market_data
    )

    # Assert
    assert result["recommended_leverage"] == 10  # 50% of max 20x
    assert result["max_leverage"] == 20
    assert result["volatility"] == 0.06
    assert result["account_stage"] == "micro"

@pytest.mark.asyncio
async def test_calculate_optimal_leverage_medium_volatility(trading_strategy):
    """Test leverage adjustment in medium volatility conditions."""
    # Setup
    balance = Decimal("15000")  # Small account
    market_data = {
        "volatility": 0.04,  # Medium volatility
        "trend": "neutral"
    }
    trading_strategy.account_monitor.get_account_stage.return_value = "small"

    # Execute
    result = await trading_strategy.calculate_optimal_leverage(
        symbol="BTCUSDT",
        balance=balance,
        market_data=market_data
    )

    # Assert
    assert result["recommended_leverage"] == 37  # 75% of max 50x
    assert result["max_leverage"] == 50
    assert result["volatility"] == 0.04
    assert result["account_stage"] == "small"

@pytest.mark.asyncio
async def test_calculate_optimal_leverage_bearish_trend(trading_strategy):
    """Test leverage reduction in bearish market conditions."""
    # Setup
    balance = Decimal("150000")  # Medium account
    market_data = {
        "volatility": 0.02,  # Low volatility
        "trend": "bearish"
    }
    trading_strategy.account_monitor.get_account_stage.return_value = "medium"

    # Execute
    result = await trading_strategy.calculate_optimal_leverage(
        symbol="BTCUSDT",
        balance=balance,
        market_data=market_data
    )

    # Assert
    assert result["recommended_leverage"] == 56  # 75% of max 75x due to bearish trend
    assert result["max_leverage"] == 75
    assert result["volatility"] == 0.02
    assert result["account_stage"] == "medium"

@pytest.mark.asyncio
async def test_determine_margin_type_micro_account(trading_strategy):
    """Test margin type selection for micro accounts."""
    # Setup
    balance = Decimal("5000")  # Micro account
    volatility = Decimal("0.02")  # Low volatility
    position_size = Decimal("100")  # Small position
    trading_strategy.account_monitor.get_account_stage.return_value = "micro"

    # Execute
    result = await trading_strategy.determine_margin_type(
        balance=balance,
        volatility=volatility,
        position_size=position_size
    )

    # Assert
    assert result == "ISOLATED"  # Micro accounts always use ISOLATED

@pytest.mark.asyncio
async def test_determine_margin_type_high_volatility(trading_strategy):
    """Test margin type selection in high volatility conditions."""
    # Setup
    balance = Decimal("50000")  # Small account
    volatility = Decimal("0.06")  # High volatility
    position_size = Decimal("1000")  # Normal position
    trading_strategy.account_monitor.get_account_stage.return_value = "small"

    # Execute
    result = await trading_strategy.determine_margin_type(
        balance=balance,
        volatility=volatility,
        position_size=position_size
    )

    # Assert
    assert result == "ISOLATED"  # High volatility triggers ISOLATED

@pytest.mark.asyncio
async def test_determine_margin_type_large_position(trading_strategy):
    """Test margin type selection with large position size."""
    # Setup
    balance = Decimal("100000")  # Medium account
    volatility = Decimal("0.02")  # Low volatility
    position_size = Decimal("15000")  # Large position (>10% of balance)
    trading_strategy.account_monitor.get_account_stage.return_value = "medium"

    # Execute
    result = await trading_strategy.determine_margin_type(
        balance=balance,
        volatility=volatility,
        position_size=position_size
    )

    # Assert
    assert result == "ISOLATED"  # Large position triggers ISOLATED

@pytest.mark.asyncio
async def test_determine_margin_type_safe_conditions(trading_strategy):
    """Test margin type selection under safe conditions."""
    # Setup
    balance = Decimal("1000000")  # Large account
    volatility = Decimal("0.02")  # Low volatility
    position_size = Decimal("50000")  # Normal position (<10% of balance)
    trading_strategy.account_monitor.get_account_stage.return_value = "large"

    # Execute
    result = await trading_strategy.determine_margin_type(
        balance=balance,
        volatility=volatility,
        position_size=position_size
    )

    # Assert
    assert result == "CROSS"  # Safe conditions allow CROSS margin

@pytest.mark.asyncio
async def test_optimize_trading_parameters_long(trading_strategy):
    """Test complete parameter optimization flow for long position."""
    # Setup
    symbol = "BTCUSDT"
    balance = Decimal("50000")  # Small account
    signal_type = "LONG"

    # Mock market data service
    market_data = {
        "volatility": 0.03,
        "trend": "bullish",
        "current_price": 50000.0,
        "volume_24h": 1000000.0
    }
    trading_strategy.market_data_service.get_market_data.return_value = market_data

    # Mock account monitor
    position_data = {
        "recommended_size": "5000.0",
        "stage": "small",
        "confidence": 0.9
    }
    trading_strategy.account_monitor.calculate_position_size.return_value = position_data
    trading_strategy.account_monitor.get_account_stage.return_value = "small"

    # Mock profit calculation
    profit_data = {
        "gross_profit": Decimal("100.0"),
        "total_fee": Decimal("10.0"),
        "net_profit": Decimal("90.0"),
        "roi_percentage": Decimal("1.8"),
        "fee_breakdown": {
            "entry_fee": Decimal("5.0"),
            "exit_fee": Decimal("5.0")
        }
    }
    trading_strategy.calculate_expected_profit = AsyncMock(return_value=profit_data)
    trading_strategy.calculate_liquidation_price = AsyncMock(return_value=Decimal("48000.0"))

    # Execute
    result = await trading_strategy.optimize_trading_parameters(
        symbol=symbol,
        balance=balance,
        signal_type=signal_type
    )

    # Assert
    assert result["symbol"] == symbol
    assert result["signal_type"] == signal_type
    assert result["leverage"] > 0
    assert result["margin_type"] in ["ISOLATED", "CROSS"]
    assert result["position_size"] == 5000.0
    assert result["current_price"] == 50000.0
    assert result["target_price"] > result["current_price"]  # Long position
    assert result["liquidation_price"] == 48000.0
    assert result["expected_profit"]["gross_profit"] == 100.0
    assert result["expected_profit"]["net_profit"] == 90.0
    assert result["expected_profit"]["roi_percentage"] == 1.8
    assert result["market_conditions"]["volatility"] == 0.03
    assert result["market_conditions"]["trend"] == "bullish"
    assert result["account_info"]["stage"] == "small"
    assert result["confidence"] == 0.9

@pytest.mark.asyncio
async def test_optimize_trading_parameters_short(trading_strategy):
    """Test parameter optimization for short position."""
    # Setup
    symbol = "BTCUSDT"
    balance = Decimal("5000")  # Micro account
    signal_type = "SHORT"

    # Mock high volatility market data
    market_data = {
        "volatility": 0.06,
        "trend": "bearish",
        "current_price": 50000.0,
        "volume_24h": 1000000.0
    }
    trading_strategy.market_data_service.get_market_data.return_value = market_data

    # Mock account monitor
    position_data = {
        "recommended_size": "250.0",
        "stage": "micro",
        "confidence": 0.85
    }
    trading_strategy.account_monitor.calculate_position_size.return_value = position_data
    trading_strategy.account_monitor.get_account_stage.return_value = "micro"

    # Mock profit calculation
    profit_data = {
        "gross_profit": Decimal("50.0"),
        "total_fee": Decimal("5.0"),
        "net_profit": Decimal("45.0"),
        "roi_percentage": Decimal("1.5"),
        "fee_breakdown": {
            "entry_fee": Decimal("2.5"),
            "exit_fee": Decimal("2.5")
        }
    }
    trading_strategy.calculate_expected_profit = AsyncMock(return_value=profit_data)
    trading_strategy.calculate_liquidation_price = AsyncMock(return_value=Decimal("52000.0"))

    # Execute
    result = await trading_strategy.optimize_trading_parameters(
        symbol=symbol,
        balance=balance,
        signal_type=signal_type
    )

    # Assert high-risk adaptations
    assert result["leverage"] <= 10  # Reduced leverage in high volatility
    assert result["margin_type"] == "ISOLATED"  # Safer margin type
    assert result["position_size"] == 250.0  # Reduced position size
    assert result["current_price"] == 50000.0
    assert result["target_price"] < result["current_price"]  # Short position
    assert result["liquidation_price"] == 52000.0
    assert result["expected_profit"]["gross_profit"] == 50.0
    assert result["expected_profit"]["net_profit"] == 45.0
    assert result["market_conditions"]["volatility"] == 0.06
    assert result["market_conditions"]["trend"] == "bearish"
    assert result["account_info"]["stage"] == "micro"
    assert result["confidence"] == 0.85

@pytest.mark.asyncio
async def test_dynamic_leverage_high_volatility(trading_strategy):
    """Test leverage reduction in high volatility conditions."""
    # Setup
    symbol = "BTCUSDT"
    balance = Decimal("100000")  # Medium account
    market_data = {
        "volatility": 0.06,  # High volatility
        "trend": "neutral",
        "current_price": 50000.0
    }

    # Mock account monitor
    trading_strategy.account_monitor.get_account_stage.return_value = "medium"
    trading_strategy.account_monitor.max_leverage = {
        "micro": 10,
        "small": 20,
        "medium": 50,
        "large": 100
    }

    # Execute
    result = await trading_strategy.calculate_optimal_leverage(
        symbol=symbol,
        balance=balance,
        market_data=market_data
    )

    # Assert leverage is reduced due to high volatility
    assert result["recommended_leverage"] <= 25  # Max 50% of max leverage
    assert result["max_leverage"] == 50
    assert result["volatility"] == 0.06
    assert result["market_trend"] == "neutral"

@pytest.mark.asyncio
async def test_dynamic_leverage_bearish_trend(trading_strategy):
    """Test leverage reduction in bearish market trend."""
    # Setup
    symbol = "BTCUSDT"
    balance = Decimal("10000")  # Small account
    market_data = {
        "volatility": 0.02,  # Low volatility
        "trend": "bearish",
        "current_price": 50000.0
    }

    # Mock account monitor
    trading_strategy.account_monitor.get_account_stage.return_value = "small"
    trading_strategy.account_monitor.max_leverage = {
        "micro": 10,
        "small": 20,
        "medium": 50,
        "large": 100
    }

    # Execute
    result = await trading_strategy.calculate_optimal_leverage(
        symbol=symbol,
        balance=balance,
        market_data=market_data
    )

    # Assert leverage is reduced due to bearish trend
    assert result["recommended_leverage"] <= 15  # Reduced by 25% due to bearish trend
    assert result["max_leverage"] == 20
    assert result["volatility"] == 0.02
    assert result["market_trend"] == "bearish"

@pytest.mark.asyncio
async def test_parameter_optimization_micro_account(trading_strategy):
    """Test parameter optimization for micro account with high risk conditions."""
    # Setup
    symbol = "BTCUSDT"
    balance = Decimal("1000")  # Micro account
    signal_type = "LONG"

    # Mock market data with high risk conditions
    market_data = {
        "volatility": 0.08,  # Very high volatility
        "trend": "bearish",
        "current_price": 50000.0,
        "volume_24h": 1000000.0
    }
    trading_strategy.market_data_service.get_market_data.return_value = market_data

    # Mock account monitor for micro account
    position_data = {
        "recommended_size": "100.0",
        "stage": "micro",
        "confidence": 0.85
    }
    trading_strategy.account_monitor.calculate_position_size.return_value = position_data
    trading_strategy.account_monitor.get_account_stage.return_value = "micro"
    trading_strategy.account_monitor.max_leverage = {
        "micro": 10,
        "small": 20,
        "medium": 50,
        "large": 100
    }

    # Mock profit calculation
    profit_data = {
        "gross_profit": Decimal("10.0"),
        "total_fee": Decimal("1.0"),
        "net_profit": Decimal("9.0"),
        "roi_percentage": Decimal("9.0"),
        "fee_breakdown": {
            "entry_fee": Decimal("0.5"),
            "exit_fee": Decimal("0.5")
        }
    }
    trading_strategy.calculate_expected_profit = AsyncMock(return_value=profit_data)
    trading_strategy.calculate_liquidation_price = AsyncMock(return_value=Decimal("48000.0"))

    # Execute
    result = await trading_strategy.optimize_trading_parameters(
        symbol=symbol,
        balance=balance,
        signal_type=signal_type
    )

    # Assert conservative parameters for micro account in high risk conditions
    assert result["leverage"] <= 5  # Very conservative leverage
    assert result["margin_type"] == "ISOLATED"  # Must use isolated margin
    assert result["position_size"] == 100.0  # Small position size
    assert result["expected_profit"]["roi_percentage"] == 9.0
    assert result["market_conditions"]["volatility"] == 0.08
    assert result["market_conditions"]["trend"] == "bearish"
    assert result["account_info"]["stage"] == "micro"

@pytest.mark.asyncio
async def test_parameter_optimization_large_account(trading_strategy):
    """Test parameter optimization for large account with favorable conditions."""
    # Setup
    symbol = "BTCUSDT"
    balance = Decimal("1000000")  # Large account
    signal_type = "LONG"

    # Mock market data with favorable conditions
    market_data = {
        "volatility": 0.02,  # Low volatility
        "trend": "bullish",
        "current_price": 50000.0,
        "volume_24h": 1000000.0
    }
    trading_strategy.market_data_service.get_market_data.return_value = market_data

    # Mock account monitor for large account
    position_data = {
        "recommended_size": "100000.0",
        "stage": "large",
        "confidence": 0.95
    }
    trading_strategy.account_monitor.calculate_position_size.return_value = position_data
    trading_strategy.account_monitor.get_account_stage.return_value = "large"
    trading_strategy.account_monitor.max_leverage = {
        "micro": 10,
        "small": 20,
        "medium": 50,
        "large": 100
    }

    # Mock profit calculation
    profit_data = {
        "gross_profit": Decimal("5000.0"),
        "total_fee": Decimal("500.0"),
        "net_profit": Decimal("4500.0"),
        "roi_percentage": Decimal("4.5"),
        "fee_breakdown": {
            "entry_fee": Decimal("250.0"),
            "exit_fee": Decimal("250.0")
        }
    }
    trading_strategy.calculate_expected_profit = AsyncMock(return_value=profit_data)
    trading_strategy.calculate_liquidation_price = AsyncMock(return_value=Decimal("48000.0"))

    # Execute
    result = await trading_strategy.optimize_trading_parameters(
        symbol=symbol,
        balance=balance,
        signal_type=signal_type
    )

    # Assert aggressive parameters for large account in favorable conditions
    assert result["leverage"] >= 50  # Can use higher leverage
    assert result["margin_type"] == "CROSS"  # Can use cross margin
    assert result["position_size"] == 100000.0  # Larger position size
    assert result["expected_profit"]["roi_percentage"] == 4.5
    assert result["market_conditions"]["volatility"] == 0.02
    assert result["market_conditions"]["trend"] == "bullish"
    assert result["account_info"]["stage"] == "large"
