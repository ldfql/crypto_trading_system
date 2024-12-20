from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, Query
from ..dependencies import get_pair_selector
from ..schemas.trading import TradingPairResponse, TradingSignal
from ..services.trading.pair_selector import PairSelector

router = APIRouter(prefix="/trading", tags=["trading"])

@router.get("/pairs", response_model=TradingPairResponse)
async def get_trading_pairs(
    account_balance: float = Query(..., gt=0, description="Account balance in USDT"),
    max_pairs: int = Query(3, ge=1, le=10, description="Maximum number of pairs to return"),
    pair_selector: PairSelector = Depends(get_pair_selector)
) -> TradingPairResponse:
    """Get recommended trading pairs with optimal parameters."""
    signals = await pair_selector.select_trading_pairs(
        account_balance=Decimal(str(account_balance)),
        max_pairs=max_pairs
    )
    return TradingPairResponse(signals=signals)
