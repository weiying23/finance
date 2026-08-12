"""Run all strategies across multiple market regimes and compare results"""
import pandas as pd
import numpy as np
from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.alpha_mining import MultiFactorAlpha, StatisticalArbitrage, MarketRegimeStrategy
from qcode.strategies.pairs_trading import PairsTradingStrategy
from config import (
    BACKTEST_CONFIG, RISK_CONFIG, STOCK_UNIVERSE, BACKTEST_PERIOD,
    MOMENTUM_STRATEGY, MEAN_REVERSION_STRATEGY, MULTI_ASSET_STRATEGY,
    MULTI_FACTOR_ALPHA, STATISTICAL_ARBITRAGE, MARKET_REGIME_STRATEGY,
    PORTFOLIO_OPTIMIZATION, EXECUTION_CONFIG, PAIRS_TRADING_STRATEGY,
    SHORT_CONFIG
)

STRATEGIES = {
    'momentum':       lambda: MomentumStrategy(**MOMENTUM_STRATEGY),
    'mean_reversion': lambda: MeanReversionStrategy(**MEAN_REVERSION_STRATEGY),
    'multi_asset':    lambda: MultiAssetStrategy(**MULTI_ASSET_STRATEGY),
    'multi_factor':   lambda: MultiFactorAlpha(**MULTI_FACTOR_ALPHA),
    'stat_arb':       lambda: StatisticalArbitrage(**STATISTICAL_ARBITRAGE),
    'regime':         lambda: MarketRegimeStrategy(**MARKET_REGIME_STRATEGY),
    'pairs_trading':  lambda: PairsTradingStrategy(**PAIRS_TRADING_STRATEGY),
}

REGIMES = ['bear', 'bull', 'sideways', 'mixed']

def make_engine(regime):
    return BacktestEngine(
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        commission=BACKTEST_CONFIG['commission'],
        slippage=BACKTEST_CONFIG['slippage'],
        enable_delta_hedging=BACKTEST_CONFIG.get('enable_delta_hedging', False),
        use_sample_data=True,
        market_regime=regime,
        max_position_size=RISK_CONFIG['max_position_size'],
        stop_loss_pct=RISK_CONFIG['stop_loss_pct'],
        target_portfolio_vol=RISK_CONFIG['target_portfolio_vol'],
        position_method=PORTFOLIO_OPTIMIZATION['method'],
        max_weight=PORTFOLIO_OPTIMIZATION['max_weight'],
        rebalance_threshold=PORTFOLIO_OPTIMIZATION['rebalance_threshold'],
        shrinkage_alpha=PORTFOLIO_OPTIMIZATION['shrinkage_alpha'],
        max_single_trade_pct=EXECUTION_CONFIG['max_single_trade_pct'],
        max_splits=EXECUTION_CONFIG['max_splits'],
        rebalance_freq=PORTFOLIO_OPTIMIZATION.get('rebalance_freq', 'monthly'),
        margin_ratio=SHORT_CONFIG['margin_ratio'],
        borrowing_cost_annual=SHORT_CONFIG['borrowing_cost_annual']
    )

def run_all_regimes():
    all_results = {}

    for regime in REGIMES:
        print(f"\n{'#'*70}")
        print(f"# Market Regime: {regime.upper()}")
        print(f"{'#'*70}")

        regime_results = {}
        for name, factory in STRATEGIES.items():
            engine = make_engine(regime)
            engine.add_strategy(factory())
            engine.load_data(STOCK_UNIVERSE, BACKTEST_PERIOD['start_date'], BACKTEST_PERIOD['end_date'])
            res = engine.run()
            metrics = engine.portfolio.get_performance_metrics()
            total_value = engine.portfolio.get_total_value()
            ret = (total_value - BACKTEST_CONFIG['initial_capital']) / BACKTEST_CONFIG['initial_capital'] * 100
            regime_results[name] = {
                'return_pct': ret,
                'sharpe': metrics.get('sharpe_ratio', 0),
                'max_dd': metrics.get('max_drawdown_pct', 0),
                'total_trades': metrics.get('total_trades', 0),
            }
            print(f"  {name:20s}: return={ret:+.2f}%  sharpe={metrics.get('sharpe_ratio', 0):.2f}  max_dd={metrics.get('max_drawdown_pct', 0):.2f}%")

        all_results[regime] = regime_results

    print(f"\n{'='*70}")
    print("SUMMARY: Returns Across Market Regimes")
    print(f"{'='*70}")

    header = f"{'Strategy':20s}"
    for regime in REGIMES:
        header += f" | {regime:>10s}"
    print(header)
    print("-" * len(header))

    for name in STRATEGIES:
        row = f"{name:20s}"
        for regime in REGIMES:
            ret = all_results[regime][name]['return_pct']
            row += f" | {ret:>+9.2f}%"
        print(row)

    print(f"\n{'='*70}")
    print("SUMMARY: Sharpe Ratios Across Market Regimes")
    print(f"{'='*70}")

    header = f"{'Strategy':20s}"
    for regime in REGIMES:
        header += f" | {regime:>10s}"
    print(header)
    print("-" * len(header))

    for name in STRATEGIES:
        row = f"{name:20s}"
        for regime in REGIMES:
            sharpe = all_results[regime][name]['sharpe']
            row += f" | {sharpe:>10.2f}"
        print(row)

    print(f"\n{'='*70}")
    print("SUMMARY: Max Drawdown Across Market Regimes")
    print(f"{'='*70}")

    header = f"{'Strategy':20s}"
    for regime in REGIMES:
        header += f" | {regime:>10s}"
    print(header)
    print("-" * len(header))

    for name in STRATEGIES:
        row = f"{name:20s}"
        for regime in REGIMES:
            dd = all_results[regime][name]['max_dd']
            row += f" | {dd:>9.2f}%"
        print(row)

    return all_results

if __name__ == "__main__":
    results = run_all_regimes()
