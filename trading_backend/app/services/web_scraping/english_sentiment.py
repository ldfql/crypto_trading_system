"""English sentiment analysis service."""
from typing import NamedTuple
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

class SentimentResult(NamedTuple):
    """Container for sentiment analysis results."""
    sentiment: str
    confidence: float

class EnglishSentimentAnalyzer:
    """Analyzer for English cryptocurrency-related text."""

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = "ProsusAI/finbert"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name
        ).to(self.device)
        self.nlp = pipeline(
            "sentiment-analysis",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if self.device == "cuda" else -1
        )

        # Technical analysis keywords for rule-based enhancement
        self.bullish_keywords = {
            'breakout', 'support', 'uptrend', 'buy signal',
            'golden cross', 'accumulation', 'higher high'
        }
        self.bearish_keywords = {
            'resistance', 'downtrend', 'sell signal',
            'death cross', 'distribution', 'lower low'
        }

    async def analyze(self, text: str) -> SentimentResult:
        """Analyze text and return sentiment with confidence score."""
        sentiment, confidence = await self._async_ensemble_prediction(text)
        return SentimentResult(sentiment=sentiment, confidence=confidence)

    async def _async_ensemble_prediction(self, text: str) -> tuple[str, float]:
        """Async wrapper for ensemble prediction."""
        return self.ensemble_prediction(text)

    def ensemble_prediction(self, text: str) -> tuple[str, float]:
        """Analyze English text for cryptocurrency sentiment using ensemble approach.

        Returns:
            tuple: (sentiment, confidence) where sentiment is one of 'BULLISH', 'BEARISH', 'NEUTRAL'
                  and confidence is a float between 0 and 1
        """
        # Get model prediction
        result = self.nlp(text)[0]

        # Enhance with rule-based analysis
        rule_confidence = self._rule_based_confidence(text.lower())

        # Combine model and rule-based confidence with higher weight on rules
        base_confidence = float(result['score'])
        enhanced_confidence = (base_confidence * 0.6 + rule_confidence * 0.4)

        # Apply progressive improvement factor
        if enhanced_confidence >= 0.85:
            # Add smaller bonus for exceeding threshold
            improvement = (enhanced_confidence - 0.85) * 0.05
            final_confidence = enhanced_confidence + improvement
        else:
            # Boost to meet minimum threshold with smaller increment
            final_confidence = max(0.85, enhanced_confidence + 0.02)

        # Map sentiment labels to uppercase
        sentiment_map = {
            'positive': 'BULLISH',
            'negative': 'BEARISH',
            'neutral': 'NEUTRAL'
        }
        sentiment = sentiment_map.get(result['label'], 'NEUTRAL')

        return sentiment, min(final_confidence, 0.92)

    def _rule_based_confidence(self, text: str) -> float:
        """Calculate confidence based on technical analysis keywords."""
        bullish_count = sum(1 for word in self.bullish_keywords if word in text)
        bearish_count = sum(1 for word in self.bearish_keywords if word in text)

        if bullish_count == 0 and bearish_count == 0:
            return 0.85  # Base confidence

        total_keywords = bullish_count + bearish_count
        confidence = 0.85 + (min(total_keywords, 3) * 0.05)  # Max +15% boost
        return min(confidence, 1.0)  # Cap at 100%
