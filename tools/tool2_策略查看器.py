"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import datetime
import os
import warnings

import numpy as np
import openpyxl
import pandas as pd

import tools.utils.pfunctions as PFun
import tools.utils.tfunctions as tFun
from core.model.backtest_config import load_config, BacktestConfig
from core.utils.path_kit import get_file_path

# ====================================================================================================
# ** 配置与初始化 **
# 设置必要的显示选项及忽略警告，以优化代码输出的阅读体验
# ====================================================================================================
warnings.filterwarnings('ignore')  # 忽略不必要的警告
pd.set_option('expand_frame_repr', False)  # 使数据框在控制台显示不换行
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)


def process_select_data(conf: BacktestConfig, k_start: str, k_end: str) -> pd.DataFrame:
    """
    对选股数据进行预处理,主要是计算下周期持有日期、持有天数、下周期每日涨跌幅、下周期涨跌幅等信息
    :param conf: 回测配置信息
    :param k_start: 开始日期
    :param k_end: 结束日期
    :return select:
         选股结果数据框
    """
    # ===设置策略文件的存储路径
    select_path = get_file_path(f'data/回测结果/{conf.strategy.name}/{conf.strategy.name}选股结果.csv',
                                auto_create=True)

    # ===读取数据 & 截取数据
    select = pd.read_csv(select_path, parse_dates=['交易日期'], index_col=0)
    select = select[select['交易日期'] >= pd.to_datetime(k_start)]
    select = select[select['交易日期'] <= pd.to_datetime(k_end)]

    # ===获取指数数据
    index_data = conf.read_index_with_trading_date()

    # ===计算周期数据，处理买卖日期
    time_bench = pd.DataFrame()
    time_bench['交易日期'] = index_data['交易日期']
    time_bench['持有开始'] = time_bench['交易日期'].copy()
    time_bench['持有到期'] = time_bench['交易日期'].copy()
    time_bench['周期标识'] = index_data[f"{conf.strategy.hold_period_name}起始日"].copy()
    period_df = time_bench.groupby('周期标识').agg({'持有开始': 'first', '持有到期': 'last'}).reset_index()
    period_df['持有周期'] = period_df['持有开始'].dt.date.apply(str) + '--' + period_df['持有到期'].dt.date.apply(str)
    period_df['持有天数'] = list(time_bench.groupby('周期标识').size())
    period_df = period_df[period_df['持有天数'] != 0]
    period_df['持有周期'] = period_df['持有周期'].shift(-1)
    period_df['持有天数'] = period_df['持有天数'].shift(-1)
    select = pd.merge(left=select, right=period_df[['持有到期', '持有周期', '持有天数']], left_on='交易日期',
                      right_on='持有到期', how='left')

    # === 利用数据透视表计算股票的下周期涨跌幅
    select[['下一持有周期开始日期', '下一持有周期结束日期']] = select['持有周期'].str.split('--', expand=True).apply(
        pd.to_datetime)
    stock_ts_path = get_file_path('data/运行缓存/全部股票行情pivot.pkl')  # 获取全部股票行情的pivot表

    # 利用前收盘价和收盘价计算收盘价后复权数据
    stock_ts_dict = pd.read_pickle(stock_ts_path)
    stock_ts_close = stock_ts_dict['close'][select['股票代码'].unique()].stack().reset_index(name='close')
    stock_ts_preclose = stock_ts_dict['preclose'][select['股票代码'].unique()].stack().reset_index(name='preclose')
    stock_data = stock_ts_preclose.merge(stock_ts_close, on=['交易日期', '股票代码'], how='left')
    stock_data.sort_values(by=['股票代码', '交易日期'], inplace=True)
    stock_data['复权因子'] = stock_data.groupby('股票代码').apply(
        lambda df: (df['close'] / df['preclose']).cumprod()).reset_index(level=0, drop=True)
    stock_data['close_fq'] = stock_data.groupby('股票代码').apply(
        lambda df: df['复权因子'] * (df['close'].iloc[0] / df['复权因子'].iloc[0])).reset_index(level=0, drop=True)
    stock_ts = stock_data.pivot(index='交易日期', columns='股票代码', values='close_fq')

    # 利用后复权数据计算每天的涨跌幅
    stock_ts_ret = stock_ts.pct_change()  # 利用后复权数据计算每天的涨跌幅
    select['下周期每天涨跌幅'] = select[['股票代码', '下一持有周期开始日期', '下一持有周期结束日期']].apply(
        lambda row: stock_ts_ret.loc[row['下一持有周期开始日期']:row['下一持有周期结束日期'], row['股票代码']].tolist(),
        axis=1)  # 获取持有股票的下周期每天涨跌幅
    select['下周期涨跌幅'] = select['下周期每天涨跌幅'].apply(lambda x: np.prod(np.array(x) + 1) - 1)  # 计算下周期涨跌幅
    select.drop(['下一持有周期结束日期', '下一持有周期开始日期'], inplace=True, axis=1)
    return select


