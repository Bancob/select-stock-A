"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import json
import os
import random
import time

import numpy as np
import pandas as pd
import requests

from core.figure import draw_equity_curve_plotly

pd.set_option('expand_frame_repr', False)
pd.set_option('future.no_silent_downcasting', True)
# print输出中文表头对齐
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)


def cal_fuquan_price(df, fuquan_type='后复权', method=None):
    """
    用于计算复权价格

    参数:
    df (DataFrame): 必须包含的字段：收盘价，前收盘价，开盘价，最高价，最低价
    fuquan_type (str, optional): 复权类型，可选值为 '前复权' 或 '后复权'，默认为 '后复权'
    method (str, optional): 额外计算复权价格的方法，如 '开盘'，默认为 None

    返回:
    DataFrame: 最终输出的df中，新增字段：收盘价_复权，开盘价_复权，最高价_复权，最低价_复权
    """

    # 计算复权因子
    fq_factor = (df['收盘价'] / df['前收盘价']).cumprod()

    # 计算前复权或后复权收盘价
    if fuquan_type == '后复权':  # 如果使用后复权方法
        fq_close = fq_factor * (df.iloc[0]['收盘价'] / fq_factor.iloc[0])
    elif fuquan_type == '前复权':  # 如果使用前复权方法
        fq_close = fq_factor * (df.iloc[-1]['收盘价'] / fq_factor.iloc[-1])
    else:  # 如果给的复权方法非上述两种标准方法会报错
        raise ValueError(f'计算复权价时，出现未知的复权类型：{fuquan_type}')

    # 计算其他价格的复权值
    fq_open = df['开盘价'] / df['收盘价'] * fq_close
    fq_high = df['最高价'] / df['收盘价'] * fq_close
    fq_low = df['最低价'] / df['收盘价'] * fq_close

    # 一次性赋值，提高计算效率
    df = df.assign(
        复权因子=fq_factor,
        收盘价_复权=fq_close,
        开盘价_复权=fq_open,
        最高价_复权=fq_high,
        最低价_复权=fq_low,
    )

    # 如果指定了额外的方法，计算该方法的复权价格
    if method and method != '开盘':
        df[f'{method}_复权'] = df[method] / df['收盘价'] * fq_close

    # 删除中间变量复权因子
    # df.drop(columns=['复权因子'], inplace=True)

    return df


def get_file_in_folder(path, file_type, contains=None, filters=(), drop_type=False):
    """
    获取指定文件夹下的文件

    参数:
    path (str): 文件夹路径
    file_type (str): 文件类型，例如 '.csv' 或 '.txt'
    contains (str, optional): 文件名中需要包含的字符串，默认为 None
    filters (list, optional): 文件名中需要过滤掉的内容，列表形式，默认为空列表
    drop_type (bool, optional): 是否要去除文件扩展名，默认为 False

    返回:
    list: 符合条件的文件名列表
    """
    # 获取文件夹下的所有文件名
    file_list = os.listdir(path)

    # 过滤出指定类型的文件
    file_list = [file for file in file_list if file.endswith(file_type)]

    # 如果指定了包含的字符串，进一步过滤
    if contains:
        file_list = [file for file in file_list if contains in file]

    # 过滤掉指定的内容
    for con in filters:
        file_list = [file for file in file_list if con not in file]

    # 如果需要去除文件扩展名
    if drop_type:
        file_list = [file[:file.rfind('.')] for file in file_list]

    return file_list


