"""Script to run the prediction system and identify current trading opportunities."""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.services.market_analysis.market_data_service import MarketDataService
from app.services.analysis.prediction_analyzer import PredictionAnalyzer
from app.services.trading_strategy.strategy import TradingStrategy
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.trading.pair_selector import PairSelector
from app.repositories.signal_repository import SignalRepository
from app.services.monitoring.signal_monitor import SignalMonitor

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/crypto_trading"

async def run_predictions(balance: Decimal = Decimal("100")):
    """Run predictions to find current trading opportunities."""
    try:
        # Initialize database
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # Initialize core services with proper dependency injection chain
        market_data_service = MarketDataService()

        # Initialize monitoring services with database session
        signal_repository = SignalRepository(session=db_session)
        account_monitor = AccountMonitor(market_data_service=market_data_service)
        signal_monitor = SignalMonitor(
            market_data_service=market_data_service,
            signal_repository=signal_repository
        )

        # Initialize pair selection and trading services
        pair_selector = PairSelector(
            market_data_service=market_data_service,
            account_monitor=account_monitor
        )

        # Initialize trading strategy with 82% minimum accuracy threshold
        strategy = TradingStrategy(
            account_monitor=account_monitor,
            pair_selector=pair_selector,
            market_data_service=market_data_service,
            min_accuracy_threshold=0.82
        )

        # Initialize prediction analyzer for accuracy tracking
        prediction_analyzer = PredictionAnalyzer(
            signal_repository=signal_repository,
            min_accuracy_threshold=0.82
        )

        # Base pairs to analyze (high liquidity pairs suitable for growth)
        base_pairs = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT",
            "XRP/USDT", "ADA/USDT", "AVAX/USDT", "MATIC/USDT"
        ]

        # Get suitable pairs based on account balance
        suitable_pairs = await strategy.select_trading_pairs(
            balance=balance,
            base_pairs=base_pairs,
            min_confidence=0.85  # Higher confidence for actual trades
        )

        if not suitable_pairs:
            print("没有找到符合置信度标准的交易对。")
            return []

        opportunities = []
        for pair in suitable_pairs:
            # Get market data
            market_data = await market_data_service.get_market_data(pair["symbol"])

            # Generate trading signal
            signal = await strategy.generate_signal(
                balance=balance,
                symbol=pair["symbol"],
                signal_type="long" if market_data.get("trend") == "bullish" else "short",
                confidence=pair["confidence"]
            )

            if signal and signal["confidence"] >= 0.82:  # Enforce minimum accuracy threshold
                # Analyze prediction accuracy
                accuracy_metrics = await prediction_analyzer.analyze_prediction(
                    symbol=pair["symbol"],
                    prediction_type=signal["signal_type"],
                    confidence=signal["confidence"]
                )

                if accuracy_metrics["historical_accuracy"] >= 0.82:
                    opportunities.append({
                        "pair": pair["symbol"],
                        "signal_type": signal["signal_type"],
                        "entry_price": market_data["current_price"],
                        "take_profit": signal["take_profit"],
                        "stop_loss": signal["stop_loss"],
                        "position_size": signal["position_size"],
                        "confidence": signal["confidence"],
                        "historical_accuracy": accuracy_metrics["historical_accuracy"],
                        "market_conditions": signal["market_conditions"],
                        "timestamp": signal["timestamp"],
                        "staged_entry": signal.get("entry_stages", None),
                        "entry_conditions": signal.get("entry_conditions", []),
                        "fees": market_data.get("trading_fees", {
                            "maker": 0.001,
                            "taker": 0.001
                        })
                    })

        return opportunities

    except Exception as e:
        print(f"运行预测时出错: {str(e)}")
        return []

if __name__ == "__main__":
    opportunities = asyncio.run(run_predictions())

    if opportunities:
        print("\n=== 当前交易机会 ===")
        for opp in opportunities:
            print(f"\n交易对: {opp['pair']}")
            print(f"信号类型: {'做多' if opp['signal_type'] == 'long' else '做空'}")
            print(f"入场价格: {opp['entry_price']:.2f} USDT")
            print(f"止盈价格: {opp['take_profit']:.2f} USDT")
            print(f"止损价格: {opp['stop_loss']:.2f} USDT")
            print(f"仓位大小: {opp['position_size']:.2f} USDT")
            print(f"置信度: {opp['confidence']:.2%}")
            print(f"历史准确率: {opp['historical_accuracy']:.2%}")

            # Calculate potential profit/loss
            position_value = opp['position_size']
            maker_fee = position_value * opp['fees']['maker']
            taker_fee = position_value * opp['fees']['taker']
            total_fees = maker_fee + taker_fee

            potential_profit = (opp['take_profit'] - opp['entry_price']) * opp['position_size'] - total_fees
            potential_loss = (opp['entry_price'] - opp['stop_loss']) * opp['position_size'] + total_fees

            print(f"\n交易费用:")
            print(f"  - Maker费用: {maker_fee:.2f} USDT")
            print(f"  - Taker费用: {taker_fee:.2f} USDT")
            print(f"  - 总费用: {total_fees:.2f} USDT")
            print(f"\n盈亏预测:")
            print(f"  - 潜在盈利: {potential_profit:.2f} USDT")
            print(f"  - 潜在亏损: {potential_loss:.2f} USDT")

            print(f"\n市场状况:")
            print(f"  - 24小时成交量: {opp['market_conditions']['volume_24h']:,.0f} USDT")
            print(f"  - 波动率: {opp['market_conditions']['volatility']:.2%}")
            print(f"  - 趋势: {'上涨' if opp['market_conditions']['trend'] == 'bullish' else '下跌'}")

            if opp.get('staged_entry'):
                print("\n分批入场点:")
                for i, stage in enumerate(opp['staged_entry'], 1):
                    print(f"  第{i}批: {stage:.2f} USDT")

            if opp.get('entry_conditions'):
                print("\n入场条件:")
                for condition in opp['entry_conditions']:
                    print(f"  - {condition['description']}: {condition['price']:.2f} USDT ({condition['type']})")
            print("-" * 50)
    else:
        print("\n当前没有满足最低置信度要求(82%)的交易机会。")
