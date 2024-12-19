"""WebSocket router for real-time monitoring."""
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.monitoring.signal_monitor import SignalMonitor
from app.repositories.signal_repository import SignalRepository
from app.services.market_analysis.market_data_service import MarketDataService

router = APIRouter()

class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Connect a new WebSocket client."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                self.disconnect(connection)

manager = ConnectionManager()

@router.websocket("/ws/monitor")
async def websocket_endpoint(
    websocket: WebSocket,
    signal_monitor: SignalMonitor,
    signal_repository: SignalRepository,
    market_data_service: MarketDataService
):
    """WebSocket endpoint for real-time monitoring."""
    await manager.connect(websocket)
    try:
        while True:
            # Monitor active signals
            monitoring_results = await signal_monitor.monitor_active_signals()

            # Get active signals
            active_signals = []
            for result in monitoring_results:
                signal = await signal_repository.get_signal(result['signal_id'])
                if signal:
                    active_signals.append({
                        'id': signal.id,
                        'symbol': signal.symbol,
                        'signal_type': signal.signal_type,
                        'entry_price': signal.entry_price,
                        'current_price': result['market_data']['current_price'],
                        'accuracy': result['current_accuracy'],
                        'confidence': signal.confidence,
                        'created_at': signal.created_at.isoformat(),
                        'market_phase': signal.market_cycle_phase,
                        'validation_count': signal.validation_count
                    })

            # Get market data for each symbol
            market_data = {}
            for signal in active_signals:
                market_data[signal['symbol']] = await market_data_service.get_market_data(
                    symbol=signal['symbol']
                )

            # Get overall statistics
            stats = await signal_repository.get_accuracy_statistics()

            # Send updates
            await websocket.send_json({
                'type': 'signals_update',
                'signals': active_signals
            })

            await websocket.send_json({
                'type': 'market_data',
                'data': market_data
            })

            await websocket.send_json({
                'type': 'stats_update',
                'stats': {
                    'average_accuracy': stats['average_accuracy'],
                    'total_signals': stats['total_signals'],
                    'active_signals': len(active_signals),
                    'successful_predictions': sum(1 for s in active_signals if s['accuracy'] >= 0.85)
                }
            })

            # Wait for 5 seconds before next update
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
