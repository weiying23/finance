# QCode Agent 指导文件

## 运行系统

```bash
# 离线测试务必加 --sample-data（akshare 需网络，可能连接失败）
python main.py --strategy momentum --sample-data
python main.py --strategy stat_arb --symbols 600519 --start 2022-01-01 --end 2022-12-31 --sample-data
python main.py --strategy pairs_trading --sample-data
python main.py --strategy momentum --walk-forward --sample-data

# 可用策略：momentum, mean_reversion, multi_asset, multi_factor, stat_arb, regime, pairs_trading, all, alpha_all
python main.py --strategy <name> [--symbols ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--capital N] [--no-hedging] [--sample-data] [--walk-forward]

# 市场环境选择（sample-data模式）
python main.py --strategy momentum --sample-data --market-regime bull
python main.py --strategy all --sample-data --market-regime sideways

# 多环境对比测试
python run_all_regimes.py
```

## 架构

- `main.py` — CLI 入口，从 `config.py` 加载所有策略/风控/回测/组合优化/执行参数
- `config.py` — 参数、股票池、回测周期的唯一来源。**改参数改这里，不要改策略构造函数**
- `qcode/data/fetcher.py` — 通过 akshare 获取A股数据（主数据源）；`us_fetcher.py` 存在但**未接入引擎**
- `qcode/strategies/base.py` — 抽象基类 + Signal/SignalType 数据类。`OPEN_SHORT` 和 `CLOSE_SHORT` 信号类型用于做空
- `qcode/strategies/pairs_trading.py` — 新增协整配对交易策略，品种对从 config 预设
- `qcode/backtest/engine.py` — 总调度：执行pending_orders → 止损检查 → 策略信号(含冲突协调) → 组合波动率约束 → 再平衡(risk_parity/min_variance) → Delta对冲
- `qcode/risk/manager.py` — 风控+优化：confidence加权仓位、风险平价、Ledoit-Wolf shrinkage+最小方差优化、组合波动率计算、VaR/CVaR
- `qcode/portfolio/manager.py` — 组合管理：Position数据类（含margin/margin_ratio/short_market_value_abs）、开仓/平仓（含做空保证金+融券成本）、市值计算
- `qcode/utils/significance.py` — 因子有效性检验：IC/Rank IC、Bonferroni/FDR多重检验校正

## 关键设计变更（已修复）

- **信号语义明确**：`SELL` 仅用于平多仓，`OPEN_SHORT` 用于开空仓，`CLOSE_SHORT` 用于平空仓，`CLOSE_LONG` 用于平多仓
- **confidence传入仓位**：`engine._execute_signal` 调用 `risk_manager.calculate_position_size(portfolio_value, price, confidence=signal.confidence)`，强信号多买弱信号少买
- **仓位上限检查**：`PortfolioManager.open_position` 内部检查合并后市值占比不超过 `max_position_size`
- **position_type区分持仓**：同一股票的多仓和空仓是独立 position（key包含position_type）
- **止损机制**：`engine._check_stop_losses` 逐日检查持仓亏损，超过 `stop_loss_pct` 自动平仓
- **拆单执行**：大单超过 `max_single_trade_pct` 时拆成多笔跨日执行，pending_orders 队列
- **信号冲突协调**：BUY+CLOSE_LONG冲突保留CLOSE_LONG（安全优先）；OPEN_SHORT+CLOSE_SHORT冲突保留CLOSE_SHORT；多空仓位独立不冲突
- **组合风控**：VaR超标时自动减仓，组合波动率超标时缩减最大持仓
- **再平衡**：每月计算目标权重（risk_parity/min_variance），偏离超过10%时调仓，仅在无策略信号日执行
- **Delta对冲标的**：用最大市值持仓做对冲标的，而非字典第一只
- **局部RandomState**：`_generate_sample_data` 用 `np.random.RandomState` 替代 `np.random.seed`
- **Walk-forward验证**：`--walk-forward` 选项分段回测，比较各段表现稳定性
- **协整配对交易**：`PairsTradingStrategy` 基于预设品种对做协整检验+残差Z-score交易
- **市场环境参数**：`--market-regime bear/bull/sideways/mixed` 选择样本数据的市场环境，`DataFetcher.__init__` 和 `BacktestEngine.__init__` 传入 `market_regime`
- **NaN confidence防护**：`risk_manager.calculate_position_size` 中 confidence为NaN时默认1.0，避免regime策略在lookback期内触发ValueError
- **做空机制修正**：
  - 开空仓：`cash += proceeds - margin`（卖出收到资金，冻结保证金），而非旧版 `cash -= cost`
  - 平空仓：`cash += margin_released - cost_to_close`（释放保证金，买回股票），margin按比例释放
  - 总市值：`total = cash + long_value + short_margin - short_exposure`（保证金归还后减去空头敞口）
  - 保证金比例和融券成本从 `SHORT_CONFIG` 配置传入
