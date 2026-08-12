"""Abstract data source interface and shared utilities.

Defines the `DataSource` contract that every backend (akshare, tushare,
baostock, yfinance, ...) implements, plus source-independent helpers such
as multi-symbol fetching, caching and implied-volatility calculation.
The concrete data libraries are imported lazily inside each adapter so that
``import qcode`` works without any data backend installed.
"""
import os
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class DataSource(ABC):
    """Abstract base for all market data sources.

    Subclasses implement real-data fetching for a specific backend.
    Sample/synthetic data is handled by `SampleDataSource` so that no backend
    library is required for offline testing.

    The canonical schema returned by `get_stock_daily` is a DataFrame indexed
    by a DatetimeIndex named 'date' with at least the columns:
    open, high, low, close, volume. Extra columns (amount, pct_change,
    turnover, symbol) are added where available.
    """

    def __init__(self, cache_data: bool = True, use_sample_data: bool = False,
                 market_regime: str = 'bear', disk_cache_dir: str = '.data_cache'):
        self.cache_data = cache_data
        self.use_sample_data = use_sample_data
        self.market_regime = market_regime
        self.disk_cache_dir = disk_cache_dir
        self._cache: Dict[str, pd.DataFrame] = {}

    # ---- abstract: the only method every backend MUST implement ----
    @abstractmethod
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch daily OHLCV for a symbol. Returns empty DataFrame on failure."""
        ...

    # ---- optional methods: backends override what they support ----
    def get_stock_list(self) -> pd.DataFrame:
        """Get list of tradable instruments. Default: empty."""
        return pd.DataFrame()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch index daily data. Default: empty."""
        return pd.DataFrame()

    def get_option_chain(self, underlying: str, date: Optional[str] = None) -> pd.DataFrame:
        """Fetch option chain data. Default: empty."""
        return pd.DataFrame()

    def get_futures_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch futures daily data. Default: empty."""
        return pd.DataFrame()

    # ---- shared concrete implementations ----
    def get_multiple_stocks(self, symbols: List[str], start_date: str,
                             end_date: str) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols, skipping empty results."""
        data = {}
        for symbol in symbols:
            df = self.get_stock_daily(symbol, start_date, end_date)
            if df is not None and not df.empty:
                data[symbol] = df
        return data

    def calculate_implied_volatility(self, option_price: float, spot: float,
                                     strike: float, time_to_maturity: float,
                                     risk_free_rate: float = 0.03,
                                     option_type: str = 'call') -> float:
        """Implied volatility via Black-Scholes (Brent's method). Source-independent."""
        from scipy.stats import norm
        from scipy.optimize import brentq

        def black_scholes(sigma: float) -> float:
            d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * sigma**2) * time_to_maturity) / \
                 (sigma * np.sqrt(time_to_maturity))
            d2 = d1 - sigma * np.sqrt(time_to_maturity)
            if option_type == 'call':
                price = spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_maturity) * norm.cdf(d2)
            else:
                price = strike * np.exp(-risk_free_rate * time_to_maturity) * norm.cdf(-d2) - spot * norm.cdf(-d1)
            return price - option_price

        try:
            return brentq(black_scholes, 0.01, 5.0)
        except Exception:
            return np.nan

    # ---- cache helpers (memory + disk) ----
    def _disk_path(self, key: str) -> str:
        """Sanitize cache key into a disk path under disk_cache_dir."""
        safe = ''.join(c if c.isalnum() else '_' for c in key)
        os.makedirs(self.disk_cache_dir, exist_ok=True)
        return os.path.join(self.disk_cache_dir, f"{safe}.csv")

    def _cached(self, key: str) -> Optional[pd.DataFrame]:
        if not self.cache_data:
            return None
        # memory
        if key in self._cache:
            return self._cache[key].copy()
        # disk
        path = self._disk_path(key)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, parse_dates=['date'], index_col='date')
                self._cache[key] = df.copy()
                return df
            except Exception:
                pass
        return None

    def _set_cache(self, key: str, df: pd.DataFrame):
        if not self.cache_data:
            return
        self._cache[key] = df.copy()
        try:
            path = self._disk_path(key)
            df.to_csv(path)
        except Exception:
            pass

    def clear_cache(self):
        """Clear in-memory cache (disk cache kept)."""
        self._cache.clear()

    def clear_disk_cache(self):
        """Clear disk cache files."""
        import shutil
        if os.path.isdir(self.disk_cache_dir):
            shutil.rmtree(self.disk_cache_dir)
        self._cache.clear()
