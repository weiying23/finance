"""Run all strategies and compare results with plots"""
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import time
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
    'momentum':       ('MomentumStrategy',       lambda: MomentumStrategy(**MOMENTUM_STRATEGY)),
    'mean_reversion': ('MeanReversionStrategy',   lambda: MeanReversionStrategy(**MEAN_REVERSION_STRATEGY)),
    'multi_asset':    ('MultiAssetStrategy',      lambda: MultiAssetStrategy(**MULTI_ASSET_STRATEGY)),
    'multi_factor':   ('MultiFactorAlpha',        lambda: MultiFactorAlpha(**MULTI_FACTOR_ALPHA)),
    'stat_arb':       ('StatisticalArbitrage',    lambda: StatisticalArbitrage(**STATISTICAL_ARBITRAGE)),
    'regime':         ('MarketRegimeStrategy',    lambda: MarketRegimeStrategy(**MARKET_REGIME_STRATEGY)),
    'pairs_trading':  ('PairsTradingStrategy',    lambda: PairsTradingStrategy(**PAIRS_TRADING_STRATEGY)),
}

def make_engine():
    return BacktestEngine(
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        commission=BACKTEST_CONFIG['commission'],
        slippage=BACKTEST_CONFIG['slippage'],
        enable_delta_hedging=BACKTEST_CONFIG.get('enable_delta_hedging', False),
        use_sample_data=True,
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

def run_all():
    results = {}
    equity_curves = {}

    for name, (cls_name, factory) in STRATEGIES.items():
        print(f"\n{'='*60}")
        print(f"Running: {name} ({cls_name})")
        print(f"{'='*60}")
        engine = make_engine()
        engine.add_strategy(factory())
        engine.load_data(STOCK_UNIVERSE, BACKTEST_PERIOD['start_date'], BACKTEST_PERIOD['end_date'])
        res = engine.run()
        metrics = engine.portfolio.get_performance_metrics()
        results[name] = metrics
        equity_df = engine.get_equity_curve()
        if not equity_df.empty:
            equity_curves[name] = equity_df

        total_value = engine.portfolio.get_total_value()
        ret = (total_value - BACKTEST_CONFIG['initial_capital']) / BACKTEST_CONFIG['initial_capital'] * 100
        sharpe = metrics.get('sharpe_ratio', 0)
        maxdd = metrics.get('max_drawdown_pct', 0)
        results[name]['total_return_pct'] = ret
        print(f"  Return: {ret:+.2f}%  Sharpe: {sharpe:.2f}  MaxDD: {maxdd:.2f}%")

    # Summary table
    print(f"\n{'='*70}")
    print("ALL STRATEGIES SUMMARY (bear market 2022-2023)")
    print(f"{'='*70}")
    print(f"{'Strategy':<18} {'Return':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8} {'WinRate':>8}")
    print("-"*70)
    profitable = []
    for name in STRATEGIES:
        m = results[name]
        ret = m.get('total_return_pct', 0)
        sharpe = m.get('sharpe_ratio', 0)
        maxdd = m.get('max_drawdown_pct', 0)
        trades = m.get('num_trades', 0)
        wr = m.get('win_rate', 0) * 100
        marker = "***" if ret > 0 else ""
        print(f"{name:<18} {ret:>7.2f}% {sharpe:>7.2f} {maxdd:>7.2f}% {trades:>7d} {wr:>7.1f}% {marker}")
        if ret > 0:
            profitable.append(name)
    print("-"*70)
    print(f"Buy-and-hold:      -73.46%  -7.23  -73.33%")
    print(f"\nProfitable strategies: {len(profitable)} / {len(STRATEGIES)}")
    if profitable:
        print(f"  Winners: {', '.join(profitable)}")
    else:
        print("  None - all strategies lost money in this bear market")

    # Plot all equity curves on one figure
    if equity_curves:
        fig, axes = plt.subplots(2, 1, figsize=(16, 10))

        colors = plt.cm.tab10(np.linspace(0, 1, len(equity_curves)))
        for i, (name, eq) in enumerate(equity_curves.items()):
            m = results[name]
            ret_label = f"{m.get('total_return_pct', 0):+.1f}%"
            axes[0].plot(eq['timestamp'], eq['total_value'],
                        label=f"{name} ({ret_label})", linewidth=1.5,
                        color=colors[i])

        axes[0].axhline(y=BACKTEST_CONFIG['initial_capital'], color='r', linestyle='--', label='Initial Capital', alpha=0.7)
        axes[0].set_title('All Strategies - Portfolio Value Over Time', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Value (¥)', fontsize=12)
        axes[0].legend(fontsize=9, loc='upper right')
        axes[0].grid(True, alpha=0.3)

        for i, (name, eq) in enumerate(equity_curves.items()):
            m = results[name]
            ret_pct = m.get('total_return_pct', 0)
            returns = eq['total_value'].pct_change().dropna()
            cum = (1 + returns).cumprod() - 1
            ts = eq['timestamp'].iloc[1:]
            axes[1].plot(ts, cum * 100,
                        label=f"{name} ({ret_pct:+.1f}%)", linewidth=1.5,
                        color=colors[i])

        axes[1].axhline(y=0, color='black', linestyle='-', alpha=0.5)
        axes[1].set_title('Cumulative Returns (%)', fontsize=14, fontweight='bold')
        axes[1].set_ylabel('Returns (%)', fontsize=12)
        axes[1].legend(fontsize=9, loc='upper right')
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.draw()
        plt.pause(3)
        plt.close()

    # Plot each strategy individually with 3s pause
    for name in STRATEGIES:
        if name not in equity_curves:
            continue
        eq = equity_curves[name]
        m = results[name]
        ret = m.get('total_return_pct', 0)
        sharpe = m.get('sharpe_ratio', 0)
        maxdd = m.get('max_drawdown_pct', 0)

        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        axes[0].plot(eq['timestamp'], eq['total_value'], linewidth=2, color='#2E86AB')
        axes[0].axhline(y=BACKTEST_CONFIG['initial_capital'], color='r', linestyle='--', alpha=0.7)
        axes[0].set_title(f'{name} — Portfolio Value (Return: {ret:+.2f}%)', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Value (¥)', fontsize=12)
        axes[0].grid(True, alpha=0.3)

        returns = eq['total_value'].pct_change().dropna()
        cum = (1 + returns).cumprod() - 1
        ts = eq['timestamp'].iloc[1:]
        axes[1].plot(ts, cum * 100, linewidth=2, color='green')
        axes[1].axhline(y=0, color='black', linestyle='-', alpha=0.5)
        axes[1].set_title(f'Cumulative Returns (Sharpe: {sharpe:.2f})', fontsize=14, fontweight='bold')
        axes[1].set_ylabel('Returns (%)', fontsize=12)
        axes[1].grid(True, alpha=0.3)

        running_max = eq['total_value'].cummax()
        drawdown = (eq['total_value'] - running_max) / running_max * 100
        axes[2].fill_between(eq['timestamp'], drawdown, 0, color='red', alpha=0.3)
        axes[2].set_title(f'Drawdown (Max: {maxdd:.2f}%)', fontsize=14, fontweight='bold')
        axes[2].set_xlabel('Date', fontsize=12)
        axes[2].set_ylabel('Drawdown (%)', fontsize=12)
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.draw()
        plt.pause(3)
        plt.close()

    # Final summary plot
    fig, ax = plt.subplots(figsize=(12, 6))
    names = list(STRATEGIES.keys())
    returns = [results[n].get('total_return_pct', 0) for n in names]
    colors_bar = ['#2ECC71' if r > 0 else '#E74C3C' for r in returns]
    bars = ax.bar(names, returns, color=colors_bar, edgecolor='black', linewidth=0.5)
    ax.axhline(y=0, color='black', linewidth=1)
    ax.axhline(y=-73.46, color='red', linewidth=2, linestyle='--', label='Buy-and-hold: -73.46%')
    for bar, val in zip(bars, returns):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1 if val > 0 else bar.get_height() - 3,
                f'{val:+.1f}%', ha='center', va='bottom' if val > 0 else 'top', fontsize=10, fontweight='bold')
    ax.set_title('Strategy Returns Comparison (Bear Market 2022-2023)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Total Return (%)', fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.draw()
    plt.pause(3)
    plt.close()

    print("\nDone!")

if __name__ == '__main__':
    run_all()
