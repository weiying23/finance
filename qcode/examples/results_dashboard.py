"""Results dashboard for analyzing backtest outputs"""
import sys
sys.path.insert(0, '..')

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path


def load_latest_results():
    """Load the most recent backtest results"""
    equity_files = list(Path('.').glob('equity_curve_*.csv'))
    trade_files = list(Path('.').glob('trades_*.csv'))
    
    if not equity_files:
        print("No equity curve files found. Run a backtest first.")
        return None, None
    
    latest_equity = max(equity_files, key=lambda p: p.stat().st_mtime)
    latest_trades = max(trade_files, key=lambda p: p.stat().st_mtime) if trade_files else None
    
    print(f"Loading: {latest_equity.name}")
    equity_df = pd.read_csv(latest_equity)
    equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
    
    trades_df = None
    if latest_trades:
        print(f"Loading: {latest_trades.name}")
        trades_df = pd.read_csv(latest_trades)
        trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    
    return equity_df, trades_df


def create_dashboard(equity_df, trades_df):
    """Create comprehensive results dashboard"""
    sns.set_style('darkgrid')
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    equity_df['returns'] = equity_df['total_value'].pct_change()
    equity_df['cumulative_returns'] = (1 + equity_df['returns']).cumprod() - 1
    
    running_max = equity_df['total_value'].cummax()
    equity_df['drawdown'] = (equity_df['total_value'] - running_max) / running_max * 100
    
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(equity_df['timestamp'], equity_df['total_value'], linewidth=2, color='#2E86AB')
    ax1.fill_between(equity_df['timestamp'], equity_df['total_value'], 
                     equity_df['total_value'].iloc[0], alpha=0.3, color='#2E86AB')
    ax1.set_title('Portfolio Value Over Time', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Value (¥)', fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(equity_df['timestamp'], equity_df['cumulative_returns'] * 100, 
            linewidth=2, color='#06A77D')
    ax2.set_title('Cumulative Returns', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Returns (%)', fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.fill_between(equity_df['timestamp'], equity_df['drawdown'], 0, 
                     color='#D62828', alpha=0.5)
    ax3.set_title('Drawdown', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Drawdown (%)', fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    ax4 = fig.add_subplot(gs[1, 2])
    returns = equity_df['returns'].dropna() * 100
    ax4.hist(returns, bins=50, color='#2E86AB', alpha=0.7, edgecolor='black')
    ax4.axvline(returns.mean(), color='red', linestyle='--', linewidth=2, label='Mean')
    ax4.set_title('Returns Distribution', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Returns (%)', fontsize=10)
    ax4.set_ylabel('Frequency', fontsize=10)
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    if trades_df is not None and not trades_df.empty:
        ax5 = fig.add_subplot(gs[2, 0])
        trade_counts = trades_df.groupby('symbol').size().sort_values(ascending=False).head(10)
        ax5.barh(range(len(trade_counts)), trade_counts.values, color='#06A77D')
        ax5.set_yticks(range(len(trade_counts)))
        ax5.set_yticklabels(trade_counts.index)
        ax5.set_title('Top 10 Traded Symbols', fontsize=12, fontweight='bold')
        ax5.set_xlabel('Number of Trades', fontsize=10)
        ax5.grid(True, alpha=0.3, axis='x')
        
        ax6 = fig.add_subplot(gs[2, 1])
        action_counts = trades_df['action'].value_counts()
        colors = ['#06A77D', '#D62828', '#F77F00', '#FCBF49']
        ax6.pie(action_counts.values, labels=action_counts.index, autopct='%1.1f%%',
               colors=colors[:len(action_counts)], startangle=90)
        ax6.set_title('Trade Actions', fontsize=12, fontweight='bold')
        
        ax7 = fig.add_subplot(gs[2, 2])
        trades_df['month'] = trades_df['timestamp'].dt.to_period('M')
        monthly_trades = trades_df.groupby('month').size()
        monthly_trades.index = monthly_trades.index.to_timestamp()
        ax7.bar(range(len(monthly_trades)), monthly_trades.values, color='#2E86AB', alpha=0.7)
        ax7.set_xticks(range(len(monthly_trades)))
        ax7.set_xticklabels([d.strftime('%Y-%m') for d in monthly_trades.index], 
                           rotation=45, ha='right', fontsize=8)
        ax7.set_title('Monthly Trading Activity', fontsize=12, fontweight='bold')
        ax7.set_ylabel('Number of Trades', fontsize=10)
        ax7.grid(True, alpha=0.3, axis='y')
    
    plt.suptitle('QCode Backtest Results Dashboard', fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig('backtest_dashboard.png', dpi=300, bbox_inches='tight')
    print("\nDashboard saved to backtest_dashboard.png")
    
    plt.show()


def print_statistics(equity_df, trades_df):
    """Print detailed statistics"""
    print("\n" + "="*60)
    print("DETAILED STATISTICS")
    print("="*60)
    
    equity_df['returns'] = equity_df['total_value'].pct_change()
    returns = equity_df['returns'].dropna()
    
    print(f"\nPortfolio Metrics:")
    print(f"  Initial Value:     ¥{equity_df['total_value'].iloc[0]:,.2f}")
    print(f"  Final Value:       ¥{equity_df['total_value'].iloc[-1]:,.2f}")
    print(f"  Total Return:      {(equity_df['total_value'].iloc[-1] / equity_df['total_value'].iloc[0] - 1) * 100:.2f}%")
    
    print(f"\nReturn Metrics:")
    print(f"  Mean Daily:        {returns.mean() * 100:.4f}%")
    print(f"  Std Daily:         {returns.std() * 100:.4f}%")
    print(f"  Best Day:          {returns.max() * 100:.2f}%")
    print(f"  Worst Day:         {returns.min() * 100:.2f}%")
    print(f"  Positive Days:     {(returns > 0).sum()} ({(returns > 0).sum() / len(returns) * 100:.1f}%)")
    print(f"  Negative Days:     {(returns < 0).sum()} ({(returns < 0).sum() / len(returns) * 100:.1f}%)")
    
    running_max = equity_df['total_value'].cummax()
    drawdown = (equity_df['total_value'] - running_max) / running_max * 100
    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown:      {drawdown.min():.2f}%")
    print(f"  Avg Drawdown:      {drawdown[drawdown < 0].mean():.2f}%")
    
    sharpe = returns.mean() / returns.std() * (252 ** 0.5) if returns.std() > 0 else 0
    print(f"  Sharpe Ratio:      {sharpe:.2f}")
    
    if trades_df is not None and not trades_df.empty:
        print(f"\nTrading Metrics:")
        print(f"  Total Trades:      {len(trades_df)}")
        print(f"  Unique Symbols:    {trades_df['symbol'].nunique()}")
        print(f"  Avg Trade Value:   ¥{trades_df['value'].mean():,.2f}")
        print(f"  Total Volume:      ¥{trades_df['value'].sum():,.2f}")
        
        print(f"\nAction Breakdown:")
        for action, count in trades_df['action'].value_counts().items():
            print(f"  {action:15s}: {count:4d} ({count/len(trades_df)*100:.1f}%)")
    
    print("="*60)


def main():
    print("="*60)
    print("QCode Results Dashboard")
    print("="*60)
    
    equity_df, trades_df = load_latest_results()
    
    if equity_df is None:
        return
    
    print_statistics(equity_df, trades_df)
    create_dashboard(equity_df, trades_df)


if __name__ == "__main__":
    main()