def import_index_data(path, date_range=(None, None), max_param=0):
    """
    导入指数数据并进行预处理

    参数:
    path (str): 指数数据文件的路径
    date_range (list, optional): 回测的时间范围，格式为 [开始日期, 结束日期]，默认为 [None, None]
    max_param (int, optional): 因子的最大周期数，用于控制开始日期，确保rolling类因子，前置数据不是NaN，默认为 0

    返回:
    DataFrame: 处理后的指数数据，包含交易日期和指数涨跌幅
    """
    # 导入指数数据
    df_index = pd.read_csv(path, parse_dates=['candle_end_time'], encoding='gbk')

    # 计算涨跌幅
    df_index['指数涨跌幅'] = df_index['close'].pct_change()
    # 第一天的指数涨跌幅是开盘买入的涨跌幅
    df_index['指数涨跌幅'] = df_index['指数涨跌幅'].fillna(value=df_index['close'] / df_index['open'] - 1)

    # 保留必要的列
    df_index = df_index[['candle_end_time', '指数涨跌幅']]

    # 去除涨跌幅为空的行
    df_index.dropna(subset=['指数涨跌幅'], inplace=True)

    # 重命名列
    df_index.rename(columns={'candle_end_time': '交易日期'}, inplace=True)

    # 根据日期范围过滤数据
    if date_range[0]:
        if max_param == 0:
            df_index = df_index[df_index['交易日期'] >= pd.to_datetime(date_range[0])]
            # print(f'💡 回测开始时间：{df_index["交易日期"].iloc[0].strftime("%Y-%m-%d")}')
        # 当提供了周期数之后
        else:
            # 计算新的开始日期
            start_index = df_index[df_index['交易日期'] >= pd.to_datetime(date_range[0])].index[0]
            start_date = df_index['交易日期'][start_index].strftime("%Y-%m-%d")

            # 移动周期，获取可以让因子数值不为Nan的开始日期
            shifted_date = df_index['交易日期'].shift(max_param)
            shifted_date.bfill(inplace=True)  # 前置数据不是NaN

            # 过滤前置数据
            df_index = df_index[df_index['交易日期'] >= shifted_date[start_index]]
            new_start_date = df_index['交易日期'].iloc[0].strftime("%Y-%m-%d")
            print(f'💡 回测开始时间：{start_date}，移动{max_param}个周期，最新交易日：{new_start_date}')
    if date_range[1]:
        df_index = df_index[df_index['交易日期'] <= pd.to_datetime(date_range[1])]
        # print(f'回测结束时间：{df_index["交易日期"].iloc[-1].strftime("%Y-%m-%d")}')

    # 按时间排序并重置索引
    df_index.sort_values(by=['交易日期'], inplace=True)
    df_index.reset_index(inplace=True, drop=True)

    return df_index


def merge_with_index_data(df, index_data, fill_0_list=()):
    """
    原始股票数据在不交易的时候没有数据。
    将原始股票数据和指数数据合并，可以补全原始股票数据没有交易的日期。

    参数:
    df (DataFrame): 股票数据
    index_data (DataFrame): 指数数据
    extra_fill_0_list (list, optional): 合并时需要填充为0的字段，默认为空列表

    返回:
    DataFrame: 合并后的股票数据，包含补全的日期
    """
    # 将股票数据和指数数据合并，结果已经排序
    df = pd.merge(left=df, right=index_data, on='交易日期', how='right', sort=True, indicator=True)

    # 对开、高、收、低、前收盘价价格进行补全处理
    # 用前一天的收盘价，补全收盘价的空值
    close = df['收盘价'].ffill()
    # 用收盘价补全开盘价、最高价、最低价的空值
    df = df.assign(
        收盘价=close,
        开盘价=df['开盘价'].fillna(value=close),
        最高价=df['最高价'].fillna(value=close),
        最低价=df['最低价'].fillna(value=close),
        均价=df['均价'].fillna(value=close),
        # 补全前收盘价
        前收盘价=df['前收盘价'].fillna(value=close.shift()),
    )

    # 如果前面算过复权，复权价也做fillna
    if '收盘价_复权' in df.columns:
        fq_cols = dict()
        fq_cols['收盘价_复权'] = df['收盘价_复权'].ffill()
        for col in ['开盘价_复权', '最高价_复权', '最低价_复权']:
            if col in df.columns:
                fq_cols[col] = df[col].fillna(value=fq_cols['收盘价_复权'])
        df = df.assign(**fq_cols)

    # 将停盘时间的某些列，数据填补为0
    fill_0_list = list(set(['成交量', '成交额', '涨跌幅'] + fill_0_list))
    df.loc[:, fill_0_list] = df[fill_0_list].fillna(value=0)

    # 用前一天的数据，补全其余空值
    df.ffill(inplace=True)

    # 去除上市之前的数据
    df = df[df['股票代码'].notnull()]

    # 判断计算当天是否交易
    df['是否交易'] = np.int8(1)
    df.loc[df['_merge'] == 'right_only', '是否交易'] = np.int8(0)
    del df['_merge']
    df.reset_index(drop=True, inplace=True)

    return df


