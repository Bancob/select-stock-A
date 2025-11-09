# 📈 select-stock-A
**A Quantitative Stock Selection and Backtesting System for A-Shares**

## 🧭 Overview
This repository provides a modular Python-based framework for quantitative stock selection and backtesting in the **Chinese A-share market**.  
It supports **multi-factor strategies**, **conditional filtering**, and **backtesting simulations** using a flexible, extensible design.

The default example strategy is a **Small-Cap Selection Strategy**, which evaluates the performance of investing in small-market-cap stocks under different rebalancing periods.

---

## 🏗️ Project Structure

```
📂 project_root/
├── config.py                  # Global backtest configuration (dates, strategy, costs, etc.)
├── 回测主程序.py               # Main controller: runs data prep, factor calc, stock selection, and backtest
├── 寻找最优参数.py             # Parameter optimization script
├── core/
│   └── model/
│       └── backtest_config.py # Loads and validates backtest settings
├── program/
│   ├── step1_整理数据.py        # Step 1: Data preparation
│   ├── step2_计算因子.py        # Step 2: Factor computation
│   ├── step3_选股.py            # Step 3: Stock selection
│   └── step4_实盘模拟.py        # Step 4: Performance simulation
├── 因子库/                    # Factor library (custom indicators)
├── 策略库/                    # Strategy library
├── 信号库/                    # Signal library (buy/sell logic)
└── data/
    ├── stock-trading-data/    # Daily stock data
    ├── stock-main-index-data/ # Index data
    └── stock-fin-data-xbx/    # Optional financial data
```

---

## ⚙️ Core Features

### 1️⃣ Data Preparation (`prepare_data`)
- Loads and cleans historical stock/index data.
- Aligns multi-frequency time series using `merge_asof`.
- Supports local data or external data subscriptions.

### 2️⃣ Factor Computation (`calculate_factors`)
- Calculates all factors defined in `config.py`.
- Supports weighted factor combinations and ranking logic.
- Allows parallel computation for faster performance.

### 3️⃣ Stock Selection (`select_stocks`)
- Applies ranking and filter-based stock screening.
- Supports fixed or percentage-based portfolio size.
- Integrates multi-factor weighted selection.

### 4️⃣ Performance Simulation (`simulate_performance`)
- Simulates trading performance and equity curve.
- Supports transaction costs, taxes, and slippage.
- Includes optional **timing models** (e.g., moving-average crossover).

---

## 🧩 Example Strategy Configuration

```python
strategy = {
    'name': 'Small Cap Strategy',
    'hold_period': 'W',           # Weekly rebalancing; supports 'M', '5D', etc.
    'select_num': 10,             # Number of stocks per cycle
    'factor_list': [
        ('市值', True, None, 1),  # Rank by Market Cap ascending (smaller = better)
    ],
    'filter_list': [
        ('收盘价', None, 'pct:<=0.2'),
        ('收盘价', None, 'val:>=1'),
    ]
}
```

Other settings include:
- `start_date` / `end_date` — backtest range  
- `excluded_boards` — exclude sectors (e.g., ChiNext, STAR, NEEQ)  
- `initial_cash` — starting capital  
- `equity_timing` — optional timing method, e.g. `{"name": "MA", "params": [3, 20]}`

---

## 🚀 Usage

### 1. Installation
Use Python 3.9+ and install dependencies:
```bash
pip install pandas numpy tqdm matplotlib backtrader
```

### 2. Run Backtest
```bash
python 回测主程序.py
```

Execution flow:
```
🌀 Backtest system starting...
→ Step 1: Prepare data
→ Step 2: Calculate factors
→ Step 3: Select stocks
→ Step 4: Simulate performance
```

### 3. Optimize Parameters
To find optimal parameters for your strategy:
```bash
python 寻找最优参数.py
```

---

## 📊 Output & Visualization
- Selected stock lists for each rebalancing period.  
- Portfolio return, drawdown, and Sharpe ratio.  
- Equity curve visualization using Matplotlib or CSV export.

---

## 🧠 Extendability
- Add new factors to `因子库/` and register them in `config.py`.  
- Implement new timing or risk-control methods in `program/step4_实盘模拟.py`.  
- Integrate APIs like **Tushare** or **AkShare** for real-time data.  
- Combine with machine learning models for adaptive strategies.



---

## ⚠️ License & Disclaimer
This repository is released under the **MIT License**.  
For **educational and research purposes only** — commercial use is strictly prohibited without permission.

---

> *“In quantitative trading, discipline is the alpha.”*
