# QCode - 量化交易回测框架

基于 Python 的 A 股量化交易回测框架:可插拔数据源、7 种内置策略、多资产多空、ATR 止损 + 波动率目标仓位 + regime 自适应的风控引擎。

> 仅供学习研究,非投资建议。历史表现不代表未来收益。

## 核心特性

- **可插拔数据源**:akshare / tushare / baostock(A 股)+ yfinance(美股/全球),通过 `config.DATA_CONFIG['data_source']` 切换;所有后端**延迟导入**,`--sample-data` 离线模式无需联网、不依赖任何数据后端库
- **7 种策略**:动量、均值回归、多资产(含期权对冲)、多因子、统计套利、市场环境自适应、协整配对交易
- **做空支持**:多空仓位独立记账(保证金 20% + 融券成本),`OPEN_SHORT`/`CLOSE_SHORT` 信号语义明确
- **风控引擎**:ATR 自适应止损、波动率目标总仓位(封顶无杠杆)、regime 仓位 overlay、VaR/CVaR 减仓、月度 min_variance 再平衡
- **组合优化**:风险平价、Ledoit-Wolf 收缩 + 最小方差(SLSQP)
- **性能分析**:Sharpe、最大回撤、胜率、年化、VaR/CVaR,并对照等权买入持有基准
- **数据缓存**:内存 + 磁盘(`.data_cache/`)双层缓存,50-100 只标的重复跑免重拉

## 安装

```bash
git clone https://github.com/weiying23/finance.git
cd finance/qcode
pip install -r requirements.txt   # pandas/numpy/scipy/statsmodels/matplotlib/seaborn/tqdm
```

数据后端按需安装(延迟导入,缺库优雅降级):
```bash
pip install akshare      # 默认 A 股后端(爬虫)
pip install baostock     # 免注册,自有 TCP 协议(akshare 失败时的可靠替代)
pip install tushare      # Pro API(需 token)
pip install yfinance     # 美股/全球
```

只用 `--sample-data` 离线测试可不装任何后端。

## 快速开始

### CLI

```bash
# 离线测试(走 SampleDataSource,不联网)
python main.py --strategy momentum --sample-data
python main.py --strategy pairs_trading --sample-data
python main.py --strategy momentum --walk-forward --sample-data

# 真实数据:去掉 --sample-data,按 config.DATA_CONFIG['data_source'] 取后端
python main.py --strategy momentum
python main.py --strategy pairs_trading --symbols 600519 000858 --start 2022-01-01 --end 2023-12-31

# 市场环境选择(仅 --sample-data 模式生效)
python main.py --strategy momentum --sample-data --market-regime bull

# 可用策略:momentum, mean_reversion, multi_asset, multi_factor, stat_arb, regime, pairs_trading, all, alpha_all
python main.py --strategy <name> [--symbols ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
                          [--capital N] [--no-hedging] [--sample-data] [--walk-forward]
```

### Python API

```python
from qcode import BacktestEngine
from qcode.strategies.momentum import MomentumStrategy

engine = BacktestEngine(initial_capital=1000000)
engine.add_strategy(MomentumStrategy(fast_period=10, slow_period=30))
engine.load_data(['600519', '000858'], '2022-01-01', '2023-12-31')
results = engine.run()
engine.print_summary()
engine.plot_results()            # 默认显示 5 秒自动关闭(传 pause_sec=0 阻塞, save_path= 存图)
```

## 内置策略

| 策略 | 原理 | 关键参数(config.py) |
|------|------|----------------------|
| `momentum` | 快慢 SMA 交叉 + RSI 超买超卖 | fast 10 / slow 30 / rsi 14 |
| `mean_reversion` | 布林带触轨回归 | bb 20 / std 2.0 |
| `multi_asset` | 趋势强度 + MACD,高波动附期权对冲 | trend 20 / hedge 0.15 |
| `multi_factor` | 动量/价值/波动率/成交量四因子加权 | 权重 0.4/0.3/0.2/0.1 |
| `stat_arb` | 滚动均值±标准差 Z-score | lookback 60 / entry 2.0 / exit 0.5 |
| `regime` | 按 60 日趋势+波动率识别 5 种市场状态 | regime_lookback 60 |
| `pairs_trading` | 预设品种对协整检验 + 残差 Z-score | lookback 60 / entry 2.0 |

信号类型:`BUY`/`SELL`(仅平多)/`OPEN_SHORT`/`CLOSE_SHORT`/`CLOSE_LONG`,以及期权 `BUY_CALL`/`SELL_CALL`/`BUY_PUT`/`SELL_PUT`。

## 数据源

通过 `config.py` 的 `DATA_CONFIG` 切换:

| 源 | 覆盖 | 需 token | 说明 |
|----|------|---------|------|
| `akshare`(默认) | A 股股/指数/期权/期货 | 否 | 爬取 sina/eastmoney,受系统代理影响 |
| `baostock` | A 股股/指数 | 否 | **自有 TCP 协议,绕开 HTTP 代理**,akshare 失败时的可靠替代 |
| `tushare` | A 股股/指数/期货/财务 | 是(免费注册) | Pro API 稳定;设 `DATA_CONFIG['tushare_token']` 或环境变量 `TUSHARE_TOKEN` |
| `yfinance` | 美股/全球,含期权链 | 否 | 走 requests,受代理影响 |

所有 adapter 输出统一 schema:日期索引 + `open/high/low/close/volume`(及 amount/pct_change/turnover 等)。

