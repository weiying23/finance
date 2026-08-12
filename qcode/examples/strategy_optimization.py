"""Strategy parameter optimization example"""
import sys
sys.path.insert(0, '..')

from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy
import itertools
import pandas as pd


def optimize_momentum_strategy():
    """Optimize momentum strategy parameters using grid search"""
    print("="*60)
    print("QCode - Strategy Parameter Optimization")
    print("="*60 + "\n")
    
    symbols = ['600519', '000858', '600036']
    start_date = '2022-01-01'
    end_date = '2023-12-31'
    
    fast_periods = [5, 10, 15]
    slow_periods = [20, 30, 40]
    rsi_periods = [10, 14, 20]
    
    results_list = []
    
    total_combinations = len(fast_periods) * len(slow_periods) * len(rsi_periods)
    current = 0
    
    print(f"Testing {total_combinations} parameter combinations...\n")
    
    for fast, slow, rsi in itertools.product(fast_periods, slow_periods, rsi_periods):
        if fast >= slow:
            continue
        
        current += 1
        print(f"[{current}/{total_combinations}] Testing: fast={fast}, slow={slow}, rsi={rsi}", end=" ")
        
        try:
            engine = BacktestEngine(
                initial_capital=1000000,
                commission=0.0003,
                slippage=0.0001,
                enable_delta_hedging=False
            )
            
            strategy = MomentumStrategy(
                name=f"Momentum_{fast}_{slow}_{rsi}",
                fast_period=fast,
                slow_period=slow,
                rsi_period=rsi
            )
            
            engine.add_strategy(strategy)
            engine.load_data(symbols, start_date, end_date)
            results = engine.run()
            
            results_list.append({
                'fast_period': fast,
                'slow_period': slow,
                'rsi_period': rsi,
                'total_return': results['total_return_pct'],
                'sharpe_ratio': results['sharpe_ratio'],
                'max_drawdown': results['max_drawdown_pct'],
                'num_trades': results['num_trades'],
                'win_rate': results['win_rate']
            })
            
            print(f"- Return: {results['total_return_pct']:.2f}%, Sharpe: {results['sharpe_ratio']:.2f}")
        
        except Exception as e:
            print(f"- Error: {str(e)}")
            continue
    
    if not results_list:
        print("\nNo successful backtests completed.")
        return
    
    results_df = pd.DataFrame(results_list)
    
    print("\n" + "="*60)
    print("OPTIMIZATION RESULTS")
    print("="*60)
    
    print("\nTop 5 by Total Return:")
    top_return = results_df.nlargest(5, 'total_return')
    print(top_return.to_string(index=False))
    
    print("\nTop 5 by Sharpe Ratio:")
    top_sharpe = results_df.nlargest(5, 'sharpe_ratio')
    print(top_sharpe.to_string(index=False))
    
    print("\nTop 5 by Win Rate:")
    top_winrate = results_df.nlargest(5, 'win_rate')
    print(top_winrate.to_string(index=False))
    
    results_df.to_csv('optimization_results.csv', index=False)
    print("\nFull results saved to optimization_results.csv")
    
    best = results_df.loc[results_df['sharpe_ratio'].idxmax()]
    print("\n" + "="*60)
    print("BEST PARAMETERS (by Sharpe Ratio):")
    print("="*60)
    print(f"Fast Period:     {int(best['fast_period'])}")
    print(f"Slow Period:     {int(best['slow_period'])}")
    print(f"RSI Period:      {int(best['rsi_period'])}")
    print(f"Total Return:    {best['total_return']:.2f}%")
    print(f"Sharpe Ratio:    {best['sharpe_ratio']:.2f}")
    print(f"Max Drawdown:    {best['max_drawdown']:.2f}%")
    print(f"Win Rate:        {best['win_rate']*100:.2f}%")
    print("="*60)


if __name__ == "__main__":
    optimize_momentum_strategy()
