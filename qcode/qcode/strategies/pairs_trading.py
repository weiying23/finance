"""Pairs trading strategy based on cointegration"""
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class PairsTradingStrategy(BaseStrategy):
    """Cointegration-based pairs trading: trade spread residual mean reversion"""

    def __init__(self, name: str = "PairsTrading",
                 lookback: int = 60,
                 entry_zscore: float = 2.0,
                 exit_zscore: float = 0.5,
                 pairs: List[Tuple[str, str]] = None):
        params = {
            'lookback': lookback,
            'entry_zscore': entry_zscore,
            'exit_zscore': exit_zscore,
            'pairs': pairs or []
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Not used for pairs trading - handled in generate_signals"""
        return data

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """Generate signals for cointegrated pairs"""
        signals = []
        pairs = self.params['pairs']

        for sym1, sym2 in pairs:
            if sym1 not in data or sym2 not in data:
                continue

            df1 = data[sym1]
            df2 = data[sym2]

            merged_idx = df1.index.intersection(df2.index)
            if len(merged_idx) < self.params['lookback']:
                continue

            price1 = df1.loc[merged_idx, 'close']
            price2 = df2.loc[merged_idx, 'close']

            recent_idx = merged_idx[-self.params['lookback']:]
            p1_recent = price1.loc[recent_idx]
            p2_recent = price2.loc[recent_idx]

            score, pvalue, _ = coint(p1_recent, p2_recent)
            if pvalue > 0.05:
                continue

            beta = np.polyfit(p2_recent, p1_recent, 1)[0]
            spread = price1 - beta * price2

            rolling_mean = spread.rolling(self.params['lookback']).mean()
            rolling_std = spread.rolling(self.params['lookback']).std()
            z_score = (spread - rolling_mean) / rolling_std

            if len(z_score) < 2:
                continue

            current_z = z_score.iloc[-1]
            previous_z = z_score.iloc[-2]
            current_date = merged_idx[-1]
            current_price1 = price1.loc[current_date]
            current_price2 = price2.loc[current_date]

            entry = self.params['entry_zscore']
            exit = self.params['exit_zscore']

            if current_z < -entry and previous_z >= -entry:
                signals.append(Signal(
                    timestamp=current_date,
                    symbol=sym1,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current_price1,
                    confidence=min(abs(current_z) / (entry * 1.5), 1.0),
                    metadata={'z_score': current_z, 'pair': (sym1, sym2), 'beta': beta}
                ))
                signals.append(Signal(
                    timestamp=current_date,
                    symbol=sym2,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current_price2,
                    confidence=min(abs(current_z) / (entry * 1.5), 1.0),
                    metadata={'z_score': current_z, 'pair': (sym1, sym2), 'beta': beta}
                ))

            elif current_z > entry and previous_z <= entry:
                signals.append(Signal(
                    timestamp=current_date,
                    symbol=sym1,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current_price1,
                    confidence=min(abs(current_z) / (entry * 1.5), 1.0),
                    metadata={'z_score': current_z, 'pair': (sym1, sym2), 'beta': beta}
                ))
                signals.append(Signal(
                    timestamp=current_date,
                    symbol=sym2,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current_price2,
                    confidence=min(abs(current_z) / (entry * 1.5), 1.0),
                    metadata={'z_score': current_z, 'pair': (sym1, sym2), 'beta': beta}
                ))

            elif abs(current_z) < exit and abs(previous_z) >= exit:
                signals.append(Signal(
                    timestamp=current_date,
                    symbol=sym1,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current_price1,
                    confidence=0.5,
                    metadata={'z_score': current_z, 'pair': (sym1, sym2)}
                ))
                signals.append(Signal(
                    timestamp=current_date,
                    symbol=sym2,
                    signal_type=SignalType.CLOSE_SHORT,
                    quantity=0,
                    price=current_price2,
                    confidence=0.5,
                    metadata={'z_score': current_z, 'pair': (sym1, sym2)}
                ))

        return signals
