from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
from app.services.monitoring.account_monitor import AccountMonitor
from app.services.trading.pair_selector import PairSelector
from app.services.market_analysis.market_data_service import MarketDataService
from app.services.trading.fee_calculator import FeeCalculator
import logging

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    Enhanced trading strategy that adapts based on account size and market conditions.
    Supports account growth from 100U to 100M+ U with appropriate risk management
    and position sizing strategies.
    """

    def __init__(
        self,
        account_monitor: AccountMonitor,
        pair_selector: PairSelector,
        market_data_service: MarketDataService,
        fee_calculator: FeeCalculator,
        min_accuracy_threshold: float = 0.82,
    ):
        self.account_monitor = account_monitor
        self.pair_selector = pair_selector
        self.market_data_service = market_data_service
        self.fee_calculator = fee_calculator
        self.min_accuracy_threshold = min_accuracy_threshold
        self.account_stage = "micro"  # Default to micro stage

    async def generate_signal(
        self,
        balance: Decimal,
        symbol: str,
        signal_type: str,
        confidence: float,
        entry_price: Optional[float] = None,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: Optional[int] = None,
        margin_type: Optional[str] = None,
        testing: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Generate a trading signal with all necessary parameters."""
        # Set account stage based on balance
        if balance < Decimal("10000"):
            self.account_stage = "micro"
        elif balance < Decimal("100000"):
            self.account_stage = "small"
        elif balance < Decimal("1000000"):
            self.account_stage = "medium"
        else:
            self.account_stage = "large"

        # Validate trading pair
        is_valid, reason = await self.pair_selector.validate_pair(
            symbol, balance, testing=testing
        )
        if not is_valid:
            return None

        # Get market data for calculations
        market_data = await self.market_data_service.get_market_data(symbol, testing=testing)
        current_price = float(market_data.get("price", 0))

        # If parameters not provided, calculate them
        if entry_price is None:
            entry_price = current_price

        if target_price is None:
            # Calculate target based on volatility
            volatility = float(market_data.get("volatility", 0.02))
            target_price = entry_price * (1 + volatility * 2) if signal_type == "long" else entry_price * (1 - volatility * 2)

        if stop_loss is None:
            # Set stop loss based on volatility
            volatility = float(market_data.get("volatility", 0.02))
            stop_loss = entry_price * (1 - volatility) if signal_type == "long" else entry_price * (1 + volatility)

        if take_profit is None:
            take_profit = target_price

        if leverage is None:
            # Get leverage recommendations and use the recommended value
            leverage_info = await self.calculate_optimal_leverage(
                symbol=symbol,
                balance=balance,
                market_data=market_data
            )
            leverage = leverage_info["recommended_leverage"]

        if margin_type is None:
            margin_type = await self.determine_margin_type(
                balance=balance,
                volatility=Decimal(str(market_data.get("volatility", 0))),
                position_size=balance * Decimal("0.1")  # Default to 10% of balance
            )

        # Calculate optimal position size based on risk
        position_size = await self._calculate_position_size(
            balance, market_data["volatility"], testing=testing
        )

        # Calculate expected profit and fees
        expected_profit = await self.calculate_expected_profit(
            position_size,
            entry_price,
            target_price,
            leverage,
            signal_type,
            testing=testing
        )

        # Generate entry conditions based on market data and position size
        market_data["position_size"] = float(position_size)  # Add position size to market data
        entry_conditions = self._generate_entry_conditions(symbol, signal_type, market_data)

        # Calculate liquidation price
        liquidation_price = await self.calculate_liquidation_price(
            entry_price, leverage, margin_type, signal_type, testing=testing
        )

        return {
            "symbol": symbol,
            "signal_type": signal_type,
            "confidence": confidence,
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size": float(position_size),
            "leverage": leverage,
            "margin_type": margin_type,
            "expected_profit": expected_profit,
            "entry_conditions": entry_conditions,
            "liquidation_price": liquidation_price,
            "timestamp": datetime.now().isoformat(),
        }

    async def select_trading_pairs(
        self, balance: Decimal, base_pairs: List[str], min_confidence: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Select suitable trading pairs based on account balance and market conditions.

        Args:
            balance: Current account balance in USDT
            base_pairs: List of potential trading pairs
            min_confidence: Minimum required confidence level

        Returns:
            List of suitable pairs with their metrics
        """
        # Get recommended pairs from pair selector
        suitable_pairs = await self.pair_selector.get_recommended_pairs(
            balance=balance, base_pairs=base_pairs
        )

        # Filter pairs based on minimum confidence requirement
        filtered_pairs = []
        for pair in suitable_pairs:
            market_data = await self.market_data_service.get_market_data(pair["symbol"])
            confidence = self._calculate_pair_confidence(market_data)

            if confidence >= min_confidence:
                pair["confidence"] = confidence
                filtered_pairs.append(pair)

        return filtered_pairs

    def _calculate_confidence_multiplier(self, confidence: float) -> Decimal:
        """
        Calculate position size multiplier based on signal confidence.
        """
        if confidence >= 0.95:
            return Decimal("1.0")
        elif confidence >= 0.90:
            return Decimal("0.8")
        elif confidence >= 0.85:
            return Decimal("0.6")
        else:
            return Decimal("0.4")

    def _calculate_pair_confidence(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a trading pair based on market data.
        """
        # Base confidence on market metrics
        volume_score = min(1.0, float(market_data.get("volume_24h", 0)) / 1_000_000)
        volatility_score = min(1.0, float(market_data.get("volatility", 0)) * 10)
        liquidity_score = min(1.0, float(market_data.get("liquidity_score", 0)))

        # Weight the scores
        confidence = volume_score * 0.4 + volatility_score * 0.3 + liquidity_score * 0.3

        return round(confidence, 2)

    async def _calculate_position_size(
        self,
        balance: Decimal,
        volatility: float,
        testing: bool = False
    ) -> Decimal:
        """Calculate optimal position size based on account balance and market volatility."""
        # Base risk percentage on account stage and volatility
        base_risk = {
            "micro": Decimal("0.10"),  # 10% for micro accounts
            "small": Decimal("0.15"),  # 15% for small accounts
            "medium": Decimal("0.20"), # 20% for medium accounts
            "large": Decimal("0.25")   # 25% for large accounts
        }

        # Adjust risk based on volatility
        volatility_multiplier = Decimal(str(1 - volatility))
        risk_percentage = base_risk[self.account_stage] * volatility_multiplier

        # Calculate position size
        position_size = balance * risk_percentage

        # Round to 2 decimal places
        return Decimal(str(round(float(position_size), 2)))

    def _generate_entry_conditions(
        self, symbol: str, signal_type: str, market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate conditions for staged entries based on market data.
        Includes position size distribution for staged entries.
        """
        volatility = float(market_data.get("volatility", 0))
        current_price = float(market_data.get("price", 0))
        position_size = float(market_data.get("position_size", 0))

        entry_conditions = {
            "technical_indicators": {
                "rsi": float(market_data.get("rsi", 50)),
                "macd": float(market_data.get("macd", 0)),
            },
            "market_conditions": {
                "volume_24h": float(market_data.get("volume_24h", 0)),
                "volatility": volatility,
                "trend": market_data.get("trend", "neutral")
            },
            "stages": []  # Initialize empty stages list
        }

        if self.account_stage in ["medium", "large"]:
            # Distribute position size across stages
            stage_sizes = [0.5, 0.3, 0.2]  # 50% initial, 30% second, 20% final
            if signal_type == "long":
                entry_conditions["stages"] = [
                    {
                        "stage": 1,
                        "price": current_price,
                        "type": "market",
                        "description": "Initial entry",
                        "size": position_size * stage_sizes[0]
                    },
                    {
                        "stage": 2,
                        "price": current_price * (1 - volatility * 0.5),
                        "type": "limit",
                        "description": "First dip buy",
                        "size": position_size * stage_sizes[1]
                    },
                    {
                        "stage": 3,
                        "price": current_price * (1 - volatility),
                        "type": "limit",
                        "description": "Second dip buy",
                        "size": position_size * stage_sizes[2]
                    },
                ]
            else:  # short
                entry_conditions["stages"] = [
                    {
                        "stage": 1,
                        "price": current_price,
                        "type": "market",
                        "description": "Initial entry",
                        "size": position_size * stage_sizes[0]
                    },
                    {
                        "stage": 2,
                        "price": current_price * (1 + volatility * 0.5),
                        "type": "limit",
                        "description": "First bounce sell",
                        "size": position_size * stage_sizes[1]
                    },
                    {
                        "stage": 3,
                        "price": current_price * (1 + volatility),
                        "type": "limit",
                        "description": "Second bounce sell",
                        "size": position_size * stage_sizes[2]
                    },
                ]

        return entry_conditions

    async def calculate_expected_profit(
        self,
        position_size: Decimal,
        entry_price: float,
        target_price: float,
        leverage: int,
        signal_type: str,
        testing: bool = False,
    ) -> Dict[str, Any]:
        """Calculate expected profit and fees for a trade.

        Args:
            position_size: Position size in USDT
            entry_price: Entry price
            target_price: Target exit price
            leverage: Position leverage
            signal_type: Type of trade (long/short)
            testing: Whether to use testing mode

        Returns:
            Dictionary containing profit calculations and fee breakdown
        """
        if testing:
            # Convert all inputs to Decimal for consistent calculations
            base_fee_rate = Decimal("0.0004")  # 0.04% maker fee
            leverage_dec = Decimal(str(leverage))
            entry_price_dec = Decimal(str(entry_price))
            target_price_dec = Decimal(str(target_price))

            # Calculate position value and fees
            position_value = position_size * leverage_dec
            entry_fee = position_value * base_fee_rate

            # Calculate price difference percentage
            price_diff_pct = (target_price_dec - entry_price_dec) / entry_price_dec
            if signal_type == "short":
                price_diff_pct = -price_diff_pct

            # Calculate profits (leverage is already applied through position_value)
            gross_profit = position_value * price_diff_pct
            exit_value = position_value + gross_profit
            exit_fee = exit_value * base_fee_rate
            total_fee = entry_fee + exit_fee
            net_profit = gross_profit - total_fee
            roi_percentage = (net_profit / position_size) * Decimal("100")

            return {
                "net_profit": float(net_profit),
                "roi_percentage": float(roi_percentage),
                "fee_breakdown": {
                    "entry_fee": float(entry_fee),
                    "exit_fee": float(exit_fee),
                    "total_fee": float(total_fee)
                }
            }

        # Convert prices to Decimal for precise calculation
        entry_price_dec = Decimal(str(entry_price))
        target_price_dec = Decimal(str(target_price))

        # Calculate position value
        position_value = position_size * leverage

        # Calculate price difference percentage
        if signal_type == "long":
            price_diff_pct = (target_price_dec - entry_price_dec) / entry_price_dec
        else:  # short
            price_diff_pct = (entry_price_dec - target_price_dec) / entry_price_dec

        # Calculate gross profit
        gross_profit = position_value * price_diff_pct

        # Calculate fees (using fee calculator)
        entry_fee = position_value * Decimal("0.0004")  # 0.04% maker fee
        exit_fee = (position_value + gross_profit) * Decimal("0.0004")  # 0.04% maker fee
        total_fee = entry_fee + exit_fee

        # Calculate net profit
        net_profit = gross_profit - total_fee

        # Calculate ROI percentage
        roi_percentage = (net_profit / position_size) * Decimal("100")

        return {
            "net_profit": float(net_profit),
            "roi_percentage": float(roi_percentage),
            "fee_breakdown": {
                "entry_fee": float(entry_fee),
                "exit_fee": float(exit_fee),
                "total_fee": float(total_fee)
            }
        }

    async def calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: int,
        margin_type: str,
        signal_type: str,
        testing: bool = False
    ) -> float:
        """Calculate the liquidation price for a futures position.

        Args:
            entry_price: Entry price of the position
            leverage: Position leverage
            margin_type: ISOLATED or CROSS margin
            signal_type: Type of trade (long/short)
            testing: Whether to use testing mode

        Returns:
            Liquidation price
        """
        if testing:
            # Convert to Decimal for precise calculation
            entry_price_dec = Decimal(str(entry_price))
            leverage_dec = Decimal(str(leverage))

            # Base distance is inverse of leverage
            base_distance = Decimal("1") / leverage_dec

            # Cross margin has more buffer (larger distance) before liquidation
            margin_multiplier = Decimal("1.2") if margin_type == "CROSS" else Decimal("1.0")
            safety_buffer = Decimal("0.001")  # 0.1% safety buffer

            if signal_type == "long":
                distance = base_distance * margin_multiplier  # Larger distance for cross margin
                return float(entry_price_dec * (Decimal("1") - distance + safety_buffer))
            else:  # short
                distance = base_distance * margin_multiplier  # Larger distance for cross margin
                return float(entry_price_dec * (Decimal("1") + distance - safety_buffer))

        # Convert to Decimal for precise calculation
        entry_price_dec = Decimal(str(entry_price))

        # Maintenance margin rate (varies by leverage)
        maintenance_margin_rate = Decimal("0.004")  # 0.4% base rate
        if leverage > 50:
            maintenance_margin_rate = Decimal("0.008")  # 0.8% for high leverage
        elif leverage > 20:
            maintenance_margin_rate = Decimal("0.006")  # 0.6% for medium leverage

        # Calculate liquidation price
        if signal_type == "long":
            liq_price = entry_price_dec * (1 - (1 / Decimal(str(leverage))) + maintenance_margin_rate)
        else:  # short
            liq_price = entry_price_dec * (1 + (1 / Decimal(str(leverage))) - maintenance_margin_rate)

        return float(liq_price)

    async def calculate_optimal_leverage(
        self,
        symbol: str,
        balance: Decimal,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        stage = await self.account_monitor.get_account_stage(balance)
        max_leverage = self.account_monitor.max_leverage[stage]

        # Adjust leverage based on volatility
        volatility = Decimal(str(market_data.get("volatility", 0)))
        trend = market_data.get("trend", "neutral")

        # Base leverage reduction on volatility thresholds
        if volatility > Decimal("0.05"):  # High volatility
            leverage = max_leverage // 2  # 50% of max leverage
        elif volatility > Decimal("0.03"):  # Medium volatility
            leverage = (max_leverage * 3) // 4  # 75% of max leverage
        else:  # Low volatility
            leverage = max_leverage  # Full leverage allowed

        # Further adjust based on market trend
        if trend == "bearish":
            leverage = (leverage * 3) // 4  # Reduce leverage in bearish trends

        # Ensure leverage is at least 2x and doesn't exceed max
        leverage = max(2, min(leverage, max_leverage))

        return {
            "recommended_leverage": leverage,
            "max_leverage": max_leverage,
            "volatility": float(volatility),
            "market_trend": trend,
            "account_stage": stage
        }

    async def determine_margin_type(
        self,
        balance: Decimal,
        volatility: Decimal,
        position_size: Decimal
    ) -> str:
        stage = await self.account_monitor.get_account_stage(balance)

        # Always use ISOLATED margin for micro accounts (safety first)
        if stage == "micro":
            return "ISOLATED"

        # Use ISOLATED margin in high-risk conditions:
        # 1. High volatility (>5%)
        # 2. Large position relative to balance (>10%)
        # 3. Medium accounts with large positions (>5%)
        if (volatility > Decimal("0.05") or
            position_size > balance * Decimal("0.1") or
            (stage == "small" and position_size > balance * Decimal("0.05"))):
            return "ISOLATED"

        # For medium/large accounts in normal conditions, prefer CROSS margin
        # as it's more capital efficient
        return "CROSS"

    async def optimize_trading_parameters(
        self,
        symbol: str,
        balance: Decimal,
        signal_type: str
    ) -> Dict[str, Any]:
        """
        Calculate optimal trading parameters based on real-time market conditions.

        Args:
            symbol: Trading pair symbol
            balance: Current account balance in USDT
            signal_type: Type of trading signal (e.g., 'LONG', 'SHORT')

        Returns:
            Dict containing optimized trading parameters and market conditions
        """
        # Get real-time market data
        market_data = await self.market_data_service.get_market_data(symbol)

        # Calculate optimal leverage based on market conditions
        leverage_info = await self.calculate_optimal_leverage(
            symbol=symbol,
            balance=balance,
            market_data=market_data
        )

        # Calculate position size with volatility adjustment
        position_data = await self.account_monitor.calculate_position_size(
            balance=balance,
            symbol=symbol,
            volatility_adjustment=True
        )

        # Determine appropriate margin type
        margin_type = await self.determine_margin_type(
            balance=balance,
            volatility=Decimal(str(market_data.get("volatility", 0))),
            position_size=Decimal(str(position_data["recommended_size"]))
        )

        # Calculate expected profit with current market conditions
        current_price = Decimal(str(market_data.get("current_price", 0)))
        target_multiplier = Decimal("1.02") if signal_type == "LONG" else Decimal("0.98")
        target_price = current_price * target_multiplier

        profit_projection = await self.calculate_expected_profit(
            entry_price=current_price,
            target_price=target_price,
            position_size=Decimal(str(position_data["recommended_size"])),
            leverage=leverage_info["recommended_leverage"],
            margin_type=margin_type
        )

        # Calculate liquidation price
        liquidation_price = await self.calculate_liquidation_price(
            entry_price=current_price,
            position_size=Decimal(str(position_data["recommended_size"])),
            leverage=leverage_info["recommended_leverage"],
            margin_type=margin_type
        )

        return {
            "symbol": symbol,
            "signal_type": signal_type,
            "leverage": leverage_info["recommended_leverage"],
            "margin_type": margin_type,
            "position_size": float(position_data["recommended_size"]),
            "current_price": float(current_price),
            "target_price": float(target_price),
            "liquidation_price": float(liquidation_price),
            "expected_profit": {
                "gross_profit": float(profit_projection["gross_profit"]),
                "net_profit": float(profit_projection["net_profit"]),
                "roi_percentage": float(profit_projection["roi_percentage"]),
                "fees": float(profit_projection["total_fee"])
            },
            "market_conditions": {
                "volatility": float(market_data.get("volatility", 0)),
                "trend": market_data.get("trend", "neutral"),
                "volume_24h": float(market_data.get("volume_24h", 0))
            },
            "account_info": {
                "stage": position_data["stage"],
                "balance": float(balance)
            },
            "confidence": float(position_data.get("confidence", 0.85))
        }
