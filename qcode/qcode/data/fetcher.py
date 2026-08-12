"""Backward-compatibility shim.

The real implementations live in qcode.data.base / *.source / factory.
This module keeps `from qcode.data.fetcher import DataFetcher` working for
existing call sites (qcode/__init__.py, qcode/backtest/engine.py, examples/).
"""
from qcode.data.factory import create_data_source, DataFetcher
from qcode.data.base import DataSource

__all__ = ["DataFetcher", "create_data_source", "DataSource"]
