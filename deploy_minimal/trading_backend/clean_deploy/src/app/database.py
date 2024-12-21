"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./trading.db"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_session() -> AsyncSession:
    """Get database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