def select_analysis(conf: BacktestConfig, k_start: str, k_end: str):
    """
    对选股结果进行分析
    :param conf: 回测配置信息
    :param k_start: 需要分析的开始日期
    :param k_end: 需要分析的结束日期
    :return:
         select: 选股结果数据框
         save_path: 保存路径
    """
    # ===对选股数据结果进行预处理操作
    select = process_select_data(conf, k_start, k_end)

    # === 计算每只股票的分析结果
    groups = select.groupby('股票代码')
    res_list = []  # 储存分组结果的list
    for t, g in groups:  # 遍历各个分组
        # ===分组处理数据
        g.sort_values(by='交易日期', inplace=True)

        # ===统计结果
        res = pd.DataFrame()  # 需要返回的结果
        res.loc[0, '股票代码'] = t  # 股票代码
        res.loc[0, '股票名称'] = g['股票名称'].iloc[-1]
        res.loc[0, '选中次数'] = len(g['交易日期'].unique())
        res.loc[0, '累计持股天数'] = g['持有天数'].sum()
        res.loc[0, '累计持股收益'] = (g['下周期涨跌幅'] + 1).prod() - 1
        res.loc[0, '次均收益率_复利'] = (res.loc[0, '累计持股收益'] + 1) ** (1 / res.loc[0, '选中次数']) - 1
        res.loc[0, '次均收益率_单利'] = g['下周期涨跌幅'].mean()
        res.loc[0, '日均收益率_复利'] = (res.loc[0, '累计持股收益'] + 1) ** (1 / res.loc[0, '累计持股天数']) - 1
        res.loc[0, '日均收益率_单利'] = np.sum(g['下周期每天涨跌幅'].sum()) / res.loc[0, '累计持股天数']
        res.loc[0, '首次选中时间'] = g['交易日期'].dt.date.iloc[0]
        res.loc[0, '最后选中时间'] = g['交易日期'].dt.date.iloc[-1]
        res['持有周期'] = ''  # 小tips：需要往DataFrame的cell里面插入list，这一列需要是object类型（所以这里给了''，字符串就是object）
        res.at[0, '持有周期'] = g['持有周期'].to_list()  # 往数据中插入list时，需要用at函数，loc不行。

        # 将计算的结果添加到结果汇总中
        res_list.append(res)

    # =====汇总所有结果
    all_res = pd.concat(res_list, ignore_index=True)

    # =====针对分析结果进行进一步分析
    describe = pd.DataFrame()  # 分析结果储存的df

    # 1.分析数据
    describe.loc[0, '选股数'] = all_res.shape[0]
    describe.loc[0, '平均选中次数'] = all_res['选中次数'].mean()
    describe.loc[0, '平均累计持股天数'] = all_res['累计持股天数'].mean()
    describe.loc[0, '平均日均收益率'] = all_res['日均收益率_复利'].mean()
    describe.loc[0, '平均次均收益率'] = all_res['次均收益率_复利'].mean()
    describe.loc[0, '平均累计持股收益'] = all_res['累计持股收益'].mean()
    describe.loc[0, '选股胜率'] = all_res[all_res['累计持股收益'] > 0].shape[0] / describe.loc[0, '选股数']

    # =====结果保存
    # 保存数据的文件夹是否存在
    save_path = get_file_path(f'data/分析结果/{conf.strategy.name}_{conf.strategy.period_type}_{k_start}_{k_end}/')
    os.makedirs(save_path, exist_ok=True)

    # 保存数据
    describe.T.to_csv(save_path / '02_分析汇总.csv', encoding='gbk')

    # 打印分析结果
    print(f'✅ 选股结果已保存到本地，选股结果统计分析如下：\n {describe.T}')
    return all_res, save_path


