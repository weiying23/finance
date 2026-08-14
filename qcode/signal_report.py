"""7 策略信号 IC 横向对比报告(因子研究方法的通用化)。

因子检验方法论不只适用于 multi_factor(因子型), 也适用于信号型策略:
每个策略都有一个"打分列"(信号强度/方向), 用 IC/ICIR/FDR 检验它是否真的
预测未来收益, 就能分辨"哪个策略的信号经得起检验, 哪个的回测收益是 beta/运气"。

信号打分定义(每个策略):
  momentum      : 信号方向 {1=多, -1=空, 2/0=无}         (离散)
  mean_reversion: -distance_to_middle (越低于中轨=越强的买信号) (连续)
  multi_asset   : position_signal {-1,0,1}                (离散)
  multi_factor  : alpha_score (因子加权分)                 (连续)
  stat_arb      : -z_score (越低于60日均线=越强的买信号)     (连续)
  regime        : 信号方向 {1=多, -1=空, 2/3/0=无}          (离散)
  pairs_trading : 配对级信号(价差 z-score), 单独一节报告      (配对)

每个策略算两组 IC:
  IC(全样本) : 打分列 vs 未来 5/10/20 日收益(标准因子 IC)
  IC(入场日) : 只在"信号变化日"(入场/出场) 计算——离散信号的更严格口径,
               回答"策略喊买的那天, 未来真的涨吗?"

用法:
  python signal_report.py                        # 7 策略横向对比(sample/mixed)
  python signal_report.py --strategy momentum    # 只看单策略
  python signal_report.py --real --symbols 600519 000858   # 真实数据
"""
import argparse
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '.')

from config import STOCK_UNIVERSE, PAIRS_TRADING_STRATEGY
from qcode.data.sample_source import SampleDataSource
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.alpha_mining import MultiFactorAlpha, StatisticalArbitrage, MarketRegimeStrategy
from qcode.utils.significance import factor_ic_report

FORWARD_PERIODS = (5, 10, 20)

DISCRETE_MAP = {1: 1.0, -1: -1.0, 2: 0.0, 3: 0.0, 0: 0.0}


def build_strategies():
    from config import (MOMENTUM_STRATEGY, MEAN_REVERSION_STRATEGY, MULTI_ASSET_STRATEGY,
                        MULTI_FACTOR_ALPHA, STATISTICAL_ARBITRAGE, MARKET_REGIME_STRATEGY)
    return {
        'momentum': (MomentumStrategy(**MOMENTUM_STRATEGY), 'discrete'),
        'mean_reversion': (MeanReversionStrategy(**MEAN_REVERSION_STRATEGY), 'continuous'),
        'multi_asset': (MultiAssetStrategy(**MULTI_ASSET_STRATEGY), 'discrete'),
        'multi_factor': (MultiFactorAlpha(**MULTI_FACTOR_ALPHA), 'continuous'),
        'stat_arb': (StatisticalArbitrage(**STATISTICAL_ARBITRAGE), 'continuous'),
        'regime': (MarketRegimeStrategy(**MARKET_REGIME_STRATEGY), 'discrete'),
    }


def extract_score(name: str, df: pd.DataFrame) -> pd.Series:
    """把每个策略的指标输出压缩成一个打分列(方向/强度)。"""
    if name == 'momentum':
        return df['signal'].map(DISCRETE_MAP).fillna(0.0)
    if name == 'mean_reversion':
        return -df['distance_to_middle']
    if name == 'multi_asset':
        return df['position_signal'].astype(float)
    if name == 'multi_factor':
        return df['alpha_score']
    if name == 'stat_arb':
        return -df['z_score']
    if name == 'regime':
        return df['signal'].map(DISCRETE_MAP).fillna(0.0)
    raise ValueError(f"unknown strategy {name}")


def load_data(sample: bool, regime: str, symbols, start: str, end: str):
    if sample:
        ds = SampleDataSource(market_regime=regime)
        return ds.get_multiple_stocks(symbols, start, end)
    # 真实数据: 与主引擎一致, 读 config.DATA_CONFIG['data_source'](默认 baostock)
    from config import DATA_CONFIG
    from qcode.data.factory import create_data_source
    ds = create_data_source(source=DATA_CONFIG.get('data_source', 'baostock'),
                            tushare_token=DATA_CONFIG.get('tushare_token', ''),
                            cache_data=True)
    return ds.get_multiple_stocks(symbols, start, end)


def compute_strategy_ic(name, strategy, data):
    """返回 {factor: {fp: {...}}} 报告结构: 'score' 全样本, 'score_entry' 入场日。"""
    indicated = {}
    for sym, df in data.items():
        ind = strategy.calculate_indicators(df)
        s = extract_score(name, ind)
        ind = ind.copy()
        ind['score'] = s
        # 入场日: 打分变化的日子(离散信号的事件口径; 连续打分每日变化 ≈ 全样本)
        ind['score_entry'] = s.where(s != s.shift(1))
        indicated[sym] = ind
    return factor_ic_report(indicated, ['score', 'score_entry'], forward_periods=FORWARD_PERIODS)


def fmt_ic(v):
    return f"{v:+.4f}"


