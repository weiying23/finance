"""Data module: pluggable market data sources.

Select a backend via config.DATA_CONFIG['data_source']
('akshare' | 'tushare' | 'baostock' | 'yfinance'). Use `create_data_source`
directly, or the backward-compatible `DataFetcher` factory.
"""
from qcode.data.base import DataSource
from qcode.data.factory import create_data_source, DataFetcher
from qcode.data.sample_source import SampleDataSource
from qcode.data.akshare_source import AkshareDataSource
from qcode.data.tushare_source import TushareDataSource
from qcode.data.baostock_source import BaostockDataSource
from qcode.data.yfinance_source import YfinanceDataSource

__all__ = [
    "DataSource",
    "DataFetcher",
    "create_data_source",
    "SampleDataSource",
    "AkshareDataSource",
    "TushareDataSource",
    "BaostockDataSource",
    "YfinanceDataSource",
]
