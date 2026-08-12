"""A-share data source backed by tushare Pro.

tushare is imported lazily. Requires a Pro token (free registration), passed
via constructor, DATA_CONFIG['tushare_token'], or env TUSHARE_TOKEN. Provides a
stable structured API, making it the recommended upgrade from akshare for
serious backtesting.
"""
import os
from typing import Optional

import pandas as pd
import numpy as np

from qcode.data.base import DataSource


def _to_ts_code(symbol: str) -> str:
    """Convert a 6-digit A-share code to tushare ts_code (e.g. 600519 -> 600519.SH)."""
    sym = symbol.replace('.SH', '').replace('.SZ', '')
    suffix = 'SH' if sym[:1] in ('6', '9') else 'SZ'
    return f"{sym}.{suffix}"


def _normalize_index_code(index_code: str) -> str:
    """Best-effort normalization of an index code to tushare ts_code.

    Accepts 'sh000001', '000001.SH', or '000001' and returns tushare form.
    """
    s = index_code.strip().lower()
    if s.startswith('sh'):
        return f"{s[2:]}.SH"
    if s.startswith('sz'):
        return f"{s[2:]}.SZ"
    if '.' in index_code:
        return index_code.upper()
    return _to_ts_code(index_code)


class TushareDataSource(DataSource):
    """Fetch A-share data via tushare Pro API."""

    def __init__(self, cache_data: bool = True, token: str = '',
                 market_regime: str = 'bear'):
        super().__init__(cache_data=cache_data, use_sample_data=False,
                         market_regime=market_regime)
        self.token = token or os.environ.get('TUSHARE_TOKEN', '')

    def _pro(self):
        """Return an authenticated tushare pro client, or raise."""
        if not self.token:
            raise RuntimeError(
                "Tushare token missing. Set DATA_CONFIG['tushare_token'] or env TUSHARE_TOKEN."
            )
        try:
            import tushare as ts
        except ImportError as e:
            raise RuntimeError(f"tushare not installed: {e}. Install with: pip install tushare")
        return ts.pro_api(self.token)

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"stock_daily_{symbol}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            pro = self._pro()
        except RuntimeError as e:
            print(f"[tushare] {e}")
            return pd.DataFrame()

        try:
            ts_code = _to_ts_code(symbol)
            sd = start_date.replace('-', '')
            ed = end_date.replace('-', '')
            df = pro.daily(ts_code=ts_code, start_date=sd, end_date=ed)
            if df is None or df.empty:
                return pd.DataFrame()
            df['date'] = pd.to_datetime(df['trade_date'])
            df = df.rename(columns={
                'vol': 'volume',
                'pct_chg': 'pct_change',
            })
            df['symbol'] = symbol
            if 'turnover' not in df.columns:
                df['turnover'] = np.nan
            df = df.set_index('date').sort_index()
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        try:
            pro = self._pro()
        except RuntimeError as e:
            print(f"[tushare] {e}")
            return pd.DataFrame()
        try:
            return pro.stock_basic(exchange='', list_status='L')
        except Exception as e:
            print(f"Error fetching stock list: {e}")
            return pd.DataFrame()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"index_daily_{index_code}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            pro = self._pro()
        except RuntimeError as e:
            print(f"[tushare] {e}")
            return pd.DataFrame()
        try:
            ts_code = _normalize_index_code(index_code)
            sd = start_date.replace('-', '')
            ed = end_date.replace('-', '')
            df = pro.index_daily(ts_code=ts_code, start_date=sd, end_date=ed)
            if df is None or df.empty:
                return pd.DataFrame()
            df['date'] = pd.to_datetime(df['trade_date'])
            df = df.rename(columns={'vol': 'volume', 'pct_chg': 'pct_change'})
            df = df.set_index('date').sort_index()
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching index data for {index_code}: {e}")
            return pd.DataFrame()

    def get_futures_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Best-effort futures daily via tushare fut_daily (may need higher points)."""
        cache_key = f"futures_daily_{symbol}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            pro = self._pro()
        except RuntimeError as e:
            print(f"[tushare] {e}")
            return pd.DataFrame()
        try:
            sd = start_date.replace('-', '')
            ed = end_date.replace('-', '')
            df = pro.fut_daily(ts_code=symbol, start_date=sd, end_date=ed)
            if df is None or df.empty:
                return pd.DataFrame()
            df['date'] = pd.to_datetime(df['trade_date'])
            df = df.rename(columns={'vol': 'volume', 'pct_chg': 'pct_change'})
            df = df.set_index('date').sort_index()
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching futures data for {symbol}: {e}")
            return pd.DataFrame()

    def get_option_chain(self, underlying: str, date: Optional[str] = None) -> pd.DataFrame:
        """Best-effort options via tushare opt_daily (may need higher points)."""
        print("[tushare] option chain not fully supported on default points; "
              "use opt_daily with sufficient quota.")
        return pd.DataFrame()