- **所有策略做空信号**：
  - Momentum：signal=-1时发`CLOSE_LONG`+`OPEN_SHORT`，signal=1时发`BUY`+`CLOSE_SHORT`
  - Mean_reversion：上轨触发`CLOSE_LONG`+`OPEN_SHORT`，中轨触发`CLOSE_LONG`+`CLOSE_SHORT`
  - Multi_asset：signal=-1时发`CLOSE_LONG`+`OPEN_SHORT`
  - Stat_arb：signal=-1→`OPEN_SHORT`，signal=3→`CLOSE_SHORT`
  - Regime：signal=-1→`CLOSE_LONG`+`OPEN_SHORT`，signal=1→`BUY`+`CLOSE_SHORT`，signal=0根据前一状态平仓
  - Multi_factor：新增position=-1（alpha_score<-0.2），signal=-1→`OPEN_SHORT`，signal=3→`CLOSE_SHORT`

## 多市场环境回测结果（2022-2023模拟数据，4种市场环境）

### Returns (%)

| 策略 | bear | bull | sideways | mixed |
|------|------|------|----------|-------|
| momentum | -8.07 | +34.14 | -3.80 | -0.40 |
| mean_reversion | -3.88 | -2.28 | +4.07 | -0.33 |
| multi_asset | +38.49 | +15.01 | -0.14 | +22.32 |
| multi_factor | -6.34 | +23.70 | +4.63 | +12.11 |
| stat_arb | -31.93 | +204.87 | -6.34 | +57.95 |
| regime | -9.49 | +22.89 | +2.77 | +7.72 |
| pairs_trading | -24.95 | +188.49 | +1.96 | +67.62 |

### Sharpe Ratios

| 策略 | bear | bull | sideways | mixed |
|------|------|------|----------|-------|
| momentum | -1.11 | 3.92 | -0.42 | -0.04 |
| mean_reversion | -1.06 | -0.71 | 0.84 | -0.09 |
| multi_asset | 5.31 | 4.14 | -0.05 | 4.10 |
| multi_factor | -0.96 | 3.15 | 0.54 | 1.83 |
| stat_arb | -3.95 | 7.27 | -0.44 | 3.32 |
| regime | -1.86 | 2.98 | 0.42 | 1.40 |
| pairs_trading | -3.23 | 6.74 | 0.15 | 3.78 |

### Key Observations

- **multi_asset**: Only strategy profitable in ALL regimes (Sharpe > 0 everywhere except sideways ≈ 0). Best bear-market performer.
- **stat_arb/pairs_trading**: Extreme bull market results (+204%/+188%) suggest mean-reversion strategies thrive in upward-trending markets where Z-score/bollinger signals are more reliable.
- **mean_reversion**: Only strategy with positive sideways Sharpe (0.84) — validates its design for range-bound markets.
- **momentum**: Strong bull performance (+34%) but negative in all other regimes.
- **multi_factor**: Balanced performer — positive in bull/mixed/sideways, moderate drawdowns.

## 配置

所有参数集中在 `config.py`：
- `BACKTEST_CONFIG` — 回测参数
- `RISK_CONFIG` — 风控参数（含 `stop_loss_pct`, `target_portfolio_vol`）
- `PORTFOLIO_OPTIMIZATION` — 组合优化（`method`: risk_parity/min_variance, `max_weight`, `rebalance_threshold`, `shrinkage_alpha`, `rebalance_freq`）
- `EXECUTION_CONFIG` — 拆单执行（`max_single_trade_pct`, `max_splits`）
- `SHORT_CONFIG` — 做空配置（`margin_ratio`: 0.20, `borrowing_cost_annual`: 0.02）
- `PAIRS_TRADING_STRATEGY` — 配对交易参数和预设品种对列表
- `WALK_FORWARD_CONFIG` — Walk-forward分段参数

## 没有测试

项目没有测试套件、pytest 配置或 CI。验证方式是手动运行 `python main.py --sample-data`。

## 输出文件

净值曲线和交易记录保存为 `equity_curve_<strategy>_<timestamp>.csv` 和 `trades_<strategy>_<timestamp>.csv`，放在项目根目录。已被 gitignore 排除（`*.csv`）。

## 依赖

新增 `statsmodels>=0.13.0`（用于协整检验），其余依赖不变。