def transfer_to_period_data(df, period, extra_agg_dict=None):
    """
    将日线数据转换为相应的周期数据

    参数:
    df (DataFrame): 原始数据
    period (str): 需要转换的数据周期，例如 'W' 表示周频，'M' 表示月频
    extra_agg_dict (dict, optional): 额外的聚合字典，默认为空字典

    返回:
    DataFrame: 转换后的周期数据
    """
    # 创造一列用于周期末的时间计算
    if extra_agg_dict is None:
        extra_agg_dict = {}
    df['周期最后交易日'] = df['交易日期']

    # agg_dict 是周期内数据整合所必须的字典。数据整合方法包括:
    # first(保留周期内第一条数据)、max(保留周期内最大的数据)、min(保留周期内最小的数据)、sum(周期内所有数据求和)、last(保留最新数据)
    agg_dict = {
        # 必须列
        '周期最后交易日': 'last',
        '股票代码': 'last',
        '股票名称': 'last',
        '是否交易': ['last', 'sum', 'count'],  # 统计局和计算是否交易，交易天数，市场交易天数
        '开盘价': 'first',
        '最高价': 'max',
        '最低价': 'min',
        '收盘价': 'last',
        '成交额': 'sum',
        '流通市值': 'last',
        '总市值': 'last',
        '上市至今交易天数': 'last',
        '下日_是否交易': 'last',
        '下日_开盘涨停': 'last',
        '下日_是否ST': 'last',
        # '下日_是否S': 'last',
        '下日_是否退市': 'last',
        # '下日_开盘买入涨跌幅': 'last',
        '复权因子': 'last'
    }
    # 合并额外的聚合字典
    agg_dict = {**agg_dict, **extra_agg_dict}

    # 根据周期offset情况，进行groupby后，得到对应的nD/周线/月线数据
    group_tag = f'{period}起始日'
    period_df = df.groupby(group_tag).agg(agg_dict)
    period_df.columns = [
        '是否交易' if col == ('是否交易', 'last') else
        '交易天数' if col == ('是否交易', 'sum') else
        '市场交易天数' if col == ('是否交易', 'count') else
        col[0] if isinstance(col, tuple) else col
        for col in period_df.columns
    ]  # 重命名列名，聚合之后的数据列名是这样的：... (股票名称, last)  (是否交易, last)  (是否交易, sum)  (是否交易, count)  (开盘价, first)  (最高价, max) ...

    # 计算其他因子
    # 计算周期资金曲线
    # period_df['每天涨跌幅'] = df.groupby(group_tag)['涨跌幅'].apply(lambda x: list(x))

    # 国庆节、春节等假期可能导致A股整周不交易，从而出现空的周期，需要删除这些空的周期
    period_df.dropna(subset=['股票代码'], inplace=True)

    # 计算涨跌幅
    period_pct_change = period_df['复权因子'].pct_change(fill_method=None)  # 用复权收盘价计算
    first_ret = (np.array(period_pct_change.iloc[0]) + 1).prod() - 1  # 第一个持仓周期的复利涨跌幅
    period_pct_change = period_pct_change.fillna(value=first_ret)  # pct_change()算的第一天是nan，但是实际是存在涨跌幅的，这里做个修正
    period_df.rename(columns={'周期最后交易日': '交易日期'}, inplace=True)

    period_df.assign(
        涨跌幅=period_pct_change,
        下周期涨跌幅=period_pct_change.shift(-1)
    )

    # 重置索引
    period_df.reset_index(drop=True, inplace=True)

    # 计算下周期每天涨幅
    # period_df['下周期每天涨跌幅'] = period_df['每天涨跌幅'].shift(-1)

    # 只保留交易日的数据
    period_df = period_df[period_df['是否交易'] == 1]

    return period_df


