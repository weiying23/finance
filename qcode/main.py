"""Main entry point for QCode trading system"""
import argparse
from datetime import datetime

from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy
from qcode.strategies.mean_reversion import MeanReversionStrategy
from qcode.strategies.multi_asset import MultiAssetStrategy
from qcode.strategies.alpha_mining import MultiFactorAlpha, StatisticalArbitrage, MarketRegimeStrategy
from qcode.strategies.pairs_trading import PairsTradingStrategy
from config import (
    BACKTEST_CONFIG, RISK_CONFIG, STOCK_UNIVERSE, BACKTEST_PERIOD,
    MOMENTUM_STRATEGY, MEAN_REVERSION_STRATEGY, MULTI_ASSET_STRATEGY,
    MULTI_FACTOR_ALPHA, STATISTICAL_ARBITRAGE, MARKET_REGIME_STRATEGY,
    PORTFOLIO_OPTIMIZATION, EXECUTION_CONFIG, PAIRS_TRADING_STRATEGY,
    WALK_FORWARD_CONFIG, SHORT_CONFIG
)


def run_backtest(strategy_name: str, symbols: list, start_date: str, end_date: str,
                initial_capital: float, enable_hedging: bool = None,
                use_sample_data: bool = False, walk_forward: bool = False,
                market_regime: str = 'bear'):
    """Run backtest with specified strategy"""

    if enable_hedging is None:
        enable_hedging = BACKTEST_CONFIG.get('enable_delta_hedging', False)

    print("\n" + "="*70)
    print(f"QCode Quantitative Trading System")
    print("="*70)
    print(f"Strategy:        {strategy_name}")
    print(f"Period:          {start_date} to {end_date}")
    print(f"Universe:        {len(symbols)} stocks")
    print(f"Initial Capital: ¥{initial_capital:,.2f}")
    print(f"Delta Hedging:   {'Enabled' if enable_hedging else 'Disabled'}")
    print(f"Position Method: {PORTFOLIO_OPTIMIZATION['method']}")
    print("="*70 + "\n")

    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission=BACKTEST_CONFIG['commission'],
        slippage=BACKTEST_CONFIG['slippage'],
        enable_delta_hedging=enable_hedging,
        use_sample_data=use_sample_data,
        market_regime=market_regime,
        max_position_size=RISK_CONFIG['max_position_size'],
        stop_loss_pct=RISK_CONFIG['stop_loss_pct'],
        target_portfolio_vol=RISK_CONFIG['target_portfolio_vol'],
        position_method=PORTFOLIO_OPTIMIZATION['method'],
        max_weight=PORTFOLIO_OPTIMIZATION['max_weight'],
        rebalance_threshold=PORTFOLIO_OPTIMIZATION['rebalance_threshold'],
        shrinkage_alpha=PORTFOLIO_OPTIMIZATION['shrinkage_alpha'],
        max_single_trade_pct=EXECUTION_CONFIG['max_single_trade_pct'],
        max_splits=EXECUTION_CONFIG['max_splits'],
        rebalance_freq=PORTFOLIO_OPTIMIZATION.get('rebalance_freq', 'monthly'),
        margin_ratio=SHORT_CONFIG['margin_ratio'],
        borrowing_cost_annual=SHORT_CONFIG['borrowing_cost_annual'],
        stop_loss_method=RISK_CONFIG.get('stop_loss_method', 'pct'),
        atr_period=RISK_CONFIG.get('atr_period', 14),
        atr_mult=RISK_CONFIG.get('atr_mult', 2.5),
        max_gross=RISK_CONFIG.get('max_gross', 1.0)
    )

    if strategy_name.lower() == 'momentum':
        strategy = MomentumStrategy(name="Momentum", **MOMENTUM_STRATEGY)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'mean_reversion':
        strategy = MeanReversionStrategy(name="MeanReversion", **MEAN_REVERSION_STRATEGY)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'multi_asset':
        strategy = MultiAssetStrategy(name="MultiAsset", **MULTI_ASSET_STRATEGY)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'multi_factor' or strategy_name.lower() == 'multifactor':
        strategy = MultiFactorAlpha(name="MultiFactorAlpha", **MULTI_FACTOR_ALPHA)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'stat_arb' or strategy_name.lower() == 'statistical_arbitrage':
        strategy = StatisticalArbitrage(name="StatArb", **STATISTICAL_ARBITRAGE)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'regime' or strategy_name.lower() == 'market_regime':
        strategy = MarketRegimeStrategy(name="RegimeAdaptive", **MARKET_REGIME_STRATEGY)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'pairs_trading' or strategy_name.lower() == 'pairs':
        strategy = PairsTradingStrategy(name="PairsTrading", **PAIRS_TRADING_STRATEGY)
        engine.add_strategy(strategy)

    elif strategy_name.lower() == 'alpha_all':
        print("Running all alpha mining strategies...\n")
        engine.add_strategy(MultiFactorAlpha(name="MultiFactorAlpha", **MULTI_FACTOR_ALPHA))
        engine.add_strategy(StatisticalArbitrage(name="StatArb", **STATISTICAL_ARBITRAGE))
        engine.add_strategy(MarketRegimeStrategy(name="RegimeAdaptive", **MARKET_REGIME_STRATEGY))

    elif strategy_name.lower() == 'all':
        print("Running all strategies...\n")
        engine.add_strategy(MomentumStrategy(name="Momentum", **MOMENTUM_STRATEGY))
        engine.add_strategy(MeanReversionStrategy(name="MeanReversion", **MEAN_REVERSION_STRATEGY))
        engine.add_strategy(MultiAssetStrategy(name="MultiAsset", **MULTI_ASSET_STRATEGY))

    else:
        print(f"Unknown strategy: {strategy_name}")
        print("Available strategies:")
        print("  Basic: momentum, mean_reversion, multi_asset, all")
        print("  Alpha Mining: multi_factor, stat_arb, regime, alpha_all")
        print("  Pairs Trading: pairs_trading")
        return

    engine.load_data(symbols, start_date, end_date)

    if walk_forward:
        results = engine.run_walk_forward(
            train_months=WALK_FORWARD_CONFIG['train_months'],
            test_months=WALK_FORWARD_CONFIG['test_months'],
            start_date=start_date,
            end_date=end_date
        )
        print("\nWalk-Forward Results:")
        for i, r in enumerate(results):
            print(f"\n  Segment {i+1}:")
            print(f"    Train: {r['train_period']}")
            print(f"    Test:  {r['test_period']}")
            metrics = r['metrics']
            if metrics:
                print(f"    Return: {metrics.get('total_return_pct', 0):.2f}%")
                print(f"    Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")
    else:
        results = engine.run()
        engine.print_summary()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        equity_df = engine.get_equity_curve()
        if not equity_df.empty:
            filename = f"equity_curve_{strategy_name}_{timestamp}.csv"
            equity_df.to_csv(filename, index=False)
            print(f"\nEquity curve saved to {filename}")

        trade_df = engine.get_trade_history()
        if not trade_df.empty:
            filename = f"trades_{strategy_name}_{timestamp}.csv"
            trade_df.to_csv(filename, index=False)
            print(f"Trade history saved to {filename}")
            print(f"\nLast 10 trades:")
            print(trade_df.tail(10))

    try:
        engine.plot_results()
    except Exception as e:
        print(f"\nCould not display plots: {e}")
        print("Results have been saved to CSV files.")


