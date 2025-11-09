"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from typing import Dict

import pandas as pd
from tqdm import tqdm

from config import n_jobs
from core.model.backtest_config import load_config, BacktestConfig
from core.model.strategy_config import get_col_name
from core.utils.factor_hub import FactorHub
from core.utils.path_kit import get_file_path
from core.fin_essentials import merge_with_finance_data
from core.market_essentials import transfer_to_period_data

# ====================================================================================================
# ** 配置与初始化 **
# 忽略警告并设定显示选项，以优化代码输出的可读性
# ====================================================================================================
warnings.filterwarnings("ignore")
pd.set_option("expand_frame_repr", False)
pd.set_option("display.unicode.ambiguous_as_wide", True)
pd.set_option("display.unicode.east_asian_width", True)

# 因子计算之后，需要保存的行情数据
FACTOR_COLS = [
    '交易日期', '股票代码', '股票名称', '周频起始日', '月频起始日', '3D起始日', '5D起始日', '10D起始日',
    '上市至今交易天数', '复权因子', '开盘价', '最高价', '最低价', '收盘价', '成交额', '是否交易', '流通市值', '总市值',
    '下日_开盘涨停', '下日_是否ST', '下日_是否交易', '下日_是否退市'
]


def cal_strategy_factors(conf: BacktestConfig, stock_code, candle_df, fin_data: Dict[str, pd.DataFrame] = None):
    """
    计算指定股票的策略因子。

    参数:
    conf (BacktestConfig): 策略配置
    stock_code (str): 股票代码
    candle_df (DataFrame): 股票的K线数据
    fin_data (dict): 财务数据

    返回:
    DataFrame: 包含计算因子的K线数据
    dict: 因子列的周期转换规则
    """
    factor_series_dict = {}
    before_len = len(candle_df)
    agg_dict = {}  # 用于数据周期转换的规则

    for factor_name, param_list in conf.factor_params_dict.items():
        factor_file = FactorHub.get_by_name(factor_name)
        for param in param_list:
            col_name = get_col_name(factor_name, param)
            factor_df, column_dict = factor_file.add_factor(
                candle_df.copy(), param, fin_data=fin_data, col_name=col_name
            )

            factor_series_dict[col_name] = factor_df[col_name].values
            # 检查因子计算是否出错
            if before_len != len(factor_series_dict[col_name]):
                print(f"{stock_code}的{factor_name}因子({param}，{col_name})导致数据长度发生变化，请检查！")
                raise Exception("因子计算出错，请避免在cal_factors中修改数据行数")
            agg_dict.update(column_dict)

    kline_with_factor_dict = {**{col_name: candle_df[col_name] for col_name in FACTOR_COLS}, **factor_series_dict}
    kline_with_factor_df = pd.DataFrame(kline_with_factor_dict)
    kline_with_factor_df.sort_values(by="交易日期", inplace=True)
    return kline_with_factor_df, agg_dict


def process_by_stock(conf: BacktestConfig, stock_code: str, candle_df: pd.DataFrame):
    # 导入财务数据，将个股数据与财务数据合并，并计算财务指标的衍生指标
    if conf.fin_cols:  # 前面已经做了预检，这边只需要动态台南佳即可
        # 分别为：个股数据、财务数据、原始财务数据（不抛弃废弃的报告数据）
        candle_df, fin_df, raw_fin_df = merge_with_finance_data(conf, stock_code, candle_df)
        fin_data = {'财务数据': fin_df, '原始财务数据': raw_fin_df}
    else:
        fin_data = None

    # 计算因子，并且获得新的因子列的周期转换规则
    factor_df, agg_dict = cal_strategy_factors(conf, stock_code, candle_df, fin_data=fin_data)

    # 对因子数据进行交易周期转换
    period_df = transfer_to_period_data(factor_df, conf.strategy.hold_period_name, agg_dict)
    return period_df, agg_dict


def calculate_factors(conf: BacktestConfig):
    """
    计算所有股票的因子，分为三步：
    1. 加载股票K线数据
    2. 计算每个股票的因子，并存储到列表
    3. 合并所有因子数据并存储

    参数:
    conf (BacktestConfig): 回测配置
    """
    print("🌀 开始计算因子...")
    s_time = time.time()

    # ====================================================================================================
    # 1. 加载股票K线数据
    # ====================================================================================================
    print("ℹ️ 配置信息检查...")
    if len(conf.fin_cols) > 0 and not conf.has_fin_data:
        print(f"⚠️ 策略需要财务因子{conf.fin_cols}，但缺少财务数据路径")
        raise ValueError("请在 config.py 中配置财务数据路径")
    elif len(conf.fin_cols) > 0:
        print(f"ℹ️ 检测到财务因子：{conf.fin_cols}")

    print("ℹ️ 读取股票K线数据...")
    candle_df_dict: Dict[str, pd.DataFrame] = pd.read_pickle(get_file_path("data", "运行缓存", "股票预处理数据.pkl"))

    # ====================================================================================================
    # 2. 计算因子并存储结果
    # ====================================================================================================
    all_factor_df_list = []  # 计算结果会存储在这个列表
    factor_col_info = dict()
    # ** 注意 **
    # `tqdm`是一个显示为进度条的，非常有用的工具
    # 目前是串行模式，比较适合debug和测试。
    # 可以用 python自带的 concurrent.futures.ProcessPoolExecutor() 并行优化，速度可以提升超过5x
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = []
        for stock_code, candle_df in candle_df_dict.items():
            futures.append(executor.submit(process_by_stock, conf, stock_code, candle_df))

        for future in tqdm(futures, desc='计算因子', total=len(futures)):
            period_df, agg_dict = future.result()
            factor_col_info.update(agg_dict)  # 更新因子列的周期转换规则
            all_factor_df_list.append(period_df)

    # ====================================================================================================
    # 3. 合并因子数据并存储
    # ====================================================================================================
    all_factors_df = pd.concat(all_factor_df_list, ignore_index=True)

    # 转化一下symbol的类型为category，可以加快因子计算速度，节省内存
    # 并且排序和整理index
    all_factors_df = (
        all_factors_df.assign(
            股票代码=all_factors_df["股票代码"].astype("category"),
            股票名称=all_factors_df["股票名称"].astype("category"),
        )
        .sort_values(by=["交易日期", "股票代码"])
        .reset_index(drop=True)
    )
    print(all_factors_df)

    print("💾 存储因子数据...")
    all_factors_df.to_pickle(get_file_path("data", "运行缓存", "因子计算结果.pkl"))
    pd.to_pickle(factor_col_info, get_file_path("data", "运行缓存", "策略因子列信息.pkl"))

    print(f"✅ 因子计算完成，耗时：{time.time() - s_time:.2f}秒\n")


if __name__ == "__main__":
    backtest_config = load_config()
    calculate_factors(backtest_config)
