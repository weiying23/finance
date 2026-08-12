"""
基于动量的交易策略，使用移动平均线交叉和RSI指标
"""
from typing import Dict, List
import pandas as pd
import numpy as np

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class MomentumStrategy(BaseStrategy):
    """动量策略：利用快慢均线交叉和RSI超买超卖产生交易信号"""

    def __init__(self, name: str = "Momentum",
                 fast_period: int = 10,
                 slow_period: int = 30,
                 rsi_period: int = 14,
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70):
        params = {
            'fast_period': fast_period,
            'slow_period': slow_period,
            'rsi_period': rsi_period,
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': rsi_overbought
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算动量指标：快慢SMA、RSI，并生成原始信号列"""
        df = data.copy()

        df['sma_fast'] = self.calculate_sma(df['close'], self.params['fast_period'])
        df['sma_slow'] = self.calculate_sma(df['close'], self.params['slow_period'])
        df['rsi'] = self.calculate_rsi(df['close'], self.params['rsi_period'])

        df['signal'] = 0
        df.loc[(df['sma_fast'] > df['sma_slow']) &
               (df['rsi'] < self.params['rsi_overbought']), 'signal'] = 1
        df.loc[(df['sma_fast'] < df['sma_slow']) |
               (df['rsi'] > self.params['rsi_overbought']), 'signal'] = -1

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """根据指标信号生成实际的交易信号（买入/卖出），所有信号都带confidence"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.params['slow_period']:
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]

            if current['signal'] == 1 and previous['signal'] != 1:
                confidence = min(abs(current['rsi'] - 50) / 50, 1.0)
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close'],
                    confidence=confidence
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=confidence
                ))

            elif current['signal'] == -1 and previous['signal'] != -1:
                confidence = min(abs(current['rsi'] - 50) / 50, 1.0)
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=confidence
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=confidence
                ))

        return signals
