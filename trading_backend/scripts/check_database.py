import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.models.signals import TradingSignal

async def check_signals():
    engine = create_async_engine('sqlite+aiosqlite:///instance/trading.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM trading_signals'))
        count = result.scalar()
        print(f'\nTotal signals in database: {count}\n')

        if count > 0:
            result = await session.execute(text('SELECT * FROM trading_signals LIMIT 5'))
            signals = result.fetchall()
            print('Sample signals:')
            for signal in signals:
                print(f'\nSignal ID: {signal[0]}')
                print(f'Symbol: {signal[1]}')
                print(f'Type: {signal[2]}')
                print(f'Created At: {signal[3]}')
                print(f'Confidence: {signal[8]}')
                print(f'Accuracy: {signal[9]}')

if __name__ == '__main__':
    asyncio.run(check_signals())
