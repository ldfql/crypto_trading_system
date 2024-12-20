from typing import Dict, List, Optional, Tuple
import pandas as pd
import pandas_ta as ta
from decimal import Decimal
from datetime import datetime, timedelta

class MarketDataService:
    def __init__(self):
        self.volume_threshold = 1000000  # Minimum 24h volume in USDT
        self.volatility_threshold = 0.02  # Minimum price volatility (2%)

    async def get_market_data(self, symbol: str, interval: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Get market data for a trading pair."""
        # PLACEHOLDER: Implementation to fetch real market data from exchange API
        # For testing, return mock data
        return pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=limit, freq='H'),
            'open': [40000] * limit,
            'high': [41000] * limit,
            'low': [39000] * limit,
            'close': [40500] * limit,
            'volume': [1000000] * limit
        })

    async def analyze_pair_metrics(self, symbol: str) -> Dict[str, float]:
        """Analyze trading pair metrics for selection criteria."""
        df = await self.get_market_data(symbol)

        # Calculate key metrics
        volume_24h = df['volume'].tail(24).sum()
        volatility = (df['high'].max() - df['low'].min()) / df['low'].min()

        # Calculate technical indicators
        df['rsi'] = ta.rsi(df['close'])
        df['macd'] = ta.macd(df['close'])['MACD_12_26_9']
        df['atr'] = ta.atr(df['high'], df['low'], df['close'])

        return {
            'volume_24h': float(volume_24h),
            'volatility': float(volatility),
            'rsi': float(df['rsi'].iloc[-1]),
            'macd': float(df['macd'].iloc[-1]),
            'atr': float(df['atr'].iloc[-1])
        }

    async def get_optimal_pairs(self, account_balance: Decimal) -> List[str]:
        """Get optimal trading pairs based on account balance."""
        base_pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

        if account_balance < Decimal('1000'):
            # For small accounts, focus on major pairs with high liquidity
            return base_pairs[:2]
        elif account_balance < Decimal('10000'):
            # Medium accounts can trade more pairs
            return base_pairs
        else:
            # Large accounts can trade additional pairs with good metrics
            additional_pairs = ['ADAUSDT', 'SOLUSDT', 'DOTUSDT']
            return base_pairs + additional_pairs

    async def calculate_position_size(self, symbol: str, account_balance: Decimal) -> Tuple[Decimal, int]:
        """Calculate optimal position size and leverage based on account balance."""
        metrics = await self.analyze_pair_metrics(symbol)

        # Base position size on account balance and volatility
        max_position_pct = Decimal('0.1')  # Start with 10% max position size
        if account_balance > Decimal('10000'):
            max_position_pct = Decimal('0.15')  # Increase for larger accounts
        elif account_balance > Decimal('100000'):
            max_position_pct = Decimal('0.2')  # Further increase for very large accounts

        position_size = account_balance * max_position_pct

        # Adjust leverage based on account size and volatility
        if account_balance < Decimal('1000'):
            leverage = 20  # Higher leverage for small accounts
        elif account_balance < Decimal('10000'):
            leverage = 10  # Moderate leverage for medium accounts
        else:
            leverage = 5   # Conservative leverage for large accounts

        return position_size, leverage
