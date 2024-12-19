import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import os
from collections import deque
import numpy as np
from ..web_scraping.ensemble_analyzer import EnsembleSentimentAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealTimeAccuracyMonitor:
    def __init__(self, window_size: int = 1000):
        """Initialize the real-time accuracy monitor."""
        self.window_size = window_size
        self.predictions = deque(maxlen=window_size)
        self.english_analyzer = EnsembleSentimentAnalyzer('english')
        self.chinese_analyzer = EnsembleSentimentAnalyzer('chinese')
        self.accuracy_history = []
        self.confidence_threshold = 0.85

    def add_prediction(self, text: str, predicted_sentiment: str,
                      confidence: float, actual_sentiment: Optional[str] = None,
                      timestamp: Optional[datetime] = None) -> None:
        """Add a new prediction to the monitoring window."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        prediction = {
            'text': text,
            'predicted': predicted_sentiment,
            'confidence': confidence,
            'actual': actual_sentiment,
            'timestamp': timestamp,
            'verified': actual_sentiment is not None
        }

        self.predictions.append(prediction)
        self._update_accuracy_metrics()

    def _update_accuracy_metrics(self) -> None:
        """Update accuracy metrics based on verified predictions."""
        verified_predictions = [p for p in self.predictions if p['verified']]
        if not verified_predictions:
            return

        correct_predictions = sum(
            1 for p in verified_predictions
            if p['predicted'] == p['actual']
        )
        total_predictions = len(verified_predictions)
        accuracy = correct_predictions / total_predictions

        high_confidence_predictions = [
            p for p in verified_predictions
            if p['confidence'] >= self.confidence_threshold
        ]
        if high_confidence_predictions:
            high_conf_correct = sum(
                1 for p in high_confidence_predictions
                if p['predicted'] == p['actual']
            )
            high_conf_accuracy = high_conf_correct / len(high_confidence_predictions)
        else:
            high_conf_accuracy = 0.0

        self.accuracy_history.append({
            'timestamp': datetime.utcnow(),
            'overall_accuracy': accuracy,
            'high_confidence_accuracy': high_conf_accuracy,
            'total_predictions': total_predictions,
            'high_confidence_predictions': len(high_confidence_predictions)
        })

    def get_current_accuracy(self) -> Dict[str, float]:
        """Get current accuracy metrics."""
        if not self.accuracy_history:
            return {
                'overall_accuracy': 0.0,
                'high_confidence_accuracy': 0.0,
                'total_predictions': 0,
                'high_confidence_predictions': 0
            }
        return self.accuracy_history[-1]

    def analyze_error_patterns(self) -> Dict[str, any]:
        """Analyze patterns in incorrect predictions."""
        verified_predictions = [p for p in self.predictions if p['verified']]
        if not verified_predictions:
            return {}

        error_patterns = {
            'confidence_distribution': {
                'low': 0,
                'medium': 0,
                'high': 0
            },
            'sentiment_confusion': {
                'bullish_as_bearish': 0,
                'bullish_as_neutral': 0,
                'bearish_as_bullish': 0,
                'bearish_as_neutral': 0,
                'neutral_as_bullish': 0,
                'neutral_as_bearish': 0
            },
            'time_based_errors': {
                'morning': 0,
                'afternoon': 0,
                'evening': 0,
                'night': 0
            }
        }

        for pred in verified_predictions:
            if pred['predicted'] != pred['actual']:
                # Analyze confidence distribution
                if pred['confidence'] < 0.5:
                    error_patterns['confidence_distribution']['low'] += 1
                elif pred['confidence'] < 0.8:
                    error_patterns['confidence_distribution']['medium'] += 1
                else:
                    error_patterns['confidence_distribution']['high'] += 1

                # Analyze sentiment confusion
                confusion_key = f"{pred['actual']}_as_{pred['predicted']}"
                if confusion_key in error_patterns['sentiment_confusion']:
                    error_patterns['sentiment_confusion'][confusion_key] += 1

                # Analyze time-based errors
                hour = pred['timestamp'].hour
                if 6 <= hour < 12:
                    error_patterns['time_based_errors']['morning'] += 1
                elif 12 <= hour < 18:
                    error_patterns['time_based_errors']['afternoon'] += 1
                elif 18 <= hour < 24:
                    error_patterns['time_based_errors']['evening'] += 1
                else:
                    error_patterns['time_based_errors']['night'] += 1

        return error_patterns

    def get_accuracy_trend(self, days: int = 30) -> List[Dict[str, any]]:
        """Get accuracy trend over specified number of days."""
        if not self.accuracy_history:
            return []

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        trend_data = [
            entry for entry in self.accuracy_history
            if entry['timestamp'] >= cutoff_date
        ]

        return [{
            'date': entry['timestamp'].strftime('%Y-%m-%d'),
            'overall_accuracy': entry['overall_accuracy'],
            'high_confidence_accuracy': entry['high_confidence_accuracy'],
            'total_predictions': entry['total_predictions']
        } for entry in trend_data]

    def save_metrics(self, file_path: str) -> None:
        """Save accuracy metrics to file."""
        metrics = {
            'current_accuracy': self.get_current_accuracy(),
            'error_patterns': self.analyze_error_patterns(),
            'accuracy_trend': self.get_accuracy_trend(),
            'last_updated': datetime.utcnow().isoformat()
        }

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4, default=str)

    def load_metrics(self, file_path: str) -> None:
        """Load accuracy metrics from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert stored metrics back to appropriate format
            if 'accuracy_trend' in data:
                for entry in data['accuracy_trend']:
                    entry_data = {
                        'timestamp': datetime.fromisoformat(entry['date']),
                        'overall_accuracy': entry['overall_accuracy'],
                        'high_confidence_accuracy': entry['high_confidence_accuracy'],
                        'total_predictions': entry['total_predictions']
                    }
                    self.accuracy_history.append(entry_data)
        except FileNotFoundError:
            logger.warning(f"No existing metrics file found at {file_path}")
        except Exception as e:
            logger.error(f"Error loading metrics: {str(e)}")

    def get_improvement_suggestions(self) -> List[str]:
        """Generate suggestions for improving accuracy."""
        suggestions = []
        current_accuracy = self.get_current_accuracy()
        error_patterns = self.analyze_error_patterns()

        if current_accuracy['overall_accuracy'] < 0.85:
            suggestions.append(
                "Overall accuracy below target threshold of 85%. "
                "Consider retraining models with more recent data."
            )

        # Analyze confidence distribution
        conf_dist = error_patterns.get('confidence_distribution', {})
        if conf_dist.get('high', 0) > 0:
            suggestions.append(
                "High confidence predictions are resulting in errors. "
                "Review confidence calculation algorithm."
            )

        # Analyze sentiment confusion
        sent_conf = error_patterns.get('sentiment_confusion', {})
        for pattern, count in sent_conf.items():
            if count > 0:
                suggestions.append(
                    f"Frequent confusion between {pattern.replace('_as_', ' and ')}. "
                    "Consider adding more training examples for these cases."
                )

        # Analyze time-based patterns
        time_errors = error_patterns.get('time_based_errors', {})
        max_time_errors = max(time_errors.items(), key=lambda x: x[1])
        if max_time_errors[1] > 0:
            suggestions.append(
                f"Higher error rate during {max_time_errors[0]} hours. "
                "Consider time-specific model adjustments."
            )

        return suggestions

    def adjust_confidence_threshold(self) -> None:
        """Dynamically adjust confidence threshold based on accuracy patterns."""
        verified_predictions = [p for p in self.predictions if p['verified']]
        if not verified_predictions:
            return

        confidence_accuracies = []
        for threshold in np.arange(0.5, 1.0, 0.05):
            high_conf_preds = [
                p for p in verified_predictions
                if p['confidence'] >= threshold
            ]
            if high_conf_preds:
                correct = sum(
                    1 for p in high_conf_preds
                    if p['predicted'] == p['actual']
                )
                accuracy = correct / len(high_conf_preds)
                confidence_accuracies.append((threshold, accuracy))

        if confidence_accuracies:
            # Find the lowest threshold that achieves 85% accuracy
            for threshold, accuracy in sorted(confidence_accuracies):
                if accuracy >= 0.85:
                    self.confidence_threshold = threshold
                    logger.info(
                        f"Adjusted confidence threshold to {threshold:.2f} "
                        f"(accuracy: {accuracy:.2f})"
                    )
                    break
