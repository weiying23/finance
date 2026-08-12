# QCode - Quantitative Trading System Framework

A comprehensive quantitative trading framework built with Python, featuring multi-asset support, delta hedging, and advanced risk management.

## Features

- **Data Integration**: Seamless integration with akshare for fetching Chinese market data (stocks, options, futures)
- **Strategy Framework**: Extensible base classes for creating custom trading strategies
- **Multi-Asset Support**: Trade stocks, options, and derivatives simultaneously
- **Delta Hedging**: Automatic portfolio delta neutralization for risk management
- **Portfolio Management**: Track positions, P&L, and performance metrics
- **Risk Management**: Position sizing, VaR calculation, Greeks computation
- **Backtesting Engine**: High-performance backtesting with realistic transaction costs
- **Performance Analytics**: Comprehensive metrics including Sharpe ratio, max drawdown, win rate

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd qcode
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start
 ### Usage Examples

  Quick Start:

  # Run a simple momentum backtest
  python main.py --strategy momentum

  # Multi-asset with delta hedging
  python main.py --strategy multi_asset --capital 2000000

  # Run all strategies
  python main.py --strategy all

  Python API:

  from qcode import BacktestEngine
  from qcode.strategies.momentum import MomentumStrategy

  engine = BacktestEngine(initial_capital=1000000, enable_delta_hedging=True)
  engine.add_strategy(MomentumStrategy(fast_period=10, slow_period=30))
  engine.load_data(['600519', '000858'], '2022-01-01', '2023-12-31')
  results = engine.run()
  engine.print_summary()

  ### Files Created

  qcode/
  ├── README.md                    # Comprehensive documentation
  ├── QUICKSTART.md                # 5-minute getting started guide
  ├── requirements.txt             # Dependencies
  ├── setup.py                     # Package installation
  ├── config.py                    # Configuration file
  ├── main.py                      # CLI entry point
  ├── qcode/
  │   ├── data/fetcher.py         # akshare integration
  │   ├── strategies/             # Strategy implementations
  │   │   ├── base.py             # Base classes
  │   │   ├── momentum.py         # Momentum strategy
  │   │   ├── mean_reversion.py  # Mean reversion
  │   │   └── multi_asset.py     # Multi-asset with hedging
  │   ├── portfolio/manager.py    # Portfolio management
  │   ├── risk/manager.py         # Risk & delta hedging
  │   ├── backtest/engine.py      # Backtesting engine
  │   └── utils/metrics.py        # Performance metrics
  └── examples/
      ├── simple_backtest.py      # Basic example
      ├── multi_asset_backtest.py # Advanced example
      ├── strategy_optimization.py # Parameter tuning
      └── results_dashboard.py    # Visualization dashboard

### Simple Momentum Strategy Backtest

```python
from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy

# Initialize backtest engine
engine = BacktestEngine(
    initial_capital=1000000,
    commission=0.0003,
    slippage=0.0001
)

# Add momentum strategy
strategy = MomentumStrategy(
    fast_period=10,
    slow_period=30,
    rsi_period=14
)
engine.add_strategy(strategy)

# Load data
symbols = ['600519', '000858', '600036']
engine.load_data(symbols, '2022-01-01', '2023-12-31')

# Run backtest
results = engine.run()
engine.print_summary()
engine.plot_results()
```

### Multi-Asset Strategy with Delta Hedging

```python
from qcode import BacktestEngine
from qcode.strategies.multi_asset import MultiAssetStrategy

# Enable delta hedging
engine = BacktestEngine(
    initial_capital=2000000,
    enable_delta_hedging=True
)

# Add multi-asset strategy
strategy = MultiAssetStrategy(
    trend_period=20,
    hedge_threshold=0.15
)
engine.add_strategy(strategy)

# Run backtest...
```

## Architecture

### Core Modules

```
qcode/
├── data/           # Data fetching and management
│   └── fetcher.py   # akshare integration
├── strategies/    # Trading strategies
│   ├── base.py            # Base strategy class
│   ├── momentum.py        # Momentum strategy
│   ├── mean_reversion.py  # Mean reversion strategy
│   └── multi_asset.py     # Multi-asset strategy
├── portfolio/     # Portfolio management
│   └── manager.py   # Position tracking and P&L
├── risk/          # Risk management
│   └── manager.py   # Greeks, VaR, delta hedging
├── backtest/      # Backtesting engine
│   └── engine.py    # Main backtest logic
└── utils/         # Utilities
    └── metrics.py   # Performance metrics
```

