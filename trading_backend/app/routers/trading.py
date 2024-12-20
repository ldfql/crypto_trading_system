from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.models.signals import TradingSignal as TradingSignalModel
from app.schemas.trading import TradingSignal
from app.repositories.signal_repository import SignalRepository
from app.services.market_analysis.market_data_service import MarketDataService
from app.dependencies import get_session

router = APIRouter(prefix="/trading", tags=["trading"])

@router.get("/signals/24h", response_model=List[TradingSignal])
async def get_24h_signals(
    time_range: str = Query("24h", regex="^(1h|4h|12h|24h)$"),
    status: Optional[str] = Query(None, regex="^(validated|expired)?$"),
    min_confidence: float = Query(0.8, ge=0.0, le=1.0),
    signal_repository: SignalRepository = Depends(get_session),
    market_data_service: MarketDataService = Depends()
) -> List[TradingSignalModel]:
    """
    Get trading signals from the last 24 hours with optional filtering.

    Args:
        time_range: Time range to fetch signals for (1h, 4h, 12h, 24h)
        status: Filter by signal status (validated, expired, or None for all)
        min_confidence: Minimum confidence threshold for signals
        signal_repository: Repository for accessing signal data
        market_data_service: Service for fetching current market prices

    Returns:
        List of trading signals matching the specified criteria
    """
    hours = int(time_range[:-1])
    since = datetime.utcnow() - timedelta(hours=hours)

    signals = await signal_repository.get_signals_since(
        since=since,
        status=status,
        min_confidence=min_confidence
    )

    # Update current prices for all signals
    for signal in signals:
        current_price = await market_data_service.get_current_price(signal.symbol)
        signal.current_price = current_price

    return signals

@router.get("/signals/current", response_model=List[TradingSignal])
async def get_current_signals(
    min_confidence: float = Query(0.8, ge=0.0, le=1.0),
    signal_repository: SignalRepository = Depends(get_session),
    market_data_service: MarketDataService = Depends()
) -> List[TradingSignalModel]:
    """
    Get currently active trading signals.

    Args:
        min_confidence: Minimum confidence threshold for signals
        signal_repository: Repository for accessing signal data
        market_data_service: Service for fetching current market prices

    Returns:
        List of currently active trading signals
    """
    signals = await signal_repository.get_active_signals(min_confidence=min_confidence)

    # Update current prices for all signals
    for signal in signals:
        current_price = await market_data_service.get_current_price(signal.symbol)
        signal.current_price = current_price

    return signals
