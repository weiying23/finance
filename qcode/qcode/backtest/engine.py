"""Backtesting engine with full signal handling, stop-loss, optimization, and risk controls"""
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tqdm import tqdm

from qcode.strategies.base import BaseStrategy, SignalType
from qcode.portfolio.manager import PortfolioManager
from qcode.risk.manager import RiskManager
from qcode.data.fetcher import DataFetcher
from qcode.utils.significance import calculate_factor_significance


class BacktestEngine:
    """Backtesting engine with multi-asset support, delta hedging, optimization, and risk controls"""

    def __init__(self, initial_capital: float = 1000000.0,
                 commission: float = 0.0003,
                 slippage: float = 0.0001,
                 enable_delta_hedging: bool = True,
                 use_sample_data: bool = False,
                 market_regime: str = 'bear',
                 max_position_size: float = 0.1,
                 stop_loss_pct: float = 0.02,
                 target_portfolio_vol: float = 0.15,
                 position_method: str = 'risk_parity',
                 max_weight: float = 0.15,
                 rebalance_threshold: float = 0.10,
                 shrinkage_alpha: float = 0.5,
                 max_single_trade_pct: float = 0.03,
                 max_splits: int = 5,
                 rebalance_freq: str = 'monthly',
                 margin_ratio: float = 0.20,
                 borrowing_cost_annual: float = 0.02):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.enable_delta_hedging = enable_delta_hedging
        self.position_method = position_method
        self.rebalance_threshold = rebalance_threshold
        self.max_single_trade_pct = max_single_trade_pct
        self.max_splits = max_splits
        self.rebalance_freq = rebalance_freq
        self._last_rebalance_month = None

        self.portfolio = PortfolioManager(
            initial_capital, max_position_size,
            margin_ratio=margin_ratio,
            borrowing_cost_annual=borrowing_cost_annual
        )
        self.risk_manager = RiskManager(
            max_position_size=max_position_size,
            stop_loss_pct=stop_loss_pct,
            target_portfolio_vol=target_portfolio_vol
        )
        self.data_fetcher = DataFetcher(use_sample_data=use_sample_data, market_regime=market_regime)

        self.strategies: List[BaseStrategy] = []
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.pending_orders: List[Dict] = []
        self.results = None

    def add_strategy(self, strategy: BaseStrategy):
        """Add a trading strategy"""
        self.strategies.append(strategy)

    def load_data(self, symbols: List[str], start_date: str, end_date: str):
        """Load market data for backtesting"""
        print(f"Loading data for {len(symbols)} symbols...")
        self.market_data = self.data_fetcher.get_multiple_stocks(symbols, start_date, end_date)
        print(f"Loaded data for {len(self.market_data)} symbols")

    def run(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Run backtest"""
        if not self.market_data:
            raise ValueError("No market data loaded. Call load_data() first.")
        if not self.strategies:
            raise ValueError("No strategies added. Call add_strategy() first.")

        all_dates = self._get_trading_dates(start_date, end_date)

        print(f"Running backtest from {all_dates[0]} to {all_dates[-1]}...")
        print(f"Total trading days: {len(all_dates)}")

        for current_date in tqdm(all_dates, desc="Backtesting"):
            self._process_date(current_date)

        self.results = self._calculate_results()
        return self.results

    def run_walk_forward(self, train_months: int = 6, test_months: int = 1,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> List[Dict]:
        """Walk-forward segmented backtest for stability verification"""
        all_dates = self._get_trading_dates(start_date, end_date)
        results = []

        train_days = train_months * 22
        test_days = test_months * 22
        pos = 0

        while pos + train_days + test_days <= len(all_dates):
            train_slice = all_dates[pos:pos + train_days]
            test_slice = all_dates[pos + train_days:pos + train_days + test_days]

            for current_date in train_slice:
                self._process_date(current_date)

            test_engine = BacktestEngine(
                initial_capital=self.portfolio.get_total_value(),
                commission=self.commission,
                slippage=self.slippage,
                enable_delta_hedging=self.enable_delta_hedging,
                position_method=self.position_method,
                max_single_trade_pct=self.max_single_trade_pct,
                max_splits=self.max_splits
            )
            for strategy in self.strategies:
                test_engine.add_strategy(strategy)
            test_engine.market_data = self.market_data

            for current_date in test_slice:
                test_engine._process_date(current_date)

            test_metrics = test_engine._calculate_results()
            results.append({
                'train_period': (str(train_slice[0]), str(train_slice[-1])),
                'test_period': (str(test_slice[0]), str(test_slice[-1])),
                'metrics': test_metrics
            })

            pos += train_days + test_days

        return results

    def _process_date(self, current_date: pd.Timestamp):
        """Process signals and positions for a single date"""
        current_prices = self._get_current_prices(current_date)

        if not current_prices:
            return

        self.portfolio.update_prices(current_prices, current_date)

        self._execute_pending_orders(current_date, current_prices)
        self._check_stop_losses(current_date, current_prices)

        available_data = self._get_historical_data(current_date)

        all_signals = []
        for strategy in self.strategies:
            signals = strategy.generate_signals(available_data)
            all_signals.extend(signals)

        resolved_signals = self._resolve_signal_conflicts(all_signals)
        has_strategy_signals = len(resolved_signals) > 0

        for signal in resolved_signals:
            self._execute_signal(signal, current_prices.get(signal.symbol, signal.price))

        self._check_portfolio_risk(current_date, current_prices)

        if not has_strategy_signals and self.rebalance_freq != 'none':
            should_rebalance = False
            if self.rebalance_freq == 'monthly':
                current_month = current_date.strftime('%Y-%m')
                if current_month != self._last_rebalance_month:
                    should_rebalance = True
                    self._last_rebalance_month = current_month
            elif self.rebalance_freq == 'daily':
                should_rebalance = True

            if should_rebalance:
                self._rebalance_portfolio(current_date, current_prices)

        if self.enable_delta_hedging:
            self._perform_delta_hedge(current_date, current_prices)

    def _execute_pending_orders(self, current_date: pd.Timestamp,
                                current_prices: Dict[str, float]):
        """Execute one batch from each pending order"""
        remaining = []
        for order in self.pending_orders:
            symbol = order['symbol']
            if symbol not in current_prices:
                remaining.append(order)
                continue

            price = self._apply_costs(current_prices[symbol], order['signal_type'])
            size = order['size_per_batch']

            if order['signal_type'] in [SignalType.BUY, SignalType.BUY_CALL, SignalType.BUY_PUT]:
                self.portfolio.open_position(
                    symbol, size, price, current_date,
                    position_type=order.get('position_type', 'long'),
                    asset_type=order.get('asset_type', 'stock'),
                    **order.get('metadata', {})
                )
            elif order['signal_type'] == SignalType.OPEN_SHORT:
                self.portfolio.open_position(
                    symbol, size, price, current_date,
                    position_type='short',
                    asset_type=order.get('asset_type', 'stock'),
                    **order.get('metadata', {})
                )
            elif order['signal_type'] in [SignalType.CLOSE_LONG]:
                self.portfolio.close_position(
                    symbol, size, price, current_date,
                    position_type='long',
                    asset_type=order.get('asset_type', 'stock')
                )
            elif order['signal_type'] == SignalType.CLOSE_SHORT:
                self.portfolio.close_position(
                    symbol, size, price, current_date,
                    position_type='short',
                    asset_type=order.get('asset_type', 'stock')
                )

            order['remaining_size'] -= size
            if order['remaining_size'] > 0:
                remaining.append(order)

        self.pending_orders = remaining

    def _check_stop_losses(self, current_date: pd.Timestamp,
                           current_prices: Dict[str, float]):
        """Check and execute trailing stop-losses for all positions

        Long: stop triggers when price drops below (highest_price * (1 - stop_loss_pct))
        Short: stop triggers when price rises above (lowest_price * (1 + stop_loss_pct))
        """
        stop_loss_pct = self.risk_manager.stop_loss_pct

        for pos_key, position in list(self.portfolio.positions.items()):
            if position.position_type == 'long':
                reference_price = position.highest_price if position.highest_price > 0 else position.entry_price
                drawdown_pct = (position.current_price - reference_price) / reference_price
                if drawdown_pct < -stop_loss_pct:
                    if position.symbol in current_prices:
                        self.portfolio.close_position(
                            position.symbol, position.quantity,
                            current_prices[position.symbol], current_date,
                            position_type='long',
                            asset_type=position.asset_type
                        )
            elif position.position_type == 'short':
                reference_price = position.lowest_price if position.lowest_price < float('inf') else position.entry_price
                rise_pct = (position.current_price - reference_price) / reference_price
                if rise_pct > stop_loss_pct:
                    if position.symbol in current_prices:
                        self.portfolio.close_position(
                            position.symbol, position.quantity,
                            current_prices[position.symbol], current_date,
                            position_type='short',
                            asset_type=position.asset_type
                        )

    def _resolve_signal_conflicts(self, signals: List) -> List:
        """Resolve conflicting signals for the same symbol

        Key principle: long and short positions are independent.
        Only truly conflicting pairs:
        - BUY + CLOSE_LONG: close first, don't open new long (safety)
        - OPEN_SHORT + CLOSE_SHORT: close first, don't open new short
        - BUY + CLOSE_LONG + OPEN_SHORT: close long, then open short (no new long)
        """
        by_symbol: Dict[str, List] = {}
        for signal in signals:
            key = signal.symbol
            if key not in by_symbol:
                by_symbol[key] = []
            by_symbol[key].append(signal)

        resolved = []
        for symbol, sig_list in by_symbol.items():
            has_buy = any(s.signal_type == SignalType.BUY for s in sig_list)
            has_close_long = any(s.signal_type == SignalType.CLOSE_LONG for s in sig_list)
            has_open_short = any(s.signal_type == SignalType.OPEN_SHORT for s in sig_list)
            has_close_short = any(s.signal_type == SignalType.CLOSE_SHORT for s in sig_list)

            if has_buy and has_close_long:
                for s in sig_list:
                    if s.signal_type != SignalType.BUY:
                        resolved.append(s)
            elif has_open_short and has_close_short:
                for s in sig_list:
                    if s.signal_type != SignalType.OPEN_SHORT:
                        resolved.append(s)
            else:
                seen = set()
                for s in sig_list:
                    if s.signal_type not in seen:
                        resolved.append(s)
                        seen.add(s.signal_type)

        return resolved

    def _execute_signal(self, signal, current_price: float):
        """Execute a trading signal with confidence-weighted sizing and split execution"""
        if current_price is None or current_price <= 0:
            return

        execution_price = self._apply_costs(current_price, signal.signal_type)
        portfolio_value = self.portfolio.get_total_value()

        if signal.signal_type in [SignalType.BUY, SignalType.BUY_CALL, SignalType.BUY_PUT]:
            position_size = self.risk_manager.calculate_position_size(
                portfolio_value, execution_price,
                confidence=signal.confidence
            )

            if signal.quantity > 0:
                position_size = min(position_size, int(signal.quantity))

            if position_size > 0:
                trade_value = position_size * execution_price
                max_single = portfolio_value * self.max_single_trade_pct

                if trade_value > max_single and self.max_splits > 1:
                    n_splits = min(int(np.ceil(trade_value / max_single)), self.max_splits)
                    size_per_batch = int(position_size / n_splits)

                    asset_type = 'option' if 'CALL' in signal.signal_type.value or 'PUT' in signal.signal_type.value else 'stock'
                    self.portfolio.open_position(
                        signal.symbol, size_per_batch, execution_price,
                        signal.timestamp, position_type='long', asset_type=asset_type,
                        **signal.metadata if signal.metadata else {}
                    )
                    if position_size - size_per_batch > 0:
                        self.pending_orders.append({
                            'symbol': signal.symbol,
                            'signal_type': signal.signal_type,
                            'remaining_size': position_size - size_per_batch,
                            'size_per_batch': size_per_batch,
                            'asset_type': asset_type,
                            'position_type': 'long',
                            'metadata': signal.metadata or {}
                        })
                else:
                    asset_type = 'option' if 'CALL' in signal.signal_type.value or 'PUT' in signal.signal_type.value else 'stock'
                    self.portfolio.open_position(
                        signal.symbol, position_size, execution_price,
                        signal.timestamp, position_type='long', asset_type=asset_type,
                        **signal.metadata if signal.metadata else {}
                    )

        elif signal.signal_type == SignalType.OPEN_SHORT:
            position_size = self.risk_manager.calculate_position_size(
                portfolio_value, execution_price,
                confidence=signal.confidence
            )
            if position_size > 0:
                self.portfolio.open_position(
                    signal.symbol, position_size, execution_price,
                    signal.timestamp, position_type='short', asset_type='stock',
                    **signal.metadata if signal.metadata else {}
                )

        elif signal.signal_type in [SignalType.SELL, SignalType.CLOSE_LONG]:
            if self.portfolio.has_position(signal.symbol, position_type='long'):
                position = self.portfolio.get_position(signal.symbol, position_type='long')
                quantity = signal.quantity if signal.quantity > 0 else position.quantity
                self.portfolio.close_position(
                    signal.symbol, quantity, execution_price, signal.timestamp,
                    position_type='long', asset_type='stock'
                )

        elif signal.signal_type == SignalType.CLOSE_SHORT:
            if self.portfolio.has_position(signal.symbol, position_type='short'):
                position = self.portfolio.get_position(signal.symbol, position_type='short')
                quantity = signal.quantity if signal.quantity > 0 else position.quantity
                self.portfolio.close_position(
                    signal.symbol, quantity, execution_price, signal.timestamp,
                    position_type='short', asset_type='stock'
                )

        elif signal.signal_type in [SignalType.SELL_CALL, SignalType.SELL_PUT]:
            if self.portfolio.has_position(signal.symbol, asset_type='option'):
                position = self.portfolio.get_position(signal.symbol, asset_type='option')
                quantity = signal.quantity if signal.quantity > 0 else position.quantity
                self.portfolio.close_position(
                    signal.symbol, quantity, execution_price, signal.timestamp,
                    asset_type='option',
                    **signal.metadata if signal.metadata else {}
                )

    def _apply_costs(self, price: float, signal_type: SignalType) -> float:
        """Apply commission and slippage to price"""
        if signal_type in [SignalType.BUY, SignalType.BUY_CALL, SignalType.BUY_PUT, SignalType.OPEN_SHORT]:
            return price * (1 + self.commission + self.slippage)
        else:
            return price * (1 - self.commission - self.slippage)

    def _check_portfolio_risk(self, current_date: pd.Timestamp,
                              current_prices: Dict[str, float]):
        """Check portfolio VaR and reduce positions if risk exceeds limits"""
        equity_df = self.portfolio.get_equity_curve_df()
        if len(equity_df) < 30:
            return

        returns = equity_df['total_value'].pct_change().dropna()
        if len(returns) < 20:
            return

        portfolio_value = self.portfolio.get_total_value()
        var_95 = self.risk_manager.calculate_var(returns, 0.95)
        max_var = -self.risk_manager.max_portfolio_var * portfolio_value

        if var_95 < max_var:
            self._reduce_positions(current_date, current_prices)

    def _reduce_positions(self, current_date: pd.Timestamp,
                          current_prices: Dict[str, float]):
        """Reduce largest positions until portfolio risk is within limits"""
        sorted_positions = sorted(
            self.portfolio.positions.items(),
            key=lambda x: x[1].market_value,
            reverse=True
        )

        for pos_key, position in sorted_positions:
            if position.symbol not in current_prices:
                continue
            reduce_qty = int(position.quantity * 0.5)
            if reduce_qty > 0:
                self.portfolio.close_position(
                    position.symbol, reduce_qty,
                    current_prices[position.symbol], current_date,
                    position_type=position.position_type,
                    asset_type=position.asset_type
                )
            break

    def _rebalance_portfolio(self, current_date: pd.Timestamp,
                             current_prices: Dict[str, float]):
        """Rebalance portfolio using risk parity or min variance weights (uses data up to current_date only)"""
        symbols = list(self.market_data.keys())
        portfolio_value = self.portfolio.get_total_value()

        volatilities = {}
        for symbol in symbols:
            if symbol in self.market_data:
                df = self.market_data[symbol]
                hist = df[df.index <= current_date]
                returns = hist['close'].pct_change().dropna()
                if len(returns) >= 20:
                    volatilities[symbol] = returns.tail(20).std() * np.sqrt(252)

        if not volatilities:
            return

        if self.position_method == 'risk_parity':
            target_weights = self.risk_manager.calculate_risk_parity_weights(volatilities)
        elif self.position_method == 'min_variance':
            returns_df = pd.DataFrame()
            for symbol in symbols:
                if symbol in self.market_data:
                    df = self.market_data[symbol]
                    hist = df[df.index <= current_date]
                    returns_df[symbol] = hist['close'].pct_change().dropna()
            returns_df = returns_df.tail(60).dropna()
            if len(returns_df) >= 30:
                target_weights = self.risk_manager.calculate_min_variance_weights(
                    returns_df, max_weight=0.15,
                    shrinkage_alpha=self.risk_manager.max_position_size
                )
            else:
                target_weights = self.risk_manager.calculate_risk_parity_weights(volatilities)
        else:
            return

        current_weights = {}
        for symbol in symbols:
            pos = self.portfolio.get_position(symbol, position_type='long')
            if pos:
                current_weights[symbol] = pos.market_value / portfolio_value
            else:
                current_weights[symbol] = 0.0

        for symbol in symbols:
            if symbol not in current_prices or symbol not in target_weights:
                continue
            target = target_weights.get(symbol, 0.0)
            current = current_weights.get(symbol, 0.0)
            deviation = abs(target - current)

            if deviation > self.rebalance_threshold and current_prices[symbol] > 0:
                target_value = target * portfolio_value
                current_value = current * portfolio_value
                diff_value = target_value - current_value

                if diff_value > 0:
                    add_qty = int(diff_value / current_prices[symbol])
                    if add_qty > 0:
                        self.portfolio.open_position(
                            symbol, add_qty,
                            current_prices[symbol] * (1 + self.commission + self.slippage),
                            current_date, position_type='long', asset_type='stock'
                        )
                elif diff_value < 0:
                    pos = self.portfolio.get_position(symbol, position_type='long')
                    if pos:
                        reduce_qty = int(abs(diff_value) / current_prices[symbol])
                        reduce_qty = min(reduce_qty, int(pos.quantity))
                        if reduce_qty > 0:
                            self.portfolio.close_position(
                                symbol, reduce_qty,
                                current_prices[symbol] * (1 - self.commission - self.slippage),
                                current_date, position_type='long', asset_type='stock'
                            )

    def _perform_delta_hedge(self, current_date: pd.Timestamp,
                             current_prices: Dict[str, float]):
        """Perform delta hedging using largest position as underlying"""
        portfolio_delta = self.risk_manager.calculate_portfolio_delta(
            self.portfolio.positions, current_prices
        )

        if abs(portfolio_delta) > 10:
            if self.portfolio.positions:
                underlying_pos = max(
                    self.portfolio.positions.values(),
                    key=lambda p: p.market_value
                )
                underlying = underlying_pos.symbol
            else:
                underlying_symbols = list(self.market_data.keys())
                if not underlying_symbols:
                    return
                underlying = underlying_symbols[0]

            underlying_price = current_prices.get(underlying)

            if underlying_price:
                action, quantity = self.risk_manager.calculate_delta_hedge(
                    portfolio_delta, underlying_price
                )

                if action == 'buy' and quantity > 0:
                    self.portfolio.open_position(
                        underlying, quantity, underlying_price,
                        current_date, position_type='long'
                    )
                elif action == 'sell' and quantity > 0:
                    if self.portfolio.has_position(underlying, position_type='long'):
                        pos = self.portfolio.get_position(underlying, position_type='long')
                        sell_qty = min(quantity, int(pos.quantity))
                        self.portfolio.close_position(
                            underlying, sell_qty, underlying_price, current_date,
                            position_type='long'
                        )

    def _get_trading_dates(self, start_date: Optional[str], end_date: Optional[str]) -> List[pd.Timestamp]:
        """Get list of trading dates from data"""
        all_dates = set()
        for symbol, data in self.market_data.items():
            all_dates.update(data.index.tolist())

        all_dates = sorted(list(all_dates))

        if start_date:
            all_dates = [d for d in all_dates if d >= pd.Timestamp(start_date)]
        if end_date:
            all_dates = [d for d in all_dates if d <= pd.Timestamp(end_date)]

        return all_dates

    def _get_current_prices(self, current_date: pd.Timestamp) -> Dict[str, float]:
        """Get current prices for all symbols"""
        prices = {}
        for symbol, data in self.market_data.items():
            if current_date in data.index:
                prices[symbol] = data.loc[current_date, 'close']
        return prices

    def _get_historical_data(self, current_date: pd.Timestamp) -> Dict[str, pd.DataFrame]:
        """Get historical data up to current date"""
        historical = {}
        for symbol, data in self.market_data.items():
            historical[symbol] = data[data.index <= current_date]
        return historical

    def _calculate_results(self) -> Dict:
        """Calculate backtest results and metrics"""
        metrics = self.portfolio.get_performance_metrics()

        equity_df = self.portfolio.get_equity_curve_df()
        if not equity_df.empty:
            equity_df['returns'] = equity_df['total_value'].pct_change()

            returns = equity_df['returns'].dropna()
            metrics['avg_daily_return'] = returns.mean() if len(returns) > 0 else 0
            metrics['std_daily_return'] = returns.std() if len(returns) > 0 else 0
            metrics['best_day'] = returns.max() if len(returns) > 0 else 0
            metrics['worst_day'] = returns.min() if len(returns) > 0 else 0

            metrics['var_95'] = self.risk_manager.calculate_var(returns, 0.95)
            metrics['cvar_95'] = self.risk_manager.calculate_cvar(returns, 0.95)

            if len(equity_df) > 0:
                total_days = (equity_df['timestamp'].iloc[-1] - equity_df['timestamp'].iloc[0]).days
                metrics['total_days'] = total_days
                metrics['annualized_return'] = (1 + metrics['total_return']) ** (365 / total_days) - 1 if total_days > 0 else 0

        trade_df = self.portfolio.get_trade_history_df()
        if not trade_df.empty:
            metrics['total_trades'] = len(trade_df)
            metrics['avg_trade_value'] = trade_df['value'].mean()

        return metrics

    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve DataFrame"""
        return self.portfolio.get_equity_curve_df()

    def get_trade_history(self) -> pd.DataFrame:
        """Get trade history DataFrame"""
        return self.portfolio.get_trade_history_df()

    def plot_results(self):
        """Plot backtest results"""
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_style('darkgrid')

        equity_df = self.get_equity_curve()

        if equity_df.empty:
            print("No data to plot")
            return

        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        axes[0].plot(equity_df['timestamp'], equity_df['total_value'], label='Total Value', linewidth=2)
        axes[0].axhline(y=self.initial_capital, color='r', linestyle='--', label='Initial Capital')
        axes[0].set_title('Portfolio Value Over Time', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Value (¥)', fontsize=12)
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        equity_df['returns'] = equity_df['total_value'].pct_change()
        equity_df['cumulative_returns'] = (1 + equity_df['returns']).cumprod() - 1

        axes[1].plot(equity_df['timestamp'], equity_df['cumulative_returns'] * 100,
                    color='green', linewidth=2)
        axes[1].set_title('Cumulative Returns', fontsize=14, fontweight='bold')
        axes[1].set_ylabel('Returns (%)', fontsize=12)
        axes[1].grid(True, alpha=0.3)

        running_max = equity_df['total_value'].cummax()
        drawdown = (equity_df['total_value'] - running_max) / running_max * 100

        axes[2].fill_between(equity_df['timestamp'], drawdown, 0,
                            color='red', alpha=0.3, label='Drawdown')
        axes[2].set_title('Drawdown', fontsize=14, fontweight='bold')
        axes[2].set_xlabel('Date', fontsize=12)
        axes[2].set_ylabel('Drawdown (%)', fontsize=12)
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def print_summary(self):
        """Print backtest summary"""
        if self.results is None:
            print("No results available. Run backtest first.")
            return

        print("\n" + "="*60)
        print("BACKTEST RESULTS SUMMARY")
        print("="*60)
        print(f"Initial Capital:        ¥{self.initial_capital:,.2f}")
        print(f"Final Value:            ¥{self.results['total_value']:,.2f}")
        print(f"Total Return:           {self.results['total_return_pct']:.2f}%")
        print(f"Annualized Return:      {self.results.get('annualized_return', 0)*100:.2f}%")
        print(f"Sharpe Ratio:           {self.results['sharpe_ratio']:.2f}")
        print(f"Max Drawdown:           {self.results['max_drawdown_pct']:.2f}%")
        print(f"VaR(95%):               {self.results.get('var_95', 0):.4f}")
        print(f"CVaR(95%):              {self.results.get('cvar_95', 0):.4f}")
        print(f"\nTotal Trades:           {self.results['num_trades']}")
        print(f"Win Rate:               {self.results['win_rate']*100:.2f}%")
        print(f"Active Positions:       {self.results['num_positions']}")
        print(f"Closed Positions:       {self.results['num_closed_positions']}")
        print(f"\nCash:                   ¥{self.results['cash']:,.2f}")
        print(f"Positions Value:        ¥{self.results['positions_value']:,.2f}")
        print("="*60 + "\n")
