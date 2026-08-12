"""Multi-asset strategy backtest with delta hedging"""
import sys
sys.path.insert(0, '..')

from qcode import DataFetcher, BacktestEngine
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy


def main():
    print("="*60)
    print("QCode - Multi-Asset Strategy Backtest with Delta Hedging")
    print("="*60 + "\n")
    
    symbols = [
        '600519',
        '000858',
        '600036',
        '601318',
        '000333',
        '601012',
        '600887',
        '000568'
    ]
    
    start_date = '2022-01-01'
    end_date = '2023-12-31'
    
    engine = BacktestEngine(
        initial_capital=2000000,
        commission=0.0003,
        slippage=0.0001,
        enable_delta_hedging=True
    )
    
    multi_asset = MultiAssetStrategy(
        name="MultiAsset",
        trend_period=20,
        volatility_period=20,
        hedge_threshold=0.15
    )
    engine.add_strategy(multi_asset)
    
    momentum = MomentumStrategy(
        name="Momentum",
        fast_period=10,
        slow_period=30
    )
    engine.add_strategy(momentum)
    
    mean_reversion = MeanReversionStrategy(
        name="MeanReversion",
        bb_period=20,
        bb_std=2.0
    )
    engine.add_strategy(mean_reversion)
    
    engine.load_data(symbols, start_date, end_date)
    
    results = engine.run()
    
    engine.print_summary()
    
    print("\nDetailed Metrics:")
    print(f"Average Daily Return:   {results.get('avg_daily_return', 0)*100:.4f}%")
    print(f"Std Daily Return:       {results.get('std_daily_return', 0)*100:.4f}%")
    print(f"Best Day:               {results.get('best_day', 0)*100:.2f}%")
    print(f"Worst Day:              {results.get('worst_day', 0)*100:.2f}%")
    print(f"Total Days:             {results.get('total_days', 0)}")
    
    engine.plot_results()
    
    equity_df = engine.get_equity_curve()
    if not equity_df.empty:
        equity_df.to_csv('equity_curve.csv', index=False)
        print("\nEquity curve saved to equity_curve.csv")
    
    trade_df = engine.get_trade_history()
    if not trade_df.empty:
        trade_df.to_csv('trade_history.csv', index=False)
        print("Trade history saved to trade_history.csv")
        print(f"\nLast 10 trades:")
        print(trade_df.tail(10))


if __name__ == "__main__":
    main()
