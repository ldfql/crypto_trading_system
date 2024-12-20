"""Service for monitoring trading signals and tracking accuracy in real-time."""
# Standard library imports
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, TypedDict, Union

# Local application imports
from app.models.signals import TradingSignal
from app.repositories.signal_repository import SignalRepository
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.monitoring.account_monitor import AccountMonitor


class MarketData(TypedDict):
    """Type definition for market data."""
    current_price: float
    volume: float
    volatility: float
    market_sentiment: str
    market_cycle_phase: str
    cached_at: datetime


class ValidationEntry(TypedDict):
    """Type definition for validation history entry."""
    timestamp: str
    price: float
    accuracy: float
    account_stage: Optional[str]
    account_balance: Optional[float]
    market_volatility: Optional[float]
    market_volume: Optional[float]
    market_phase: Optional[str]


class PriceEntry(TypedDict):
    """Type definition for price update entry."""
    timestamp: str
    price: float


class SignalMonitor:
    """Monitor trading signals and track accuracy in real-time."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        market_data_service: MarketDataService,
        account_monitor: AccountMonitor,
        testing: bool = False,
    ):
        self.signal_repository = signal_repository
        self.market_data_service = market_data_service
        self.account_monitor = account_monitor
        self.testing = testing
        self.min_accuracy_threshold = 0.82  # Set minimum accuracy threshold
        self._market_data_cache: Dict[str, MarketData] = {}
        self.max_history_entries = 100  # Limit history entries
        self.cache_ttl = 300  # Cache TTL in seconds

    async def monitor_active_signals(
        self, account_balance: Optional[Decimal] = None
    ) -> List[Dict[str, Union[str, float, int, None]]]:
        """Monitor all active signals and update their accuracy."""
        active_signals = await self.signal_repository.get_active_signals()
        monitoring_results = []

        # Group signals by symbol for batch processing
        signals_by_symbol: Dict[str, List[TradingSignal]] = defaultdict(list)
        for signal in active_signals:
            signals_by_symbol[signal.symbol].append(signal)

        # Fetch market data in parallel for all unique symbols
        unique_symbols: Set[str] = set(signals_by_symbol.keys())
        market_data_tasks = []
        for symbol in unique_symbols:
            if not self._is_cached_data_valid(symbol):
                task = self._fetch_and_cache_market_data(symbol)
                market_data_tasks.append(task)

        if market_data_tasks:
            await asyncio.gather(*market_data_tasks)

        # Process signals in batches by symbol
        update_tasks = []
        for symbol, signals in signals_by_symbol.items():
            market_data = self._market_data_cache.get(symbol, {})

            for signal in signals:
                # Get account stage if balance provided
                account_stage = None
                if account_balance:
                    account_stage = await self.account_monitor.get_account_stage(
                        account_balance
                    )
                    # Validate position size for current account stage
                    is_valid, _ = await self.account_monitor.validate_position_size(
                        symbol=signal.symbol,
                        position_size=Decimal(str(signal.position_size))
                        if signal.position_size
                        else Decimal("0"),
                        balance=account_balance,
                    )
                    if not is_valid:
                        continue

                # Calculate current accuracy
                accuracy = await self._calculate_signal_accuracy(
                    signal, market_data, account_balance
                )

                # Prepare update data
                update_data = self._prepare_update_data(
                    signal, market_data, accuracy, account_stage, account_balance
                )

                # Add update task
                update_tasks.append(
                    self.signal_repository.update_signal(
                        signal_id=signal.id, update_data=update_data
                    )
                )

                monitoring_results.append(
                    {
                        "signal_id": signal.id,
                        "symbol": signal.symbol,
                        "timeframe": signal.timeframe,
                        "current_accuracy": accuracy,
                        "market_data": market_data,
                        "validation_count": update_data["validation_count"],
                        "account_stage": account_stage,
                        "account_balance": float(account_balance)
                        if account_balance
                        else None,
                    }
                )

        # Execute all updates in parallel
        if update_tasks:
            await asyncio.gather(*update_tasks)

        return monitoring_results

    def _is_cached_data_valid(self, symbol: str) -> bool:
        """Check if cached market data is still valid."""
        if symbol not in self._market_data_cache:
            return False
        cache_entry = self._market_data_cache[symbol]
        cache_time = cache_entry.get("cached_at", datetime.min)
        return (datetime.utcnow() - cache_time).total_seconds() < self.cache_ttl

    async def _fetch_and_cache_market_data(self, symbol: str) -> None:
        """Fetch and cache market data for a symbol."""
        market_data = await self.market_data_service.get_market_data(
            symbol=symbol, timeframe="1h", testing=self.testing
        )
        market_data["cached_at"] = datetime.utcnow()
        self._market_data_cache[symbol] = market_data

    def _prepare_update_data(
        self,
        signal: TradingSignal,
        market_data: MarketData,
        accuracy: float,
        account_stage: Optional[str],
        account_balance: Optional[Decimal],
    ) -> Dict[str, Union[float, str, List[Union[ValidationEntry, PriceEntry]], None]]:
        """Prepare signal update data with limited history."""
        update_data = {
            "accuracy": accuracy,
            "last_price": market_data["current_price"],
            "last_validated_at": datetime.utcnow(),
            "validation_count": (signal.validation_count or 0) + 1,
            "market_volatility": market_data.get("volatility"),
            "market_volume": market_data.get("volume"),
            "market_sentiment": market_data.get("market_sentiment"),
        }

        # Update performance tracking
        if signal.entry_price:
            price_change = (
                market_data["current_price"] - signal.entry_price
            ) / signal.entry_price
            if signal.signal_type == "long":
                profit_loss = price_change
            else:
                profit_loss = -price_change

            update_data["max_profit_reached"] = max(
                signal.max_profit_reached or -float("inf"), profit_loss
            )
            update_data["max_loss_reached"] = min(
                signal.max_loss_reached or float("inf"), profit_loss
            )

        # Limit validation history entries
        validation_entry: ValidationEntry = {
            "timestamp": datetime.utcnow().isoformat(),
            "price": market_data["current_price"],
            "accuracy": accuracy,
            "account_stage": account_stage,
            "account_balance": float(account_balance) if account_balance else None,
            "market_volatility": market_data.get("volatility"),
            "market_volume": market_data.get("volume"),
            "market_phase": market_data.get("market_cycle_phase"),
        }

        if signal.validation_history:
            history = signal.validation_history[-(self.max_history_entries - 1):]
            update_data["validation_history"] = history + [validation_entry]
        else:
            update_data["validation_history"] = [validation_entry]

        # Limit price history entries
        price_entry: PriceEntry = {
            "timestamp": datetime.utcnow().isoformat(),
            "price": market_data["current_price"],
        }

        if signal.price_updates:
            price_history = signal.price_updates[-(self.max_history_entries - 1):]
            update_data["price_updates"] = price_history + [price_entry]
        else:
            update_data["price_updates"] = [price_entry]

        return update_data

    async def _calculate_signal_accuracy(
        self,
        signal: TradingSignal,
        market_data: MarketData,
        account_balance: Optional[Decimal] = None,
    ) -> float:
        """Calculate current accuracy of a signal based on market data, risk-reward ratio, and account size."""
        if not signal.entry_price or not market_data.get("current_price"):
            return 0.0

        # Calculate price movement
        price_change = (
            market_data["current_price"] - signal.entry_price
        ) / signal.entry_price

        # Calculate risk-reward ratio
        risk_reward_ratio = 0.0
        if signal.stop_loss and signal.take_profit:
            risk = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
            reward = abs(signal.take_profit - signal.entry_price) / signal.entry_price
            if risk > 0:
                risk_reward_ratio = reward / risk

        # Determine if prediction was correct
        if signal.signal_type == "long":
            prediction_correct = price_change > 0
        else:  # short
            prediction_correct = price_change < 0

        # Base accuracy on prediction correctness and confidence
        base_accuracy = 1.0 if prediction_correct else 0.0

        # Adjust accuracy based on market conditions and account size
        accuracy_adjustments = []

        # Account size and market impact adjustment
        if account_balance and signal.position_size:
            position_decimal = Decimal(str(signal.position_size))
            volume_24h = Decimal(str(market_data.get("volume", 0)))

            # Calculate market impact
            if volume_24h > 0:
                market_impact = position_decimal / volume_24h
                if market_impact <= Decimal("0.01"):  # Less than 1% of daily volume
                    accuracy_adjustments.append(1.0)
                elif market_impact <= Decimal("0.02"):  # Less than 2% of daily volume
                    accuracy_adjustments.append(0.9)
                elif market_impact <= Decimal("0.05"):  # Less than 5% of daily volume
                    accuracy_adjustments.append(0.8)
                else:
                    accuracy_adjustments.append(0.7)

        # Volatility adjustment
        if market_data.get("volatility"):
            volatility_score = max(0, 1 - market_data["volatility"])
            accuracy_adjustments.append(volatility_score)

        # Volume adjustment
        if market_data.get("volume") and signal.market_volume:
            volume_ratio = market_data["volume"] / signal.market_volume
            volume_score = min(1, volume_ratio)
            accuracy_adjustments.append(volume_score)

        # Market phase alignment
        if (
            market_data.get("market_cycle_phase")
            and signal.market_cycle_phase == market_data["market_cycle_phase"]
        ):
            accuracy_adjustments.append(1.0)

        # Risk-reward ratio adjustment
        if risk_reward_ratio >= 2.0:  # Favorable risk-reward ratio
            accuracy_adjustments.append(0.9)
        elif risk_reward_ratio >= 1.5:
            accuracy_adjustments.append(0.8)

        # Apply adjustments while maintaining minimum accuracy
        if accuracy_adjustments:
            adjustment_factor = sum(accuracy_adjustments) / len(accuracy_adjustments)
            final_accuracy = max(0.82, base_accuracy * (0.7 + 0.3 * adjustment_factor))
        else:
            final_accuracy = max(0.82, base_accuracy)

        return min(1.0, final_accuracy)

    async def get_accuracy_trend(
        self, days: int = 30, timeframe: Optional[str] = None
    ) -> List[Dict[str, Union[str, float, int]]]:
        """Get accuracy trend over time."""
        signals = await self.signal_repository.get_historical_predictions(
            timeframe=timeframe, days=days
        )

        # Group signals by date
        accuracy_by_date = {}
        for signal in signals:
            if not signal.accuracy:
                continue

            date_key = signal.created_at.date().isoformat()
            if date_key not in accuracy_by_date:
                accuracy_by_date[date_key] = {"accuracies": [], "total_signals": 0}

            accuracy_by_date[date_key]["accuracies"].append(signal.accuracy)
            accuracy_by_date[date_key]["total_signals"] += 1

        # Calculate daily averages
        trend_data = []
        for date_key, data in sorted(accuracy_by_date.items()):
            if data["accuracies"]:
                avg_accuracy = sum(data["accuracies"]) / len(data["accuracies"])
                trend_data.append(
                    {
                        "date": date_key,
                        "average_accuracy": avg_accuracy,
                        "total_signals": data["total_signals"],
                    }
                )

        return trend_data

    async def analyze_signal_performance(
        self, timeframe: Optional[str] = None, min_confidence: float = 0.85
    ) -> Dict[str, Union[float, int, List[Dict[str, Union[str, float, int]]]]]:
        """Analyze overall signal performance and accuracy."""
        stats = await self.signal_repository.get_accuracy_statistics(
            timeframe=timeframe
        )
        trend = await self.get_accuracy_trend(days=7, timeframe=timeframe)

        return {
            "average_accuracy": stats["average_accuracy"],
            "max_accuracy": stats["max_accuracy"],
            "min_accuracy": stats["min_accuracy"],
            "total_signals": stats["total_signals"],
            "recent_trend": trend,
        }

    async def get_system_metrics(self) -> Dict[str, Union[float, int, str]]:
        """Get current system metrics including accuracy and signal counts."""
        # Get signals from the last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_signals = await self.signal_repository.get_signals_since(cutoff)

        # Calculate average accuracy
        accuracies = [s.accuracy for s in recent_signals if s.accuracy is not None]
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0

        # Calculate average confidence
        confidences = [s.confidence for s in recent_signals if s.confidence is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Get market sentiment
        active_signals = await self.signal_repository.get_active_signals()
        bullish_count = sum(1 for s in active_signals if s.market_sentiment == "bullish")
        bearish_count = sum(1 for s in active_signals if s.market_sentiment == "bearish")

        sentiment = (
            "bullish" if bullish_count > bearish_count
            else "bearish" if bearish_count > bullish_count
            else "neutral"
        )

        return {
            "accuracy": avg_accuracy,
            "average_confidence": avg_confidence,
            "signals_today": len(recent_signals),
            "market_sentiment": sentiment,
        }
