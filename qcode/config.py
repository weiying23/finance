"""Configuration file for QCode trading system"""

# Backtest Configuration
BACKTEST_CONFIG = {
    'initial_capital': 1000000,
    'commission': 0.0003,
    'slippage': 0.0001,
    'enable_delta_hedging': False  # Disabled by default - only for options strategies
}

# Risk Management Configuration
RISK_CONFIG = {
    'max_position_size': 0.1,
    'max_portfolio_var': 0.02,
    'risk_free_rate': 0.03,
    'stop_loss_pct': 0.05,
    'target_portfolio_vol': 0.15
}

# Portfolio Optimization
PORTFOLIO_OPTIMIZATION = {
    'method': 'risk_parity',
    'max_weight': 0.15,
    'rebalance_threshold': 0.10,
    'shrinkage_alpha': 0.5,
    'rebalance_freq': 'monthly'
}

# Execution Configuration
EXECUTION_CONFIG = {
    'max_single_trade_pct': 0.03,
    'max_splits': 5
}

# Short Position Configuration
SHORT_CONFIG = {
    'margin_ratio': 0.20,
    'borrowing_cost_annual': 0.02
}

# Pairs Trading Strategy
PAIRS_TRADING_STRATEGY = {
    'lookback': 60,
    'entry_zscore': 2.0,
    'exit_zscore': 0.5,
    'pairs': [('600519', '000858'), ('600036', '601318'), ('000333', '600887')]
}

# Walk-Forward Configuration
WALK_FORWARD_CONFIG = {
    'train_months': 6,
    'test_months': 1
}

# Data Configuration
DATA_CONFIG = {
    'cache_data': True,
    'data_source': 'akshare'
}

# Strategy Configuration
MOMENTUM_STRATEGY = {
    'fast_period': 10,
    'slow_period': 30,
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70
}

MEAN_REVERSION_STRATEGY = {
    'bb_period': 20,
    'bb_std': 2.0,
    'lookback': 5
}

MULTI_ASSET_STRATEGY = {
    'trend_period': 20,
    'volatility_period': 20,
    'hedge_threshold': 0.15
}

# Alpha Mining Strategies
MULTI_FACTOR_ALPHA = {
    'momentum_weight': 0.4,
    'value_weight': 0.3,
    'volatility_weight': 0.2,
    'volume_weight': 0.1
}

STATISTICAL_ARBITRAGE = {
    'lookback': 60,
    'entry_zscore': 2.0,
    'exit_zscore': 0.5,
    'stop_loss_zscore': 3.0  # Exit if z-score worsens beyond this
}

MARKET_REGIME_STRATEGY = {
    'regime_lookback': 60
}

# Trading Universe
STOCK_UNIVERSE = [
    '600519',
    '000858',
    '600036',
    '601318',
    '000333',
    '601012',
    '600887',
    '000568',
    '600900',
    '000651'
]

# Backtest Period
BACKTEST_PERIOD = {
    'start_date': '2022-01-01',
    'end_date': '2023-12-31'
}
