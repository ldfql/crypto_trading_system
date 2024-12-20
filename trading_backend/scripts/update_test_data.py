import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import random

async def update_test_data():
    engine = create_async_engine('sqlite+aiosqlite:///instance/trading.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Update accuracy values
        await session.execute(
            text('UPDATE trading_signals SET accuracy = :accuracy WHERE accuracy = :test_data'),
            {'accuracy': 0.85, 'test_data': 'test_data'}
        )

        # Update market conditions data
        await session.execute(
            text('''
                UPDATE trading_signals
                SET market_volume = :volume,
                    market_volatility = :volatility,
                    market_cycle_phase = :phase
                WHERE market_volume IS NULL
            '''),
            {
                'volume': random.uniform(1000000, 5000000),
                'volatility': random.uniform(0.01, 0.05),
                'phase': random.choice(['accumulation', 'uptrend', 'distribution', 'downtrend'])
            }
        )

        await session.commit()
        print('Test data updated successfully')

if __name__ == '__main__':
    asyncio.run(update_test_data())
