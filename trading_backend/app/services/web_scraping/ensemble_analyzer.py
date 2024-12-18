from typing import List, Dict, Tuple, Any, Optional
import logging
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import os
from .sentiment_analyzer import SentimentAnalyzer
from app.services.monitoring.technical_indicators import TechnicalIndicators
from app.services.market_analysis.market_cycle_analyzer import MarketCycleAnalyzer

logger = logging.getLogger(__name__)

class EnsembleSentimentAnalyzer:
    """Ensemble sentiment analyzer combining multiple analysis methods."""

    def __init__(self, language: str = 'english', model_cache_dir: Optional[str] = None):
        """Initialize ensemble analyzer with component weights and language support."""
        self.language = language.lower()
        self.model_cache_dir = model_cache_dir
        self.model = None
        self.tokenizer = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Initialize components
        self.sentiment_analyzer = SentimentAnalyzer()
        self.technical_indicators = TechnicalIndicators()
        self.market_analyzer = MarketCycleAnalyzer()

        # Component weights for ensemble voting with balanced weights
        self.base_weights = {
            'bert': 0.4,        # BERT sentiment weight
            'technical': 0.4,   # Technical analysis weight
            'market': 0.2       # Market context weight
        }

        # Standardize label mappings across all methods
        self.label_mapping = {
            'positive': 'bullish',
            'negative': 'bearish',
            'neutral': 'neutral',
            'bullish': 'bullish',
            'bearish': 'bearish'
        }

        # Label indices for model outputs
        self.label_map = {'bearish': 0, 'neutral': 1, 'bullish': 2}

        # Confidence thresholds - adjusted for better accuracy
        self.min_confidence = 0.25  # Lower minimum threshold to allow more signals
        self.high_confidence = 0.80  # Slightly lower high confidence threshold
        self.neutral_confidence = 0.40  # Lower neutral threshold to reduce neutral classifications

        # Initialize model synchronously in constructor
        self._sync_initialize_model()

    def _sync_initialize_model(self):
        """Synchronous initialization of the model."""
        try:
            # Select model based on language
            model_name = 'ProsusAI/finbert' if self.language == 'english' else 'bert-base-chinese'
            model_path = os.path.join('models', 'chinese_bert_finetuned') if self.language == 'chinese' else None

            if model_path and os.path.exists(model_path):
                logger.info(f"Loading fine-tuned Chinese BERT model from {model_path}")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    model_path,
                    num_labels=3,
                    cache_dir=self.model_cache_dir
                )
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    cache_dir=self.model_cache_dir
                )
            else:
                logger.info(f"Loading {model_name} model")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    model_name,
                    num_labels=3,
                    cache_dir=self.model_cache_dir
                )
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    cache_dir=self.model_cache_dir
                )

            # Ensure model is in evaluation mode and on correct device
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Model initialization complete for {self.language} language")

        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            raise

    async def initialize_model(self):
        """Initialize BERT model with proper configuration."""
        try:
            # Load FinBERT model and tokenizer
            self.model = AutoModelForSequenceClassification.from_pretrained(
                'ProsusAI/finbert',
                num_labels=3,
                cache_dir=self.model_cache_dir
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                'ProsusAI/finbert',
                cache_dir=self.model_cache_dir
            )

            # Ensure model is in evaluation mode
            self.model.eval()

            # Verify label mapping
            # FinBERT's output mapping: 0=negative (bearish), 1=neutral, 2=positive (bullish)
            test_texts = [
                "Strong buy signal with increasing volume",  # Should be bullish
                "Market showing significant weakness",       # Should be bearish
                "Price consolidating in range"              # Should be neutral
            ]

            # Validate model outputs
            for text in test_texts:
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True
                )
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probs = torch.softmax(outputs.logits, dim=1)
                    prediction = torch.argmax(probs, dim=1).item()
                    logger.info(f"Test prediction for '{text}': {prediction}")

            logger.info("Model initialization and validation complete")

        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            raise

    async def _get_bert_sentiment(self, text: str) -> Dict[str, Any]:
        """Get BERT sentiment analysis results."""
        try:
            sentiment_score, confidence = await self.sentiment_analyzer._get_bert_sentiment(text)

            # Map sentiment score to categorical sentiment with wider thresholds
            if sentiment_score > 0.2:  # Less strict threshold for bullish
                sentiment = 'bullish'
                confidence *= 1.2  # Boost confidence for clear signals
            elif sentiment_score < -0.2:  # Less strict threshold for bearish
                sentiment = 'bearish'
                confidence *= 1.2  # Boost confidence for clear signals
            else:
                sentiment = 'neutral'
                confidence *= 0.7  # Reduce confidence for neutral predictions

            return {
                'sentiment': sentiment,
                'confidence': min(0.95, confidence),
                'score': sentiment_score
            }

        except Exception as e:
            logger.error(f"Error in BERT sentiment analysis: {str(e)}")
            return {
                'sentiment': 'neutral',
                'confidence': self.min_confidence,
                'score': 0.0
            }

    async def _apply_technical_rules(self, text: str) -> Dict[str, Any]:
        """Apply technical analysis rules to identify patterns and signals."""
        try:
            # Initialize pattern scores
            bullish_score = 0.0
            bearish_score = 0.0
            pattern_count = 0

            # Define technical patterns with weights
            bullish_patterns = {
                'golden cross': 0.9,
                'breakout': 0.8,
                'support': 0.7,
                'strong volume': 0.7,
                'accumulation': 0.6,
                'higher low': 0.6,
                'uptrend': 0.8,
                'double bottom': 0.8,
                'bullish divergence': 0.7,
                'oversold': 0.6
            }

            bearish_patterns = {
                'death cross': 0.9,
                'resistance': 0.7,
                'breakdown': 0.8,
                'weak volume': 0.7,
                'distribution': 0.6,
                'lower high': 0.6,
                'downtrend': 0.8,
                'double top': 0.8,
                'bearish divergence': 0.7,
                'overbought': 0.6
            }

            # Convert text to lowercase for pattern matching
            text_lower = text.lower()

            # Check for bullish patterns
            for pattern, weight in bullish_patterns.items():
                if pattern in text_lower:
                    bullish_score += weight
                    pattern_count += 1
                    logger.info(f"Found bullish pattern: {pattern}, weight: {weight}")

            # Check for bearish patterns
            for pattern, weight in bearish_patterns.items():
                if pattern in text_lower:
                    bearish_score += weight
                    pattern_count += 1
                    logger.info(f"Found bearish pattern: {pattern}, weight: {weight}")

            # Calculate final sentiment and confidence
            total_score = bullish_score + bearish_score

            # Determine sentiment based on pattern scores
            if pattern_count == 0:
                sentiment = 'neutral'
                confidence = 0.25  # Low confidence when no patterns found
            else:
                # Calculate normalized scores
                if total_score > 0:
                    bullish_ratio = bullish_score / total_score
                    bearish_ratio = bearish_score / total_score

                    # Strong signal threshold
                    if bullish_ratio > 0.6:
                        sentiment = 'bullish'
                        confidence = min(0.95, bullish_ratio * (1 + (pattern_count * 0.1)))
                    elif bearish_ratio > 0.6:
                        sentiment = 'bearish'
                        confidence = min(0.95, bearish_ratio * (1 + (pattern_count * 0.1)))
                    else:
                        sentiment = 'neutral'
                        confidence = 0.4  # Moderate confidence for mixed signals
                else:
                    sentiment = 'neutral'
                    confidence = 0.25  # Low confidence when no clear direction

            logger.info(f"Technical analysis - Sentiment: {sentiment}, Confidence: {confidence}")
            logger.info(f"Pattern scores - Bullish: {bullish_score}, Bearish: {bearish_score}")

            return {
                'sentiment': sentiment,
                'confidence': confidence,
                'details': {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'pattern_count': pattern_count
                }
            }

        except Exception as e:
            logger.error(f"Error in technical rules analysis: {str(e)}")
            return {'sentiment': 'neutral', 'confidence': self.min_confidence}

    async def _analyze_market_context(self, text: str) -> Dict[str, Any]:
        """Analyze market context and institutional activity."""
        try:
            # Initialize scores
            bullish_score = 0.0
            bearish_score = 0.0
            context_count = 0

            # Market context indicators with weights
            bullish_indicators = {
                'institutional buying': 0.9,
                'accumulation': 0.8,
                'strong demand': 0.8,
                'market cycle bottom': 0.9,
                'oversold': 0.7,
                'higher low': 0.7,
                'support level': 0.7,
                'bullish divergence': 0.8,
                'increasing volume': 0.7,
                'market strength': 0.7
            }

            bearish_indicators = {
                'institutional selling': 0.9,
                'distribution': 0.8,
                'weak demand': 0.8,
                'market cycle top': 0.9,
                'overbought': 0.7,
                'lower high': 0.7,
                'resistance level': 0.7,
                'bearish divergence': 0.8,
                'decreasing volume': 0.7,
                'market weakness': 0.7
            }

            text_lower = text.lower()

            # Check for bullish indicators
            for indicator, weight in bullish_indicators.items():
                if indicator in text_lower:
                    bullish_score += weight
                    context_count += 1

            # Check for bearish indicators
            for indicator, weight in bearish_indicators.items():
                if indicator in text_lower:
                    bearish_score += weight
                    context_count += 1

            # Calculate final sentiment and confidence
            total_score = bullish_score + bearish_score

            # Determine sentiment based on market context
            if context_count == 0:
                sentiment = 'neutral'
                confidence = 0.25  # Low confidence when no context found
            else:
                # Calculate normalized scores
                if total_score > 0:
                    bullish_ratio = bullish_score / total_score
                    bearish_ratio = bearish_score / total_score

                    # Strong signal threshold
                    if bullish_ratio > 0.6:
                        sentiment = 'bullish'
                        confidence = min(0.95, bullish_ratio * (1 + (context_count * 0.1)))
                    elif bearish_ratio > 0.6:
                        sentiment = 'bearish'
                        confidence = min(0.95, bearish_ratio * (1 + (context_count * 0.1)))
                    else:
                        sentiment = 'neutral'
                        confidence = 0.4  # Moderate confidence for mixed signals
                else:
                    sentiment = 'neutral'
                    confidence = 0.25  # Low confidence when no clear direction

            return {
                'sentiment': sentiment,
                'confidence': confidence,
                'details': {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'context_count': context_count
                }
            }

        except Exception as e:
            logger.error(f"Error in market context analysis: {str(e)}")
            return {'sentiment': 'neutral', 'confidence': self.min_confidence}

    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment using ensemble of methods."""
        try:
            # Get sentiment from each component
            bert_result = await self._get_bert_sentiment(text)
            technical_result = await self._apply_technical_rules(text)
            market_result = await self._analyze_market_context(text)

            # Extract individual sentiments and confidences
            sentiments = {
                'bert': bert_result['sentiment'],
                'technical': technical_result['sentiment'],
                'market': market_result['sentiment']
            }
            confidences = {
                'bert': bert_result['confidence'],
                'technical': technical_result['confidence'],
                'market': market_result['confidence']
            }

            # Initialize sentiment scores
            sentiment_scores = {
                'bullish': 0.0,
                'bearish': 0.0,
                'neutral': 0.0
            }

            # Calculate weighted sentiment scores with enhanced technical weighting
            for source, sentiment in sentiments.items():
                base_weight = self.base_weights[source]
                confidence = confidences[source]

                # Significantly boost technical analysis weight for strong signals
                if source == 'technical':
                    if confidence > 0.8:
                        base_weight *= 2.0  # Double weight for strong technical signals
                    elif confidence > 0.6:
                        base_weight *= 1.5  # 50% boost for moderate technical signals

                # Reduce BERT weight when it conflicts with strong technical or market signals
                if source == 'bert':
                    if technical_result['confidence'] > 0.8 and sentiment != technical_result['sentiment']:
                        base_weight *= 0.5  # Reduce BERT weight more aggressively
                    elif market_result['confidence'] > 0.8 and sentiment != market_result['sentiment']:
                        base_weight *= 0.7  # Moderate reduction for market conflicts

                # Apply weighted vote
                weight = base_weight * confidence
                sentiment_scores[sentiment] += weight

            # Normalize scores
            total_score = sum(sentiment_scores.values())
            if total_score > 0:
                sentiment_scores = {k: v/total_score for k, v in sentiment_scores.items()}

            # Add bias against neutral predictions
            if max(sentiment_scores.values()) < 0.5:  # No strong signal
                neutral_penalty = 0.3  # Increased penalty
                for sentiment in ['bullish', 'bearish']:
                    sentiment_scores[sentiment] *= (1 + neutral_penalty)
                total = sum(sentiment_scores.values())
                sentiment_scores = {k: v/total for k, v in sentiment_scores.items()}

            # Determine final sentiment based on highest weighted score
            final_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])[0]

            # Calculate agreement score with higher weight for technical agreement
            agreement_count = sum(1 for s in sentiments.values() if s == final_sentiment)
            tech_agreement = 1 if technical_result['sentiment'] == final_sentiment else 0
            agreement_score = (agreement_count + tech_agreement) / (len(sentiments) + 1)

            # Calculate confidence with stronger technical weighting
            base_confidence = sum(
                (self.base_weights[source] * 2.0 if source == 'technical' else self.base_weights[source])
                * conf for source, conf in confidences.items()
            )

            # Adjust confidence based on agreement and sentiment strength
            agreement_boost = agreement_score * 0.5  # Increased from 0.4
            sentiment_strength = max(sentiment_scores.values())
            strength_boost = sentiment_strength * 0.4  # Increased from 0.3

            final_confidence = min(0.95, base_confidence + agreement_boost + strength_boost)

            # Reduce confidence for disagreements less aggressively
            if agreement_score < 0.67:  # Less than 2/3 agreement
                final_confidence *= 0.85  # Changed from 0.8
            elif sentiment_scores['neutral'] > 0.25:  # Lowered threshold further
                final_confidence *= 0.9

            # Ensure minimum confidence threshold
            final_confidence = max(self.min_confidence, final_confidence)

            logger.info(f"Ensemble analysis - Final: {final_sentiment}, Confidence: {final_confidence}")
            logger.info(f"Component sentiments: {sentiments}")
            logger.info(f"Component confidences: {confidences}")
            logger.info(f"Sentiment scores: {sentiment_scores}")

            return {
                'sentiment': final_sentiment,
                'confidence': final_confidence,
                'components': {
                    'bert': bert_result,
                    'technical': technical_result,
                    'market': market_result
                }
            }

        except Exception as e:
            logger.error(f"Error in ensemble sentiment analysis: {str(e)}")
            return {'sentiment': 'neutral', 'confidence': self.min_confidence}