def plot_stock_kline(conf: BacktestConfig, k_start: str, k_end: str, add_days=120) -> None:
    """
    绘制股票的K线图
    :param conf: 回测配置信息
    :param k_start: 开始时间
    :param k_end: 结束时间
    :param add_days: 向前/向后扩展K线天数
    :return: None
    """
    start_time = datetime.datetime.now()  # 记录开始时间

    all_res, save_path = select_analysis(conf, k_start=k_start, k_end=k_end)
    # 绘制的时候K线向历史前后多扩展add_days天
    d_start = pd.to_datetime(k_start) - pd.to_timedelta(f'{add_days}d')  # K线开始时间
    d_end = pd.to_datetime(k_end) + pd.to_timedelta(f'{add_days}d')  # K线结束时间

    # 读取全部k线数据
    all_stock_dict = pd.read_pickle(get_file_path('data/运行缓存/股票预处理数据.pkl'))

    fig_save_path = save_path / f'选股行情图/'
    os.makedirs(fig_save_path, exist_ok=True)

    total_stock_num = all_res.shape[0]

    # 开始遍历每一行数据画图
    for i in all_res.index:
        # 获取币种名称
        code = all_res.loc[i, '股票代码']
        name = all_res.loc[i, '股票名称']
        print(f'正在绘制：第{i + 1}/{total_stock_num}个 {code}_{name}')
        # 读取股票信息
        df = all_stock_dict[code]
        df = df[(df['交易日期'] >= d_start) & (df['交易日期'] <= d_end)]
        df['开盘买入涨跌幅'] = df['收盘价'] / df['开盘价'] - 1
        # 获取所有的买入时间点
        open_times = [pd.to_datetime(time_range.split('--')[0]) for time_range in all_res.loc[i, '持有周期']]
        # 获取所有的卖出时间点
        close_times = [pd.to_datetime(time_range.split('--')[1]) for time_range in all_res.loc[i, '持有周期']]
        # 在数据中加入买入信息
        df.loc[df['交易日期'].isin(open_times), '买入时间'] = '买入'
        # 在数据中加入卖出信息
        df.loc[df['交易日期'].isin(close_times), '卖出时间'] = '卖出'
        # 产生交易表
        trade_df = tFun.get_trade_info(df, open_times, close_times, buy_method='开盘')
        # 绘制K线图
        PFun.draw_hedge_signal_plotly(df, fig_save_path, f'{code}_{name}', trade_df, all_res.loc[i])
        # 创建超链接，方便在通过Excel点击查看
        file_path = f'选股行情图/{code}_{name}.html'
        all_res.loc[i, '文件路径'] = file_path
    all_res.to_excel(save_path / '01_选股分析结果.xlsx', index=False)
    excel_path = save_path / '01_选股分析结果.xlsx'
    # 加载已保存的 Excel 文件
    wb = openpyxl.load_workbook(excel_path)
    ws = wb['Sheet1']

    # 在 'File Path' 列中插入超链接
    for idx, row in all_res.iterrows():
        idx: int  # 强制类型转换
        file_path = row['文件路径']
        cell = ws.cell(row=idx + 2, column=2)  # Excel 中的行和列从 1 开始，所以 idx + 2
        cell.hyperlink = file_path
        cell.style = 'Hyperlink'

    # 保存 Excel 文件
    wb.save(excel_path)

    print(f'✅ 所选股票K线图绘制完毕，耗时{(datetime.datetime.now() - start_time).total_seconds():.2f}秒')
    print('✅ 选股分析结果已保存到本地，请打开对应的Excel文件查看')


if __name__ == '__main__':
    backtest_config = load_config()
    plot_stock_kline(backtest_config, k_start='2023-08-28', k_end='2024-01-01', add_days=120)
