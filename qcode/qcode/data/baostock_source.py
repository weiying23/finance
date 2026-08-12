"""A-share data source backed by baostock.

baostock is free, requires no registration/token, and provides daily K-line
and financial data. It is a good zero-friction alternative to akshare, with a
narrower instrument scope (mainly A-share stocks and indices).
"""
from typing import Optional

import pandas as pd
import numpy as np

from qcode.data.base import DataSource


def _to_bs_code(symbol: str) -> str:
    """Convert a 6-digit A-share code to baostock code (e.g. 600519 -> sh.600519)."""
    sym = symbol.replace('sh.', '').replace('sz.', '')
    prefix = 'sh' if sym[:1] in ('6', '9') else 'sz'
    return f"{prefix}.{sym}"


def _normalize_date(date_str: str) -> str:
    """Normalize to YYYY-MM-DD (baostock requirement)."""
    return date_str.replace('-', '') if '-' not in date_str else date_str


class BaostockDataSource(DataSource):
    """Fetch A-share data via baostock (no token required)."""

    def __init__(self, cache_data: bool = True, market_regime: str = 'bear'):
        super().__init__(cache_data=cache_data, use_sample_data=False,
                         market_regime=market_regime)

    @staticmethod
    def _login():
        import baostock as bs
        return bs.login()

    @staticmethod
    def _logout():
        import baostock as bs
        try:
            bs.logout()
        except Exception:
            pass

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"stock_daily_{symbol}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import baostock as bs
        except ImportError as e:
            print(f"[baostock] not installed: {e}. Install with: pip install baostock")
            return pd.DataFrame()

        try:
            self._login()
            code = _to_bs_code(symbol)
            sd = _normalize_date(start_date)
            ed = _normalize_date(end_date)
            rs = bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume,amount,turn,pctChg",
                start_date=sd, end_date=ed, frequency='d', adjustflag='2'
            )
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=rs.fields)
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.rename(columns={'turn': 'turnover', 'pctChg': 'pct_change'})
            df['symbol'] = symbol
            df['change'] = df['close'].diff()
            df['amplitude'] = np.nan
            df = df.set_index('date').sort_index()
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()
        finally:
            self._logout()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"index_daily_{index_code}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import baostock as bs
        except ImportError as e:
            print(f"[baostock] not installed: {e}. Install with: pip install baostock")
            return pd.DataFrame()

        try:
            self._login()
            s = index_code.strip().lower()
            if s.startswith('sh') or s.startswith('sz'):
                code = f"{s[:2]}.{s[2:]}"
            else:
                code = _to_bs_code(index_code)
            sd = _normalize_date(start_date)
            ed = _normalize_date(end_date)
            rs = bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume,amount",
                start_date=sd, end_date=ed, frequency='d'
            )
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=rs.fields)
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.set_index('date').sort_index()
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching index data for {index_code}: {e}")
            return pd.DataFrame()
        finally:
            self._logout()

    def get_stock_list(self) -> pd.DataFrame:
        """baostock has no single full A-share list endpoint; returns empty."""
        return pd.DataFrame()

    def get_option_chain(self, underlying: str, date: Optional[str] = None) -> pd.DataFrame:
        return pd.DataFrame()

    def get_futures_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()
