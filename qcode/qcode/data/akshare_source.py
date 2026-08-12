"""A-share data source backed by akshare.

akshare is imported lazily inside each method, so this module can be imported
without akshare installed. Network calls are retried with proxy suppression.
"""
import os
import time
import warnings
from functools import wraps
from typing import Optional

import pandas as pd

from qcode.data.base import DataSource

warnings.filterwarnings('ignore')


def _suppress_proxy_for_akshare():
    """Remove proxy env vars so akshare/requests can connect directly."""
    saved = {}
    for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)
    return saved


def _restore_proxy(saved):
    """Restore proxy env vars."""
    os.environ.update(saved)


def retry_on_connection_error(max_retries=5, delay=5):
    """Decorator: retry on connection errors, suppressing proxy env during call."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            saved = _suppress_proxy_for_akshare()
            try:
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        error_str = str(e)
                        if any(x in error_str for x in
                               ['Connection', 'Remote', 'Proxy', 'timeout', 'read timed out']):
                            if attempt < max_retries - 1:
                                wait_time = delay * (attempt + 1)
                                print(f"Connection error, retrying in {wait_time}s... "
                                      f"(attempt {attempt+1}/{max_retries})")
                                time.sleep(wait_time)
                            else:
                                print(f"Failed after {max_retries} attempts: {e}")
                                raise
                        else:
                            raise
            finally:
                _restore_proxy(saved)
            return None
        return wrapper
    return decorator


class AkshareDataSource(DataSource):
    """Fetch A-share (stocks, index, options, futures) data via akshare."""

    def __init__(self, cache_data: bool = True, market_regime: str = 'bear'):
        super().__init__(cache_data=cache_data, use_sample_data=False,
                         market_regime=market_regime)

    @retry_on_connection_error(max_retries=3, delay=2)
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"stock_daily_{symbol}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import akshare as ak
        except ImportError as e:
            print(f"[akshare] not installed: {e}. Install with: pip install akshare")
            return pd.DataFrame()

        try:
            sd = start_date.replace('-', '')
            ed = end_date.replace('-', '')
            df = ak.stock_zh_a_hist(symbol=symbol, start_date=sd,
                                    end_date=ed, adjust="qfq")
            df['date'] = pd.to_datetime(df['日期'])
            df = df.rename(columns={
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })
            df['symbol'] = symbol
            df = df.set_index('date')
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as e:
            print(f"[akshare] not installed: {e}. Install with: pip install akshare")
            return pd.DataFrame()
        try:
            return ak.stock_zh_a_spot_em()
        except Exception as e:
            print(f"Error fetching stock list: {e}")
            return pd.DataFrame()

    @retry_on_connection_error(max_retries=3, delay=2)
    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"index_daily_{index_code}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import akshare as ak
        except ImportError as e:
            print(f"[akshare] not installed: {e}. Install with: pip install akshare")
            return pd.DataFrame()

        try:
            df = ak.stock_zh_index_daily(symbol=index_code)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            sd = pd.to_datetime(start_date.replace('-', ''))
            ed = pd.to_datetime(end_date.replace('-', ''))
            df = df[(df.index >= sd) & (df.index <= ed)]
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching index data for {index_code}: {e}")
            return pd.DataFrame()

    def get_option_chain(self, underlying: str, date: Optional[str] = None) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as e:
            print(f"[akshare] not installed: {e}. Install with: pip install akshare")
            return pd.DataFrame()
        try:
            return ak.option_finance_board(symbol=underlying)
        except Exception as e:
            print(f"Error fetching option chain: {e}")
            return pd.DataFrame()

    @retry_on_connection_error(max_retries=3, delay=2)
    def get_futures_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"futures_daily_{symbol}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import akshare as ak
        except ImportError as e:
            print(f"[akshare] not installed: {e}. Install with: pip install akshare")
            return pd.DataFrame()

        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            sd = pd.to_datetime(start_date.replace('-', ''))
            ed = pd.to_datetime(end_date.replace('-', ''))
            df = df[(df.index >= sd) & (df.index <= ed)]
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching futures data for {symbol}: {e}")
            return pd.DataFrame()
