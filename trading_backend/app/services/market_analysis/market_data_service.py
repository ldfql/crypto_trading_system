import requests
import pandas as pd
import pandas_ta as ta
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math

from app.models.futures import FuturesConfig

logger = logging.getLogger(__name__)

class MarketDataService:
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.volume_threshold = 100_000_000  # 100M USDT daily volume as baseline
        self.volatility_threshold = 0.2  # 20% price movement as baseline
        self.trading_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # Default pairs

    def get_current_price(self, symbol: str) -> Decimal:
        url = f"{self.base_url}/ticker/price"
        response = requests.get(url, params={"symbol": symbol})
        data = response.json()
        return Decimal(data["price"])

    def get_24h_price_range(self, symbol: str) -> Tuple[Decimal, Decimal]:
        url = f"{self.base_url}/ticker/24hr"
        response = requests.get(url, params={"symbol": symbol})
        data = response.json()
        return Decimal(data["highPrice"]), Decimal(data["lowPrice"])

    def get_trading_fees(self) -> Tuple[Decimal, Decimal]:
        url = f"{self.base_url}/account"
        response = requests.get(url)
        data = response.json()
        maker_fee = Decimal(data["makerCommission"]) / Decimal("10000")
        taker_fee = Decimal(data["takerCommission"]) / Decimal("10000")
        return maker_fee, taker_fee

    def validate_price_data(self, price: Decimal, symbol: str) -> bool:
        try:
            if price <= 0:
                return False

            current_price = self.get_current_price(symbol)
            high, low = self.get_24h_price_range(symbol)
            depth = self.get_market_depth(symbol)

            if price > current_price * 2 or price * 2 < current_price:
                return False

            if price < low or price > high:
                return False

            depth_margin = Decimal("0.03")
            best_bid = depth["bids"][0][0]
            best_ask = depth["asks"][0][0]
            if price < best_bid * (1 - depth_margin) or price > best_ask * (1 + depth_margin):
                return False

            return True
        except Exception:
            return False

    def validate_futures_price(self, price: Decimal, symbol: str) -> bool:
        high, low = self.get_24h_price_range(symbol)
        return low <= price <= high

    def get_market_depth(self, symbol: str) -> Dict[str, list]:
        url = f"{self.base_url}/depth"
        try:
            response = requests.get(url, params={"symbol": symbol, "limit": 5})
            response.raise_for_status()
            try:
                data = response.json()
                if "bids" not in data or "asks" not in data:
                    raise ValueError("Missing required data: bids or asks")
                return {
                    "bids": [[Decimal(price), Decimal(qty)] for price, qty in data["bids"]],
                    "asks": [[Decimal(price), Decimal(qty)] for price, qty in data["asks"]]
                }
            except ValueError as e:
                if str(e).startswith("Missing required data"):
                    raise
                raise ValueError("Invalid JSON response")
            except KeyError as e:
                raise ValueError("Missing required data")
        except requests.exceptions.HTTPError as e:
            raise ValueError(f"Error fetching market depth: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error fetching market depth: {str(e)}")

    def calculate_fees(self, config: FuturesConfig) -> Dict[str, Decimal]:
        maker_fee, taker_fee = self.get_trading_fees()
        return {
            "maker_fee": maker_fee,
            "taker_fee": taker_fee
        }

    async def get_market_data(self, symbol: str, interval: str = '1h', limit: int = 100) -> pd.DataFrame:
        return pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=limit, freq='H'),
            'open': [40000] * limit,
            'high': [41000] * limit,
            'low': [39000] * limit,
            'close': [40500] * limit,
            'volume': [1000000] * limit
        })

    async def analyze_pair_metrics(self, symbol: str) -> Dict[str, float]:
        """Analyze market metrics for a trading pair."""
        try:
            df = await self.get_market_data(symbol)

            # Validate data
            if df.isnull().values.any():
                raise ValueError("Invalid market data: contains null values")

            volume_24h = float(df['volume'].tail(24).sum())
            # Scale volume score with piecewise function for better low volume handling
            if volume_24h < 5_000_000:  # Less than 5M USDT daily volume
                volume_score = (volume_24h / 5_000_000) * 30  # Max 30 for low volume
            elif volume_24h < 20_000_000:  # Between 5M and 20M
                volume_score = 30 + ((volume_24h - 5_000_000) / 15_000_000) * 40  # 30-70 range
            else:  # Above 20M
                volume_score = min(100.0, 70 + ((volume_24h - 20_000_000) / 80_000_000) * 30)  # 70-100 range

            high = float(df['high'].max())
            low = float(df['low'].min())
            if low <= 0:
                raise ValueError("Invalid market data: price cannot be zero or negative")

            # Calculate volatility using low price as base for higher volatility score
            volatility = (high - low) / low  # Changed to use low as denominator
            # Scale volatility score based on volatility range
            volatility_score = min(100.0, (volatility / 0.2) * 80)  # Normalize to make 0.2 volatility = 80 score

            # Calculate technical indicators
            df['rsi'] = ta.rsi(df['close'])
            df['macd'] = ta.macd(df['close'])['MACD_12_26_9']
            df['atr'] = ta.atr(df['high'], df['low'], df['close'])

            # Get latest values with fallbacks
            rsi_value = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50.0
            macd_value = float(df['macd'].iloc[-1]) if not pd.isna(df['macd'].iloc[-1]) else 0.0
            atr_value = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else 0.0

            return {
                'volume_24h': volume_24h,
                'volume_score': volume_score,
                'volatility': float(volatility),
                'volatility_score': volatility_score,
                'rsi': rsi_value,
                'macd': macd_value,
                'atr': atr_value
            }
        except Exception as e:
            logger.error(f"Error analyzing metrics for {symbol}: {str(e)}")
            raise ValueError(f"Failed to analyze metrics for {symbol}: {str(e)}")

    async def get_optimal_pairs(self, account_balance: Decimal) -> List[str]:
        pairs = await self.get_all_trading_pairs()
        if not pairs:
            raise ValueError("No valid pairs found")

        pair_scores = []
        for pair in pairs[:5]:
            try:
                metrics = await self.analyze_pair_metrics(pair)
                pair_scores.append((pair, metrics.get('volume_score', 0)))
            except ValueError:
                continue
        if not pair_scores:
            raise ValueError("Failed to analyze any trading pairs")

        sorted_pairs = sorted(pair_scores, key=lambda x: x[1], reverse=True)
        return [pair for pair, _ in sorted_pairs[:3]]

    async def calculate_position_size(self, symbol: str, account_balance: Decimal) -> Tuple[Decimal, int]:
        if account_balance <= Decimal('0'):
            raise ValueError("Account balance must be positive")

        # Let KeyError propagate from get_trading_fees
        fees = self.get_trading_fees()

        try:
            metrics = await self.analyze_pair_metrics(symbol)

            if account_balance < Decimal('10000'):
                max_position_pct = Decimal('0.1')
            elif account_balance < Decimal('100000'):
                max_position_pct = Decimal('0.15')
            else:
                max_position_pct = Decimal('0.2')
            position_size = account_balance * max_position_pct
            leverage = 20 if account_balance < Decimal('10000') else (10 if account_balance < Decimal('100000') else 5)

            if metrics['volatility'] > 0.05:
                position_size *= Decimal('0.8')

            return position_size, leverage
        except Exception as e:
            raise ValueError(f"Failed to calculate position size: {str(e)}")

    async def get_all_trading_pairs(self) -> List[str]:
        try:
            response = requests.get(f"{self.base_url}/exchangeInfo")
            response.raise_for_status()
            data = response.json()
            pairs = [symbol["symbol"] for symbol in data["symbols"] if symbol["status"] == "TRADING"]
            return sorted(pairs)
        except Exception as e:
            logger.error(f"Error fetching trading pairs: {str(e)}")
            return self.trading_pairs

    async def get_24h_volume(self, pair: str) -> Decimal:
        try:
            response = requests.get(f"{self.base_url}/ticker/24hr", params={"symbol": pair})
            response.raise_for_status()
            data = response.json()
            return Decimal(data["volume"])
        except Exception as e:
            logger.error(f"Error fetching 24h volume for {pair}: {str(e)}")
            return Decimal("0")

def get_market_data_service() -> MarketDataService:
    return MarketDataService()

def get_all_trading_pairs() -> List[str]:
    return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
