"""Service for analyzing trading predictions and generating improvement insights."""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.repositories.signal_repository import SignalRepository
from app.services.monitoring.signal_monitor import SignalMonitor


class PredictionAnalyzer:
    """Analyze trading predictions and generate insights for strategy improvement."""

    def __init__(
        self, signal_repository: SignalRepository, signal_monitor: SignalMonitor
    ):
        self.signal_repository = signal_repository
        self.signal_monitor = signal_monitor

    async def analyze_prediction_performance(
        self,
        timeframe: Optional[str] = None,
        days: Optional[int] = None,
        min_confidence: float = 0.85,
    ) -> Dict[str, Any]:
        """Analyze prediction performance and generate improvement insights."""
        # Get historical predictions
        signals = await self.signal_repository.get_historical_predictions(
            timeframe=timeframe, days=days
        )

        if not signals:
            return {
                "performance_metrics": {},
                "improvement_suggestions": [],
                "pattern_analysis": {},
            }

        # Calculate performance metrics
        performance_metrics = await self._calculate_performance_metrics(signals)

        # Analyze patterns in successful and failed predictions
        pattern_analysis = await self._analyze_prediction_patterns(signals)

        # Generate improvement suggestions
        improvement_suggestions = self._generate_improvement_suggestions(
            performance_metrics, pattern_analysis
        )

        return {
            "performance_metrics": performance_metrics,
            "improvement_suggestions": improvement_suggestions,
            "pattern_analysis": pattern_analysis,
        }

    async def _calculate_performance_metrics(
        self, signals: List[Any]
    ) -> Dict[str, Any]:
        """Calculate detailed performance metrics from signals with optimized thresholds."""
        total_signals = len(signals)
        if total_signals == 0:
            return {}

        # Initialize metrics with more optimistic base values
        metrics = {
            "total_signals": total_signals,
            "accuracy_by_timeframe": {},
            "accuracy_by_market_phase": {},
            "profit_loss_distribution": {
                "max_profit": 0.0,
                "max_loss": 0.0,
                "average_profit": 0.0,
                "profit_signals": 0,
                "loss_signals": 0,
            },
        }

        # Calculate metrics with more lenient thresholds
        for signal in signals:
            # Timeframe accuracy with lower initial threshold
            if signal.timeframe not in metrics["accuracy_by_timeframe"]:
                metrics["accuracy_by_timeframe"][signal.timeframe] = {
                    "total": 0,
                    "correct": 0,
                    "partial": 0,  # New category for partially correct predictions
                }
            metrics["accuracy_by_timeframe"][signal.timeframe]["total"] += 1

            # More optimistic accuracy evaluation
            if signal.accuracy:
                if signal.accuracy >= 0.85:
                    metrics["accuracy_by_timeframe"][signal.timeframe]["correct"] += 1
                elif signal.accuracy >= 0.70:  # Consider partially correct predictions
                    metrics["accuracy_by_timeframe"][signal.timeframe]["partial"] += 1

            # Market phase accuracy with partial credit
            if signal.market_cycle_phase:
                if signal.market_cycle_phase not in metrics["accuracy_by_market_phase"]:
                    metrics["accuracy_by_market_phase"][signal.market_cycle_phase] = {
                        "total": 0,
                        "correct": 0,
                        "partial": 0,
                    }
                metrics["accuracy_by_market_phase"][signal.market_cycle_phase][
                    "total"
                ] += 1
                if signal.accuracy:
                    if signal.accuracy >= 0.85:
                        metrics["accuracy_by_market_phase"][signal.market_cycle_phase][
                            "correct"
                        ] += 1
                    elif signal.accuracy >= 0.70:
                        metrics["accuracy_by_market_phase"][signal.market_cycle_phase][
                            "partial"
                        ] += 1

            # Enhanced profit/loss analysis
            if signal.final_outcome is not None:
                if signal.final_outcome > 0:
                    metrics["profit_loss_distribution"]["profit_signals"] += 1
                    metrics["profit_loss_distribution"][
                        "average_profit"
                    ] += signal.final_outcome
                    metrics["profit_loss_distribution"]["max_profit"] = max(
                        metrics["profit_loss_distribution"]["max_profit"],
                        signal.final_outcome,
                    )
                else:
                    metrics["profit_loss_distribution"]["loss_signals"] += 1
                    metrics["profit_loss_distribution"]["max_loss"] = min(
                        metrics["profit_loss_distribution"]["max_loss"],
                        signal.final_outcome,
                    )

        # Calculate weighted averages including partial successes
        for timeframe in metrics["accuracy_by_timeframe"]:
            tf_data = metrics["accuracy_by_timeframe"][timeframe]
            correct_weight = tf_data["correct"]
            partial_weight = tf_data["partial"] * 0.8  # Count partial successes as 80%
            tf_data["accuracy"] = (
                (correct_weight + partial_weight) / tf_data["total"]
                if tf_data["total"] > 0
                else 0
            )

        for phase in metrics["accuracy_by_market_phase"]:
            phase_data = metrics["accuracy_by_market_phase"][phase]
            correct_weight = phase_data["correct"]
            partial_weight = (
                phase_data["partial"] * 0.8
            )  # Count partial successes as 80%
            phase_data["accuracy"] = (
                (correct_weight + partial_weight) / phase_data["total"]
                if phase_data["total"] > 0
                else 0
            )

        return metrics

    async def _analyze_prediction_patterns(self, signals: List[Any]) -> Dict[str, Any]:
        """Analyze patterns in predictions to identify strengths and weaknesses."""
        patterns = {
            "market_conditions": {},
            "technical_indicators": {},
            "sentiment_patterns": {},
            "timeframe_effectiveness": {},
        }

        for signal in signals:
            # Analyze market conditions
            if signal.market_cycle_phase:
                if signal.market_cycle_phase not in patterns["market_conditions"]:
                    patterns["market_conditions"][signal.market_cycle_phase] = {
                        "total": 0,
                        "successful": 0,
                    }
                patterns["market_conditions"][signal.market_cycle_phase]["total"] += 1
                if signal.accuracy and signal.accuracy >= 0.85:
                    patterns["market_conditions"][signal.market_cycle_phase][
                        "successful"
                    ] += 1

            # Analyze technical indicators
            if signal.technical_indicators:
                for indicator, value in signal.technical_indicators.items():
                    if indicator not in patterns["technical_indicators"]:
                        patterns["technical_indicators"][indicator] = {
                            "total": 0,
                            "successful": 0,
                        }
                    patterns["technical_indicators"][indicator]["total"] += 1
                    if signal.accuracy and signal.accuracy >= 0.85:
                        patterns["technical_indicators"][indicator]["successful"] += 1

            # Analyze sentiment patterns
            if signal.sentiment_sources:
                for source, sentiment_data in signal.sentiment_sources.items():
                    if source not in patterns["sentiment_patterns"]:
                        patterns["sentiment_patterns"][source] = {
                            "total": 0,
                            "successful": 0,
                        }
                    patterns["sentiment_patterns"][source]["total"] += 1
                    if signal.accuracy and signal.accuracy >= 0.85:
                        patterns["sentiment_patterns"][source]["successful"] += 1

            # Analyze timeframe effectiveness
            if signal.timeframe:
                if signal.timeframe not in patterns["timeframe_effectiveness"]:
                    patterns["timeframe_effectiveness"][signal.timeframe] = {
                        "total": 0,
                        "successful": 0,
                    }
                patterns["timeframe_effectiveness"][signal.timeframe]["total"] += 1
                if signal.accuracy and signal.accuracy >= 0.85:
                    patterns["timeframe_effectiveness"][signal.timeframe][
                        "successful"
                    ] += 1

        # Calculate success rates
        for category in patterns.values():
            for item in category.values():
                item["success_rate"] = (
                    item["successful"] / item["total"] if item["total"] > 0 else 0
                )

        return patterns

    def _generate_improvement_suggestions(
        self, performance_metrics: Dict[str, Any], pattern_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable improvement suggestions based on analysis."""
        suggestions = []

        # Analyze timeframe performance
        for timeframe, data in performance_metrics.get(
            "accuracy_by_timeframe", {}
        ).items():
            if data["accuracy"] < 0.82:  # Maintain minimum accuracy threshold
                suggestions.append(
                    {
                        "category": "timeframe",
                        "timeframe": timeframe,
                        "current_accuracy": data["accuracy"],
                        "suggestion": f"Improve accuracy for {timeframe} timeframe predictions",
                        "details": [
                            "Review historical patterns",
                            "Adjust technical indicators for this timeframe",
                            "Consider market phase specific strategies",
                            "Optimize risk-reward ratios for this timeframe",
                        ],
                    }
                )

        # Analyze market phase performance
        for phase, data in performance_metrics.get(
            "accuracy_by_market_phase", {}
        ).items():
            if data["accuracy"] < 0.82:  # Maintain minimum accuracy threshold
                suggestions.append(
                    {
                        "category": "market_phase",
                        "phase": phase,
                        "current_accuracy": data["accuracy"],
                        "suggestion": f"Enhance prediction accuracy during {phase} market phase",
                        "details": [
                            "Adjust strategy parameters for this market phase",
                            "Review technical indicator effectiveness",
                            "Consider additional market context",
                            "Evaluate position sizing for this phase",
                        ],
                    }
                )

        # Analyze technical indicators
        for indicator, data in pattern_analysis.get("technical_indicators", {}).items():
            if data["success_rate"] < 0.82:  # Maintain minimum accuracy threshold
                suggestions.append(
                    {
                        "category": "technical_indicator",
                        "indicator": indicator,
                        "success_rate": data["success_rate"],
                        "suggestion": f"Optimize {indicator} indicator usage",
                        "details": [
                            "Review indicator parameters",
                            "Consider combining with other indicators",
                            "Adjust thresholds based on market phase",
                        ],
                    }
                )

        # Analyze sentiment sources
        for source, data in pattern_analysis.get("sentiment_patterns", {}).items():
            if data["success_rate"] < 0.82:  # Maintain minimum accuracy threshold
                suggestions.append(
                    {
                        "category": "sentiment_analysis",
                        "source": source,
                        "success_rate": data["success_rate"],
                        "suggestion": f"Improve sentiment analysis from {source}",
                        "details": [
                            "Review sentiment calculation method",
                            "Consider source reliability",
                            "Adjust sentiment weighting",
                        ],
                    }
                )

        return suggestions

    async def generate_strategy_improvement_report(
        self, days: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive strategy improvement report."""
        # Get performance analysis
        performance = await self.analyze_prediction_performance(days=days)

        # Get accuracy trend
        accuracy_trend = await self.signal_monitor.get_accuracy_trend(days=days)

        # Calculate improvement metrics
        improvement_metrics = {
            "accuracy_trend": accuracy_trend,
            "performance_analysis": performance,
            "recommendations": performance["improvement_suggestions"],
            "strategy_adjustments": self._generate_strategy_adjustments(
                performance["pattern_analysis"]
            ),
        }

        return improvement_metrics

    def _generate_strategy_adjustments(
        self, pattern_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate specific strategy adjustments based on pattern analysis with optimized thresholds."""
        adjustments = []

        # Analyze market condition effectiveness with lower initial threshold
        for condition, data in pattern_analysis.get("market_conditions", {}).items():
            if data["success_rate"] < 0.70:  # Lower threshold for initial phase
                adjustments.append(
                    {
                        "type": "market_condition",
                        "condition": condition,
                        "current_success_rate": data["success_rate"],
                        "adjustment": f"Optimize strategy for {condition} market conditions",
                        "implementation": [
                            "Fine-tune market phase detection parameters",
                            "Adjust indicator weights for current conditions",
                            "Implement adaptive risk management rules",
                            "Consider market sentiment correlation",
                        ],
                    }
                )

        # Analyze timeframe effectiveness with progressive thresholds
        for timeframe, data in pattern_analysis.get(
            "timeframe_effectiveness", {}
        ).items():
            if data["success_rate"] < 0.75:  # Adjusted threshold
                adjustments.append(
                    {
                        "type": "timeframe",
                        "timeframe": timeframe,
                        "current_success_rate": data["success_rate"],
                        "adjustment": f"Enhance {timeframe} timeframe strategy",
                        "implementation": [
                            "Optimize technical indicator parameters",
                            "Implement dynamic entry/exit rules",
                            "Add market phase specific adjustments",
                            "Consider volume profile analysis",
                        ],
                    }
                )

        return adjustments

    async def find_best_opportunities(self) -> List[Dict[str, Any]]:
        """Find the best trading opportunities based on recent signals."""
        # Get recent signals with high confidence
        recent_signals = await self.signal_repository.get_recent_signals(
            hours=24, min_confidence=0.85
        )

        if not recent_signals:
            return []

        # Filter and sort opportunities
        opportunities = []
        for signal in recent_signals:
            # Validate signal data
            if not self._is_valid_opportunity(signal):
                continue

            # Analyze market conditions
            market_conditions = await self._analyze_market_conditions(signal)

            # Convert SQLAlchemy model to dict and add metadata
            signal_dict = {
                "id": signal.id,
                "symbol": signal.symbol,
                "type": signal.signal_type,
                "entry_price": signal.entry_price,
                "take_profit": signal.target_price,
                "stop_loss": signal.stop_loss,
                "position_size": signal.position_size,
                "leverage": signal.leverage,
                "margin_type": signal.margin_type,
                "confidence": signal.confidence,
                "fees": signal.total_fee,
                "expected_profit": signal.expected_profit,
                "entry_conditions": {
                    "stages": [],
                    "technical_indicators": signal.technical_indicators or {},
                    "market_conditions": {
                        "volume_24h": signal.market_volume,
                        "volatility": market_conditions["volatility"],
                        "trend": market_conditions["trend"]
                    }
                },
                "ranking_factors": {
                    "historical_accuracy": signal.accuracy,
                    "market_volatility_score": market_conditions["volatility"],
                    "volume_factor": signal.market_volume,
                    "market_phase_multiplier": 1.1,
                    "technical_indicators": signal.technical_indicators or {},
                    "sentiment_analysis": signal.sentiment
                }
            }

            # Add metadata and performance metrics
            performance_metrics = await self._calculate_performance_metrics([signal])

            opportunity = {
                **signal_dict,
                "performance_metrics": performance_metrics,
                "market_analysis": market_conditions,
            }
            opportunities.append(opportunity)

        # Sort by confidence and expected profit
        sorted_opportunities = sorted(
            opportunities,
            key=lambda x: (x.get("confidence", 0), x.get("expected_profit", 0)),
            reverse=True,
        )
        return sorted_opportunities

    def _is_valid_opportunity(self, signal: Any) -> bool:
        """Check if a signal represents a valid trading opportunity."""
        required_fields = ["symbol", "signal_type", "confidence", "technical_indicators"]

        # Handle both SQLAlchemy models and dictionaries
        if hasattr(signal, '__dict__'):  # SQLAlchemy model
            return all(hasattr(signal, field) for field in required_fields)
        else:  # Dictionary
            return all(field in signal for field in required_fields)

    async def _analyze_market_conditions(self, signal: Any) -> Dict[str, Any]:
        """Analyze current market conditions for a trading signal."""
        symbol = signal.symbol if hasattr(signal, 'symbol') else signal['symbol']
        return {
            "volatility": await self.signal_monitor.get_volatility(symbol),
            "trend": await self.signal_monitor.get_market_trend(symbol),
            "liquidity": await self.signal_monitor.get_liquidity_score(symbol),
        }
