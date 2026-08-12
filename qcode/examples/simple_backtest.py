"""Simple backtest example using momentum strategy"""
import sys
sys.path.insert(0, '..')

from qcode import DataFetcher, BacktestEngine
from qcode.strategies.momentum import MomentumStrategy


def main():
    print("="*60)
    print("QCode - Simple Momentum Strategy Backtest")
    print("="*60 + "\n")
    
    symbols = ['600519', '000858', '600036', '601318', '000333']
    start_date = '2022-01-01'
    end_date = '2023-12-31'
    
    engine = BacktestEngine(
        initial_capital=1000000,
        commission=0.0003,
        slippage=0.0001,
        enable_delta_hedging=False
    )
    
    momentum_strategy = MomentumStrategy(
        name="Momentum_10_30",
        fast_period=10,
        slow_period=30,
        rsi_period=14
    )
    
    engine.add_strategy(momentum_strategy)
    
    engine.load_data(symbols, start_date, end_date)
    
    results = engine.run()
    
    engine.print_summary()
    
    engine.plot_results()
    
    print("\nTrade History:")
    trade_df = engine.get_trade_history()
    if not trade_df.empty:
        print(trade_df.tail(10))
    else:
        print("No trades executed")


if __name__ == "__main__":
    main()