def cal_zdt_price(df):
    """
    计算股票当天的涨跌停价格。在计算涨跌停价格的时候，按照严格的四舍五入。
    包含ST股，但是不包含新股。

    涨跌停制度规则:
        ---2020年8月23日
        非ST股票 10%
        ST股票 5%

        ---2020年8月24日至今
        普通非ST股票 10%
        普通ST股票 5%

        科创板（sh68） 20%（一直是20%，不受时间限制）
        创业板（sz3） 20%
        科创板和创业板即使ST，涨跌幅限制也是20%

        北交所（bj） 30%

    参数:
    df (DataFrame): 必须得是日线数据。必须包含的字段：前收盘价，开盘价，最高价，最低价

    返回:
    DataFrame: 包含涨停价、跌停价、一字涨停、一字跌停、开盘涨停、开盘跌停等字段的DataFrame
    """
    from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
    # 计算普通股票的涨停价和跌停价
    cond = df['股票名称'].str.contains('ST')
    df['涨停价'] = df['前收盘价'] * 1.1
    df['跌停价'] = df['前收盘价'] * 0.9
    df.loc[cond, '涨停价'] = df['前收盘价'] * 1.05
    df.loc[cond, '跌停价'] = df['前收盘价'] * 0.95

    # 计算科创板和新规后的创业板的涨停价和跌停价
    rule_kcb = df['股票代码'].str.contains('sh68')  # 科创板
    new_rule_cyb = (df['交易日期'] > pd.to_datetime('2020-08-23')) & df['股票代码'].str.contains('sz3')  # 新规后的创业板
    df.loc[rule_kcb | new_rule_cyb, '涨停价'] = df['前收盘价'] * 1.2
    df.loc[rule_kcb | new_rule_cyb, '跌停价'] = df['前收盘价'] * 0.8

    # 计算北交所的涨停价和跌停价
    cond_bj = df['股票代码'].str.contains('bj')
    df.loc[cond_bj, '涨停价'] = df['前收盘价'] * 1.3
    df.loc[cond_bj, '跌停价'] = df['前收盘价'] * 0.7

    # 四舍五入
    def price_round(x):
        return float(Decimal(x + 1e-7).quantize(Decimal('1.00'), ROUND_HALF_UP))
    df.loc[~cond_bj, '涨停价'] = df['涨停价'].apply(price_round)
    df.loc[~cond_bj, '跌停价'] = df['跌停价'].apply(price_round)

    # 北交所特殊处理：北交所的规则是涨跌停价格小于等于30%，不做四舍五入，所以超过30%的部分需要减去1分钱
    def price_round_bj(x):
        return float(Decimal(x).quantize(Decimal('0.00'), rounding=ROUND_DOWN))
    df.loc[cond_bj, '涨停价'] = df['涨停价'].apply(price_round_bj)
    df.loc[cond_bj, '跌停价'] = df['跌停价'].apply(price_round_bj)

    # 判断是否一字涨停
    df['一字涨停'] = False
    df.loc[df['最低价'] >= df['涨停价'], '一字涨停'] = True

    # 判断是否一字跌停
    df['一字跌停'] = False
    df.loc[df['最高价'] <= df['跌停价'], '一字跌停'] = True

    # 判断是否开盘涨停
    df['开盘涨停'] = False
    df.loc[df['开盘价'] >= df['涨停价'], '开盘涨停'] = True

    # 判断是否开盘跌停
    df['开盘跌停'] = False
    df.loc[df['开盘价'] <= df['跌停价'], '开盘跌停'] = True

    return df


def get_trade_date(index_data: pd.DataFrame) -> pd.DataFrame:
    # ==获取交易日历
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_ZGXSRL",
        "columns": "ALL",
        "pageSize": 200,
        "sortColumns": "SDATE",
        "sortTypes": -1,
        "callback": f"jQuery1123{random.randint(10000000000000000, 99999999999999999)}_" + str(int(time.time() * 1000)),
        # 动态生成时间戳
        "_": int(time.time() * 1000)  # 动态生成时间戳
    }

    response = requests.get(url, params=params)
    content = response.text

    # 去除JSONP封装
    start = content.find('(') + 1
    end = content.rfind(')')
    json_data = json.loads(content[start:end])

    # ==处理交易日历
    holiday_df = pd.DataFrame(json_data['result']['data'])
    holiday_df = holiday_df[holiday_df['MKT'] == 'A股'].sort_values('SDATE').reset_index(drop=True)
    holiday_df['SDATE'] = pd.to_datetime(holiday_df['SDATE'])
    holiday_df['EDATE'] = pd.to_datetime(holiday_df['EDATE'])
    # 日历从最小的时间点开始
    start = holiday_df['SDATE'].min()
    # 截止到最大的时间点的年底
    end = pd.to_datetime(f"{holiday_df['EDATE'].max().year}-12-31")

    # 创建日历，并标记不交易的日期
    date_range = pd.DataFrame(pd.date_range(start=start, end=end), columns=['交易日期'])
    for i in holiday_df.index:
        con = (date_range['交易日期'] >= holiday_df.loc[i, 'SDATE']) & (
                date_range['交易日期'] <= holiday_df.loc[i, 'EDATE'])
        date_range.loc[con, '交易日期'] = np.nan

    # 正常的周末也是不交易的
    con = date_range['交易日期'].dt.weekday.isin([5, 6])
    date_range.loc[con, '交易日期'] = np.nan
    date_range = date_range[date_range['交易日期'].notnull()]

    # ==合并交易日
    trade_date_df = pd.concat([index_data[['交易日期']], date_range], ignore_index=True)
    trade_date_df = trade_date_df.drop_duplicates(subset='交易日期', keep='first').reset_index(drop=True)
    return trade_date_df


