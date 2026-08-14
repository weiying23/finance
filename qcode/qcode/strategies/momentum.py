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
        """计算动量指标: 快慢SMA、RSI、ADX(趋势滤子), 生成原始信号列。

        signal 语义:
          1  = 多头(sma_fast>sma_slow 且 RSI 未超买) → BUY + CLOSE_SHORT
         -1  = 空头入场(sma 死叉 且 ADX>阈值, 强下跌趋势) → CLOSE_LONG + OPEN_SHORT
          2  = 止盈(RSI 超买) → 仅 CLOSE_LONG, 不反手做空(避免逆势接飞刀)
          0  = 中性
        """
        df = data.copy()

        df['sma_fast'] = self.calculate_sma(df['close'], self.params['fast_period'])
        df['sma_slow'] = self.calculate_sma(df['close'], self.params['slow_period'])
        df['rsi'] = self.calculate_rsi(df['close'], self.params['rsi_period'])
        df['adx'] = self.calculate_adx(df['high'], df['low'], df['close'], self.params['rsi_period'])
        adx_thresh = self.params.get('adx_threshold', 25)

        df['signal'] = 0
        # 多头: 快线上穿慢线且未超买
        df.loc[(df['sma_fast'] > df['sma_slow']) & (df['rsi'] < self.params['rsi_overbought']), 'signal'] = 1
        # 空头入场: 死叉 + ADX 强趋势(过滤震荡市的假信号)
        df.loc[(df['sma_fast'] < df['sma_slow']) & (df['adx'] > adx_thresh), 'signal'] = -1
        # 止盈: RSI 超买 → 仅平多, 不反手做空
        df.loc[df['rsi'] > self.params['rsi_overbought'], 'signal'] = 2

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """根据指标信号生成交易信号, RSI 超买只止盈不平空。"""
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
                    timestamp=current.name, symbol=symbol,
                    signal_type=SignalType.BUY, quantity=0, price=current['close'],
                    confidence=confidence
                ))
                signals.append(Signal(
                    timestamp=current.name, symbol=symbol,
                    signal_type=SignalType.CLOSE_SHORT, quantity=0, price=current['close'],
                    confidence=confidence
                ))

            elif current['signal'] == -1 and previous['signal'] != -1:
                confidence = min(abs(current['rsi'] - 50) / 50, 1.0)
                signals.append(Signal(
                    timestamp=current.name, symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG, quantity=0, price=current['close'],
                    confidence=confidence
                ))
                signals.append(Signal(
                    timestamp=current.name, symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT, quantity=0, price=current['close'],
                    confidence=confidence
                ))

            elif current['signal'] == 2 and previous['signal'] != 2:
                # RSI 超买止盈: 仅平多, 不开空(避免趋势中反复"超买做空"被扫损)
                confidence = min(abs(current['rsi'] - 50) / 50, 1.0)
                signals.append(Signal(
                    timestamp=current.name, symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG, quantity=0, price=current['close'],
                    confidence=confidence
                ))

        return signals
