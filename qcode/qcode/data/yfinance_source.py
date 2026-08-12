"""US/global market data source backed by yfinance.

yfinance is imported lazily. Suitable for US tickers (e.g. AAPL, NVDA, TSLA)
and a range of international instruments. This adapter supersedes the legacy
`USDataFetcher`.
"""
from typing import Optional, List, Dict

import pandas as pd
import numpy as np

from qcode.data.base import DataSource


class YfinanceDataSource(DataSource):
    """Fetch US/global stock data via yfinance."""

    def __init__(self, cache_data: bool = True, market_regime: str = 'bear'):
        super().__init__(cache_data=cache_data, use_sample_data=False,
                         market_regime=market_regime)

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_key = f"stock_daily_{symbol}_{start_date}_{end_date}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import yfinance as yf
        except ImportError as e:
            print(f"[yfinance] not installed: {e}. Install with: pip install yfinance")
            return pd.DataFrame()

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            if df.empty:
                print(f"No data found for {symbol}")
                return pd.DataFrame()
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            df['symbol'] = symbol
            df['pct_change'] = df['close'].pct_change() * 100
            df['amplitude'] = (df['high'] - df['low']) / df['low'].replace(0, np.nan) * 100
            df.index.name = 'date'
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_options_chain(self, symbol: str) -> Dict:
        """Fetch options chain for a US stock (first expiration).

        Returns dict with 'calls', 'puts', 'expiration', or empty dict.
        """
        try:
            import yfinance as yf
        except ImportError as e:
            print(f"[yfinance] not installed: {e}. Install with: pip install yfinance")
            return {}
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                print(f"No options available for {symbol}")
                return {}
            exp_date = expirations[0]
            opt_chain = ticker.option_chain(exp_date)
            return {
                'calls': opt_chain.calls,
                'puts': opt_chain.puts,
                'expiration': exp_date
            }
        except Exception as e:
            print(f"Error fetching options for {symbol}: {e}")
            return {}

    def get_option_chain(self, underlying: str, date: Optional[str] = None) -> pd.DataFrame:
        """Return a stacked calls+puts DataFrame (type column distinguishes)."""
        chain = self.get_options_chain(underlying)
        if not chain:
            return pd.DataFrame()
        calls = chain['calls'].copy()
        calls['option_type'] = 'call'
        puts = chain['puts'].copy()
        puts['option_type'] = 'put'
        return pd.concat([calls, puts], ignore_index=True)

    def get_current_price(self, symbol: str) -> float:
        """Get current/last price for a US ticker."""
        try:
            import yfinance as yf
        except ImportError as e:
            print(f"[yfinance] not installed: {e}. Install with: pip install yfinance")
            return 0.0
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d')
            if not data.empty:
                return float(data['Close'].iloc[-1])
            return 0.0
        except Exception as e:
            print(f"Error fetching current price for {symbol}: {e}")
            return 0.0

    def calculate_implied_volatility(self, symbol_or_price, spot=None, strike=None,
                                     time_to_maturity=None, risk_free_rate=0.03,
                                     option_type='call') -> float:
        """Overload: (symbol) -> historical vol proxy; or (price, spot, strike, T, r, type) -> BS IV."""
        if spot is None:
            # historical volatility proxy for a symbol
            try:
                end = pd.Timestamp.now()
                start = end - pd.Timedelta(days=90)
                df = self.get_stock_daily(
                    symbol_or_price, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
                )
                if df.empty:
                    return 0.3
                returns = df['close'].pct_change().dropna()
                return float(returns.std() * np.sqrt(252))
            except Exception:
                return 0.3
        return super().calculate_implied_volatility(
            symbol_or_price, spot, strike, time_to_maturity, risk_free_rate, option_type
        )
