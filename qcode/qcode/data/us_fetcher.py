"""Backward-compatibility shim for US stock data.

The legacy `USDataFetcher` is now `YfinanceDataSource`. This module preserves
the old import path `from qcode.data.us_fetcher import USDataFetcher`.
"""
from qcode.data.yfinance_source import YfinanceDataSource

# Legacy alias
USDataFetcher = YfinanceDataSource

__all__ = ["USDataFetcher", "YfinanceDataSource"]
