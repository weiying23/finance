"""Configuration file for QCode trading system"""

# Backtest Configuration
BACKTEST_CONFIG = {
    'initial_capital': 1000000,
    'commission': 0.0003,
    'slippage': 0.0001,
    'enable_delta_hedging': False  # Disabled by default - only for options strategies
}

# Risk Management Configuration
RISK_CONFIG = {
    'max_position_size': 0.15,          # 单标的硬上限(与 max_weight 对齐, 避免再平衡目标被截断打架)
    'max_portfolio_var': 0.02,
    'risk_free_rate': 0.03,
    'stop_loss_method': 'atr',          # 'atr'(ATR标定) | 'pct'(固定百分比)
    'stop_loss_pct': 0.05,             # method='pct' 时用;ATR 模式下保留作兜底
    'atr_period': 14,                   # ATR 计算窗口
    'atr_mult': 2.5,                    # ATR 倍数(多头止损=最高价-mult*ATR)
    'target_portfolio_vol': 0.15,      # 组合目标年化波动率(vol-target 用)
    'max_gross': 1.0,                   # 总杠杆封顶(1.0=无借贷),阶段1决策
}

# Portfolio Optimization
PORTFOLIO_OPTIMIZATION = {
    'method': 'min_variance',   # risk_parity(1/σ,反动量) | min_variance(Ledoit-Wolf收缩)
    'max_weight': 0.15,
    'rebalance_threshold': 0.10,
    'shrinkage_alpha': 0.5,
    'rebalance_freq': 'monthly'
}

# Execution Configuration
EXECUTION_CONFIG = {
    'max_single_trade_pct': 0.03,
    'max_splits': 5
}

# Fee & A-share Realism Configuration
# 印花税(卖出单边 0.05%) + 过户费(沪市双向 0.001%) + 涨跌停
FEE_CONFIG = {
    'stamp_tax': 0.0005,          # 印花税,卖出单边
    'transfer_fee': 0.00001,      # 过户费,沪市双向(深市为 0)
    'limit_pct_default': 0.10,    # 主板涨跌停
    'limit_pct_wide': 0.20,       # 创业板(300/301)/科创板(688)/北交所(8/4)
    't_plus_1': True,             # T+1: 当日买入次日才可卖
}

# Short Position Configuration
SHORT_CONFIG = {
    'margin_ratio': 0.20,
    'borrowing_cost_annual': 0.02
}

# Pairs Trading Strategy
PAIRS_TRADING_STRATEGY = {
    'lookback': 60,
    'entry_zscore': 2.0,
    'exit_zscore': 0.5,
    'pairs': [('600519', '000858'), ('600036', '601318'), ('000333', '600887')]
}

# Walk-Forward Configuration
WALK_FORWARD_CONFIG = {
    'train_months': 6,
    'test_months': 1
}

# Data Configuration
# data_source: 'akshare' | 'tushare' | 'baostock' | 'yfinance'
#   - akshare:  默认,覆盖最广(股/期权/期货/指数),爬虫实现,稳定性一般
#   - tushare:  推荐(严肃回测),Pro API 稳定,需 token(免费注册)
#   - baostock: 免注册,K线为主,覆盖窄但稳定
#   - yfinance: 美股/全球,延迟导入
# use_sample_data 时以上设置不生效,走 SampleDataSource(无网络无依赖)
DATA_CONFIG = {
    'cache_data': True,
    'data_source': 'baostock',  # 当前环境 akshare 走 HTTP 代理失败,baostock 自有协议可直连
    'tushare_token': '',  # 或设置环境变量 TUSHARE_TOKEN
}

# Strategy Configuration
MOMENTUM_STRATEGY = {
    'fast_period': 10,
    'slow_period': 30,
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70
}

MEAN_REVERSION_STRATEGY = {
    'bb_period': 20,
    'bb_std': 2.0,
    'lookback': 5
}

MULTI_ASSET_STRATEGY = {
    'trend_period': 20,
    'volatility_period': 20,
    'hedge_threshold': 0.15
}

# Alpha Mining Strategies
MULTI_FACTOR_ALPHA = {
    'momentum_weight': 0.4,
    'value_weight': 0.3,
    'volatility_weight': 0.2,
    'volume_weight': 0.1
}

STATISTICAL_ARBITRAGE = {
    'lookback': 60,
    'entry_zscore': 2.0,
    'exit_zscore': 0.5,
    'stop_loss_zscore': 3.0  # Exit if z-score worsens beyond this
}

MARKET_REGIME_STRATEGY = {
    'regime_lookback': 60
}

# Trading Universe (沪深300按流动性前50,见 qcode/data/universe.py 动态选池避免前视)
STOCK_UNIVERSE = [
    '000625', '601127', '600519', '300750', '300502', '300418', '300308', '000977', '301236', '002594',
    '601012', '000858', '688041', '000063', '002466', '002230', '300059', '601318', '600036', '688256',
    '002475', '601901', '603019', '000568', '601899', '300394', '600900', '603259', '601888', '300274',
    '601138', '000988', '600150', '002371', '600030', '002460', '002241', '601288', '000651', '600276',
    '601881', '000333', '000725', '688271', '601398', '300033', '601360', '600048', '688981', '603986',
]

# Universe Selection (point-in-time, 按起点前流动性选池,消除前视/幸存者偏差)
UNIVERSE_SELECTION = {
    'method': 'liquidity',       # 'static'(用 STOCK_UNIVERSE) | 'liquidity'(动态按起点前成交额)
    'as_of': 'pre_period',       # 'pre_period': 用回测起点前 N 日 | 'fixed_date': 用 as_of_date
    'as_of_date': '2019-01-01',  # method=liquidity + as_of=fixed_date 时生效
    'lookback_days': 60,
    'top_n': 50,
}

# Backtest Period
BACKTEST_PERIOD = {
    'start_date': '2022-01-01',
    'end_date': '2023-12-31'
}
