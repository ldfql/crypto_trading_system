"""Script to insert test trading signals for frequency analysis testing."""
import asyncio
from datetime import datetime, timedelta
import random
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.signals import Base, TradingSignal

async def create_tables(engine):
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def insert_test_signals():
    """Insert test trading signals with varying accuracies and timestamps."""
    engine = create_async_engine('sqlite+aiosqlite:///instance/trading.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables if they don't exist
    await create_tables(engine)

    async with async_session() as session:
        # Generate signals for the past 30 days
        for days_ago in range(30):
            # Generate 2-5 signals per day
            num_signals = random.randint(2, 5)
            for _ in range(num_signals):
                # Create signal with random accuracy, but ensure some are above 82%
                accuracy = random.uniform(0.75, 0.95) if random.random() > 0.3 else random.uniform(0.6, 0.81)

                # Generate timestamp for this day
                date = datetime.utcnow() - timedelta(days=days_ago)
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                timestamp = date.replace(hour=hour, minute=minute)

                signal = TradingSignal(
                    symbol='BTC/USDT',
                    signal_type=random.choice(['long', 'short']),
                    timeframe=random.choice(['1h', '4h', '1d']),
                    entry_price=random.uniform(40000, 45000),
                    confidence=random.uniform(0.8, 0.95),
                    accuracy=accuracy,
                    source='test_data',
                    market_cycle_phase=random.choice(['accumulation', 'uptrend', 'distribution', 'downtrend']),
                    created_at=timestamp
                )
                session.add(signal)

        await session.commit()
        print("Test signals inserted successfully")

if __name__ == '__main__':
    asyncio.run(insert_test_signals())
