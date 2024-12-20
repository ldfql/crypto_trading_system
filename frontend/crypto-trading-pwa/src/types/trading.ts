export interface TradingSignal {
  id: number;
  symbol: string;
  signal_type: 'long' | 'short';
  entry_price: number;
  current_price: number;
  target_price: number;
  stop_loss: number;
  accuracy: number;
  confidence: number;
  created_at: string;
  market_phase: string;
  validation_count: number;
  // Futures trading specific fields
  leverage?: number;
  margin_type?: 'ISOLATED' | 'CROSS';
  position_size?: number;
  trading_fee?: number;
  entry_fee?: number;
  exit_fee?: number;
  total_fee?: number;
  expected_profit?: number;
  liquidation_price?: number;
  funding_rate?: number;
  last_price?: number;
}

export interface SystemMetrics {
  overall_accuracy: number;
  total_signals: number;
  successful_predictions: number;
  average_confidence: number;
  market_sentiment: 'bullish' | 'bearish' | 'neutral';
}

export interface WebSocketMessage {
  type: 'signal_update' | 'metrics_update' | 'market_data';
  data: TradingSignal | SystemMetrics | any;
}
