"""Signal repository for database operations."""
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.signals import TradingSignal
from ..models.futures import FuturesConfig

class SignalRepository:
    """Repository for managing trading signals."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def create_signal(self, signal: TradingSignal) -> TradingSignal:
        """Create a new trading signal."""
        self.session.add(signal)
        self.session.commit()
        self.session.refresh(signal)
        return signal

    def get_signal(self, signal_id: int) -> Optional[TradingSignal]:
        """Get trading signal by ID."""
        return self.session.query(TradingSignal).filter(TradingSignal.id == signal_id).first()

    def get_signals(self, limit: int = 100) -> List[TradingSignal]:
        """Get recent trading signals."""
        return self.session.query(TradingSignal).order_by(TradingSignal.created_at.desc()).limit(limit).all()

    def update_signal(self, signal_id: int, futures_config: FuturesConfig) -> Optional[TradingSignal]:
        """Update trading signal with futures configuration."""
        signal = self.get_signal(signal_id)
        if signal:
            # Convert Decimal values to strings for JSON serialization
            config_dict = futures_config.model_dump()
            config_dict["position_size"] = str(config_dict["position_size"])
            config_dict["max_position_size"] = str(config_dict["max_position_size"])
            signal.futures_config = config_dict
            self.session.commit()
            self.session.refresh(signal)
        return signal

    def delete_signal(self, signal_id: int) -> bool:
        """Delete trading signal by ID."""
        signal = self.get_signal(signal_id)
        if signal:
            self.session.delete(signal)
            self.session.commit()
            return True
        return False
