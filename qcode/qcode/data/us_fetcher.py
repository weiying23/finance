"""Data fetcher for US stocks using yfinance"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict
import warnings
warnings.filterwarnings('ignore')


class USDataFetcher:
    """Fetch US stock data using yfinance"""

    def __init__(self, cache_data: bool = True):
        self.cache_data = cache_data
        self._cache = {}

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch daily stock data for US stocks

        Args:
            symbol: Stock ticker (e.g., 'NVDA', 'AAPL', 'TSLA')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"stock_daily_{symbol}_{start_date}_{end_date}"
        if self.cache_data and cache_key in self._cache:
            return self._cache[cache_key].copy()

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                print(f"No data found for {symbol}")
                return pd.DataFrame()
            
            # Standardize column names
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            df['symbol'] = symbol
            df.index.name = 'date'
            
            # Calculate additional fields
            df['pct_change'] = df['close'].pct_change() * 100
            df['amplitude'] = (df['high'] - df['low']) / df['low'] * 100
            
            if self.cache_data:
                self._cache[cache_key] = df.copy()
            
            return df
        
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_multiple_stocks(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple US stocks

        Args:
            symbols: List of stock tickers
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        for symbol in symbols:
            print(f"Fetching {symbol}...")
            df = self.get_stock_daily(symbol, start_date, end_date)
            if not df.empty:
                data[symbol] = df
        return data

    def get_options_chain(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch options chain for US stock

        Args:
            symbol: Stock ticker

        Returns:
            Dictionary with 'calls' and 'puts' DataFrames
        """
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            
            if not expirations:
                print(f"No options available for {symbol}")
                return {}
            
            # Get first expiration date
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

    def get_current_price(self, symbol: str) -> float:
        """Get current stock price

        Args:
            symbol: Stock ticker

        Returns:
            Current price
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d')
            if not data.empty:
                return data['Close'].iloc[-1]
            return 0.0
        except Exception as e:
            print(f"Error fetching current price for {symbol}: {e}")
            return 0.0

    def calculate_implied_volatility(self, symbol: str) -> float:
        """Calculate historical volatility as proxy for IV

        Args:
            symbol: Stock ticker

        Returns:
            Annualized volatility
        """
        try:
            df = self.get_stock_daily(symbol, 
                                     (pd.Timestamp.now() - pd.Timedelta(days=90)).strftime('%Y-%m-%d'),
                                     pd.Timestamp.now().strftime('%Y-%m-%d'))
            if df.empty:
                return 0.3  # Default 30% volatility
            
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)
            return volatility
        
        except Exception as e:
            print(f"Error calculating volatility for {symbol}: {e}")
            return 0.3

    def clear_cache(self):
        """Clear cached data"""
        self._cache.clear()
