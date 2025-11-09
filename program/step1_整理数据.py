"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import time
import warnings
from concurrent.futures.process import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from config import n_jobs
from core.model.backtest_config import load_config, BacktestConfig
from core.utils.path_kit import get_file_path
from core.market_essentials import cal_fuquan_price, cal_zdt_price, merge_with_index_data

# ====================================================================================================
# ** 配置与初始化 **
# 设置必要的显示选项及忽略警告，以优化代码输出的阅读体验
# ====================================================================================================
warnings.filterwarnings("ignore")  # 忽略不必要的警告
pd.set_option("expand_frame_repr", False)  # 使数据框在控制台显示不换行
pd.set_option("display.unicode.ambiguous_as_wide", True)
pd.set_option("display.unicode.east_asian_width", True)

# 定义股票数据所需的列
STOCK_DATA_COLS = [
    "股票代码",
    "股票名称",
    "交易日期",
    "开盘价",
    "最高价",
    "最低价",
    "收盘价",
    "前收盘价",
    "成交量",
    "成交额",
    "流通市值",
    "总市值",
]


def prepare_data(conf: BacktestConfig):
    start_time = time.time()  # 记录数据准备开始时间

    # 排除板块
    stock_hints = []
    for board, name in [("kcb", "科创板"), ("cyb", "创业板"), ("bj", "北交所")]:
        if board in conf.excluded_boards:
            print(f"🗑️ [策略配置] 需要排除`{name}`")
            stock_hints.append(name)
    stock_hint = "、".join(stock_hints) if stock_hints else ""
    if stock_hint:
        stock_hint = f"不包括{stock_hint}"
    else:
        stock_hint = "包括所有板块"

    # 1. 获取股票代码列表
    stock_code_list = []  # 用于存储股票代码
    # 遍历文件夹下，所有csv文件
    for filename in conf.stock_data_path.glob("*.csv"):
        # 排除隐藏文件
        if filename.stem.startswith("."):
            continue
        # 判断是否为北交所股票（代码以 'bj' 开头）
        if filename.stem.startswith("bj") and ("bj" in conf.excluded_boards):
            continue
        # 判断是否为科创板股票（代码以 'sh68' 开头）
        if filename.stem.startswith("sh68") and ("kcb" in conf.excluded_boards):
            continue
        # 判断是否为科创板股票（代码以 'sz30' 开头）
        if filename.stem.startswith("sz30") and ("cyb" in conf.excluded_boards):
            continue
        stock_code_list.append(filename.stem)
    stock_code_list = sorted(stock_code_list)
    print(f"📂 读取到股票数量：{len(stock_code_list)}，{stock_hint}")

    # 2. 读取并处理指数数据，确保股票数据与指数数据的时间对齐
    index_data = conf.read_index_with_trading_date()
    all_candle_data_dict = {}  # 用于存储所有股票的K线数据
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = []
        for code in stock_code_list:
            file_path = conf.stock_data_path / f'{code}.csv'
            futures.append(executor.submit(pre_process, file_path, index_data))

        for future in tqdm(futures, desc='预处理数据', total=len(futures)):
            df = future.result()
            if not df.empty:
                code = df['股票代码'].iloc[0]
                all_candle_data_dict[code] = df  # 仅存储非空数据

    # 3. 缓存预处理后的数据
    cache_path = get_file_path("data", "运行缓存", "股票预处理数据.pkl")
    print("💾 保存到缓存文件...", cache_path)
    pd.to_pickle(all_candle_data_dict, cache_path)

    # 4. 准备并缓存pivot透视表数据，用于后续回测
    print("ℹ️ 准备透视表数据...")
    market_pivot_dict = make_market_pivot(all_candle_data_dict)
    pivot_cache_path = get_file_path("data", "运行缓存", "全部股票行情pivot.pkl")
    print("💾 保存到缓存文件...", pivot_cache_path)
    pd.to_pickle(market_pivot_dict, pivot_cache_path)

    print(f"✅ 数据准备耗时：{time.time() - start_time} 秒\n")


