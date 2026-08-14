"""
多资产交易策略：趋势 + MACD 生成股票多空信号（纯股票多空，已移除失效的期权死代码分支）
"""
from typing import Dict, List
import pandas as pd
import numpy as np

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class MultiAssetStrategy(BaseStrategy):
    """多资产策略：趋势强度 + MACD 柱生成股票多空信号。高波动通过 vol-target/regime overlay 在引擎层降仓处理。"""

    def __init__(self, name: str = "MultiAsset",
                 trend_period: int = 20,
                 volatility_period: int = 20,
                 hedge_threshold: float = 0.15):
        params = {
            'trend_period': trend_period,
            'volatility_period': volatility_period,
            'hedge_threshold': hedge_threshold
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算多资产所需指标"""
        df = data.copy()

        df['sma'] = self.calculate_sma(df['close'], self.params['trend_period'])
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(self.params['volatility_period']).std() * np.sqrt(252)

        df['trend_strength'] = (df['close'] - df['sma']) / df['sma']

        macd, signal, hist = self.calculate_macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist

        df['position_signal'] = 0
        df.loc[(df['trend_strength'] > 0.02) & (df['macd_hist'] > 0), 'position_signal'] = 1
        df.loc[(df['trend_strength'] < -0.02) & (df['macd_hist'] < 0), 'position_signal'] = -1

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """根据指标生成股票多空信号，所有信号带confidence"""
        signals = []

        for symbol, df in data.items():
            if len(df) < max(self.params['trend_period'], self.params['volatility_period']):
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]

            if current['position_signal'] == 1 and previous['position_signal'] != 1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend_strength']), 1.0),
                    metadata={'volatility': current['volatility']}
                ))

            elif current['position_signal'] == -1 and previous['position_signal'] != -1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend_strength']), 1.0)
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend_strength']), 1.0)
                ))

        return signals
