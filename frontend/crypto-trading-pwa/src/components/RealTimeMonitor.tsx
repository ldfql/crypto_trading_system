import React, { useEffect, useState } from 'react';
import { Card } from './ui/card';
import { Progress } from './ui/progress';
import { Alert } from './ui/alert';
import { useWebSocket } from '../hooks/useWebSocket';
import { formatDistance } from 'date-fns';

interface Signal {
  id: number;
  symbol: string;
  signal_type: 'long' | 'short';
  entry_price: number;
  current_price: number;
  accuracy: number;
  confidence: number;
  created_at: string;
  market_phase: string;
  validation_count: number;
}

interface MarketData {
  volatility: number;
  volume: number;
  sentiment: string;
}

interface MonitoringStats {
  average_accuracy: number;
  total_signals: number;
  active_signals: number;
  successful_predictions: number;
}

export const RealTimeMonitor: React.FC = () => {
  const [activeSignals, setActiveSignals] = useState<Signal[]>([]);
  const [marketData, setMarketData] = useState<Record<string, MarketData>>({});
  const [stats, setStats] = useState<MonitoringStats>({
    average_accuracy: 0,
    total_signals: 0,
    active_signals: 0,
    successful_predictions: 0
  });

  const ws = useWebSocket('ws://localhost:8000/ws/monitor');

  useEffect(() => {
    if (ws) {
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'signals_update') {
          setActiveSignals(data.signals);
        } else if (data.type === 'market_data') {
          setMarketData(data.data);
        } else if (data.type === 'stats_update') {
          setStats(data.stats);
        }
      };
    }
  }, [ws]);

  const getAccuracyColor = (accuracy: number) => {
    if (accuracy >= 0.85) return 'bg-green-500';
    if (accuracy >= 0.7) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="p-4 space-y-4">
      {/* Overall Statistics */}
      <Card className="p-4">
        <h2 className="text-xl font-bold mb-4">System Performance</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-gray-500">Average Accuracy</p>
            <div className="flex items-center space-x-2">
              <Progress
                value={stats.average_accuracy * 100}
                className={getAccuracyColor(stats.average_accuracy)}
              />
              <span className="font-bold">
                {(stats.average_accuracy * 100).toFixed(1)}%
              </span>
            </div>
          </div>
          <div>
            <p className="text-sm text-gray-500">Active Signals</p>
            <p className="text-2xl font-bold">{stats.active_signals}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Total Signals</p>
            <p className="text-2xl font-bold">{stats.total_signals}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Successful Predictions</p>
            <p className="text-2xl font-bold">{stats.successful_predictions}</p>
          </div>
        </div>
      </Card>

      {/* Active Signals */}
      <Card className="p-4">
        <h2 className="text-xl font-bold mb-4">Active Signals</h2>
        <div className="space-y-4">
          {activeSignals.map((signal) => (
            <Card key={signal.id} className="p-4 border-l-4 border-blue-500">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Symbol</p>
                  <p className="font-bold">{signal.symbol}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Type</p>
                  <p className={`font-bold ${
                    signal.signal_type === 'long' ? 'text-green-500' : 'text-red-500'
                  }`}>
                    {signal.signal_type.toUpperCase()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Entry Price</p>
                  <p className="font-bold">${signal.entry_price.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Current Price</p>
                  <p className={`font-bold ${
                    signal.current_price > signal.entry_price ? 'text-green-500' : 'text-red-500'
                  }`}>
                    ${signal.current_price.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Accuracy</p>
                  <Progress
                    value={signal.accuracy * 100}
                    className={getAccuracyColor(signal.accuracy)}
                  />
                </div>
                <div>
                  <p className="text-sm text-gray-500">Confidence</p>
                  <Progress value={signal.confidence * 100} className="bg-blue-500" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">Market Phase</p>
                  <p className="font-medium">{signal.market_phase}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Age</p>
                  <p className="font-medium">
                    {formatDistance(new Date(signal.created_at), new Date(), { addSuffix: true })}
                  </p>
                </div>
              </div>

              {/* Market Data */}
              {marketData[signal.symbol] && (
                <div className="mt-4 grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Volatility</p>
                    <p className="font-medium">
                      {(marketData[signal.symbol].volatility * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Volume</p>
                    <p className="font-medium">
                      {marketData[signal.symbol].volume.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Market Sentiment</p>
                    <p className="font-medium capitalize">
                      {marketData[signal.symbol].sentiment}
                    </p>
                  </div>
                </div>
              )}

              {/* Validation Alert */}
              {signal.validation_count > 0 && signal.accuracy >= 0.85 && (
                <Alert className="mt-4 bg-green-50">
                  Signal validated {signal.validation_count} times with {(signal.accuracy * 100).toFixed(1)}% accuracy
                </Alert>
              )}
            </Card>
          ))}
        </div>
      </Card>
    </div>
  );
};