def print_strategy_row(name, score_type, report):
    row = report.get('score', {})
    row_e = report.get('score_entry', {})
    ic5 = row.get(5, {}).get('mean_ic', 0.0)
    ic5e = row_e.get(5, {}).get('mean_ic', 0.0)
    icir5 = row.get(5, {}).get('ic_ir', 0.0)
    fdr5 = row.get(5, {}).get('num_significant_bh', 0)
    n5 = row.get(5, {}).get('num_tests', 0)
    ic_strs = ''.join(fmt_ic(row.get(fp, {}).get('mean_ic', 0.0)) for fp in FORWARD_PERIODS)
    if score_type == 'discrete':
        verdict = "入场日IC转正/显著" if ic5e > 0.02 else ("负预测力" if ic5e < -0.02 else "无预测力")
    else:
        verdict = "有正预测力" if ic5 > 0.02 else ("负预测力" if ic5 < -0.02 else "无预测力")
    print(f"{name:<16}{score_type:<11}{ic_strs}{ic5e:>+9.4f}{icir5:>8.3f}"
          f"{str(fdr5)+'/'+str(n5):>10}  {verdict}")


def pairs_signal_ic(data, pairs, lookback=60, forward_periods=(5, 10, 20)):
    """配对级信号 IC: 价差 z-score 是否预测价差向均值回归。

    score = -z(价差低于均值=买腿信号), 被预测变量 = 未来价差变化 Δspread。
    IC > 0 表示"价差偏低时未来价差上升(回归均值)", 即均值回归信号有效。
    """
    rows = []
    for sym1, sym2 in pairs:
        if sym1 not in data or sym2 not in data:
            continue
        df1, df2 = data[sym1], data[sym2]
        idx = df1.index.intersection(df2.index)
        if len(idx) < lookback + 30:
            continue
        p1, p2 = df1.loc[idx, 'close'], df2.loc[idx, 'close']
        recent = idx[-lookback:]
        beta = np.polyfit(p2.loc[recent], p1.loc[recent], 1)[0]
        spread = p1 - beta * p2
        m = spread.rolling(lookback).mean()
        s = spread.rolling(lookback).std()
        z = (spread - m) / s
        ic_row = []
        for fp in forward_periods:
            fwd_change = spread.shift(-fp) - spread
            pair_df = pd.DataFrame({'score': -z, 'ret': fwd_change}).dropna()
            ic = pair_df['score'].corr(pair_df['ret']) if len(pair_df) >= 30 else 0.0
            ic_row.append(ic)
        rows.append((f"{sym1}/{sym2}", ic_row))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--strategy', default=None, help='只看单个策略(默认全部)')
    ap.add_argument('--real', action='store_true', help='真实数据(默认 sample)')
    ap.add_argument('--regime', default='mixed', choices=['bear', 'bull', 'sideways', 'mixed'])
    ap.add_argument('--symbols', nargs='+', default=None)
    ap.add_argument('--start', default='2022-01-01')
    ap.add_argument('--end', default='2023-12-31')
    args = ap.parse_args()

    symbols = args.symbols or (['600519', '000858', '600036', '601318', '000333', '600887',
                                '601012', '000651', '601901', '600030', '601288', '000625']
                               if not args.real else STOCK_UNIVERSE)
    print(f"数据: {'sample(' + args.regime + ')' if not args.real else 'real'} | "
          f"{len(symbols)} 只 | {args.start} ~ {args.end}\n")

    data = load_data(not args.real, args.regime, symbols, args.start, args.end)
    strategies = build_strategies()

    print(f"{'策略':<16}{'打分类型':<11}" + ''.join(f"{f'IC@{fp}':>9}" for fp in FORWARD_PERIODS)
          + f"{'入场IC@5':>10}{'ICIR@5':>9}{'FDR@5':>11}  判定")
    print("-" * (16 + 11 + 9 * len(FORWARD_PERIODS) + 10 + 9 + 11 + 4))

    for name, (strat, score_type) in strategies.items():
        if args.strategy and name != args.strategy:
            continue
        report = compute_strategy_ic(name, strat, data)
        print_strategy_row(name, score_type, report)

    print()
    print("--- pairs_trading(配对级信号: 价差 z-score 预测回归) ---")
    pairs = PAIRS_TRADING_STRATEGY.get('pairs', [])
    pair_rows = pairs_signal_ic(data, pairs)
    if pair_rows:
        print(f"{'配对':<20}" + ''.join(f"{f'IC@fp={fp}':>12}" for fp in FORWARD_PERIODS))
        print("-" * (20 + 12 * len(FORWARD_PERIODS)))
        for label, ic_row in pair_rows:
            print(f"{label:<20}" + ''.join(f"{v:>+12.4f}" for v in ic_row))
    else:
        print("(无配对数据)")
    print()
    print("口径说明:")
    print("  IC = 打分列与未来收益的时间序列相关性(逐股算后平均); ICIR = 平均IC/IC波动(信噪比);")
    print("  FDR = 显著性检验(样本太少时多为 0/N, 说明检验力不足, 需更多股票);")
    print("  入场IC@5 = 只在信号变化日算的 5 日 IC(离散信号更严格口径);")
    print("  |IC| >= 0.02~0.05 才算有微弱预测力(机构经验值)。")


if __name__ == '__main__':
    main()
