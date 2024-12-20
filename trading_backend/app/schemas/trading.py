"""Pydantic models for trading signals."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class TradingSignalBase(BaseModel):
    """Base Pydantic model for trading signals."""
    symbol: str = Field(..., description="币种名 (Currency pair)")
    signal_type: str
    timeframe: str
    entry_price: float = Field(..., description="入场价格 (Entry price)")
    target_price: Optional[float] = Field(None, description="目标价格 (Target price)")
    stop_loss: Optional[float] = Field(None, description="止损点 (Stop loss)")
    take_profit: Optional[float] = Field(None, description="止盈点 (Take profit)")
    confidence: float = Field(..., description="准确度置信度 (Accuracy confidence)")
    source: Optional[str] = None
    market_cycle_phase: Optional[str] = None
    accuracy: Optional[float] = Field(None, description="历史准确率 (Historical accuracy)")
    validation_count: Optional[int] = 0
    last_price: Optional[float] = Field(None, description="目前价格 (Current price)")
    position_size: Optional[float] = Field(None, description="仓位大小 (Position size)")
    leverage: Optional[int] = Field(None, description="杠杆倍数 (Leverage multiplier)")
    margin_type: Optional[str] = Field(None, description="全仓还是逐仓 (Cross/Isolated margin)")
    trading_fee: Optional[float] = Field(None, description="实时手续费 (Real-time fees)")
    expected_profit: Optional[float] = Field(None, description="预计利润 (Expected profit)")
    liquidation_price: Optional[float] = Field(None, description="强平价格 (Liquidation price)")
    max_profit_reached: Optional[float] = 0.0
    max_loss_reached: Optional[float] = 0.0
    market_volatility: Optional[float] = None
    market_volume: Optional[float] = None
    market_sentiment: Optional[str] = None
    technical_indicators: Optional[Dict[str, Any]] = None
    sentiment_sources: Optional[Dict[str, Any]] = None
    final_outcome: Optional[str] = None
    status: Optional[str] = "pending"
    validation_history: Optional[List[Dict[str, Any]]] = None

class TradingSignalCreate(TradingSignalBase):
    """Pydantic model for creating trading signals."""
    pass

class TradingSignal(TradingSignalBase):
    """Pydantic model for reading trading signals."""
    id: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_validated_at: Optional[datetime] = None
    price_updates: Optional[List[Dict[str, Any]]] = None

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
