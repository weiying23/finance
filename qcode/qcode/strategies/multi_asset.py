"""
多资产交易策略，结合股票与衍生品（期权、期货）
"""
from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import timedelta

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class MultiAssetStrategy(BaseStrategy):
    """多资产策略：利用趋势和波动率指标生成股票多空信号，并在高波动时附加期权信号"""

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

        df['hedge_signal'] = 0
        df.loc[df['volatility'] > self.params['hedge_threshold'], 'hedge_signal'] = 1

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """根据指标生成多资产交易信号，所有信号带confidence"""
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

                if current['hedge_signal'] == 1:
                    strike_price = current['close'] * 0.95
                    signals.append(Signal(
                        timestamp=current.name,
                        symbol=symbol,
                        signal_type=SignalType.BUY_PUT,
                        quantity=0,
                        price=current['close'] * 0.03,
                        confidence=min(abs(current['trend_strength']), 1.0),
                        metadata={
                            'strike': strike_price,
                            'expiry': current.name + timedelta(days=30),
                            'option_type': 'put',
                            'volatility': current['volatility']
                        }
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

            if current['volatility'] > self.params['hedge_threshold'] * 1.5:
                strike_price = current['close'] * 1.05
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.SELL_CALL,
                    quantity=0,
                    price=current['close'] * 0.02,
                    confidence=0.5,
                    metadata={
                        'strike': strike_price,
                        'expiry': current.name + timedelta(days=30),
                        'option_type': 'call',
                        'volatility': current['volatility']
                    }
                ))

        return signals
