from typing import Dict, Any, List, Tuple
import logging
import torch
import torch.nn.functional as F
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    def __init__(self, language: str = "english"):
        """Initialize the sentiment analyzer with enhanced preprocessing."""
        self.language = language
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Device set to use {self.device}")

        # Financial terms with sentiment scores and importance weights
        self.financial_terms = {
            # Strong bullish indicators (weight: 1.0)
            "strong buy": (1.0, 1.0),
            "breakout confirmed": (1.0, 1.0),
            "golden cross": (1.0, 1.0),
            "double bottom": (1.0, 1.0),
            # Moderate bullish indicators (weight: 0.8)
            "accumulation": (0.8, 0.8),
            "higher highs": (0.8, 0.8),
            "bullish divergence": (0.8, 0.8),
            "support holding": (0.8, 0.8),
            # Weak bullish indicators (weight: 0.6)
            "buy": (0.6, 0.6),
            "uptrend": (0.6, 0.6),
            "long": (0.6, 0.6),
            # Strong bearish indicators (weight: -1.0)
            "strong sell": (-1.0, 1.0),
            "breakdown confirmed": (-1.0, 1.0),
            "death cross": (-1.0, 1.0),
            "double top": (-1.0, 1.0),
            # Moderate bearish indicators (weight: -0.8)
            "distribution": (-0.8, 0.8),
            "lower lows": (-0.8, 0.8),
            "bearish divergence": (-0.8, 0.8),
            "resistance broken": (-0.8, 0.8),
            # Weak bearish indicators (weight: -0.6)
            "sell": (-0.6, 0.6),
            "downtrend": (-0.6, 0.6),
            "short": (-0.6, 0.6),
        }

        # Technical patterns with improved scoring
        self.technical_patterns = {
            "double bottom": 0.95,
            "inverse head and shoulders": 0.90,
            "golden cross": 0.85,
            "bullish divergence": 0.80,
            "higher highs": 0.75,
            "support holding": 0.70,
            "volume increasing": 0.65,
            "double top": -0.95,
            "head and shoulders": -0.90,
            "death cross": -0.85,
            "bearish divergence": -0.80,
            "lower lows": -0.75,
            "resistance break": -0.70,
            "volume decreasing": -0.65,
        }

        # Trading rules with adjusted weights
        self.trading_rules = {
            "uptrend": 0.85,
            "downtrend": -0.85,
            "breakout": 0.75,
            "breakdown": -0.75,
            "accumulation": 0.65,
            "distribution": -0.65,
            "strong support": 0.55,
            "strong resistance": -0.55,
        }

        # Initialize BERT model and tokenizer
        self._initialize_model()

        # Confidence thresholds with adjusted values for better accuracy
        self.min_confidence = 0.45  # Increased minimum confidence
        self.high_confidence = 0.85  # Maintained high confidence threshold
        self.neutral_confidence = 0.60  # Increased neutral confidence threshold

        # Pattern matching weights with increased BERT emphasis
        self.pattern_weight = 0.35  # Reduced pattern weight
        self.bert_weight = 0.65  # Increased BERT weight for better accuracy

        # Initialize accuracy tracking
        self.accuracy_history = []

    def _initialize_model(self):
        """Initialize the appropriate BERT model based on language."""
        try:
            if self.language == "chinese":
                # Try to load fine-tuned model first, fall back to base model if not available
                model_path = os.path.join("models", "chinese_bert_finetuned")
                if os.path.exists(model_path):
                    self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                    self.model = AutoModelForSequenceClassification.from_pretrained(
                        model_path, num_labels=3  # bearish, neutral, bullish
                    ).to(self.device)
                    logger.info(
                        "Successfully initialized fine-tuned Chinese BERT model"
                    )
                else:
                    model_name = "bert-base-chinese"
                    self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                    self.model = AutoModelForSequenceClassification.from_pretrained(
                        model_name, num_labels=3
                    ).to(self.device)
                    logger.warning(
                        "Fine-tuned model not found, using base Chinese BERT model"
                    )
            else:  # default to English
                model_name = "ProsusAI/finbert"
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    model_name
                ).to(self.device)
                logger.info("Successfully initialized English FinBERT model")

            # Set model to evaluation mode
            self.model.eval()

        except Exception as e:
            logger.error(f"Error initializing BERT model: {str(e)}")
            raise

    async def analyze_content(self, text: str) -> Tuple[float, float]:
        """Analyze content with enhanced preprocessing and pattern matching."""
        try:
            if not text:
                return 0.0, 0.0

            # Get component predictions with detailed logging
            bert_score, bert_confidence = await self._get_bert_sentiment(text)
            logger.debug(
                f"BERT sentiment: {bert_score:.3f}, confidence: {bert_confidence:.3f}"
            )

            technical_score = self._detect_technical_patterns(text)
            logger.debug(f"Technical score: {technical_score:.3f}")

            trading_score = self._apply_trading_rules(text)
            logger.debug(f"Trading score: {trading_score:.3f}")

            # Calculate pattern-based sentiment with increased weights
            pattern_sentiment = 0.0
            pattern_confidence = 0.0
            matched_terms = 0

            text_lower = text.lower()
            for term, (score, weight) in self.financial_terms.items():
                if term in text_lower:
                    pattern_sentiment += score * weight * 1.2  # Increased weight
                    pattern_confidence += weight * 1.2  # Increased confidence
                    matched_terms += 1
                    logger.debug(
                        f"Matched term '{term}': score={score}, weight={weight}"
                    )

            # Normalize pattern-based sentiment with higher base confidence
            if matched_terms > 0:
                pattern_sentiment /= matched_terms
                pattern_confidence = min(
                    self.high_confidence, pattern_confidence / matched_terms * 1.5
                )  # Higher boost

            logger.debug(
                f"Pattern sentiment: {pattern_sentiment:.3f}, confidence: {pattern_confidence:.3f}"
            )

            # Combine signals with weighted average - increased BERT weight
            weights = [0.45, 0.25, 0.15, 0.15]  # BERT weight increased to 0.45
            signals = [bert_score, pattern_sentiment, technical_score, trading_score]

            final_sentiment = sum(w * s for w, s in zip(weights, signals))

            # Calculate base confidence with higher weights
            confidences = [
                bert_confidence * 1.2,  # Increased BERT confidence
                pattern_confidence * 1.1,  # Increased pattern confidence
                abs(technical_score),  # Technical confidence
                abs(trading_score),  # Trading confidence
            ]

            base_confidence = max(confidences)
            logger.debug(f"Base confidence scores: {[f'{c:.3f}' for c in confidences]}")

            # Boost confidence if multiple methods agree with lower threshold
            signs = [np.sign(s) for s in signals if abs(s) > 0.1]  # Lower threshold
            if len(set(signs)) == 1 and len(signs) >= 2:
                final_confidence = min(
                    base_confidence * 2.0, self.high_confidence
                )  # Higher boost
                logger.debug(f"Agreement boost applied: {len(signs)} signals agree")
            else:
                final_confidence = max(base_confidence, self.min_confidence)
                logger.debug(f"No agreement boost: {len(set(signs))} different signs")

            # Track prediction
            self.track_accuracy(final_sentiment, final_confidence)

            logger.info(
                f"Final sentiment: {final_sentiment:.3f}, confidence: {final_confidence:.3f}"
            )
            return float(np.clip(final_sentiment, -1.0, 1.0)), float(final_confidence)

        except Exception as e:
            logger.error(f"Error in content analysis: {e}")
            return 0.0, 0.0

    async def analyze_text(self, text: str) -> Tuple[float, float]:
        """Alias for analyze_content for backward compatibility."""
        return await self.analyze_content(text)

    async def _get_bert_sentiment(self, text: str) -> Tuple[float, float]:
        """Get sentiment from BERT model with improved confidence calculation."""
        try:
            # Tokenize and prepare input
            inputs = self.tokenizer(
                text, return_tensors="pt", padding=True, truncation=True, max_length=512
            ).to(self.device)

            # Get model outputs
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = F.softmax(logits, dim=1)

                # Get probability distribution
                probs = probabilities.squeeze().cpu().numpy()

                # Calculate entropy-based confidence
                entropy = -np.sum(probs * np.log2(probs + 1e-10))
                max_entropy = -np.log2(1 / 3)  # Maximum entropy for 3 classes
                entropy_confidence = 1 - (entropy / max_entropy)

                # Get predicted class and its probability
                pred_class = torch.argmax(probabilities, dim=1).item()
                class_prob = probs[pred_class]

                # Calculate margin of confidence
                sorted_probs = np.sort(probs)[::-1]
                margin = sorted_probs[0] - sorted_probs[1]
                margin_confidence = min(1.0, margin * 2.0)  # Scale margin to [0, 1]

                # Combine confidence metrics with adjusted weights
                base_confidence = (
                    entropy_confidence * 0.3
                    + class_prob * 0.5  # Reduced weight for entropy
                    + margin_confidence  # Increased weight for class probability
                    * 0.2  # Margin-based confidence
                )

                # Map sentiment to score (-1 to 1)
                # FinBERT: 0=negative/bearish, 1=neutral, 2=positive/bullish
                # Chinese BERT: 0=positive/bullish, 1=neutral, 2=negative/bearish
                if self.language == "english":
                    sentiment_map = {0: -1.0, 1: 0.0, 2: 1.0}
                else:  # Chinese model
                    sentiment_map = {
                        0: 0.8,
                        1: 0.0,
                        2: -0.8,
                    }  # Adjusted scale for Chinese model

                base_score = sentiment_map.get(pred_class, 0.0)
                sentiment_score = base_score * class_prob

                # Adjust confidence based on prediction strength
                if abs(sentiment_score) < 0.3:
                    final_confidence = (
                        base_confidence * 0.8
                    )  # Reduce confidence for weak predictions
                elif abs(sentiment_score) > 0.7:
                    final_confidence = min(
                        base_confidence * 1.1, 1.0
                    )  # Boost confidence for strong predictions
                else:
                    final_confidence = base_confidence

                # Ensure minimum confidence threshold
                final_confidence = max(self.min_confidence, min(final_confidence, 0.95))

                return sentiment_score, float(final_confidence)

        except Exception as e:
            logger.error(f"Error in BERT sentiment analysis: {e}")
            return 0.0, self.min_confidence

    def _detect_technical_patterns(self, text: str) -> float:
        """Detect technical patterns with enhanced scoring."""
        try:
            text_lower = text.lower()

            # Strong bullish patterns with maximum weights
            strong_bullish = {
                "golden cross": 1.0,
                "inverse head and shoulders": 1.0,
                "double bottom": 0.95,
                "bullish breakout": 0.95,
                "higher lows": 0.9,
            }

            # Strong bearish patterns with maximum weights
            strong_bearish = {
                "death cross": -1.0,
                "head and shoulders": -1.0,
                "double top": -0.95,
                "bearish breakdown": -0.95,
                "lower highs": -0.9,
            }

            # Calculate pattern scores with maximum boost
            score = 0.0
            weight_sum = 0.0

            for pattern, weight in strong_bullish.items():
                if pattern in text_lower:
                    score += weight * 2.5
                    weight_sum += abs(weight)

            for pattern, weight in strong_bearish.items():
                if pattern in text_lower:
                    score += weight * 2.5
                    weight_sum += abs(weight)

            if weight_sum > 0:
                final_score = score / weight_sum
                return float(np.clip(final_score, -1.0, 1.0))

            return 0.0

        except Exception as e:
            logger.error(f"Error in technical pattern detection: {e}")
            return 0.0

    def _apply_trading_rules(self, text: str) -> float:
        """Apply trading rules to text and return sentiment score."""
        score = 0.0
        text = text.lower()
        matched_rules = 0

        for rule, rule_score in self.trading_rules.items():
            if rule in text:
                score += rule_score
                matched_rules += 1

        if matched_rules > 0:
            score /= matched_rules
            # Apply non-linear boost for multiple rule matches
            if matched_rules > 1:
                score *= 1 + 0.1 * (matched_rules - 1)

        return float(np.clip(score, -1.0, 1.0))

    def track_accuracy(self, sentiment: float, confidence: float) -> None:
        """Track prediction accuracy for monitoring."""
        self.accuracy_history.append(
            {
                "timestamp": datetime.now(),
                "sentiment": sentiment,
                "confidence": confidence,
            }
        )

        # Keep only recent history
        if len(self.accuracy_history) > 100:
            self.accuracy_history = self.accuracy_history[-100:]