## Creating Custom Strategies

Extend the `BaseStrategy` class to create your own strategies:

```python
from qcode.strategies.base import BaseStrategy, Signal, SignalType
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self, param1=10, param2=20):
        params = {'param1': param1, 'param2': param2}
        super().__init__("MyStrategy", params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        # Add your indicators
        df = data.copy()
        df['sma'] = self.calculate_sma(df['close'], self.params['param1'])
        return df
    
    def generate_signals(self, data: dict) -> list:
        signals = []
        for symbol, df in data.items():
            df = self.calculate_indicators(df)
            current = df.iloc[-1]
            
            # Your signal logic
            if current['close'] > current['sma']:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close']
                ))
        return signals
```

## Built-in Strategies

### 1. Momentum Strategy
Uses moving average crossovers and RSI to identify trending opportunities.

**Parameters:**
- `fast_period`: Fast MA period (default: 10)
- `slow_period`: Slow MA period (default: 30)
- `rsi_period`: RSI period (default: 14)
- `rsi_oversold`: RSI oversold level (default: 30)
- `rsi_overbought`: RSI overbought level (default: 70)

### 2. Mean Reversion Strategy
Trades based on Bollinger Bands mean reversion.

**Parameters:**
- `bb_period`: Bollinger Bands period (default: 20)
- `bb_std`: Standard deviation multiplier (default: 2.0)
- `lookback`: Lookback period (default: 5)

### 3. Multi-Asset Strategy
Combines stocks with options for hedging based on volatility.

**Parameters:**
- `trend_period`: Trend identification period (default: 20)
- `volatility_period`: Volatility calculation period (default: 20)
- `hedge_threshold`: Volatility threshold for hedging (default: 0.15)

## Risk Management

### Position Sizing
Automatically calculates optimal position sizes based on:
- Maximum position size (% of portfolio)
- Risk per trade (stop-loss based)
- Kelly Criterion optimization

### Delta Hedging
Automatically neutralizes portfolio delta by:
1. Calculating portfolio-level delta from all positions
2. Identifying required hedge quantity
3. Executing hedge trades in underlying assets

### Greeks Calculation
Supports full Black-Scholes Greeks for options:
- Delta: Price sensitivity
- Gamma: Delta sensitivity
- Theta: Time decay
- Vega: Volatility sensitivity
- Rho: Interest rate sensitivity

## Performance Metrics

The framework calculates comprehensive performance metrics:

- **Returns**: Total, annualized, daily average
- **Risk**: Volatility, max drawdown, VaR, CVaR
- **Risk-adjusted**: Sharpe ratio, Sortino ratio, Calmar ratio
- **Trading**: Win rate, profit factor, number of trades
- **Portfolio**: Cash, positions value, total value

## Examples

### Running Examples

```bash
# Simple momentum backtest
python examples/simple_backtest.py

# Multi-asset strategy with delta hedging
python examples/multi_asset_backtest.py
```

### Data Sources

The framework uses akshare to fetch:
- **Stocks**: A-share daily OHLCV data with adjustments
- **Indices**: Major Chinese indices (SSE, SZSE, etc.)
- **Options**: Option chain data for supported underlyings
- **Futures**: Commodity and financial futures

## Configuration

### Backtest Engine Parameters

```python
engine = BacktestEngine(
    initial_capital=1000000,      # Starting capital
    commission=0.0003,            # Commission rate (0.03%)
    slippage=0.0001,              # Slippage rate (0.01%)
    enable_delta_hedging=True     # Enable delta hedging
)
```

### Risk Manager Parameters

```python
from qcode.risk.manager import RiskManager

risk_mgr = RiskManager(
    max_position_size=0.1,        # Max 10% per position
    max_portfolio_var=0.02,       # Max 2% VaR
    risk_free_rate=0.03           # 3% risk-free rate
)
```

## Advanced Usage

### Combining Multiple Strategies