**无前视选池**:`qcode/data/universe.py` 的 `select_liquidity_universe(as_of, lookback_days=60)` 按回测起点前 N 日成交额选 top-50,消除幸存者/前视偏差。

**联网说明**:本机若设了 HTTP 代理且对国内域名判为"直连"而直连又不通,akshare/yfinance 会报 `ProxyError`/`RemoteDisconnected`。修法:代理规则里把 `eastmoney.com`/`github.com` 设为代理,或用 baostock(不经 HTTP 代理)。

## 配置

所有参数集中在 `config.py`(**改参数改这里,不要改策略构造函数**):

| 配置段 | 作用 |
|--------|------|
| `BACKTEST_CONFIG` | 初始资金、佣金、滑点、Delta 对冲开关 |
| `RISK_CONFIG` | 仓位上限、止损(ATR/百分比)、波动率目标、总杠杆封顶 |
| `PORTFOLIO_OPTIMIZATION` | 再平衡方法(min_variance)、max_weight、再平衡频率 |
| `EXECUTION_CONFIG` | 拆单(单笔上限、最大拆分) |
| `SHORT_CONFIG` | 做空保证金比例、融券成本 |
| `DATA_CONFIG` | 数据源、tushare token |
| `STOCK_UNIVERSE` | 50 只标的池(沪深 300 按流动性前 50) |
| `*_STRATEGY` | 各策略参数 |

### 风控引擎(Phase 1 改进)

针对"策略本质是低 beta 保险、牛市跑输持有"的发现做的改进:

- **ATR 止损**(`stop_loss_method='atr'`,`atr_mult=2.5`):止损 = 最高价 − k×ATR,自适应波动,避免固定 5% 被日常波动扫损
- **波动率目标总仓位**(`target_portfolio_vol=0.15`,`max_gross=1.0`):`gross = clip(target_vol/realized_vol, 0.3, 1.0)`,封顶无借贷,低波满仓、高波降仓持现金
- **regime overlay**:市场趋势 < −3% 时进一步压仓到 0.5
- **min_variance 再平衡**:Ledoit-Wolf 收缩 + SLSQP 最小方差(替代反动量的 risk_parity)
- **VaR 减仓**:组合 VaR 超标时自动缩减最大持仓

## 自定义策略

继承 `BaseStrategy`,实现 `calculate_indicators` + `generate_signals`:

```python
from qcode.strategies.base import BaseStrategy, Signal, SignalType
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self, period=20):
        super().__init__("MyStrategy", {'period': period})

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['sma'] = self.calculate_sma(df['close'], self.params['period'])
        return df

    def generate_signals(self, data: dict) -> list:
        signals = []
        for symbol, df in data.items():
            df = self.calculate_indicators(df)
            cur = df.iloc[-1]
            if cur['close'] > cur['sma']:
                signals.append(Signal(cur.name, symbol, SignalType.BUY, 0, cur['close']))
        return signals
```

`BaseStrategy` 提供静态指标方法:`calculate_sma / ema / rsi / bollinger_bands / macd / atr`。

## 可视化与导出

```python
engine.plot_results(pause_sec=5, save_path='equity.png')   # 5 秒自动关闭
equity_df = engine.get_equity_curve()      # 净值曲线 DataFrame
trade_df  = engine.get_trade_history()     # 交易记录 DataFrame
equity_df.to_csv('equity.csv', index=False)
```

## 回测结果文档

跨市场(熊/震荡/牛)对比 + Phase 1 改进的真实数据回测结论,见项目根目录:

- [熊市策略回测结果.md](熊市策略回测结果.md) — 2022-2023(10 只白马,逐股 + 暴跌保险拆解)
- [牛市策略回测结果.md](牛市策略回测结果.md) — 2019-2020
- [震荡市策略回测结果.md](震荡市策略回测结果.md) — 2021
- [跨市场对比.md](跨市场对比.md) — 三段合成:策略本质是"低 beta 暴跌保险"
- [Phase1改进结果.md](Phase1改进结果.md) — ATR止损/波动率目标/regime overlay + 50 只池改进;multi_asset 三段全转正,但牛市闸门(-100pp)未过,按约定停手不上 Phase 3

## 项目结构

```
qcode/
├── main.py                  # CLI 入口
├── config.py                # 所有参数(策略/风控/回测/数据源)
├── requirements.txt
├── qcode/                   # 包
│   ├── data/                # 可插拔数据源(后端延迟导入)
│   │   ├── base.py          # DataSource ABC + 内存/磁盘缓存 + IV
│   │   ├── factory.py       # create_data_source() + DataFetcher 兼容工厂
│   │   ├── sample_source.py # 离线样本数据(4 种市场环境)
│   │   ├── akshare_source.py / tushare_source.py / baostock_source.py / yfinance_source.py
│   │   ├── universe.py      # 无前视流动性选池
│   │   ├── fetcher.py / us_fetcher.py   # 兼容 shim
│   ├── strategies/          # base / momentum / mean_reversion / multi_asset / alpha_mining(多因子+统计套利+regime) / pairs_trading
│   ├── portfolio/manager.py # 持仓记账(多空独立 + 保证金 + 融券成本)
│   ├── risk/manager.py      # 仓位/风险平价/最小方差/Greeks/VaR
│   ├── backtest/engine.py   # 回测引擎总调度
│   └── utils/               # metrics / significance(IC 检验)
└── examples/                # simple_backtest / multi_asset_backtest / strategy_optimization / results_dashboard
```

## License

MIT License
