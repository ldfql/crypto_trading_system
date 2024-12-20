"""Script to analyze historical trading signal frequency."""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Tuple

from app.repositories.signal_repository import SignalRepository
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

async def get_session() -> AsyncSession:
    """Create database session."""
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trading.db"))
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session()

async def analyze_signal_frequency(
    signal_repository: SignalRepository,
    days: int = 30,
    min_accuracy: float = 0.82
) -> Dict[str, any]:
    """
    Analyze trading signal frequency over specified period.

    Returns:
    - Dictionary containing:
        - average_signals_per_day: float
        - min_signals_per_day: int
        - max_signals_per_day: int
        - total_signals: int
        - signals_by_type: Dict[str, int]
        - daily_distribution: Dict[str, int]
    """
    signals = await signal_repository.get_historical_predictions(
        days=days,
        min_accuracy=min_accuracy
    )

    # Group signals by day and type
    daily_counts: Dict[str, int] = defaultdict(int)
    type_counts: Dict[str, int] = defaultdict(int)

    for signal in signals:
        day = signal.created_at.date().isoformat()
        daily_counts[day] += 1
        if hasattr(signal, 'signal_type'):
            type_counts[signal.signal_type] += 1

    if not daily_counts:
        return {
            "average_signals_per_day": 0.0,
            "min_signals_per_day": 0,
            "max_signals_per_day": 0,
            "total_signals": 0,
            "signals_by_type": {},
            "daily_distribution": {}
        }

    # Calculate statistics
    counts = list(daily_counts.values())
    stats = {
        "average_signals_per_day": sum(counts) / len(counts),
        "min_signals_per_day": min(counts),
        "max_signals_per_day": max(counts),
        "total_signals": len(signals),
        "signals_by_type": dict(type_counts),
        "daily_distribution": dict(daily_counts)
    }

    return stats

async def main():
    """Run signal frequency analysis."""
    session = await get_session()
    try:
        repo = SignalRepository(session)
        stats = await analyze_signal_frequency(repo)

        print(f"分析结果 (过去30天):")
        print(f"每日平均信号数量: {stats['average_signals_per_day']:.1f}")
        print(f"范围: 每日 {stats['min_signals_per_day']} 到 {stats['max_signals_per_day']} 个信号")
        print(f"总信号数量: {stats['total_signals']}")
        print(f"按信号类型统计:")
        for signal_type, count in stats['signals_by_type'].items():
            print(f"  - {signal_type}: {count}个")
        print(f"注意: 仅统计准确率达到82%以上的信号")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