def pre_process(stock_file_path: str | Path, index_data: pd.DataFrame) -> pd.DataFrame:
    """
    对股票数据进行预处理，包括合并指数数据和计算未来交易日状态。

    参数:
    stock_file_path (str | Path): 股票日线数据的路径
    index_data (DataFrame): 指数数据

    返回:
    df (DataFrame): 预处理后的数据
    """
    # 计算涨跌幅、换手率等关键指标
    df = pd.read_csv(stock_file_path, encoding='gbk', skiprows=1, parse_dates=['交易日期'], usecols=STOCK_DATA_COLS)
    pct_change = df['收盘价'] / df['前收盘价'] - 1
    turnover_rate = df['成交额'] / df['流通市值']
    trading_days = df.index.astype('int') + 1
    avg_price = df['成交额'] / df['成交量']

    # 一次性赋值提高性能
    df = df.assign(涨跌幅=pct_change, 换手率=turnover_rate, 上市至今交易天数=trading_days, 均价=avg_price)

    # 复权价计算及涨跌停价格计算
    df = cal_fuquan_price(df, fuquan_type="后复权")
    df = cal_zdt_price(df)

    # 合并股票与指数数据，补全停牌日期等信息
    df = merge_with_index_data(df, index_data.copy(), fill_0_list=["换手率"])

    # 股票退市时间小于指数开始时间，就会出现空值
    if df.empty:
        # 如果出现这种情况，返回空的DataFrame用于后续操作
        return pd.DataFrame(columns=STOCK_DATA_COLS)

    # 计算开盘买入涨跌幅和未来交易日状态
    df = df.assign(
        下日_是否交易=df["是否交易"].astype("int8").shift(-1),
        下日_一字涨停=df["一字涨停"].astype("int8").shift(-1),
        下日_开盘涨停=df["开盘涨停"].astype("int8").shift(-1),
        下日_是否ST=df["股票名称"].str.contains("ST").astype("int8").shift(-1),
        下日_是否S=df["股票名称"].str.contains("S").astype("int8").shift(-1),
        下日_是否退市=df["股票名称"].str.contains("退").astype("int8").shift(-1),
    )

    # 处理最后一根K线的数据：最后一根K线默认沿用前一日的数据
    state_cols = ["下日_是否交易", "下日_是否ST", "下日_是否S", "下日_是否退市"]
    df[state_cols] = df[state_cols].ffill()

    # 清理退市数据，保留有效交易数据
    if ("退" in df["股票名称"].iloc[-1]) or ("S" in df["股票名称"].iloc[-1]):
        if df["成交额"].iloc[-1] == 0 and np.all(df["成交额"] == 0):
            return pd.DataFrame(columns=STOCK_DATA_COLS)
        # @马超 同学于2024年11月20日提供退市逻辑优化处理。
        # 解决因为起始时间太靠前，导致数据可能为空报错的问题，加入了empty情况的容错
        df_tmp = df[(df["成交额"] != 0) & (df["成交额"].shift(-1) == 0)]
        if df_tmp.empty:
            end_date = df["交易日期"].iloc[-1]
        else:
            end_date = df_tmp.iloc[-1]["交易日期"]
        df = df[df["交易日期"] <= end_date]

    return df if not df.empty else pd.DataFrame(columns=STOCK_DATA_COLS)


def make_market_pivot(market_dict):
    """
    构建市场数据的pivot透视表，便于回测计算。

    参数:
    market_dict (dict): 股票K线数据字典

    返回:
    dict: 包含开盘价、收盘价及前收盘价的透视表数据
    """
    cols = ["交易日期", "股票代码", "开盘价", "收盘价", "前收盘价"]
    df_list = [df[cols].dropna(subset="股票代码") for df in market_dict.values()]
    df_all_market = pd.concat(df_list, ignore_index=True)
    df_open = df_all_market.pivot(values="开盘价", index="交易日期", columns="股票代码")
    df_close = df_all_market.pivot(values="收盘价", index="交易日期", columns="股票代码")
    df_preclose = df_all_market.pivot(values="前收盘价", index="交易日期", columns="股票代码")

    return {"open": df_open, "close": df_close, "preclose": df_preclose}


if __name__ == "__main__":
    backtest_config = load_config()
    prepare_data(backtest_config)
