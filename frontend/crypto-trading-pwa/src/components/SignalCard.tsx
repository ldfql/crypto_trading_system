import React from 'react';
import { TradingSignal } from '../types/trading';
import { formatDistanceToNow } from 'date-fns';

interface SignalCardProps {
  signal: TradingSignal;
  historical?: boolean;
}

const formatPrice = (price: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 8
  }).format(price);
};

const formatPercentage = (value: number) => {
  return `${(value * 100).toFixed(2)}%`;
};

const SignalCard: React.FC<SignalCardProps> = ({ signal, historical = false }) => {
  return (
    <div
      className={`p-4 border rounded-lg shadow-sm ${historical ? 'bg-gray-50' : 'bg-white'}`}
      data-testid="signal-card"
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="text-lg font-semibold" data-testid="signal-pair">{signal.symbol}</h3>
          <p className={signal.signal_type === 'long' ? 'text-sm text-green-600' : 'text-sm text-red-600'}>
            {signal.signal_type === 'long' ? '做多 (Long)' : '做空 (Short)'}
          </p>
        </div>
        {signal.status && (
          <span className={
            signal.status === 'validated' ? 'px-2 py-1 rounded text-xs bg-green-100 text-green-800' :
            signal.status === 'expired' ? 'px-2 py-1 rounded text-xs bg-red-100 text-red-800' :
            'px-2 py-1 rounded text-xs bg-blue-100 text-blue-800'
          }>
            {signal.status === 'validated' ? '已验证' :
             signal.status === 'expired' ? '已过期' : '进行中'}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <div>
          <p className="text-sm text-gray-500">目前价格 (Current)</p>
          <p className="font-medium" data-testid="current-price">
            {formatPrice(signal.last_price || 0)}
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-500">入场价格 (Entry)</p>
          <p className="font-medium" data-testid="entry-price">
            {formatPrice(signal.entry_price)}
          </p>
        </div>
        {signal.take_profit && (
          <div>
            <p className="text-sm text-gray-500">止盈价格 (Take Profit)</p>
            <p className="font-medium text-green-600" data-testid="take-profit">
              {formatPrice(signal.take_profit)}
            </p>
          </div>
        )}
        {signal.stop_loss && (
          <div>
            <p className="text-sm text-gray-500">止损价格 (Stop Loss)</p>
            <p className="font-medium text-red-600" data-testid="stop-loss">
              {formatPrice(signal.stop_loss)}
            </p>
          </div>
        )}
        <div>
          <p className="text-sm text-gray-500">准确度置信度 (Accuracy)</p>
          <p className="font-medium" data-testid="signal-confidence">
            {formatPercentage(signal.confidence || 0)}
          </p>
        </div>
        {signal.leverage && (
          <div>
            <p className="text-sm text-gray-500">杠杆倍数 (Leverage)</p>
            <p className="font-medium" data-testid="leverage">
              {signal.leverage}x
            </p>
          </div>
        )}
        {signal.margin_type && (
          <div>
            <p className="text-sm text-gray-500">保证金模式 (Margin)</p>
            <p className="font-medium" data-testid="margin-type">
              {signal.margin_type === 'ISOLATED' ? '逐仓' : '全仓'} ({signal.margin_type})
            </p>
          </div>
        )}
        {signal.position_size && (
          <div>
            <p className="text-sm text-gray-500">仓位比例 (Position)</p>
            <p className="font-medium" data-testid="position-size">
              {formatPrice(signal.position_size)}
            </p>
          </div>
        )}
        {signal.trading_fee && (
          <div>
            <p className="text-sm text-gray-500">实时手续费 (Fees)</p>
            <p className="font-medium" data-testid="trading-fee">
              {formatPrice(signal.trading_fee)}
            </p>
          </div>
        )}
        {signal.expected_profit && (
          <div>
            <p className="text-sm text-gray-500">预计利润 (Profit)</p>
            <p className="font-medium" data-testid="expected-profit">
              {formatPrice(signal.expected_profit)}
            </p>
          </div>
        )}
      </div>

      {signal.source && (
        <div className="mb-2">
          <p className="text-sm text-gray-500">信号来源 (Source)</p>
          <p className="text-sm font-medium capitalize" data-testid="signal-source">
            {signal.source}
          </p>
        </div>
      )}

      {signal.created_at && (
        <div className="text-xs text-gray-500 mt-2">
          Created {formatDistanceToNow(new Date(signal.created_at))} ago
        </div>
      )}

      {signal.last_validated_at && signal.last_validated_at !== signal.created_at && (
        <div className="text-xs text-gray-500">
          Updated {formatDistanceToNow(new Date(signal.last_validated_at))} ago
        </div>
      )}
    </div>
  );
};

export default SignalCard;
