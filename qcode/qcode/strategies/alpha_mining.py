"""Advanced alpha mining strategies"""
from typing import Dict, List
import pandas as pd
import numpy as np
from scipy import stats

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class MultiFactorAlpha(BaseStrategy):
    """Multi-factor alpha mining strategy combining multiple signals"""

    def __init__(self, name: str = "MultiFactorAlpha",
                 momentum_weight: float = 0.3,
                 value_weight: float = 0.3,
                 volatility_weight: float = 0.2,
                 volume_weight: float = 0.2):
        params = {
            'momentum_weight': momentum_weight,
            'value_weight': value_weight,
            'volatility_weight': volatility_weight,
            'volume_weight': volume_weight,
            'lookback_short': 5,
            'lookback_medium': 20,
            'lookback_long': 60
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate multi-factor indicators"""
        df = data.copy()

        df['returns_5d'] = df['close'].pct_change(5)
        df['returns_20d'] = df['close'].pct_change(20)
        df['momentum_score'] = (df['returns_5d'] * 0.4 + df['returns_20d'] * 0.6)

        df['sma_60'] = df['close'].rolling(60).mean()
        df['value_score'] = (df['sma_60'] - df['close']) / df['sma_60']

        df['volatility'] = df['close'].pct_change().rolling(20).std()
        vol_mean = df['volatility'].mean()
        vol_std = df['volatility'].std()
        if vol_std > 0:
            df['volatility_score'] = -(df['volatility'] - vol_mean) / vol_std
        else:
            df['volatility_score'] = 0

        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_score'] = (df['volume'] - df['volume_ma']) / df['volume_ma']

        for col in ['momentum_score', 'value_score', 'volume_score']:
            if df[col].std() > 0:
                df[col] = (df[col] - df[col].mean()) / df[col].std()
                df[col] = df[col].clip(-2, 2) / 2

        df['alpha_score'] = (
            df['momentum_score'] * self.params['momentum_weight'] +
            df['value_score'] * self.params['value_weight'] +
            df['volatility_score'] * self.params['volatility_weight'] +
            df['volume_score'] * self.params['volume_weight']
        )

        df['position'] = 0
        df.loc[df['alpha_score'] > 0.2, 'position'] = 1
        df.loc[df['alpha_score'] < -0.2, 'position'] = -1
        df.loc[(df['position'].shift(1) == 1) & (df['alpha_score'] < -0.1), 'position'] = 0
        df.loc[(df['position'].shift(1) == -1) & (df['alpha_score'] > 0.1), 'position'] = 0

        df['signal'] = 0
        df.loc[(df['position'] == 1) & (df['position'].shift(1) != 1), 'signal'] = 1
        df.loc[(df['position'] == 0) & (df['position'].shift(1) == 1), 'signal'] = 2
        df.loc[(df['position'] == -1) & (df['position'].shift(1) != -1), 'signal'] = -1
        df.loc[(df['position'] == 0) & (df['position'].shift(1) == -1), 'signal'] = 3

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """Generate trading signals based on alpha score"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.params['lookback_long']:
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]

            if current['signal'] == 1 and previous['signal'] != 1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['alpha_score']), 1.0),
                    metadata={'alpha_score': current['alpha_score']}
                ))

            elif current['signal'] == 2 and previous['signal'] != 2:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['alpha_score']), 1.0),
                    metadata={'alpha_score': current['alpha_score']}
                ))

            elif current['signal'] == -1 and previous['signal'] != -1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['alpha_score']), 1.0),
                    metadata={'alpha_score': current['alpha_score']}
                ))

            elif current['signal'] == 3 and previous['signal'] != 3:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['alpha_score']), 1.0),
                    metadata={'alpha_score': current['alpha_score']}
                ))

        return signals


class StatisticalArbitrage(BaseStrategy):
    """Statistical arbitrage using mean reversion and z-scores"""

    def __init__(self, name: str = "StatArb",
                 lookback: int = 60,
                 entry_zscore: float = 2.0,
                 exit_zscore: float = 0.5,
                 stop_loss_zscore: float = 3.0):
        params = {
            'lookback': lookback,
            'entry_zscore': entry_zscore,
            'exit_zscore': exit_zscore,
            'stop_loss_zscore': stop_loss_zscore
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate statistical arbitrage indicators"""
        df = data.copy()

        df['rolling_mean'] = df['close'].rolling(self.params['lookback']).mean()
        df['rolling_std'] = df['close'].rolling(self.params['lookback']).std()
        df['z_score'] = (df['close'] - df['rolling_mean']) / df['rolling_std']

        df['position'] = 0
        df.loc[df['z_score'] < -self.params['entry_zscore'], 'position'] = 1
        df.loc[df['z_score'] > self.params['entry_zscore'], 'position'] = -1

        df.loc[(df['position'].shift(1) == 1) & (df['z_score'] > -self.params['exit_zscore']), 'position'] = 0
        df.loc[(df['position'].shift(1) == -1) & (df['z_score'] < self.params['exit_zscore']), 'position'] = 0

        df.loc[(df['position'].shift(1) == 1) & (df['z_score'] < -self.params['stop_loss_zscore']), 'position'] = 0
        df.loc[(df['position'].shift(1) == -1) & (df['z_score'] > self.params['stop_loss_zscore']), 'position'] = 0

        df['signal'] = 0
        df.loc[(df['position'] == 1) & (df['position'].shift(1) != 1), 'signal'] = 1
        df.loc[(df['position'] == 0) & (df['position'].shift(1) == 1), 'signal'] = 2
        df.loc[(df['position'] == -1) & (df['position'].shift(1) != -1), 'signal'] = -1
        df.loc[(df['position'] == 0) & (df['position'].shift(1) == -1), 'signal'] = 3

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """Generate stat arb signals with OPEN_SHORT for short positions"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.params['lookback']:
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]

            if current['signal'] == 1 and previous['signal'] != 1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['z_score']) / 3, 1.0),
                    metadata={'z_score': current['z_score']}
                ))
            elif current['signal'] == 2 and previous['signal'] != 2:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['z_score']) / 3, 1.0),
                    metadata={'z_score': current['z_score']}
                ))

            elif current['signal'] == -1 and previous['signal'] != -1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['z_score']) / 3, 1.0),
                    metadata={'z_score': current['z_score']}
                ))

            elif current['signal'] == 3 and previous['signal'] != 3:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['z_score']) / 3, 1.0),
                    metadata={'z_score': current['z_score']}
                ))

        return signals


