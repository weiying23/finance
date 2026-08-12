"""Performance metrics and visualization utilities"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict


def calculate_metrics(equity_curve: pd.DataFrame, initial_capital: float) -> Dict:
    """Calculate comprehensive performance metrics

    Args:
        equity_curve: DataFrame with equity curve data
        initial_capital: Initial capital amount

    Returns:
        Dictionary with performance metrics
    """
    if equity_curve.empty:
        return {}
    
    equity_curve = equity_curve.copy()
    equity_curve['returns'] = equity_curve['total_value'].pct_change()
    
    returns = equity_curve['returns'].dropna()
    
    total_return = (equity_curve['total_value'].iloc[-1] - initial_capital) / initial_capital
    
    annual_return = returns.mean() * 252
    annual_volatility = returns.std() * np.sqrt(252)
    
    sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
    
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252)
    sortino_ratio = annual_return / downside_std if downside_std > 0 else 0
    
    cumulative_returns = (1 + returns).cumprod()
    running_max = cumulative_returns.cummax()
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = drawdown.min()
    
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]
    win_rate = len(positive_returns) / len(returns) if len(returns) > 0 else 0
    
    avg_win = positive_returns.mean() if len(positive_returns) > 0 else 0
    avg_loss = abs(negative_returns.mean()) if len(negative_returns) > 0 else 0
    profit_factor = (avg_win * len(positive_returns)) / (avg_loss * len(negative_returns)) if avg_loss > 0 else 0
    
    return {
        'total_return': total_return,
        'total_return_pct': total_return * 100,
        'annual_return': annual_return,
        'annual_return_pct': annual_return * 100,
        'annual_volatility': annual_volatility,
        'annual_volatility_pct': annual_volatility * 100,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio,
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': max_drawdown * 100,
        'win_rate': win_rate,
        'win_rate_pct': win_rate * 100,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }


def plot_equity_curve(equity_df: pd.DataFrame, initial_capital: float, save_path: str = None):
    """Plot comprehensive equity curve analysis

    Args:
        equity_df: DataFrame with equity curve data
        initial_capital: Initial capital amount
        save_path: Optional path to save the plot
    """
    if equity_df.empty:
        print("No data to plot")
        return
    
    sns.set_style('darkgrid')
    fig, axes = plt.subplots(4, 1, figsize=(15, 12))
    
    axes[0].plot(equity_df['timestamp'], equity_df['total_value'], 
                label='Portfolio Value', linewidth=2, color='#2E86AB')
    axes[0].axhline(y=initial_capital, color='red', linestyle='--', 
                   label='Initial Capital', linewidth=1.5)
    axes[0].set_title('Portfolio Value Over Time', fontsize=15, fontweight='bold')
    axes[0].set_ylabel('Value (¥)', fontsize=12)
    axes[0].legend(loc='best')
    axes[0].grid(True, alpha=0.3)
    
    equity_df['returns'] = equity_df['total_value'].pct_change()
    equity_df['cumulative_returns'] = (1 + equity_df['returns']).cumprod() - 1
    
    axes[1].plot(equity_df['timestamp'], equity_df['cumulative_returns'] * 100,
                color='#06A77D', linewidth=2)
    axes[1].fill_between(equity_df['timestamp'], equity_df['cumulative_returns'] * 100, 0,
                        where=(equity_df['cumulative_returns'] >= 0), 
                        color='#06A77D', alpha=0.3)
    axes[1].fill_between(equity_df['timestamp'], equity_df['cumulative_returns'] * 100, 0,
                        where=(equity_df['cumulative_returns'] < 0), 
                        color='#D62828', alpha=0.3)
    axes[1].set_title('Cumulative Returns', fontsize=15, fontweight='bold')
    axes[1].set_ylabel('Returns (%)', fontsize=12)
    axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    axes[1].grid(True, alpha=0.3)
    
    running_max = equity_df['total_value'].cummax()
    drawdown = (equity_df['total_value'] - running_max) / running_max * 100
    
    axes[2].fill_between(equity_df['timestamp'], drawdown, 0,
                        color='#D62828', alpha=0.5, label='Drawdown')
    axes[2].set_title('Drawdown Analysis', fontsize=15, fontweight='bold')
    axes[2].set_ylabel('Drawdown (%)', fontsize=12)
    axes[2].legend(loc='best')
    axes[2].grid(True, alpha=0.3)
    
    axes[3].bar(equity_df['timestamp'], equity_df['returns'] * 100,
               color=['#06A77D' if r >= 0 else '#D62828' for r in equity_df['returns']],
               alpha=0.6, width=1)
    axes[3].set_title('Daily Returns', fontsize=15, fontweight='bold')
    axes[3].set_xlabel('Date', fontsize=12)
    axes[3].set_ylabel('Returns (%)', fontsize=12)
    axes[3].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    axes[3].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    
    plt.show()
