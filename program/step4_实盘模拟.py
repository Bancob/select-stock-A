"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import time
import warnings

import pandas as pd

from core.equity import calc_equity, show_plot_performance
from core.model.backtest_config import BacktestConfig, load_config
from core.model.timing_signal import EquityTiming
from core.utils.path_kit import get_file_path

# ====================================================================================================
# ** 配置与初始化 **
# 忽略不必要的警告并设置显示选项，以优化控制台输出的可读性
# ====================================================================================================
warnings.filterwarnings("ignore")
pd.set_option("expand_frame_repr", False)
pd.set_option("display.unicode.ambiguous_as_wide", True)
pd.set_option("display.unicode.east_asian_width", True)


def save_performance_df_csv(conf: BacktestConfig, **kwargs):
    for name, df in kwargs.items():
        file_path = conf.get_result_folder() / f"{name}.csv"
        df.to_csv(file_path, encoding="utf-8-sig")


# ====================================================================================================
# 动态杠杆再择时模拟
# 1. 生成动态杠杆
# 2. 进行动态杠杆再择时的回测模拟
# 3. 保存结果
# ====================================================================================================
def simu_equity_timing(conf: BacktestConfig, pivot_dict_stock: dict, df_stock_ratio: pd.DataFrame):
    """
    动态杠杆再择时模拟
    :param conf: 回测配置
    :param df_stock_ratio: 股票目标资金占比
    :return: 资金曲线，策略收益，年化收益
    """
    print(f"资金曲线再择时，生成动态杠杆")

    # 记录开始时间，用于计算耗时
    s_time = time.time()

    # 读取资金曲线数据，作为动态杠杆计算的基础
    account_df = pd.read_csv(conf.get_result_folder() / "资金曲线.csv", index_col=0, encoding="utf-8-sig")

    # 生成动态杠杆，根据资金曲线的权益变化进行杠杆调整
    equity_signal = conf.equity_timing.get_equity_signal(account_df)
    print(f"✅ 完成生成动态杠杆，花费时间： {time.time() - s_time:.3f}秒")

    # 将equity_signals的index设置为交易日期
    equity_signal.index = pd.to_datetime(account_df["交易日期"])
    # 对每个换仓日期，找到对应的动态杠杆值并相乘
    df_stock_ratio = df_stock_ratio.mul(equity_signal.reindex(df_stock_ratio.index), axis=0)

    # 记录时间，用于后续动态杠杆再择时的耗时统计
    s_time = time.time()
    print(f"🌀 开始动态杠杆再择时模拟交易，累计回溯{len(account_df):,} 天...")

    # 进行资金曲线的再择时回测模拟
    # - 使用动态杠杆调整后的持仓计算资金曲线
    # - 包括现货和合约的比例数据
    # - 计算回测的总体收益、年度收益、季度收益和月度收益
    account_df, rtn, year_return, month_return, quarter_return = calc_equity(conf, pivot_dict_stock, df_stock_ratio)

    # 保存回测结果，包括再择时后的资金曲线和收益评价指标
    save_performance_df_csv(
        conf,
        资金曲线_再择时=account_df,
        策略评价_再择时=rtn,
        年度账户收益_再择时=year_return,
        季度账户收益_再择时=quarter_return,
        月度账户收益_再择时=month_return,
    )

    print(f"✅ 完成动态杠杆再择时模拟交易，花费时间：{time.time() - s_time:.3f}秒")

    # 返回再择时后的资金曲线和收益结果，用于后续分析或评估
    return account_df, rtn, year_return


def simulate_performance(conf: BacktestConfig, select_results, show_plot=True):
    """
    模拟投资组合的表现，生成资金曲线以跟踪组合收益变化。

    参数:
    conf (BacktestConfig): 回测配置
    select_results (DataFrame): 选股结果数据
    show_plot (bool): 是否显示回测结果图表

    返回:
    None
    """
    # ====================================================================================================
    # 1. 聚合选股结果中的权重
    # ====================================================================================================
    s_time = time.time()
    print("🌀 开始权重聚合...")
    df_stock_ratio = select_results.pivot(index="交易日期", columns="股票代码", values="目标资金占比").fillna(0)
    print(f"✅ 权重聚合完成，耗时：{time.time() - s_time:.3f}秒\n")

    # ====================================================================================================
    # 2. 对数据进行处理
    # ====================================================================================================
    pivot_dict_stock = pd.read_pickle(get_file_path("data", "运行缓存", "全部股票行情pivot.pkl"))

    # 确定回测区间
    data_date_max = f"{df_stock_ratio.index.max().date()}"
    conf.start_date = max(conf.start_date, f"{df_stock_ratio.index.min().date()}")
    conf.end_date = min(conf.end_date or data_date_max, data_date_max)
    print("🗓️ 回测区间:", conf.start_date, conf.end_date)

    # 获取换仓日历
    index_data = conf.read_index_with_trading_date()
    rebalance_dates = index_data.groupby(f"{conf.strategy.hold_period_name}起始日")["交易日期"].last()

    # 对于交易日可能为空的周期进行重新填充
    df_stock_ratio = df_stock_ratio.reindex(rebalance_dates, fill_value=0)
    df_stock_ratio = df_stock_ratio.sort_index()

    # ====================================================================================================
    # 3. 计算资金曲线
    # ====================================================================================================
    print(f"🌀 开始模拟日线交易，回溯 {len(df_stock_ratio):,} 天...")
    # 计算资金曲线及收益数据
    account_df, rtn, year_return, month_return, quarter_return = calc_equity(conf, pivot_dict_stock, df_stock_ratio)

    # - 保存计算出的资金曲线、策略评价、年度、季度和月度的收益数据
    save_performance_df_csv(
        conf,
        资金曲线=account_df,
        策略评价=rtn,
        年度账户收益=year_return,
        季度账户收益=quarter_return,
        月度账户收益=month_return,
    )

    # 检查配置中是否启用了择时信号
    has_equity_signal = isinstance(conf.equity_timing, EquityTiming)

    if has_equity_signal:
        print(f"🌀 开始计算资金曲线再择时...")
        # 进行再择时回测，计算动态杠杆后的资金曲线和收益指标
        account_df2, rtn2, year_return2 = simu_equity_timing(conf, pivot_dict_stock, df_stock_ratio)

        # 可选：绘制再择时的资金曲线图表
        if show_plot:
            # 绘制再择时后的资金曲线并显示各项收益指标
            show_plot_performance(
                conf, account_df2, rtn2, year_return2, title_prefix="再择时-", 再择时前资金曲线=account_df["净值"]
            )
    elif show_plot:
        show_plot_performance(conf, account_df, rtn, year_return)

    print(f"✅ 回测完成，耗时：{time.time() - s_time:.3f}秒\n")

    return conf.report


if __name__ == "__main__":
    # 加载回测配置
    backtest_config = load_config()
    # 读取选股结果
    select_stock_result = backtest_config.get_result_folder() / f"{backtest_config.strategy.name}选股结果.pkl"
    _results = pd.read_pickle(select_stock_result)

    # 模拟组合表现
    simulate_performance(backtest_config, _results)