```python
engine = BacktestEngine(initial_capital=2000000)

# Add multiple strategies
engine.add_strategy(MomentumStrategy())
engine.add_strategy(MeanReversionStrategy())
engine.add_strategy(MultiAssetStrategy())

# They will all generate signals
results = engine.run()
```

### Custom Risk Management

```python
from qcode.risk.manager import RiskManager

risk_mgr = RiskManager(max_position_size=0.05)

# Calculate position size
size = risk_mgr.calculate_position_size(
    portfolio_value=1000000,
    entry_price=50.0,
    stop_loss_pct=0.02
)

# Calculate Greeks
greeks = risk_mgr.calculate_option_greeks(
    spot=50.0,
    strike=55.0,
    time_to_maturity=0.25,
    volatility=0.3,
    option_type='call'
)
```

## Visualization

The framework provides built-in visualization:

```python
# Plot backtest results
engine.plot_results()

# Or use custom plotting
from qcode.utils.metrics import plot_equity_curve

equity_df = engine.get_equity_curve()
plot_equity_curve(equity_df, initial_capital=1000000, save_path='results.png')
```

## Export Results

```python
# Get results as DataFrames
equity_df = engine.get_equity_curve()
trade_df = engine.get_trade_history()

# Export to CSV
equity_df.to_csv('equity_curve.csv', index=False)
trade_df.to_csv('trades.csv', index=False)
```

## Multi-Regime Backtest Results (Trailing Stop 5%)

Test conditions: sample data, 2022-01 to 2023-12, 10 stocks, initial capital 1M, trailing stop-loss 5% from highest price.

### Returns (%)

| Strategy | bear | bull | sideways | mixed |
|----------|------|------|----------|-------|
| momentum | -12.25 | +12.82 | -4.65 | -2.50 |
| mean_reversion | -5.48 | +2.02 | +5.05 | -2.74 |
| **multi_asset** | **+0.66** | +5.30 | +0.10 | +5.99 |
| multi_factor | -11.49 | +4.89 | +3.91 | +19.75 |
| stat_arb | -32.66 | +19.74 | +4.07 | +21.37 |
| regime | -12.79 | +5.49 | +1.57 | +9.08 |
| pairs_trading | -28.97 | +24.18 | -3.42 | +5.18 |

### Sharpe Ratios

Sharpe = (R_p - R_f) / σ_p, annualized as √252 × mean(returns) / std(returns)

| Strategy | bear | bull | sideways | mixed |
|----------|------|------|----------|-------|
| momentum | -1.54 | 1.60 | -0.48 | -0.34 |
| mean_reversion | -1.23 | 0.63 | 0.94 | -0.71 |
| **multi_asset** | **0.44** | 2.08 | 0.05 | 2.51 |
| multi_factor | -1.63 | 0.75 | 0.46 | 2.62 |
| stat_arb | -4.21 | 1.85 | 0.40 | 2.04 |
| regime | -2.14 | 0.87 | 0.24 | 1.45 |
| pairs_trading | -3.67 | 2.02 | -0.26 | 0.55 |

### Max Drawdown (%)

| Strategy | bear | bull | sideways | mixed |
|----------|------|------|----------|-------|
| momentum | -14.58 | -3.02 | -8.36 | -7.41 |
| mean_reversion | -6.71 | -1.61 | -2.74 | -4.04 |
| **multi_asset** | **-0.76** | -1.07 | -1.55 | -0.80 |
| multi_factor | -13.25 | -3.55 | -4.75 | -2.58 |
| stat_arb | -33.38 | -4.96 | -7.10 | -3.81 |
| regime | -13.99 | -3.58 | -2.91 | -2.33 |
| pairs_trading | -29.73 | -4.28 | -9.64 | -6.03 |

### Key Findings

- **multi_asset**: Only strategy profitable across ALL regimes, max drawdown never exceeds 1.55%
- **mean_reversion**: Best sideways performer (Sharpe 0.94), validates range-bound design
- **stat_arb/pairs_trading**: Extreme polarization — large gains in bull, large losses in bear
- **momentum**: Strong bull (Sharpe 1.60) but negative in all other regimes
- **multi_factor**: Best mixed regime performer (Sharpe 2.62, return +19.75%)

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

MIT License

## Disclaimer

This framework is for educational and research purposes only. Past performance does not guarantee future results. Always conduct thorough testing before deploying any trading strategy with real capital.
