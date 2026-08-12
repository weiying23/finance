"""Mean reversion trading strategy"""
from typing import Dict, List
import pandas as pd
import numpy as np

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands"""

    def __init__(self, name: str = "MeanReversion",
                 bb_period: int = 20,
                 bb_std: float = 2.0,
                 lookback: int = 5):
        params = {
            'bb_period': bb_period,
            'bb_std': bb_std,
            'lookback': lookback
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate mean reversion indicators"""
        df = data.copy()

        middle, upper, lower = self.calculate_bollinger_bands(
            df['close'], self.params['bb_period'], self.params['bb_std']
        )

        df['bb_middle'] = middle
        df['bb_upper'] = upper
        df['bb_lower'] = lower
        df['bb_width'] = (upper - lower) / middle

        df['distance_to_middle'] = (df['close'] - middle) / middle

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """Generate trading signals with clear semantic distinction"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.params['bb_period']:
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]

            if current['close'] <= current['bb_lower'] and current['bb_width'] > 0.05:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['distance_to_middle']), 1.0)
                ))

            elif current['close'] >= current['bb_upper'] and current['bb_width'] > 0.05:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['distance_to_middle']), 1.0)
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['distance_to_middle']), 1.0)
                ))

            elif abs(current['distance_to_middle']) < 0.01:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['distance_to_middle']), 1.0)
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['distance_to_middle']), 1.0)
                ))

        return signals
