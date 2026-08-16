"""全策略回归基线快照测试(Phase A)。

跑 7 个策略 × sample 数据, 与 tests/baselines/regression_baseline.json 基线对比:
  final_value / max_drawdown_pct / num_trades 三项, 相对偏差超过阈值即失败。

用途: 任何代码改动后跑一遍, 防"修一个策略意外改变其他策略行为"的回归。
注意: 基线验证的是**代码正确性**(sample 数据是确定性合成数据), 不是策略有效性
(策略有效性靠真实数据 + walk-forward)。

用法:
  python tests/test_regression.py             # 校验(任一失败退出码非 0)
  python tests/test_regression.py --update    # 重新生成基线(记录 git hash)
  pytest tests/test_regression.py             # pytest 方式同上
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.alpha_mining import MultiFactorAlpha, StatisticalArbitrage, MarketRegimeStrategy
from qcode.strategies.pairs_trading import PairsTradingStrategy
from qcode.strategies.cross_sectional import CrossSectionalStrategy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # qcode/
REPO_DIR = os.path.dirname(BASE_DIR)                                     # finance/ (git root)
BASELINE = os.path.join(BASE_DIR, 'tests', 'baselines', 'regression_baseline.json')

# 与 main.py 一致的引擎参数来源
from config import (BACKTEST_CONFIG, RISK_CONFIG, PORTFOLIO_OPTIMIZATION, EXECUTION_CONFIG,
                    SHORT_CONFIG, FEE_CONFIG, MOMENTUM_STRATEGY, MEAN_REVERSION_STRATEGY,
                    MULTI_ASSET_STRATEGY, MULTI_FACTOR_ALPHA, STATISTICAL_ARBITRAGE,
                    MARKET_REGIME_STRATEGY, PAIRS_TRADING_STRATEGY, CROSS_SECTIONAL_CONFIG)

SYMBOLS = ['600519', '000858', '600036', '601318', '000333', '600887',
           '601012', '000651', '601901', '600030', '601288', '000625']
START, END = '2022-01-01', '2023-12-31'
MARKET_REGIME = 'mixed'          # sample 数据市场环境(确定性)
TOLERANCE = 0.001                # 相对偏差阈值: 0.1%
TRADE_TOLERANCE = 5              # 交易笔数绝对偏差容忍


def build_engine():
    return BacktestEngine(
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        commission=BACKTEST_CONFIG['commission'],
        slippage=BACKTEST_CONFIG['slippage'],
        enable_delta_hedging=BACKTEST_CONFIG['enable_delta_hedging'],
        use_sample_data=True, market_regime=MARKET_REGIME,
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
        borrowing_cost_annual=SHORT_CONFIG['borrowing_cost_annual'],
        stop_loss_method=RISK_CONFIG.get('stop_loss_method', 'pct'),
        atr_period=RISK_CONFIG.get('atr_period', 14),
        atr_mult=RISK_CONFIG.get('atr_mult', 2.5),
        max_gross=RISK_CONFIG.get('max_gross', 1.0),
        fee_config=FEE_CONFIG,
    )


def build_strategies():
    return {
        'momentum': MomentumStrategy(**MOMENTUM_STRATEGY),
        'mean_reversion': MeanReversionStrategy(**MEAN_REVERSION_STRATEGY),
        'multi_asset': MultiAssetStrategy(**MULTI_ASSET_STRATEGY),
        'multi_factor': MultiFactorAlpha(**MULTI_FACTOR_ALPHA),
        'stat_arb': StatisticalArbitrage(**STATISTICAL_ARBITRAGE),
        'regime': MarketRegimeStrategy(**MARKET_REGIME_STRATEGY),
        'pairs_trading': PairsTradingStrategy(**PAIRS_TRADING_STRATEGY),
        'cross_sectional': CrossSectionalStrategy(**{**CROSS_SECTIONAL_CONFIG, 'factor_weights': MULTI_FACTOR_ALPHA}),
    }


def run_strategy(name: str, strategy) -> dict:
    eng = build_engine()
    eng.add_strategy(strategy)
    eng.load_data(SYMBOLS, START, END)
    eng.run()
    m = eng.portfolio.get_performance_metrics()
    return {
        'final_value': round(float(m['total_value']), 2),
        'max_drawdown_pct': round(float(m['max_drawdown_pct']), 4),
        'num_trades': int(m['num_trades']),
    }


def git_hash() -> str:
    try:
        out = subprocess.run(['git', '-C', REPO_DIR, 'rev-parse', 'HEAD'],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else 'unknown'
    except Exception:
        return 'unknown'


def compare(measured: dict, baseline: dict) -> list:
    """返回差异描述列表(空 = 通过)。"""
    fails = []
    for key in ('final_value', 'max_drawdown_pct', 'num_trades'):
        if key not in baseline:
            continue
        m, b = measured[key], baseline[key]
        if key == 'num_trades':
            if abs(m - b) > TRADE_TOLERANCE:
                fails.append(f"  {key}: {m} vs 基线 {b} (差 {m - b:+d})")
        else:
            denom = abs(b) if abs(b) > 1e-9 else 1.0
            rel = abs(m - b) / denom
            if rel > TOLERANCE:
                fails.append(f"  {key}: {m} vs 基线 {b} (相对偏差 {rel:.4%} > {TOLERANCE:.1%})")
    return fails


def load_baseline() -> dict:
    if not os.path.exists(BASELINE):
        return {}
    with open(BASELINE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_baseline(data: dict):
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def run_all(update: bool) -> int:
    strategies = build_strategies()
    old = load_baseline().get('strategies', {}) if os.path.exists(BASELINE) else {}
    new_strategies = {}
    failed = []

    for name, strat in strategies.items():
        print(f"回测 {name} ...", flush=True)
        measured = run_strategy(name, strat)
        new_strategies[name] = measured
        if not update:
            base = old.get(name)
            if not base:
                failed.append(f"{name}: 无基线(先跑 --update)")
                print(f"  {name}: 无基线, 需 --update")
                continue
            diffs = compare(measured, base)
            if diffs:
                failed.append(f"{name}:")
                failed.extend(diffs)
                print(f"  {name}: FAIL")
            else:
                print(f"  {name}: PASS (final={measured['final_value']:.0f}, "
                      f"trades={measured['num_trades']})")

    if update:
        payload = {
            'meta': {
                'git_hash': git_hash(),
                'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
                'market_regime': MARKET_REGIME,
                'universe': SYMBOLS,
                'tolerance': TOLERANCE,
                'note': 'sample 数据基线, 验证代码正确性; 策略有效性需真实数据 + walk-forward',
            },
            'strategies': new_strategies,
        }
        save_baseline(payload)
        print(f"\n基线已写入 {BASELINE} (git {payload['meta']['git_hash']})")
        return 0

    if failed:
        print("\n" + "\n".join(failed))
        print(f"\n基线: {BASELINE} (git {load_baseline().get('meta', {}).get('git_hash', '?')})")
        print("FAIL: 存在回归, 检查本次改动; 若是有意的行为变更, 用 --update 更新基线")
        return 1
    print("\nALL STRATEGIES MATCH BASELINE")
    return 0


def test_regression_baselines():
    """pytest 入口: 基线存在时校验, 不存在则失败并提示 --update。"""
    if not os.path.exists(BASELINE):
        raise AssertionError(f"基线缺失: {BASELINE}, 先运行 python tests/test_regression.py --update")
    rc = run_all(update=False)
    assert rc == 0, "回归基线校验失败"


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--update', action='store_true', help='重新生成基线(而非校验)')
    args = ap.parse_args()
    sys.exit(run_all(update=args.update))
