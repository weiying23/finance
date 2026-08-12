"""Strategy module"""
from qcode.strategies.base import BaseStrategy, Signal, SignalType
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.alpha_mining import MultiFactorAlpha, StatisticalArbitrage, MarketRegimeStrategy
from qcode.strategies.pairs_trading import PairsTradingStrategy

__all__ = [
    "BaseStrategy",
    "Signal",
    "SignalType",
    "MomentumStrategy",
    "MeanReversionStrategy",
    "MultiAssetStrategy",
    "MultiFactorAlpha",
    "StatisticalArbitrage",
    "MarketRegimeStrategy",
    "PairsTradingStrategy"
]
