"""Service for monitoring trading signals and tracking accuracy in real-time."""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.repositories.signal_repository import SignalRepository
from app.services.market_analysis.market_data_service import MarketDataService

class SignalMonitor:
    """Monitor trading signals and track accuracy in real-time."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        market_data_service: MarketDataService,
        testing: bool = False
    ):
        self.signal_repository = signal_repository
        self.market_data_service = market_data_service
        self.testing = testing

    async def monitor_active_signals(self) -> List[Dict[str, Any]]:
        """Monitor all active signals and update their accuracy."""
        active_signals = await self.signal_repository.get_active_signals()
        monitoring_results = []

        for signal in active_signals:
            # Get current market data
            market_data = await self.market_data_service.get_market_data(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                testing=self.testing
            )

            # Calculate current accuracy
            accuracy = await self._calculate_signal_accuracy(signal, market_data)

            # Update signal with new data
            validation_data = {
                'market_volatility': market_data.get('volatility'),
                'market_volume': market_data.get('volume'),
                'market_phase': market_data.get('market_cycle_phase')
            }

            update_data = {
                'accuracy': accuracy,
                'last_price': market_data['current_price'],
                'last_validated_at': datetime.utcnow(),
                'validation_count': (signal.validation_count or 0) + 1,
                'market_volatility': market_data.get('volatility'),
                'market_volume': market_data.get('volume'),
                'market_sentiment': market_data.get('market_sentiment')
            }

            # Update performance tracking
            if signal.entry_price:
                price_change = (market_data['current_price'] - signal.entry_price) / signal.entry_price
                if signal.signal_type == 'long':
                    profit_loss = price_change
                else:
                    profit_loss = -price_change

                update_data['max_profit_reached'] = max(
                    signal.max_profit_reached or -float('inf'),
                    profit_loss
                )
                update_data['max_loss_reached'] = min(
                    signal.max_loss_reached or float('inf'),
                    profit_loss
                )

            # Update validation history
            validation_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'price': market_data['current_price'],
                'accuracy': accuracy,
                **validation_data
            }

            if signal.validation_history:
                update_data['validation_history'] = signal.validation_history + [validation_entry]
            else:
                update_data['validation_history'] = [validation_entry]

            # Update price history
            price_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'price': market_data['current_price']
            }

            if signal.price_updates:
                update_data['price_updates'] = signal.price_updates + [price_entry]
            else:
                update_data['price_updates'] = [price_entry]

            updated_signal = await self.signal_repository.update_signal(
                signal_id=signal.id,
                update_data=update_data
            )

            monitoring_results.append({
                'signal_id': signal.id,
                'symbol': signal.symbol,
                'timeframe': signal.timeframe,
                'current_accuracy': accuracy,
                'market_data': market_data,
                'validation_count': updated_signal.validation_count
            })

        return monitoring_results

    async def _calculate_signal_accuracy(
        self,
        signal: Any,
        market_data: Dict[str, Any]
    ) -> float:
        """Calculate current accuracy of a signal based on market data."""
        if not signal.entry_price or not market_data.get('current_price'):
            return 0.0

        # Calculate price movement
        price_change = (market_data['current_price'] - signal.entry_price) / signal.entry_price

        # Determine if prediction was correct
        if signal.signal_type == 'long':
            prediction_correct = price_change > 0
        else:  # short
            prediction_correct = price_change < 0

        # Base accuracy on prediction correctness and confidence
        base_accuracy = 1.0 if prediction_correct else 0.0

        # Adjust accuracy based on market conditions
        accuracy_adjustments = []

        # Volatility adjustment
        if market_data.get('volatility'):
            volatility_score = max(0, 1 - market_data['volatility'])
            accuracy_adjustments.append(volatility_score)

        # Volume adjustment
        if market_data.get('volume') and signal.market_volume:
            volume_ratio = market_data['volume'] / signal.market_volume
            volume_score = min(1, volume_ratio)
            accuracy_adjustments.append(volume_score)

        # Market phase alignment
        if (market_data.get('market_cycle_phase') and
            signal.market_cycle_phase == market_data['market_cycle_phase']):
            accuracy_adjustments.append(1.0)

        # Apply adjustments
        if accuracy_adjustments:
            adjustment_factor = sum(accuracy_adjustments) / len(accuracy_adjustments)
            final_accuracy = base_accuracy * (0.7 + 0.3 * adjustment_factor)
        else:
            final_accuracy = base_accuracy

        return min(max(final_accuracy, 0.0), 1.0)

    async def get_accuracy_trend(
        self,
        days: int = 30,
        timeframe: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get accuracy trend over time."""
        signals = await self.signal_repository.get_historical_predictions(
            timeframe=timeframe,
            days=days
        )

        # Group signals by date
        accuracy_by_date = {}
        for signal in signals:
            if not signal.accuracy:
                continue

            date_key = signal.created_at.date().isoformat()
            if date_key not in accuracy_by_date:
                accuracy_by_date[date_key] = {
                    'accuracies': [],
                    'total_signals': 0
                }

            accuracy_by_date[date_key]['accuracies'].append(signal.accuracy)
            accuracy_by_date[date_key]['total_signals'] += 1

        # Calculate daily averages
        trend_data = []
        for date_key, data in sorted(accuracy_by_date.items()):
            if data['accuracies']:
                avg_accuracy = sum(data['accuracies']) / len(data['accuracies'])
                trend_data.append({
                    'date': date_key,
                    'average_accuracy': avg_accuracy,
                    'total_signals': data['total_signals']
                })

        return trend_data

    async def analyze_signal_performance(
        self,
        timeframe: Optional[str] = None,
        min_confidence: float = 0.85
    ) -> Dict[str, Any]:
        """Analyze overall signal performance and accuracy."""
        stats = await self.signal_repository.get_accuracy_statistics(timeframe=timeframe)
        trend = await self.get_accuracy_trend(days=7, timeframe=timeframe)

        return {
            'average_accuracy': stats['average_accuracy'],
            'max_accuracy': stats['max_accuracy'],
            'min_accuracy': stats['min_accuracy'],
            'total_signals': stats['total_signals'],
            'recent_trend': trend
        }
