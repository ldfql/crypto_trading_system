"""Account monitoring and management endpoints."""
from decimal import Decimal
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, Depends
from pydantic import BaseModel

from app.models.futures import AccountStage, FuturesConfig
from app.services.monitoring.account_monitor import AccountMonitor, AccountMonitoringError

router = APIRouter(prefix="/account", tags=["account"])

class AccountUpdate(BaseModel):
    """Account balance update model."""
    balance: Decimal
    leverage: Optional[int] = None
    risk_percentage: Optional[Decimal] = None

class AccountStatus(BaseModel):
    """Account status response model."""
    current_balance: Decimal
    current_stage: AccountStage
    stage_progress: float
    remaining_to_next_stage: Optional[Decimal]
    max_leverage: int
    recommended_position_size: Optional[Decimal]

@router.post("/update", response_model=AccountStatus)
async def update_account_balance(update: AccountUpdate) -> Dict:
    """Update account balance and get new status."""
    try:
        monitor = AccountMonitor(update.balance)
        progress, remaining = monitor.get_stage_progress()

        params = {}
        if update.leverage is not None and update.risk_percentage is not None:
            params = monitor.get_trading_parameters(
                risk_percentage=update.risk_percentage,
                leverage=update.leverage
            )

        return {
            "current_balance": monitor.current_balance,
            "current_stage": monitor.current_stage,
            "stage_progress": float(progress),
            "remaining_to_next_stage": remaining if remaining > 0 else None,
            "max_leverage": monitor.MAX_LEVERAGE[monitor.current_stage],
            "recommended_position_size": params.get("position_size")
        }
    except AccountMonitoringError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/validate-config")
async def validate_futures_config(config: FuturesConfig) -> Dict[str, bool]:
    """Validate futures trading configuration."""
    try:
        monitor = AccountMonitor(config.position_size)
        is_valid = monitor.validate_futures_config(config)
        return {"is_valid": is_valid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time account monitoring."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                balance = Decimal(str(data.get("balance", "0")))
                monitor = AccountMonitor(balance)
                progress, remaining = monitor.get_stage_progress()

                await websocket.send_json({
                    "current_balance": str(monitor.current_balance),
                    "current_stage": monitor.current_stage.value,
                    "stage_progress": float(progress),
                    "remaining_to_next_stage": str(remaining) if remaining > 0 else None,
                    "max_leverage": monitor.MAX_LEVERAGE[monitor.current_stage]
                })
            except (ValueError, AccountMonitoringError) as e:
                await websocket.send_json({"error": str(e)})
    except Exception:
        await websocket.close()
