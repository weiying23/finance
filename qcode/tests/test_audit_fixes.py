"""审计修复的最小行为测试(可用 pytest 或 `python tests/test_audit_fixes.py` 直接跑)。

覆盖:
  #1 _new_engine 透传 fee_config(walk-forward 引擎与主引擎口径一致)
  #2 信号开仓受 max_gross 封顶(原 2.4x 杠杆失控)
  #3 T+1: 当日新建仓不可当日平
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qcode.backtest.engine import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy
from qcode.data.sample_source import SampleDataSource
import pandas as pd


def test_fee_config_passthrough():
    """#1: _new_engine 必须透传 fee_config, 否则 walk-forward 引擎缺印花税/T+1/涨跌停。"""
    parent = BacktestEngine(
        initial_capital=1_000_000, use_sample_data=True, market_regime='bear',
        fee_config={'stamp_tax': 0.0005, 'transfer_fee': 0.00001,
                    'limit_pct_default': 0.10, 'limit_pct_wide': 0.20, 't_plus_1': True},
    )
    child = parent._new_engine(parent.initial_capital)
    assert child.stamp_tax == parent.stamp_tax, "stamp_tax 未透传"
    assert child.transfer_fee == parent.transfer_fee, "transfer_fee 未透传"
    assert child.t_plus_1 == parent.t_plus_1, "t_plus_1 未透传"
    assert child.limit_pct_wide == parent.limit_pct_wide, "limit_pct_wide 未透传"
    print("  #1 fee_config 透传: PASS")


def test_gross_cap_no_leverage():
    """#2: 信号开仓后总杠杆不得超 max_gross(默认 1.0, 无借贷)。

    原 bug: OPEN_SHORT 的 proceeds 抬高 cash → 反复开多 → 总敞口达 2.4x NAV。
    修复后 equity_df.positions_value / total_value 应全程 ≤ ~1.0(允许价格小幅漂移)。
    """
    eng = BacktestEngine(
        initial_capital=1_000_000, use_sample_data=True, market_regime='bear',
        max_gross=1.0, max_position_size=0.15, fee_config={'t_plus_1': True, 'stamp_tax': 0.0005},
    )
    eng.add_strategy(MomentumStrategy(name="Momentum"))
    # 3 只样本股, 满足 momentum 所需数据
    ds = SampleDataSource(market_regime='bear')
    eng.market_data = ds.get_multiple_stocks(['600519', '000858', '600036'],
                                             '2022-01-01', '2023-12-31')
    eng.run()
    eq = eng.portfolio.get_equity_curve_df()
    assert not eq.empty, "无净值曲线"
    nav = eq['total_value'].clip(lower=1.0)
    gross_ratio = eq['positions_value'] / nav
    peak = gross_ratio.max()
    assert peak <= 1.05, f"总杠杆失控: peak gross/NAV = {peak:.2f}x (>1.05)"
    print(f"  #2 总杠杆封顶: peak gross/NAV = {peak:.2f}x (≤1.05) PASS")


def test_t1_same_day_not_closable():
    """#3: T+1 — 当日新建仓的 position, _is_t1_blocked 返回 True。"""
    from qcode.portfolio.manager import Position
    from datetime import datetime
    eng = BacktestEngine(initial_capital=1_000_000, fee_config={'t_plus_1': True})
    today = pd.Timestamp('2023-06-01')
    pos = Position(symbol='600519', quantity=100, entry_price=100.0,
                   entry_time=datetime(2023, 6, 1), position_type='long')
    assert eng._is_t1_blocked(pos, today) is True, "当日新仓应被 T+1 阻挡"
    yesterday = pd.Timestamp('2023-05-31')
    assert eng._is_t1_blocked(pos, yesterday) is False, "前日仓位不应被 T+1 阻挡"
    # fee_config 关闭 T+1 时永远不阻挡
    eng2 = BacktestEngine(initial_capital=1_000_000, fee_config={'t_plus_1': False})
    assert eng2._is_t1_blocked(pos, today) is False, "t_plus_1=False 应不阻挡"
    print("  #3 T+1 当日新仓阻挡: PASS")


def _run_all():
    for fn in [test_fee_config_passthrough, test_gross_cap_no_leverage, test_t1_same_day_not_closable]:
        print(f"running {fn.__name__}...")
        fn()
    print("\nALL TESTS PASSED")


if __name__ == '__main__':
    _run_all()
