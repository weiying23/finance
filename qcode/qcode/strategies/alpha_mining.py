"""Advanced alpha mining strategies"""
from typing import Dict, List
import pandas as pd
import numpy as np
from scipy import stats

from qcode.strategies.base import BaseStrategy, Signal, SignalType


class MultiFactorAlpha(BaseStrategy):
    """Multi-factor alpha mining strategy combining multiple signals

    因子清单(权重在 config.MULTI_FACTOR_ALPHA, 未启用因子权重置 0):
      旧四因子: momentum / value(价格-60日均线反转) / volatility(低波) / volume(量)
      新五因子(2026-08, 50只×5年 IC 检验后加入):
        turnover    换手率(低换手=冷门反转)         数据: baostock turn
        reversal    250日长期反转(年度反转效应)      数据: close
        amihud      非流动性(Amihud |收益|/成交额)  数据: close+amount
        pb          -log(PB), 越便宜越高分          数据: baostock pbMRQ
        pe          -log(PE, 仅正值), 越便宜越高分   数据: baostock peTTM
    """

    def __init__(self, name: str = "MultiFactorAlpha",
                 momentum_weight: float = 0.3,
                 value_weight: float = 0.3,
                 volatility_weight: float = 0.2,
                 volume_weight: float = 0.2,
                 turnover_weight: float = 0.0,
                 reversal_weight: float = 0.0,
                 amihud_weight: float = 0.0,
                 pb_weight: float = 0.0,
                 pe_weight: float = 0.0,
                 roe_weight: float = 0.0,
                 gp_margin_weight: float = 0.0,
                 debt_ratio_weight: float = 0.0,
                 yoy_ni_weight: float = 0.0):
        params = {
            'momentum_weight': momentum_weight,
            'value_weight': value_weight,
            'volatility_weight': volatility_weight,
            'volume_weight': volume_weight,
            'turnover_weight': turnover_weight,
            'reversal_weight': reversal_weight,
            'amihud_weight': amihud_weight,
            'pb_weight': pb_weight,
            'pe_weight': pe_weight,
            'roe_weight': roe_weight,
            'gp_margin_weight': gp_margin_weight,
            'debt_ratio_weight': debt_ratio_weight,
            'yoy_ni_weight': yoy_ni_weight,
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

        # --- 新因子(2026-08) ---
        # 换手率: 20日均换手, 低换手=冷门(方向由 IC 检验决定)
        if 'turnover' in df.columns:
            df['turnover_score'] = df['turnover'].rolling(20).mean()
        else:
            df['turnover_score'] = np.nan

        # 250日长期反转: 过去一年涨幅取负(涨太多=低分, A股年度反转效应)
        df['reversal_score'] = -df['close'].pct_change(250)

        # Amihud 非流动性: 60日均值(|日收益|/成交额), 大=流动性差
        if 'amount' in df.columns and df['amount'].notna().any() and (df['amount'].fillna(0) > 0).any():
            amihud = (df['close'].pct_change().abs() / df['amount'].replace(0, np.nan))
            df['amihud_score'] = amihud.rolling(60).mean()
        else:
            df['amihud_score'] = np.nan

        # PB / PE: 负值/缺失 → NaN(亏损股无 PE; log 只对正值有意义)
        if 'pb' in df.columns:
            df['pb_score'] = -np.log(df['pb'].where(df['pb'] > 0))
        else:
            df['pb_score'] = np.nan
        if 'pe_ttm' in df.columns:
            df['pe_score'] = -np.log(df['pe_ttm'].where(df['pe_ttm'] > 0))
        else:
            df['pe_score'] = np.nan

        # --- 质量因子(2026-08, baostock 年报, pubDate 时点对齐后由 fundamental.py 注入) ---
        # roe/gp_margin/yoy_ni 越高越好; debt_ratio(资产负债率)越低越好 → 取负
        if 'roe' in df.columns:
            df['roe_score'] = df['roe']
        else:
            df['roe_score'] = np.nan
        if 'gp_margin' in df.columns:
            df['gp_margin_score'] = df['gp_margin']
        else:
            df['gp_margin_score'] = np.nan
        if 'debt_ratio' in df.columns:
            df['debt_ratio_score'] = -df['debt_ratio']
        else:
            df['debt_ratio_score'] = np.nan
        if 'yoy_ni' in df.columns:
            df['yoy_ni_score'] = df['yoy_ni']
        else:
            df['yoy_ni_score'] = np.nan

        for col in ['momentum_score', 'value_score', 'volume_score',
                    'turnover_score', 'reversal_score', 'amihud_score', 'pb_score', 'pe_score',
                    'roe_score', 'gp_margin_score', 'debt_ratio_score', 'yoy_ni_score']:
            if col not in df.columns:
                continue
            # std > 1e-12 才归一化: 近常数列(如长期不变的 pb)因浮点噪声 std≈1e-16,
            # 若按 std>0 判断会被误归一化并用 1e-16 做分母放大成野值
            if df[col].std() > 1e-12:
                df[col] = (df[col] - df[col].mean()) / df[col].std()
                df[col] = df[col].clip(-2, 2) / 2

        df['alpha_score'] = (
            df['momentum_score'] * self.params['momentum_weight'] +
            df['value_score'] * self.params['value_weight'] +
            df['volatility_score'] * self.params['volatility_weight'] +
            df['volume_score'] * self.params['volume_weight'] +
            df['turnover_score'].fillna(0) * self.params['turnover_weight'] +
            df['reversal_score'].fillna(0) * self.params['reversal_weight'] +
            df['amihud_score'].fillna(0) * self.params['amihud_weight'] +
            df['pb_score'].fillna(0) * self.params['pb_weight'] +
            df['pe_score'].fillna(0) * self.params['pe_weight'] +
            df['roe_score'].fillna(0) * self.params['roe_weight'] +
            df['gp_margin_score'].fillna(0) * self.params['gp_margin_weight'] +
            df['debt_ratio_score'].fillna(0) * self.params['debt_ratio_weight'] +
            df['yoy_ni_score'].fillna(0) * self.params['yoy_ni_weight']
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

        # signal 语义统一为"想持有什么方向", 不再有同值双义:
        #   1 = 想多头(BUY+CLOSE_SHORT)  -1 = 想空头(CLOSE_LONG+OPEN_SHORT)
        #   2 = 平多(止盈/退出)          3 = 平空
        #   0 = 观望
        df['signal'] = 0

        # 上升趋势低波: 突破买入, 跌破均线仅平多(不在上升趋势里做空)
        mask = (df['regime'] == 'uptrend_low_vol')
        df.loc[mask & (df['close'] > df['sma_20']) & (df['close'].shift(1) <= df['sma_20'].shift(1)), 'signal'] = 1
        df.loc[mask & (df['close'] < df['sma_20']), 'signal'] = 2

        # 上升趋势高波: 站上 SMA50 才持多
        mask = (df['regime'] == 'uptrend_high_vol')
        df.loc[mask & (df['close'] > df['sma_50']), 'signal'] = 1
        df.loc[mask & (df['close'] < df['sma_50']), 'signal'] = 2

        # 震荡: 下轨买入、上轨做空(典型均值回归)
        mask = (df['regime'] == 'sideways')
        df.loc[mask & (df['close'] < df['sma_20'] * 0.98), 'signal'] = 1
        df.loc[mask & (df['close'] > df['sma_20'] * 1.02), 'signal'] = -1

        # 下跌趋势低波: 弱势做空(破位), 反弹仅平空
        mask = (df['regime'] == 'downtrend_low_vol')
        df.loc[mask & (df['close'] < df['sma_20'] * 0.98), 'signal'] = -1
        df.loc[mask & (df['close'] > df['sma_20'] * 1.02), 'signal'] = 3

        # 下跌趋势高波: 反手做空(原逻辑只平仓不反手, 不闭环; 现在做空吃跌)
        # 反弹过 SMA50 则平空退出(避免 z 字下跌里一直持有空头挨反弹)
        mask = (df['regime'] == 'downtrend_high_vol')
        df.loc[mask, 'signal'] = -1
        df.loc[mask & (df['close'] > df['sma_50']), 'signal'] = 3

        return df

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """按 signal 值路由动作: 1=多头, -1=空头, 2=平多, 3=平空, 0=观望。"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.params['regime_lookback']:
                continue

            df = self.calculate_indicators(df)

            if len(df) < 2:
                continue

            current = df.iloc[-1]
            previous = df.iloc[-2]
            conf = min(abs(current['trend']) / 0.05, 1.0)
            meta = {'regime': current['regime']}

            def sig(stype):
                return Signal(timestamp=current.name, symbol=symbol, signal_type=stype,
                              quantity=0, price=current['close'], confidence=conf, metadata=meta)

            cur, prev = current['signal'], previous['signal']

            if cur == 1 and prev != 1:
                signals.append(sig(SignalType.BUY))
                signals.append(sig(SignalType.CLOSE_SHORT))
            elif cur == -1 and prev != -1:
                signals.append(sig(SignalType.CLOSE_LONG))
                signals.append(sig(SignalType.OPEN_SHORT))
            elif cur == 2 and prev != 2:
                signals.append(sig(SignalType.CLOSE_LONG))
            elif cur == 3 and prev != 3:
                signals.append(sig(SignalType.CLOSE_SHORT))
            elif cur == 0 and prev != 0:
                if prev == 1:
                    signals.append(sig(SignalType.CLOSE_LONG))
                elif prev == -1:
                    signals.append(sig(SignalType.CLOSE_SHORT))

        return signals