class MarketRegimeStrategy(BaseStrategy):
    """Adaptive strategy that changes based on market regime"""

    def __init__(self, name: str = "RegimeAdaptive",
                 regime_lookback: int = 60):
        params = {
            'regime_lookback': regime_lookback,
            'trend_threshold': 0.02,
            'volatility_threshold': 0.25
        }
        super().__init__(name, params)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Detect market regime and apply appropriate strategy"""
        df = data.copy()

        df['returns'] = df['close'].pct_change()
        df['trend'] = df['returns'].rolling(self.params['regime_lookback']).mean()
        df['volatility'] = df['returns'].rolling(self.params['regime_lookback']).std() * np.sqrt(252)

        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()

        df['regime'] = 'sideways'
        df.loc[(df['trend'] > self.params['trend_threshold']) &
               (df['volatility'] < self.params['volatility_threshold']), 'regime'] = 'uptrend_low_vol'
        df.loc[(df['trend'] > self.params['trend_threshold']) &
               (df['volatility'] >= self.params['volatility_threshold']), 'regime'] = 'uptrend_high_vol'
        df.loc[(df['trend'] < -self.params['trend_threshold']) &
               (df['volatility'] < self.params['volatility_threshold']), 'regime'] = 'downtrend_low_vol'
        df.loc[(df['trend'] < -self.params['trend_threshold']) &
               (df['volatility'] >= self.params['volatility_threshold']), 'regime'] = 'downtrend_high_vol'

        df['signal'] = 0

        mask = (df['regime'] == 'uptrend_low_vol') & (df['close'] > df['sma_20'])
        df.loc[mask & (df['close'].shift(1) <= df['sma_20'].shift(1)), 'signal'] = 1
        df.loc[mask & (df['close'] < df['sma_20']), 'signal'] = -1

        mask = (df['regime'] == 'uptrend_high_vol') & (df['close'] > df['sma_50'])
        df.loc[mask & (df['close'].shift(1) <= df['sma_50'].shift(1)), 'signal'] = 1

        mask = df['regime'].isin(['downtrend_low_vol', 'sideways'])
        df.loc[mask & (df['close'] < df['sma_20'] * 0.98), 'signal'] = 1
        df.loc[mask & (df['close'] > df['sma_20'] * 1.02), 'signal'] = -1

        mask = df['regime'] == 'downtrend_high_vol'
        df.loc[mask, 'signal'] = 0

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """Generate regime-adaptive signals with clear BUY/OPEN_SHORT/CLOSE distinction"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.params['regime_lookback']:
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]

            if current['signal'] == 1 and previous['signal'] != 1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend']) / 0.05, 1.0),
                    metadata={'regime': current['regime']}
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend']) / 0.05, 1.0),
                    metadata={'regime': current['regime']}
                ))

            elif current['signal'] == -1 and previous['signal'] != -1:
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.CLOSE_LONG,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend']) / 0.05, 1.0),
                    metadata={'regime': current['regime']}
                ))
                signals.append(Signal(
                    timestamp=current.name,
                    symbol=symbol,
                    signal_type=SignalType.OPEN_SHORT,
                    quantity=0,
                    price=current['close'],
                    confidence=min(abs(current['trend']) / 0.05, 1.0),
                    metadata={'regime': current['regime']}
                ))

            elif current['signal'] == 0 and previous['signal'] != 0:
                if previous['signal'] == 1:
                    signals.append(Signal(
                        timestamp=current.name,
                        symbol=symbol,
                        signal_type=SignalType.CLOSE_LONG,
                        quantity=0,
                        price=current['close'],
                        confidence=min(abs(current['trend']) / 0.05, 1.0),
                        metadata={'regime': current['regime']}
                    ))
                elif previous['signal'] == -1:
                    signals.append(Signal(
                        timestamp=current.name,
                        symbol=symbol,
                        signal_type=SignalType.CLOSE_SHORT,
                        quantity=0,
                        price=current['close'],
                        confidence=min(abs(current['trend']) / 0.05, 1.0),
                        metadata={'regime': current['regime']}
                    ))

        return signals
