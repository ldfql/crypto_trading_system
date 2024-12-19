import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.signals import TradingSignal
from app.repositories.signal_repository import SignalRepository

class TestSignalStorage:
    @pytest.fixture
    async def signal_repository(self, db_session: AsyncSession):
        return SignalRepository(db_session)

    async def test_store_long_term_signal(self, signal_repository):
        """Test storing long-term trading signal with high accuracy requirement"""
        signal = TradingSignal(
            symbol="BTC/USDT",
            timeframe="long",
            signal_type="spot",
            entry_price=45000.0,
            confidence=0.92,  # High confidence requirement
            source="market_analysis",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            market_cycle_phase="accumulation",
            accuracy=0.88  # Above 85% accuracy requirement
        )

        stored_signal = await signal_repository.create(signal)
        assert stored_signal.id is not None
        assert stored_signal.confidence > 0.85
        assert stored_signal.accuracy > 0.85

    async def test_entry_point_detection(self, signal_repository):
        """Test contract entry point detection for stored signals"""
        # Store a long-term signal
        signal = TradingSignal(
            symbol="ETH/USDT",
            timeframe="long",
            signal_type="futures",
            entry_price=2800.0,
            confidence=0.89,
            source="technical_analysis",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=14),
            market_cycle_phase="markup",
            accuracy=0.87
        )
        await signal_repository.create(signal)

        # Test entry point detection
        entry_points = await signal_repository.find_entry_points(
            symbol="ETH/USDT",
            min_confidence=0.85,
            min_accuracy=0.85
        )
        assert len(entry_points) > 0
        for point in entry_points:
            assert point.confidence >= 0.85
            assert point.accuracy >= 0.85

    async def test_accuracy_validation(self, signal_repository):
        """Test signal accuracy validation with real-time data"""
        # Create a signal with initial accuracy
        signal = TradingSignal(
            symbol="BTC/USDT",
            timeframe="medium",
            signal_type="futures",
            entry_price=46000.0,
            confidence=0.90,
            source="sentiment_analysis",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7),
            market_cycle_phase="distribution",
            accuracy=0.86
        )
        stored_signal = await signal_repository.create(signal)

        # Update accuracy based on real-time validation
        updated_signal = await signal_repository.validate_accuracy(
            signal_id=stored_signal.id,
            current_price=47000.0,
            market_data={"volume": 1000000, "volatility": 0.02}
        )

        assert updated_signal.accuracy >= 0.85
        assert updated_signal.last_validated_at is not None

    async def test_continuous_accuracy_improvement(self, signal_repository):
        """Test continuous accuracy improvement beyond 85%"""
        signal = TradingSignal(
            symbol="BTC/USDT",
            timeframe="long",
            signal_type="spot",
            entry_price=45000.0,
            confidence=0.95,
            source="combined_analysis",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            market_cycle_phase="accumulation",
            accuracy=0.88
        )
        stored_signal = await signal_repository.create(signal)

        # Simulate multiple accuracy updates
        prices = [45100.0, 45300.0, 45600.0, 46000.0]
        for price in prices:
            updated_signal = await signal_repository.validate_accuracy(
                signal_id=stored_signal.id,
                current_price=price,
                market_data={"volume": 1000000, "volatility": 0.015}
            )
            # Verify accuracy improves or maintains high level
            assert updated_signal.accuracy >= stored_signal.accuracy
            stored_signal = updated_signal
