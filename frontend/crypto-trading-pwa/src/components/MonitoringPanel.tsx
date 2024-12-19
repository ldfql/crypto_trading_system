import React, { useEffect, useState } from 'react';
import { Card } from './ui/card';
import { Progress } from './ui/progress';
import type { TradingSignal, SystemMetrics, WebSocketMessage } from '../types/trading';
import { createWebSocketService } from '../services/websocket';
import { formatDate, formatPrice, calculatePercentageChange } from '../lib/utils';

export const MonitoringPanel: React.FC = () => {
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [wsService] = useState(() => createWebSocketService());

  useEffect(() => {
    const handleMessage = (message: WebSocketMessage) => {
      console.log('Received WebSocket message:', message);
      switch (message.type) {
        case 'signal_update':
          const signalData = message.data as TradingSignal;
          console.log('Processing signal update:', signalData);
          setSignals(prev => {
            const updated = [...prev];
            const index = updated.findIndex(s => s.id === signalData.id);
            if (index >= 0) {
              updated[index] = signalData;
            } else {
              updated.push(signalData);
            }
            return updated;
          });
          break;
        case 'metrics_update':
          const metricsData = message.data as SystemMetrics;
          console.log('Processing metrics update:', metricsData);
          setMetrics(metricsData);
          break;
      }
    };

    console.log('Setting up WebSocket connection...');
    wsService.addMessageHandler(handleMessage);
    wsService.connect();

    return () => {
      console.log('Cleaning up WebSocket connection...');
      wsService.removeMessageHandler(handleMessage);
      wsService.disconnect();
    };
  }, [wsService]);

  return (
    <div className="space-y-6">
      {metrics && (
        <Card className="p-6">
          <h2 className="text-2xl font-bold mb-4">System Metrics</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Overall Accuracy</p>
              <Progress value={metrics.overall_accuracy / 100} className="mt-2" />
              <p className="text-lg font-semibold mt-1">
                {metrics.overall_accuracy.toFixed(2)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Average Confidence</p>
              <Progress value={metrics.average_confidence / 100} className="mt-2" />
              <p className="text-lg font-semibold mt-1">
                {metrics.average_confidence.toFixed(2)}%
              </p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Total Signals</p>
              <p className="text-lg font-semibold">{metrics.total_signals}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Successful Predictions</p>
              <p className="text-lg font-semibold">{metrics.successful_predictions}</p>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-sm text-gray-500">Market Sentiment</p>
            <p className={`text-lg font-semibold capitalize ${
              metrics.market_sentiment === 'bullish' ? 'text-green-600' :
              metrics.market_sentiment === 'bearish' ? 'text-red-600' :
              'text-yellow-600'
            }`}>
              {metrics.market_sentiment}
            </p>
          </div>
        </Card>
      )}

      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Active Signals</h2>
        {signals.map((signal) => (
          <Card key={signal.id} className="p-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-lg font-semibold">{signal.symbol}</h3>
                <p className={`text-sm ${signal.signal_type === 'long' ? 'text-green-600' : 'text-red-600'}`}>
                  {signal.signal_type.toUpperCase()}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500">Entry Price</p>
                <p className="font-semibold">{formatPrice(signal.entry_price)}</p>
                <p className="text-sm text-gray-500 mt-1">Current Price</p>
                <p className="font-semibold">
                  {formatPrice(signal.current_price)}
                  <span className={`ml-2 text-sm ${
                    signal.current_price > signal.entry_price ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {calculatePercentageChange(signal.current_price, signal.entry_price)}
                  </span>
                </p>
              </div>
            </div>
            <div className="mt-4">
              <div className="flex justify-between text-sm">
                <span>Accuracy</span>
                <span>{signal.accuracy.toFixed(2)}%</span>
              </div>
              <Progress value={signal.accuracy / 100} className="mt-1" />
            </div>
            <div className="mt-2">
              <div className="flex justify-between text-sm">
                <span>Confidence</span>
                <span>{signal.confidence.toFixed(2)}%</span>
              </div>
              <Progress value={signal.confidence / 100} className="mt-1" />
            </div>
            <div className="mt-4 text-sm text-gray-500">
              <p>Market Phase: {signal.market_phase}</p>
              <p>Created: {formatDate(signal.created_at)}</p>
              <p>Validations: {signal.validation_count}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