def main():
    parser = argparse.ArgumentParser(
        description='QCode Quantitative Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --strategy momentum --sample-data
  python main.py --strategy pairs_trading --sample-data
  python main.py --strategy all --walk-forward --sample-data
        """
    )

    parser.add_argument(
        '--strategy',
        type=str,
        default='momentum',
        choices=['momentum', 'mean_reversion', 'multi_asset', 'multi_factor',
                 'stat_arb', 'regime', 'pairs_trading', 'all', 'alpha_all'],
        help='Trading strategy to use'
    )

    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        default=None,
        help='Stock symbols (default: use configured universe)'
    )

    parser.add_argument(
        '--start',
        type=str,
        default=BACKTEST_PERIOD['start_date'],
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        default=BACKTEST_PERIOD['end_date'],
        help='End date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=BACKTEST_CONFIG['initial_capital'],
        help='Initial capital'
    )

    parser.add_argument(
        '--no-hedging',
        action='store_true',
        help='Disable delta hedging (default: use config value)'
    )

    parser.add_argument(
        '--sample-data',
        action='store_true',
        help='Use sample data for offline testing'
    )

    parser.add_argument(
        '--market-regime',
        type=str,
        default='bear',
        choices=['bear', 'bull', 'sideways', 'mixed'],
        help='Market regime for sample data (bear/bull/sideways/mixed)'
    )

    parser.add_argument(
        '--walk-forward',
        action='store_true',
        help='Run walk-forward segmented backtest'
    )

    args = parser.parse_args()

    symbols = args.symbols if args.symbols else STOCK_UNIVERSE
    enable_hedging = None if not args.no_hedging else False

    run_backtest(
        strategy_name=args.strategy,
        symbols=symbols,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        enable_hedging=enable_hedging,
        use_sample_data=args.sample_data,
        walk_forward=args.walk_forward,
        market_regime=args.market_regime
    )


if __name__ == "__main__":
    main()
