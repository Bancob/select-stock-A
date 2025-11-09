"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import time

import numba as nb
import numpy as np
import pandas as pd

from core.evaluate import strategy_evaluate
from core.figure import draw_equity_curve_plotly
from core.market_essentials import import_index_data
from core.model.backtest_config import BacktestConfig
from core.model.type_def import BSE_MAIN, SimuParams, StockMarketData, get_symbol_type
from core.rebalance import RebAlways
from core.simulator import Simulator
from core.utils.path_kit import get_file_path

pd.set_option("display.max_rows", 1000)
pd.set_option("expand_frame_repr", False)  # 当列太多时不换行


def read_trading_dates(first_date, last_date):
    calendar = pd.read_csv(get_file_path("data", "交易日历.csv"), encoding="utf-8", parse_dates=["交易日期"])
    trading_dates = calendar["交易日期"]

    trading_dates = trading_dates[(trading_dates >= first_date) & (trading_dates <= last_date)]
    return trading_dates


def get_stock_market(pivot_dict_stock, trading_dates, symbols, symbol_types) -> StockMarketData:
    df_open: pd.DataFrame = pivot_dict_stock["open"].loc[trading_dates, symbols]
    df_close: pd.DataFrame = pivot_dict_stock["close"].loc[trading_dates, symbols]
    df_preclose: pd.DataFrame = pivot_dict_stock["preclose"].loc[trading_dates, symbols]
    # Not sure if necessary
    should_copy = True

    data = StockMarketData(
        candle_begin_ts=(trading_dates.astype(np.int64) // 1000000000).to_numpy(copy=should_copy),
        op=df_open.to_numpy(copy=should_copy),
        cl=df_close.to_numpy(copy=should_copy),
        pre_cl=df_preclose.to_numpy(copy=should_copy),
        types=np.array(symbol_types, dtype=np.int16),
    )

    return data


def calc_equity(conf: BacktestConfig, pivot_dict_stock: dict, df_stock_ratio: pd.DataFrame):
    """
    计算资金曲线
    :param conf: 回测配置
    :param pivot_dict_stock: 股票行情
    :param df_stock_ratio: 股票目标资金占比
    """
    symbols = sorted(df_stock_ratio.columns)
    symbol_types = [get_symbol_type(sym) for sym in symbols]
    if any(x == BSE_MAIN for x in symbol_types):
        raise ValueError(f"BSE not supported")  # No Beijing stocks

    # 确定回测区间
    start_date = max(df_stock_ratio.index.min(), pd.to_datetime(conf.start_date))
    trading_dates = read_trading_dates(start_date, conf.end_date)

    # 读取行情
    market = get_stock_market(pivot_dict_stock, trading_dates, symbols, symbol_types)

    # 开始回测
    df_stock_ratio = df_stock_ratio.loc[start_date : conf.end_date, symbols]
    params = SimuParams(
        init_cash=conf.initial_cash,  # 初始资金
        stamp_tax_rate=conf.t_rate,  # 印花税率
        commission_rate=conf.c_rate,  # 券商佣金费率
    )
    adj_dts = df_stock_ratio.index.to_numpy().astype(np.int64) // 1000000000
    ratios = df_stock_ratio.to_numpy()
    pos_calc = RebAlways(market.types)

    s_time = time.perf_counter()
    cashes, pos_values, stamp_taxes, commissions = start_simulation(market, params, adj_dts, ratios, pos_calc)

    print(f"✅ 完成模拟交易，花费时间: {time.perf_counter() - s_time:.3f}秒\n")

    account_df = pd.DataFrame(
        {
            "交易日期": trading_dates,
            "账户可用资金": cashes,
            "持仓市值": pos_values,
            "印花税": stamp_taxes,
            "券商佣金": commissions,
        }
    )

    account_df["总资产"] = account_df["账户可用资金"] + account_df["持仓市值"]
    account_df["净值"] = account_df["总资产"] / conf.initial_cash
    account_df["手续费"] = account_df["印花税"] + account_df["券商佣金"]
    account_df["涨跌幅"] = account_df["净值"].pct_change()
    account_df = account_df.assign(
        总资产=account_df["账户可用资金"] + account_df["持仓市值"],
        净值=account_df["总资产"] / conf.initial_cash,
        手续费=account_df["印花税"] + account_df["券商佣金"],
        涨跌幅=account_df["净值"].pct_change(),
    )

    # 策略评价
    rtn, year_return, month_return, quarter_return = strategy_evaluate(account_df, net_col="净值", pct_col="涨跌幅")
    conf.set_report(rtn.T)

    return account_df, rtn, year_return, month_return, quarter_return


@nb.njit(boundscheck=True)
def start_simulation(market, simu_params, adj_dts, ratios, pos_calc):
    n_bars = len(market.candle_begin_ts)
    n_syms = len(market.types)

    # Equity at end of day
    pos_values = np.zeros(n_bars, dtype=np.float64)
    cashes = np.zeros(n_bars, dtype=np.float64)
    stamp_taxes = np.zeros(n_bars, dtype=np.float64)
    commissions = np.zeros(n_bars, dtype=np.float64)

    init_pos_values = np.zeros(n_syms, dtype=np.float64)
    simu = Simulator(simu_params.init_cash, simu_params.commission_rate, simu_params.stamp_tax_rate, init_pos_values)

    idx_adj = 0

    buy_next_open = False

    for idx_bar in range(n_bars):
        # 开盘前，用前收盘价替换上一周期收盘价，可能因除权除息产生变化，不改变仓位价值
        simu.fill_last_prices(market.pre_cl[idx_bar])

        # 集合竞价结束，计算开盘仓位价值，并更新最新价为开盘价
        simu.settle_pos_values(market.op[idx_bar])
        simu.fill_last_prices(market.op[idx_bar])

        stamp_tax = commission = 0.0

        if buy_next_open:
            # 如果本交易日需要买入，集合竞价结束时，基于开盘价计算买入仓位
            target_pos = pos_calc.calc_lots(simu.cash, market.op[idx_bar], ratios[idx_adj])
            idx_adj += 1
            buy_next_open = False

            # 连续竞价开始，基于开盘价买入股票
            commission = simu.buy_stocks(market.op[idx_bar], target_pos)
        elif idx_adj < len(adj_dts) and adj_dts[idx_adj] == market.candle_begin_ts[idx_bar]:
            # 根据交易日历，本交易日结束后需要计算下交易周期股票权重，则收盘清空仓位
            stamp_tax, commission = simu.sell_all(market.cl[idx_bar])
            buy_next_open = True

        # 计算收盘仓位价值，不需要更新最新价
        simu.settle_pos_values(market.cl[idx_bar])

        stamp_taxes[idx_bar] = stamp_tax
        commissions[idx_bar] = commission
        pos_values[idx_bar] = simu.get_pos_value()
        cashes[idx_bar] = simu.cash

    return cashes, pos_values, stamp_taxes, commissions


def show_plot_performance(conf: BacktestConfig, account_df, rtn, year_return, title_prefix="", **kwargs):
    # 添加指数数据
    for index_code, index_name in zip(["sh000300", "sh000905"], ["沪深300", "中证500"]):
        index_path = conf.index_data_path / f"{index_code}.csv"
        if not index_path.exists():
            print(f"{index_name}({index_code})指数数据不存在，无法添加指数数据")
            continue
        index_df = import_index_data(index_path, [account_df["交易日期"].min(), conf.end_date])
        account_df = pd.merge(left=account_df, right=index_df[["交易日期", "指数涨跌幅"]], on=["交易日期"], how="left")
        account_df[index_name + "指数"] = (account_df["指数涨跌幅"] + 1).cumprod()
        del account_df["指数涨跌幅"]

    print(
        f"""策略评价：
{rtn}
分年收益率：
{year_return}"""
    )
    print(f'✅ 总手续费: ￥{account_df["手续费"].sum():,.2f}')
    print()

    print("🌀 开始绘制资金曲线...")

    # 生成画图数据字典，可以画出所有offset资金曲线以及各个offset资金曲线
    data_dict = {"资金曲线": "净值", "沪深300指数": "沪深300指数", "中证500指数": "中证500指数"}
    right_axis = {"最大回撤": "净值dd2here"}

    # 添加自定义数据
    for col_name, col_series in kwargs.items():
        account_df[col_name] = col_series.reset_index(drop=True)
        data_dict[col_name] = col_name

    # 如果画资金曲线，同时也会画上回撤曲线
    pic_title = f"累积净值:{rtn.at['累积净值', 0]}, 年化收益:{rtn.at['年化收益', 0]}, 最大回撤:{rtn.at['最大回撤', 0]}"
    pic_desc = conf.get_fullname()
    # 调用画图函数
    draw_equity_curve_plotly(
        account_df,
        data_dict=data_dict,
        date_col="交易日期",
        right_axis=right_axis,
        title=pic_title,
        desc=pic_desc,
        path=conf.get_result_folder() / f"{title_prefix}资金曲线.html",
    )
