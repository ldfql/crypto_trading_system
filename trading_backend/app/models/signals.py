"""Trading signal model definitions for long-term signal storage and accuracy tracking."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradingSignal(Base):
    """Model for storing trading signals with comprehensive accuracy tracking."""
    __tablename__ = 'trading_signals'

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    signal_type = Column(String, nullable=False)  # 'long' or 'short'
    timeframe = Column(String, nullable=False)  # '1h', '4h', '1d', '1w', etc.
    entry_price = Column(Float, nullable=False)
    target_price = Column(Float)
    stop_loss = Column(Float)
    confidence = Column(Float, nullable=False)
    accuracy = Column(Float)
    sentiment = Column(String)  # 'bullish', 'bearish', or 'neutral'
    source = Column(String)  # Source of the trading signal (e.g., 'technical', 'sentiment', 'ensemble')

    # Market context at prediction time
    market_cycle_phase = Column(String)
    market_volatility = Column(Float)
    market_volume = Column(Float)
    market_sentiment = Column(String)

    # Position and prediction details
    position_size = Column(Float)  # Recommended position size based on account balance
    entry_reason = Column(Text)  # Detailed reasoning for entry
    technical_indicators = Column(JSON)  # Key technical indicators at entry
    sentiment_sources = Column(JSON)  # Sources contributing to sentiment analysis

    # Temporal tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_validated_at = Column(DateTime)
    validation_count = Column(Integer, default=0)

    # Performance tracking
    max_profit_reached = Column(Float)
    max_loss_reached = Column(Float)
    final_outcome = Column(Float)  # Actual profit/loss when signal expires
    accuracy_improvement = Column(Float)  # How much the accuracy improved from this signal

    # Real-time monitoring
    last_price = Column(Float)  # Last known price during monitoring
    price_updates = Column(JSON)  # Historical price updates during signal lifetime
    validation_history = Column(JSON)  # History of accuracy validations

    def __repr__(self):
        return (
            f"<TradingSignal("
            f"symbol='{self.symbol}', "
            f"type='{self.signal_type}', "
            f"timeframe='{self.timeframe}', "
            f"confidence={self.confidence}, "
            f"accuracy={self.accuracy}"
            f")>"
        )
