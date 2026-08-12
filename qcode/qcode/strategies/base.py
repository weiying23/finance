"""
基础策略类和信号定义模块
提供交易策略的抽象基类、信号枚举类型和数据类，
以及常用的技术指标计算工具方法。
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np


class SignalType(Enum):
    """交易信号类型枚举，定义所有可能的操作指令"""
    BUY = "buy"                # 买入（开多）
    SELL = "sell"              # 卖出（仅用于平多仓）
    HOLD = "hold"              # 持仓不变
    OPEN_SHORT = "open_short"  # 开空仓
    CLOSE_LONG = "close_long"  # 平多仓
    CLOSE_SHORT = "close_short" # 平空仓
    BUY_CALL = "buy_call"      # 买入看涨期权
    SELL_CALL = "sell_call"    # 卖出看涨期权
    BUY_PUT = "buy_put"        # 买入看跌期权
    SELL_PUT = "sell_put"      # 卖出看跌期权


@dataclass
class Signal:
    """
    交易信号数据类，封装一次交易指令的所有信息
    """
    timestamp: pd.Timestamp          # 信号生成的时间戳
    symbol: str                      # 交易品种代码
    signal_type: SignalType          # 信号类型
    quantity: float                  # 交易数量（0表示由外部系统自动计算）
    price: Optional[float] = None    # 信号触发时的价格（可选，用于参考）
    metadata: Optional[Dict[str, Any]] = None  # 附加元数据（如期权行权价、到期日等）
    confidence: float = 1.0           # 信号置信度，范围[0,1]，默认1.0表示最高


class BaseStrategy(ABC):
    """
    所有交易策略的抽象基类
    定义策略必须实现的接口，并提供通用的技术指标计算静态方法
    """

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        """
        初始化策略
        :param name: 策略名称
        :param params: 策略参数字典
        """
        self.name = name
        self.params = params or {}
        self.data = {}
        self.indicators = {}
        self.signals = []
        self._indicator_cache: Dict[str, pd.DataFrame] = {}

    @abstractmethod
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        根据市场数据生成交易信号（抽象方法，子类必须实现）
        :param data: 字典，键为品种代码，值为包含OHLCV数据的DataFrame
        :return: 信号对象列表
        """
        pass

    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标（抽象方法，子类必须实现）
        :param data: 包含OHLCV数据的DataFrame
        :return: 添加了指标列的DataFrame
        """
        pass

    def update_data(self, symbol: str, data: pd.DataFrame):
        """
        更新内部存储的某个品种的市场数据
        :param symbol: 品种代码
        :param data: 新的OHLCV数据
        """
        self.data[symbol] = data

    def get_params(self) -> Dict[str, Any]:
        """获取当前策略参数"""
        return self.params

    def set_params(self, params: Dict[str, Any]):
        """更新策略参数（合并到现有参数字典）"""
        self.params.update(params)

    # ---------- 以下是常用的技术指标静态方法 ----------

    @staticmethod
    def calculate_sma(data: pd.Series, window: int) -> pd.Series:
        """
        计算简单移动平均线 (Simple Moving Average)
        :param data: 输入价格序列（如收盘价）
        :param window: 窗口大小
        :return: SMA序列
        """
        return data.rolling(window=window).mean()

    @staticmethod
    def calculate_ema(data: pd.Series, span: int) -> pd.Series:
        """
        计算指数移动平均线 (Exponential Moving Average)
        :param data: 输入价格序列
        :param span: 平滑窗口（类似周期）
        :return: EMA序列
        """
        return data.ewm(span=span, adjust=False).mean()

    @staticmethod
    def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
        """
        计算相对强弱指标 (Relative Strength Index)
        :param data: 输入价格序列（通常为收盘价）
        :param window: 计算周期，默认14
        :return: RSI序列，取值范围[0,100]
        """
        delta = data.diff()                      # 价格变化
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()  # 平均上涨幅度
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean() # 平均下跌幅度
        rs = gain / loss                          # 相对强弱比率
        rsi = 100 - (100 / (1 + rs))               # RSI公式
        return rsi

    @staticmethod
    def calculate_bollinger_bands(data: pd.Series, window: int = 20, num_std: float = 2.0) -> tuple:
        """
        计算布林带 (Bollinger Bands)
        :param data: 输入价格序列
        :param window: 移动平均窗口，默认20
        :param num_std: 标准差倍数，默认2.0
        :return: 包含三条线的元组 (中轨, 上轨, 下轨)
        """
        middle_band = data.rolling(window=window).mean()          # 中轨：移动平均
        std = data.rolling(window=window).std()                    # 滚动标准差
        upper_band = middle_band + (std * num_std)                 # 上轨
        lower_band = middle_band - (std * num_std)                 # 下轨
        return middle_band, upper_band, lower_band

    @staticmethod
    def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """
        计算MACD指标 (Moving Average Convergence Divergence)
        :param data: 输入价格序列
        :param fast: 快线EMA周期，默认12
        :param slow: 慢线EMA周期，默认26
        :param signal: 信号线EMA周期，默认9
        :return: 包含三个序列的元组 (MACD线, 信号线, 柱状图)
        """
        ema_fast = data.ewm(span=fast, adjust=False).mean()       # 快线EMA
        ema_slow = data.ewm(span=slow, adjust=False).mean()       # 慢线EMA
        macd_line = ema_fast - ema_slow                            # MACD线
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()  # 信号线
        histogram = macd_line - signal_line                        # 柱状图（MACD与信号线之差）
        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """
        计算平均真实波幅 (Average True Range)
        :param high: 最高价序列
        :param low: 最低价序列
        :param close: 收盘价序列
        :param window: 计算周期，默认14
        :return: ATR序列
        """
        high_low = high - low                                      # 当日最高最低差
        high_close = np.abs(high - close.shift())                  # 当日最高与昨日收盘的绝对值
        low_close = np.abs(low - close.shift())                    # 当日最低与昨日收盘的绝对值
        # 取三者最大值作为真实波幅
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=window).mean()             # 真实波幅的移动平均
        return atr