"""Run all strategies with real bull market data (2019-01 to 2021-06)
Data was pre-fetched via akshare and saved to CSV.
"""
import pandas as pd
import numpy as np
import os
from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.alpha_mining import MultiFactorAlpha, StatisticalArbitrage, MarketRegimeStrategy
from qcode.strategies.pairs_trading import PairsTradingStrategy
from config import (
    BACKTEST_CONFIG, RISK_CONFIG, STOCK_UNIVERSE,
    MOMENTUM_STRATEGY, MEAN_REVERSION_STRATEGY, MULTI_ASSET_STRATEGY,
    MULTI_FACTOR_ALPHA, STATISTICAL_ARBITRAGE, MARKET_REGIME_STRATEGY,
    PORTFOLIO_OPTIMIZATION, EXECUTION_CONFIG, PAIRS_TRADING_STRATEGY,
    SHORT_CONFIG
)

BULL_PERIOD = {'start_date': '2019-01-01', 'end_date': '2021-06-01'}
DATA_DIR = '/var/folders/1_/j_cx52hs2mb2rxxgzy1182zc0000gn/T/opencode'

STRATEGIES = {
    'momentum':       lambda: MomentumStrategy(**MOMENTUM_STRATEGY),
    'mean_reversion': lambda: MeanReversionStrategy(**MEAN_REVERSION_STRATEGY),
    'multi_asset':    lambda: MultiAssetStrategy(**MULTI_ASSET_STRATEGY),
    'multi_factor':   lambda: MultiFactorAlpha(**MULTI_FACTOR_ALPHA),
    'stat_arb':       lambda: StatisticalArbitrage(**STATISTICAL_ARBITRAGE),
    'regime':         lambda: MarketRegimeStrategy(**MARKET_REGIME_STRATEGY),
    'pairs_trading':  lambda: PairsTradingStrategy(**PAIRS_TRADING_STRATEGY),
}

def load_real_data(symbols, start_date, end_date):
    market_data = {}
    for symbol in symbols:
        filepath = os.path.join(DATA_DIR, f'real_{symbol}.csv')
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            df['date'] = pd.to_datetime(df['日期'])
            df = df.rename(columns={
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })
            df['symbol'] = symbol
            df = df.set_index('date')
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            if len(df) > 0:
                market_data[symbol] = df
                print(f'  {symbol}: {len(df)} rows, close {df["close"].iloc[0]:.2f} -> {df["close"].iloc[-1]:.2f} ({(df["close"].iloc[-1]/df["close"].iloc[0]-1)*100:+.2f}%)')
        else:
            print(f'  {symbol}: no data file found')
    return market_data


def make_engine():
    return BacktestEngine(
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        commission=BACKTEST_CONFIG['commission'],
        slippage=BACKTEST_CONFIG['slippage'],
        enable_delta_hedging=BACKTEST_CONFIG.get('enable_delta_hedging', False),
        use_sample_data=False,
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


def run_all_real_bull():
    print("Loading real bull market data (2019-01 to 2021-06)...")
    market_data = load_real_data(STOCK_UNIVERSE, BULL_PERIOD['start_date'], BULL_PERIOD['end_date'])
    if not market_data:
        print("No data available. Need to fetch first.")
        return

    results = {}
    for name, factory in STRATEGIES.items():
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print(f"{'='*60}")

        engine = make_engine()
        engine.add_strategy(factory())
        engine.market_data = market_data
        engine._last_rebalance_month = None
        engine.pending_orders = []
        engine.results = None

        all_dates = engine._get_trading_dates(BULL_PERIOD['start_date'], BULL_PERIOD['end_date'])
        print(f"Trading days: {len(all_dates)}")

        for current_date in all_dates:
            engine._process_date(current_date)

        engine.results = engine._calculate_results()
        metrics = engine.portfolio.get_performance_metrics()
        total_value = engine.portfolio.get_total_value()
        ret = (total_value - BACKTEST_CONFIG['initial_capital']) / BACKTEST_CONFIG['initial_capital'] * 100

        results[name] = {
            'return_pct': ret,
            'sharpe': metrics.get('sharpe_ratio', 0),
            'max_dd': metrics.get('max_drawdown_pct', 0),
            'total_trades': metrics.get('total_trades', 0),
        }
        print(f"  return={ret:+.2f}%  sharpe={metrics.get('sharpe_ratio', 0):.2f}  max_dd={metrics.get('max_drawdown_pct', 0):.2f}%  trades={metrics.get('total_trades', 0)}")

    print(f"\n{'='*70}")
    print("BULL MARKET RESULTS (Real Data 2019-01 to 2021-06)")
    print(f"{'='*70}")
    print(f"{'Strategy':20s} | {'Return':>10s} | {'Sharpe':>8s} | {'MaxDD':>8s} | {'Trades':>8s}")
    print("-" * 60)
    for name in STRATEGIES:
        r = results[name]
        print(f"{name:20s} | {r['return_pct']:>+9.2f}% | {r['sharpe']:>8.2f} | {r['max_dd']:>7.2f}% | {r['total_trades']:>8}")

    bh_ret = sum((market_data[s]['close'].iloc[-1] / market_data[s]['close'].iloc[0] - 1) for s in market_data) / len(market_data) * 100
    print(f"\nBuy-and-hold (equal-weight): {bh_ret:+.2f}%")

    return results


if __name__ == "__main__":
    run_all_real_bull()
