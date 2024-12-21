"""Account monitoring and management endpoints."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, Depends
from pydantic import BaseModel, ValidationError

from src.app.models.signals import AccountStage
from src.app.models.futures import FuturesConfig
from src.app.services.monitoring.account_monitor import AccountMonitor, AccountMonitoringError
from src.app.dependencies import get_account_monitor

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

@router.get("/status")
async def get_account_status(
    balance: Decimal,
    account_monitor: AccountMonitor = Depends(get_account_monitor)
) -> AccountStatus:
    """Get current account status."""
    try:
        if balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        account_monitor.update_balance(balance)
        progress, remaining = account_monitor.get_stage_progress()
        return AccountStatus(
            current_balance=balance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            current_stage=account_monitor.current_stage,
            stage_progress=float(progress),
            remaining_to_next_stage=remaining.quantize(Decimal("1"), rounding=ROUND_HALF_UP) if remaining > 0 else None,
            max_leverage=account_monitor.get_max_leverage(),
            recommended_position_size=None
        )
    except (AccountMonitoringError, InvalidOperation) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update", response_model=AccountStatus)
async def update_account_balance(
    update: AccountUpdate,
    account_monitor: AccountMonitor = Depends(get_account_monitor)
) -> Dict:
    """Update account balance and get new status."""
    try:
        if update.balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        account_monitor.update_balance(update.balance)
        progress, remaining = account_monitor.get_stage_progress()

        params = {}
        if update.leverage is not None and update.risk_percentage is not None:
            params = account_monitor.get_trading_parameters(update.risk_percentage)

        return {
            "current_balance": str(update.balance.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            "current_stage": account_monitor.current_stage,
            "stage_progress": float(progress),
            "remaining_to_next_stage": str(remaining.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if remaining > 0 else None,
            "max_leverage": account_monitor.get_max_leverage(),
            "recommended_position_size": params.get("position_size")
        }
    except (AccountMonitoringError, InvalidOperation) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate-config")
async def validate_futures_config(
    config: FuturesConfig,
    balance: Decimal,
    account_monitor: AccountMonitor = Depends(get_account_monitor)
) -> Dict[str, bool | str]:
    """Validate futures trading configuration."""
    try:
        if balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        account_monitor.update_balance(balance)
        account_monitor.validate_futures_config(config)
        return {"is_valid": True}
    except ValueError as e:
        return {"is_valid": False, "error": str(e)}
    except (AccountMonitoringError, ValidationError, InvalidOperation) as e:
        return {"is_valid": False, "error": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trading-parameters")
async def get_trading_parameters(
    balance: Decimal,
    risk_percentage: Decimal,
    account_monitor: AccountMonitor = Depends(get_account_monitor)
) -> Dict:
    """Get recommended trading parameters."""
    try:
        if balance <= 0:
            raise AccountMonitoringError("Balance must be positive")

        account_monitor.update_balance(balance)
        params = account_monitor.get_trading_parameters(risk_percentage)
        return params
    except (AccountMonitoringError, InvalidOperation) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/monitor")
async def websocket_endpoint(
    websocket: WebSocket,
    account_monitor: AccountMonitor = Depends(get_account_monitor)
):
    """WebSocket endpoint for real-time account monitoring."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                balance = Decimal(str(data.get("balance", "0")))
                if balance <= 0:
                    raise AccountMonitoringError("Balance must be positive")

                account_monitor.update_balance(balance)
                progress, remaining = account_monitor.get_stage_progress()

                await websocket.send_json({
                    "current_balance": str(balance.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                    "current_stage": account_monitor.current_stage.value,
                    "stage_progress": float(progress),
                    "remaining_to_next_stage": str(remaining.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if remaining > 0 else None,
                    "max_leverage": account_monitor.get_max_leverage()
                })
            except (ValueError, AccountMonitoringError, InvalidOperation) as e:
                await websocket.send_json({"error": str(e)})
    except Exception:
        await websocket.close()
