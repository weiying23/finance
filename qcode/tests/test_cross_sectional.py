"""CrossSectionalStrategy 单元测试。

覆盖:
  #1 排名选股: 分数最高的 top-N 被选中
  #2 行业中性: 每行业最多 max_per_industry 只
  #3 月频调仓: 同月内不发信号, 跨月才调仓
"""
import os
import sys

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qcode.strategies.cross_sectional import CrossSectionalStrategy
from qcode.strategies.base import SignalType


def _mk_data(scores: dict, n_days: int = 250, start='2022-01-01'):
    """构造 250 天行情 + 指定末行 alpha 用的因子列(直接伪造 alpha_score 不可行,
    这里用 pb 列伪造分数: pb 越低 alpha 越高, 便于控制排名)。"""
    idx = pd.date_range(start, periods=n_days, freq='B')
    out = {}
    for sym, pb in scores.items():
        close = np.linspace(10, 20, n_days)
        df = pd.DataFrame({
            'close': close, 'high': close * 1.01, 'low': close * 0.99,
            'volume': np.full(n_days, 1e6), 'amount': np.full(n_days, 1e8),
            'pb': np.full(n_days, pb), 'pe_ttm': np.full(n_days, 15.0),
            'turnover': np.full(n_days, 1.0),
        }, index=idx)
        out[sym] = df
    return out


def test_top_n_ranking():
    """#1: top_n=2 时应选 pb 最低的两只(pb 低 → -log(pb) 高 → alpha 高)。"""
    data = _mk_data({'A': 1.0, 'B': 2.0, 'C': 3.0, 'D': 4.0})
    strat = CrossSectionalStrategy(top_n=2, max_per_industry=None,
                                   factor_weights=dict(pb_weight=1.0, amihud_weight=0.0, pe_weight=0.0))
    sigs = strat.generate_signals(data)  # 首月调仓
    buys = {s.symbol for s in sigs if s.signal_type == SignalType.BUY}
    assert buys == {'A', 'B'}, f"应选 pb 最低的 A/B, 实际 {buys}"
    print("  #1 排名选 top-N: PASS")


def test_industry_cap():
    """#2: max_per_industry=1 时, 同行业最多选 1 只。"""
    data = _mk_data({'A': 1.0, 'B': 1.5, 'C': 3.0, 'D': 4.0})
    ind = {'A': '白酒', 'B': '白酒', 'C': '银行', 'D': '银行'}
    strat = CrossSectionalStrategy(top_n=2, max_per_industry=1, industry_map=ind,
                                   factor_weights=dict(pb_weight=1.0, amihud_weight=0.0, pe_weight=0.0))
    sigs = strat.generate_signals(data)
    buys = {s.symbol for s in sigs if s.signal_type == SignalType.BUY}
    # A(白酒,分数最高) 必选; B 因同行业被挡; 轮到 C(银行)
    assert buys == {'A', 'C'}, f"行业中性应选 A/C, 实际 {buys}"
    print("  #2 行业中性: PASS")


def test_monthly_rebalance():
    """#3: 调仓后同月内不再发信号, 跨月才重新调仓。"""
    data = _mk_data({'A': 1.0, 'B': 2.0, 'C': 3.0, 'D': 4.0})
    strat = CrossSectionalStrategy(top_n=2, max_per_industry=None,
                                   factor_weights=dict(pb_weight=1.0, amihud_weight=0.0, pe_weight=0.0))
    sigs1 = strat.generate_signals(data)
    assert len(sigs1) > 0, "首月应有调仓信号"
    # 同月下一交易日: 无信号(持仓不动)
    data2 = {s: df.iloc[:-1] for s, df in data.items()}  # 少一天仍在同月
    sigs2 = strat.generate_signals(data2)
    assert sigs2 == [], f"同月不应再调仓, 实际 {len(sigs2)} 个信号"
    # 跨月: 重新调仓(分数变化 → 持仓变化 → 有信号)
    idx_new = pd.date_range('2022-02-01', periods=250, freq='B')
    data3 = {}
    for i, sym in enumerate(data.keys()):
        d = data[sym].copy()
        d.index = idx_new
        d['pb'] = np.full(len(d), 4.0 - i)  # 反转 pb: 原最高分变最低分
        data3[sym] = d
    sigs3 = strat.generate_signals(data3)
    assert len(sigs3) > 0, "跨月分数变化应重新调仓"
    assert strat._last_rebalance_month == '2023-01', "调仓后应记录新月份"
    print("  #3 月频调仓: PASS")


def _run_all():
    for fn in [test_top_n_ranking, test_industry_cap, test_monthly_rebalance]:
        print(f"running {fn.__name__}...")
        fn()
    print("\nALL TESTS PASSED")


if __name__ == '__main__':
    _run_all()