def save_latest_result(conf, select_result_df):
    # 导入指数
    index_data = conf.read_index_with_trading_date()
    last_date = select_result_df['交易日期'].max()
    period_end = index_data[index_data['交易日期'] == last_date][f'{conf.strategy.hold_period_name}终止日'].iloc[0]

    if pd.isnull(conf.end_date) and period_end:
        # 获得最新的选股结果
        new_select_df = select_result_df[select_result_df['交易日期'] == last_date].rename(
            columns={'交易日期': '选股日期'})
        # 次交易日才是真正的交易日期
        trade_date = index_data[index_data['交易日期'] == last_date]['次交易日'].iloc[0]
        new_select_df['交易日期'] = trade_date
        # 只保留需要的列
        keep_cols = ['选股日期', '交易日期', '股票代码', '股票名称']
        new_select_df = new_select_df[keep_cols]

        new_result_path = conf.get_result_folder() / '最新选股结果.csv'
        if new_result_path.exists():
            old_result_df = pd.read_csv(new_result_path, encoding='utf-8-sig', parse_dates=['选股日期', '交易日期'])
            # 删除重复的选股结果
            con1 = old_result_df['选股日期'] != last_date
            con2 = old_result_df['交易日期'] != trade_date
            old_result_df = old_result_df[con1 & con2]
            result_df = pd.concat([old_result_df, new_select_df], ignore_index=True)
        else:
            result_df = new_select_df

        result_df.to_csv(new_result_path, encoding='utf-8-sig', index=False)


def select_analysis(conf, select_df: pd.DataFrame, top_n=10, show_plot=True) -> None:
    # 新增函数：分析每年的选股情况

    # 新增：获取所有股票最新的名字
    last_stock_name = pd.DataFrame(select_df.groupby('股票代码')['股票名称'].last()).reset_index()
    # 每年选股次数n的股票
    select_df['年份'] = select_df['交易日期'].dt.year
    # 每年的次数
    year_count = pd.DataFrame(select_df.groupby(['年份', '股票代码'])['股票代码'].count()).rename(
        columns={'股票代码': '选中次数'}).reset_index()
    # 合并股票名称
    year_count = year_count.merge(last_stock_name, on='股票代码', how='left')
    # 计算选中次数排名
    year_count['选中次数_排名'] = year_count.groupby('年份')['选中次数'].rank(method='min', ascending=False)
    year_count = year_count[year_count['选中次数_排名'] <= top_n]
    # 每年选择排名靠前的股票
    groups = year_count.groupby('年份')
    years = pd.DataFrame()
    for t, g in groups:
        inx = 0 if pd.isnull(years.index.max()) else years.index.max() + 1
        years.loc[inx, '年份'] = str(int(t))
        g = g.sort_values(by='选中次数_排名').reset_index()
        g['历年选股最多'] = g['股票名称'].astype(str) + '_' + g['选中次数'].astype(str) + ' '
        txt = g['历年选股最多'].sum()
        years.loc[inx, '历年选股最多'] = txt
    print(years)
    years.to_csv(conf.get_result_folder() / f'{conf.strategy.name}历年选股最多.csv', encoding='utf-8-sig')

    # 计算每天的平均市值 & 平均分位数
    period_market_value = select_df.groupby('交易日期').agg({'总市值': 'mean', '市值分位': 'mean'}).reset_index()
    period_market_value['总市值'] /= 100000000
    # 画图
    data_dict = {'平均市值': '总市值'}
    ds = period_market_value['总市值']
    txt = f'均值：{ds.mean():.2f}（亿）  中值：{ds.median():.2f}（亿）  最小值：{ds.min():.2f}（亿）  最大值：{ds.max():.2f}（亿）'
    draw_equity_curve_plotly(period_market_value, data_dict, '交易日期', desc=txt, title='持仓平均市值',
              path=conf.get_result_folder() / '平均市值.html', show=show_plot)

    data_dict = {'平均市值分位数': '市值分位'}
    ds = period_market_value['市值分位']
    txt = f'均值：{ds.mean():.2f}  中值：{ds.median():.2f}  最小值：{ds.min():.2f}  最大值：{ds.max():.2f}'
    draw_equity_curve_plotly(period_market_value, data_dict, '交易日期', desc=txt, title='持仓平均市值分位数',
              path=conf.get_result_folder() / '平均市值分位数.html', show=show_plot)
