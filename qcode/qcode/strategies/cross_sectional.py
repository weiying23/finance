"""月度截面选股策略(Phase 3 第一步: 把 IC 验证过的因子用在对的地方)。

与日频阈值多空(multi_factor)的本质区别:
  - 比较对象: 同一天所有股票互相排名(横截面), 而非单股指标触发(时间序列)
  - 选股方式: 排名取 top-N, 而非分数>阈值
  - 持仓周期: 月度调仓(匹配 IC@20 衰减), 而非日频进出
  - 只做多: 不做空(实测 2019-2023 牛市做空是失血源)
  - 行业中性: 每行业最多 max_per_industry 只, 避免组合被单一行业绑架
  - 等权: 通过 Signal.metadata['weight'] 让引擎按组合净值×权重开仓

流程(每月首个交易日):
  1. 对每只股票算 alpha_score(复用 MultiFactorAlpha 的因子, 权重来自 config)
  2. 按分数排名, 行业中性贪心选取 top-N
  3. 卖出掉出 top-N 的旧持仓, 买入新进 top-N 的(等权)
  4. 其余时间不发信号(持仓不动 = 低换手)
"""
from typing import Dict, List, Optional, Set

import pandas as pd

from qcode.strategies.base import BaseStrategy, Signal, SignalType
from qcode.strategies.alpha_mining import MultiFactorAlpha


class CrossSectionalStrategy(BaseStrategy):
    """月度截面选股: 排名选 top-N, 等权持有, 行业中性, 只做多。"""

    def __init__(self, name: str = "CrossSectional",
                 top_n: int = 10,
                 max_per_industry: Optional[int] = 2,
                 min_data_days: int = 120,
                 industry_map: Optional[Dict[str, str]] = None,
                 factor_weights: Optional[Dict] = None):
        params = {
            'top_n': top_n,
            'max_per_industry': max_per_industry,
            'min_data_days': min_data_days,
        }
        super().__init__(name, params)
        self.industry_map = industry_map or {}
        self._mf = MultiFactorAlpha(name="MF", **(factor_weights or {}))
        self._last_rebalance_month: Optional[str] = None
        self._current_picks: Set[str] = set()

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """抽象方法实现: 复用 MultiFactorAlpha 的因子计算(含 alpha_score)。"""
        return self._mf.calculate_indicators(data)

    def _alpha_scores(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """每只股票截至当前日的 alpha_score(取最后一个有效值)。"""
        scores = {}
        for sym, df in data.items():
            if len(df) < self.params['min_data_days']:
                continue
            ind = self._mf.calculate_indicators(df)
            if 'alpha_score' not in ind.columns:
                continue
            series = ind['alpha_score'].dropna()
            if series.empty:
                continue
            scores[sym] = float(series.iloc[-1])
        return scores

    def _select_picks(self, scores: Dict[str, float]) -> List[str]:
        """按分数排名 + 行业中性贪心选 top-N。"""
        top_n = self.params['top_n']
        max_per = self.params['max_per_industry']
        ranked = sorted(scores.items(), key=lambda x: -x[1])

        if not max_per:
            return [s for s, _ in ranked[:top_n]]

        industry_count = {}
        picks = []
        for sym, _ in ranked:
            ind = self.industry_map.get(sym)
            if ind is not None and industry_count.get(ind, 0) >= max_per:
                continue
            picks.append(sym)
            if ind is not None:
                industry_count[ind] = industry_count.get(ind, 0) + 1
            if len(picks) >= top_n:
                break
        return picks

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        if not data:
            return []

        # 当前交易日: 任意标的索引末尾(各标的共享交易日历)
        current_date = next(iter(data.values())).index[-1]
        current_month = current_date.strftime('%Y-%m')

        # 非调仓月: 不发信号(持仓不动, 低换手)
        if current_month == self._last_rebalance_month:
            return []

        scores = self._alpha_scores(data)
        if not scores:
            return []

        new_picks = self._select_picks(scores)
        new_set = set(new_picks)

        signals: List[Signal] = []
        # 先平掉掉出 top-N 的旧持仓
        for sym in sorted(self._current_picks - new_set):
            if sym in data:
                df = data[sym]
                signals.append(Signal(
                    timestamp=current_date, symbol=sym,
                    signal_type=SignalType.CLOSE_LONG, quantity=0,
                    price=float(df['close'].iloc[-1]), confidence=1.0,
                    metadata={'reason': 'out_of_top_n'}
                ))
        # 再买入新进 top-N 的(等权: weight=1/N, 引擎按净值×weight 开仓)
        weight = 1.0 / len(new_picks) if new_picks else 0.0
        for sym in sorted(new_set - self._current_picks):
            if sym in data:
                df = data[sym]
                signals.append(Signal(
                    timestamp=current_date, symbol=sym,
                    signal_type=SignalType.BUY, quantity=0,
                    price=float(df['close'].iloc[-1]), confidence=1.0,
                    metadata={'weight': weight, 'alpha_score': scores.get(sym, 0.0)}
                ))

        self._current_picks = new_set
        self._last_rebalance_month = current_month
        return signals
