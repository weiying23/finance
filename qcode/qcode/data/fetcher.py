"""Data fetcher using akshare library"""
import akshare as ak
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Union
import warnings
import time
from functools import wraps
import requests as _requests
warnings.filterwarnings('ignore')


def _suppress_proxy_for_akshare():
    """Remove proxy env vars so akshare/requests can connect directly"""
    saved = {}
    for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)
    return saved


def _restore_proxy(saved):
    """Restore proxy env vars"""
    os.environ.update(saved)




def retry_on_connection_error(max_retries=5, delay=5):
    """Decorator to retry on connection errors, suppressing proxy env during call"""
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
                        if any(x in error_str for x in ['Connection', 'Remote', 'Proxy', 'timeout', 'read timed out']):
                            if attempt < max_retries - 1:
                                wait_time = delay * (attempt + 1)
                                print(f"Connection error, retrying in {wait_time}s... (attempt {attempt+1}/{max_retries})")
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

class DataFetcher:
    """Fetch market data from akshare for stocks, options, and derivatives"""

    def __init__(self, cache_data: bool = True, use_sample_data: bool = False, market_regime: str = 'bear'):
        self.cache_data = cache_data
        self.use_sample_data = use_sample_data
        self.market_regime = market_regime
        self._cache = {}

    @retry_on_connection_error(max_retries=3, delay=2)
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch daily stock data

        Args:
            symbol: Stock code (e.g., '000001' for SZ, '600000' for SH)
            start_date: Start date (YYYYMMDD or YYYY-MM-DD)
            end_date: End date (YYYYMMDD or YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """

        # Use sample data for offline testing
        if self.use_sample_data:
            return self._generate_sample_data(symbol, start_date, end_date, self.market_regime)
        
        cache_key = f"stock_daily_{symbol}_{start_date}_{end_date}"
        if self.cache_data and cache_key in self._cache:
            return self._cache[cache_key].copy()

        try:
            start_date = start_date.replace('-', '')
            end_date = end_date.replace('-', '')
            df = ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, 
                                     end_date=end_date, adjust="qfq")
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
            
            if self.cache_data:
                self._cache[cache_key] = df.copy()
            
            return df
        except Exception as e:
            print(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()

    def _generate_sample_data(self, symbol: str, start_date: str, end_date: str,
                              market_regime: str = 'bear') -> pd.DataFrame:
        """Generate realistic sample data for offline testing

        Args:
            symbol: Stock code
            start_date: Start date string
            end_date: End date string
            market_regime: 'bear' (all stocks drop), 'bull' (all stocks rise),
                           'sideways' (mixed/flat), or 'mixed' (some up some down)
        """
        start = pd.to_datetime(start_date.replace('-', ''))
        end = pd.to_datetime(end_date.replace('-', ''))
        dates = pd.date_range(start, end, freq='B')

        rng = np.random.RandomState(int(symbol) if symbol.isdigit() else 42)
        n = len(dates)

        base_price = 1500 if symbol == '600519' else 100

        returns = np.zeros(n)

        if market_regime == 'bear':
            for i in range(n):
                if rng.random() < 0.1:
                    returns[i] = rng.normal(-0.02, 0.03)
                else:
                    returns[i] = rng.normal(-0.001, 0.015)

        elif market_regime == 'bull':
            for i in range(n):
                if rng.random() < 0.10:
                    returns[i] = rng.normal(0.004, 0.020)
                else:
                    returns[i] = rng.normal(0.001, 0.015)

        elif market_regime == 'sideways':
            for i in range(n):
                if rng.random() < 0.3:
                    returns[i] = rng.normal(-0.001, 0.025)
                else:
                    returns[i] = rng.normal(0.0003, 0.02)

        elif market_regime == 'mixed':
            stock_num = int(symbol) if symbol.isdigit() else 0
            group = stock_num % 3
            if group == 0:
                for i in range(n):
                    returns[i] = rng.normal(0.002, 0.015)
            elif group == 1:
                for i in range(n):
                    returns[i] = rng.normal(-0.001, 0.015)
            else:
                for i in range(n):
                    returns[i] = rng.normal(0.0003, 0.02)
        else:
            returns = rng.normal(0.0005, 0.02, n)

        prices = base_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            'open': prices * (1 + rng.uniform(-0.01, 0.01, n)),
            'high': prices * (1 + np.abs(rng.uniform(0, 0.02, n))),
            'low': prices * (1 - np.abs(rng.uniform(0, 0.02, n))),
            'close': prices,
            'volume': rng.randint(1000000, 10000000, n),
            'amount': prices * rng.randint(1000000, 10000000, n),
            'amplitude': rng.uniform(1, 5, n),
            'pct_change': returns * 100,
            'change': returns * prices,
            'turnover': rng.uniform(0.1, 5, n),
            'symbol': symbol
        }, index=dates)

        return df

    def get_stock_list(self) -> pd.DataFrame:
        """Get list of all A-share stocks"""
        try:
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            print(f"Error fetching stock list: {e}")
            return pd.DataFrame()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch index data

        Args:
            index_code: Index code (e.g., 'sh000001' for SSE Composite)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with index OHLCV data
        """
        cache_key = f"index_daily_{index_code}_{start_date}_{end_date}"
        if self.cache_data and cache_key in self._cache:
            return self._cache[cache_key].copy()

        try:
            start_date = start_date.replace('-', '')
            end_date = end_date.replace('-', '')
            df = ak.stock_zh_index_daily(symbol=index_code)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            
            if self.cache_data:
                self._cache[cache_key] = df.copy()
            
            return df
        except Exception as e:
            print(f"Error fetching index data for {index_code}: {e}")
            return pd.DataFrame()

    def get_option_chain(self, underlying: str, date: Optional[str] = None) -> pd.DataFrame:
        """Fetch option chain data

        Args:
            underlying: Underlying asset code
            date: Trading date (optional)

        Returns:
            DataFrame with option chain data
        """
        try:
            df = ak.option_finance_board(symbol=underlying)
            return df
        except Exception as e:
            print(f"Error fetching option chain: {e}")
            return pd.DataFrame()

    def get_futures_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch futures daily data

        Args:
            symbol: Futures code
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with futures OHLCV data
        """
        cache_key = f"futures_daily_{symbol}_{start_date}_{end_date}"
        if self.cache_data and cache_key in self._cache:
            return self._cache[cache_key].copy()

        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            
            if self.cache_data:
                self._cache[cache_key] = df.copy()
            
            return df
        except Exception as e:
            print(f"Error fetching futures data for {symbol}: {e}")
            return pd.DataFrame()

    def get_multiple_stocks(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple stocks

        Args:
            symbols: List of stock codes
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        for symbol in symbols:
            df = self.get_stock_daily(symbol, start_date, end_date)
            if not df.empty:
                data[symbol] = df
        return data

    def calculate_implied_volatility(self, option_price: float, spot: float, strike: float,
                                    time_to_maturity: float, risk_free_rate: float = 0.03,
                                    option_type: str = 'call') -> float:
        """Calculate implied volatility using Black-Scholes (simplified Newton-Raphson)

        Args:
            option_price: Market price of option
            spot: Current price of underlying
            strike: Strike price
            time_to_maturity: Time to maturity in years
            risk_free_rate: Risk-free rate
            option_type: 'call' or 'put'

        Returns:
            Implied volatility
        """
        from scipy.stats import norm
        from scipy.optimize import brentq

        def black_scholes(sigma):
            d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * sigma**2) * time_to_maturity) / (sigma * np.sqrt(time_to_maturity))
            d2 = d1 - sigma * np.sqrt(time_to_maturity)
            
            if option_type == 'call':
                price = spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_maturity) * norm.cdf(d2)
            else:
                price = strike * np.exp(-risk_free_rate * time_to_maturity) * norm.cdf(-d2) - spot * norm.cdf(-d1)
            
            return price - option_price

        try:
            iv = brentq(black_scholes, 0.01, 5.0)
            return iv
        except:
            return np.nan

    def clear_cache(self):
        """Clear cached data"""
        self._cache.clear()
