"""Portfolio manager for tracking positions and performance"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np


@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    position_type: str
    asset_type: str = "stock"
    strike: Optional[float] = None
    expiry: Optional[datetime] = None
    option_type: Optional[str] = None
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    margin: float = 0.0
    margin_ratio: float = 0.0
    metadata: Dict = field(default_factory=dict)

    @property
    def market_value(self) -> float:
        """Calculate current market value (long: positive, short: negative for portfolio)"""
        if self.position_type == "long":
            return self.quantity * self.current_price
        else:
            return -(self.quantity * self.current_price)

    @property
    def short_market_value_abs(self) -> float:
        """Absolute market value of short position"""
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L"""
        if self.position_type == "long":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage"""
        if self.entry_price == 0:
            return 0.0
        if self.position_type == "long":
            return (self.current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.current_price) / self.entry_price * 100


class PortfolioManager:
    """Manage portfolio positions, cash, and performance with short position support"""

    def __init__(self, initial_capital: float = 1000000.0,
                 max_position_size: float = 0.1,
                 margin_ratio: float = 0.20,
                 borrowing_cost_annual: float = 0.02):
        self.initial_capital = initial_capital
        self.max_position_size = max_position_size
        self.margin_ratio = margin_ratio
        self.borrowing_cost_annual = borrowing_cost_annual
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.trade_history: List[Dict] = []
        self.equity_curve: List[Dict] = []

    def open_position(self, symbol: str, quantity: float, price: float,
                     timestamp: datetime, position_type: str = "long",
                     asset_type: str = "stock", **kwargs) -> bool:
        """Open a new position with position size limit check and short margin logic"""
        portfolio_value = self.get_total_value()
        position_key = self._get_position_key(symbol, asset_type, kwargs, position_type)

        if position_type == "long":
            cost = quantity * price
            if position_key in self.positions:
                existing = self.positions[position_key]
                new_total_value = (existing.quantity + quantity) * price
                if new_total_value / portfolio_value > self.max_position_size:
                    max_allowed_qty = int(portfolio_value * self.max_position_size / price) - int(existing.quantity)
                    if max_allowed_qty <= 0:
                        return False
                    quantity = max_allowed_qty
                    cost = quantity * price
                if cost > self.cash:
                    return False
                total_quantity = existing.quantity + quantity
                avg_price = (existing.entry_price * existing.quantity + price * quantity) / total_quantity
                existing.quantity = total_quantity
                existing.entry_price = avg_price
            else:
                if cost / portfolio_value > self.max_position_size:
                    quantity = int(portfolio_value * self.max_position_size / price)
                    cost = quantity * price
                if cost > self.cash or quantity <= 0:
                    return False
                position_kwargs = {
                    'strike': kwargs.get('strike'),
                    'expiry': kwargs.get('expiry'),
                    'option_type': kwargs.get('option_type')
                }
                position_kwargs = {k: v for k, v in position_kwargs.items() if v is not None}
                metadata = {k: v for k, v in kwargs.items() if k not in ['strike', 'expiry', 'option_type']}
                position = Position(
                    symbol=symbol, quantity=quantity, entry_price=price,
                    entry_time=timestamp, position_type=position_type,
                    asset_type=asset_type, current_price=price,
                    metadata=metadata, **position_kwargs
                )
                self.positions[position_key] = position

            self.cash -= cost
            self._record_trade(timestamp, symbol, "BUY", quantity, price, asset_type)

        elif position_type == "short":
            proceeds = quantity * price
            margin = proceeds * self.margin_ratio

            short_value_abs = quantity * price
            if position_key in self.positions:
                existing = self.positions[position_key]
                new_total_abs = (existing.quantity + quantity) * price
                if new_total_abs / portfolio_value > self.max_position_size:
                    max_allowed_qty = int(portfolio_value * self.max_position_size / price) - int(existing.quantity)
                    if max_allowed_qty <= 0:
                        return False
                    quantity = max_allowed_qty
                    proceeds = quantity * price
                    margin = proceeds * self.margin_ratio
                if margin > self.cash:
                    return False
                total_quantity = existing.quantity + quantity
                avg_price = (existing.entry_price * existing.quantity + price * quantity) / total_quantity
                existing.quantity = total_quantity
                existing.entry_price = avg_price
                existing.margin += margin
            else:
                if short_value_abs / portfolio_value > self.max_position_size:
                    quantity = int(portfolio_value * self.max_position_size / price)
                    proceeds = quantity * price
                    margin = proceeds * self.margin_ratio
                if margin > self.cash or quantity <= 0:
                    return False
                position_kwargs = {
                    'strike': kwargs.get('strike'),
                    'expiry': kwargs.get('expiry'),
                    'option_type': kwargs.get('option_type')
                }
                position_kwargs = {k: v for k, v in position_kwargs.items() if v is not None}
                metadata = {k: v for k, v in kwargs.items() if k not in ['strike', 'expiry', 'option_type']}
                position = Position(
                    symbol=symbol, quantity=quantity, entry_price=price,
                    entry_time=timestamp, position_type='short',
                    asset_type=asset_type, current_price=price,
                    margin=margin, margin_ratio=self.margin_ratio,
                    metadata=metadata, **position_kwargs
                )
                self.positions[position_key] = position

            self.cash += proceeds - margin
            self._record_trade(timestamp, symbol, "SELL_SHORT", quantity, price, asset_type)

        return True

    def close_position(self, symbol: str, quantity: float, price: float,
                       timestamp: datetime, asset_type: str = "stock",
                       position_type: str = "long", **kwargs) -> bool:
        """Close an existing position"""
        position_key = self._get_position_key(symbol, asset_type, kwargs, position_type)

        if position_key not in self.positions:
            return False

        position = self.positions[position_key]
        if quantity > position.quantity:
            quantity = position.quantity

        if position.position_type == "long":
            proceeds = quantity * price
            self.cash += proceeds
        elif position.position_type == "short":
            cost_to_close = quantity * price
            margin_released = position.margin * (quantity / position.quantity)
            self.cash += margin_released - cost_to_close
        if quantity == position.quantity:
            closed_pos = self.positions.pop(position_key)
            closed_pos.current_price = price
            self.closed_positions.append(closed_pos)
        else:
            position.quantity -= quantity
            if position.position_type == "short":
                position.margin -= margin_released
        action = "SELL" if position.position_type == "long" else "BUY_TO_COVER"
        self._record_trade(timestamp, symbol, action, quantity, price, asset_type)
        return True

    def update_prices(self, prices: Dict[str, float], timestamp: datetime):
        """Update current prices for all positions

        Args:
            prices: Dictionary mapping position key to current price
            timestamp: Current timestamp
        """
        for key, position in self.positions.items():
            if position.symbol in prices:
                new_price = prices[position.symbol]
                position.current_price = new_price
                if position.position_type == "long":
                    if position.highest_price == 0.0 or new_price > position.highest_price:
                        position.highest_price = new_price
                elif position.position_type == "short":
                    if position.lowest_price == float('inf') or new_price < position.lowest_price:
                        position.lowest_price = new_price

        self._record_equity(timestamp)

    def get_total_value(self) -> float:
        """Get total portfolio value = cash + long + (margin - short_exposure)"""
        long_value = sum(pos.market_value for pos in self.positions.values() if pos.position_type == "long")
        short_margin = sum(pos.margin for pos in self.positions.values() if pos.position_type == "short")
        short_exposure = sum(pos.short_market_value_abs for pos in self.positions.values() if pos.position_type == "short")
        return self.cash + long_value + short_margin - short_exposure

    def get_positions_value(self) -> float:
        """Get gross exposure (long + short absolute)"""
        long_value = sum(pos.market_value for pos in self.positions.values() if pos.position_type == "long")
        short_exposure = sum(pos.short_market_value_abs for pos in self.positions.values() if pos.position_type == "short")
        return long_value + short_exposure

    def get_total_pnl(self) -> float:
        """Get total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    def get_position(self, symbol: str, asset_type: str = "stock",
                     position_type: str = "long", **kwargs) -> Optional[Position]:
        """Get position by symbol and type"""
        position_key = self._get_position_key(symbol, asset_type, kwargs, position_type)
        return self.positions.get(position_key)

    def has_position(self, symbol: str, asset_type: str = "stock",
                     position_type: str = "long", **kwargs) -> bool:
        """Check if position exists"""
        position_key = self._get_position_key(symbol, asset_type, kwargs, position_type)
        return position_key in self.positions

    def get_performance_metrics(self) -> Dict:
        """Calculate portfolio performance metrics"""
        if not self.equity_curve:
            return {}
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['returns'] = equity_df['total_value'].pct_change()
        total_return = (self.get_total_value() - self.initial_capital) / self.initial_capital
        returns = equity_df['returns'].dropna()
        sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if len(returns) > 0 else 0
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min() if len(drawdown) > 0 else 0
        positions_value = self.get_positions_value()
        long_value = sum(pos.market_value for pos in self.positions.values() if pos.position_type == "long")
        short_margin = sum(pos.margin for pos in self.positions.values() if pos.position_type == "short")
        short_exposure = sum(pos.short_market_value_abs for pos in self.positions.values() if pos.position_type == "short")
        win_trades = [t for t in self.closed_positions if t.unrealized_pnl > 0]
        win_rate = len(win_trades) / len(self.closed_positions) if self.closed_positions else 0
        return {
            'total_value': self.cash + long_value + short_margin - short_exposure,
            'cash': self.cash,
            'positions_value': positions_value,
            'long_value': long_value,
            'short_exposure': short_exposure,
            'short_margin': short_margin,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'num_trades': len(self.trade_history),
            'num_positions': len(self.positions),
            'win_rate': win_rate,
            'num_closed_positions': len(self.closed_positions)
        }

    def get_equity_curve_df(self) -> pd.DataFrame:
        """Get equity curve as DataFrame"""
        return pd.DataFrame(self.equity_curve)

    def get_trade_history_df(self) -> pd.DataFrame:
        """Get trade history as DataFrame"""
        return pd.DataFrame(self.trade_history)

    def _get_position_key(self, symbol: str, asset_type: str, kwargs: Dict,
                          position_type: str = "long") -> str:
        """Generate unique position key including position_type"""
        if asset_type == "option":
            strike = kwargs.get('strike', '')
            expiry = kwargs.get('expiry', '')
            option_type = kwargs.get('option_type', '')
            return f"{symbol}_{asset_type}_{position_type}_{strike}_{expiry}_{option_type}"
        return f"{symbol}_{asset_type}_{position_type}"

    def _record_trade(self, timestamp: datetime, symbol: str, action: str, 
                     quantity: float, price: float, asset_type: str):
        """Record trade in history"""
        self.trade_history.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'asset_type': asset_type,
            'value': quantity * price
        })

    def _record_equity(self, timestamp: datetime):
        """Record equity curve point"""
        self.equity_curve.append({
            'timestamp': timestamp,
            'cash': self.cash,
            'positions_value': self.get_positions_value(),
            'total_value': self.get_total_value()
        })
