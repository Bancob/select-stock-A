"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import math
import pandas as pd
from pathlib import Path
from typing import Union


def float_num_process(num, return_type=float, keep=2, max=5):
    """
    针对绝对值小于1的数字进行特殊处理，保留非0的N位（N默认为2，即keep参数）
    输入  0.231  输出  0.23
    输入  0.0231  输出  0.023
    输入  0.00231  输出  0.0023
    如果前面max个都是0，直接返回0.0
    :param num: 输入的数据
    :param return_type: 返回的数据类型，默认是float
    :param keep: 需要保留的非零位数
    :param max: 最长保留多少位
    :return:
        返回一个float或str
    """
    # 如果输入的数据是0，直接返回0.0
    if num == 0.:
        return 0.0

    # 绝对值大于1的数直接保留对应的位数输出
    if abs(num) > 1:
        return round(num, keep)
    # 获取小数点后面有多少个0
    zero_count = -int(math.log10(abs(num)))
    # 实际需要保留的位数
    keep = min(zero_count + keep, max)

    # 如果指定return_type是float，则返回float类型的数据
    if return_type == float:
        return round(num, keep)
    # 如果指定return_type是str，则返回str类型的数据
    else:
        return str(round(num, keep))


def filter_stock(df: pd.DataFrame) -> pd.DataFrame:
    """
    过滤函数，ST/退市/交易天数不足等情况
    :param df: 原始数据，包含股票名称、交易日期、开盘价、收盘价、交易量、交易额、市场交易天数等信息
    :return df:返回过滤后的df
    """
    # =删除不能交易的周期数
    # 删除月末为st状态的周期数
    df = df[df['股票名称'].str.contains('ST') == False]
    # 删除月末为s状态的周期数
    df = df[df['股票名称'].str.contains('S') == False]
    # 删除月末有退市风险的周期数
    df = df[df['股票名称'].str.contains('\*') == False]
    df = df[df['股票名称'].str.contains('退') == False]
    # 删除交易天数过少的周期数
    df = df[df['交易天数'] / df['市场交易天数'] >= 0.8]
    df = df[df['下日_是否交易'] == 1]
    df = df[df['下日_开盘涨停'] == False]
    df = df[df['下日_是否ST'] == False]
    df = df[df['下日_是否退市'] == False]
    df = df[df['上市至今交易天数'] > 250]
    return df


def get_trade_info(_df, open_times, close_times, buy_method):
    """
    获取每一笔的交易信息
    :param _df:算完复权的基础价格数据
    :param open_times:买入日的list
    :param close_times:卖出日的list
    :param buy_method:同config.py中设定买入股票的方法，即在什么时候买入
    :return: df:'买入日期', '卖出日期', '买入价', '卖出价', '收益率',在个股结果中展示
    """
    df = pd.DataFrame(columns=['买入日期', '卖出日期'])
    df['买入日期'] = open_times
    df['卖出日期'] = close_times
    # 买入的价格合并
    df = pd.merge(left=df, right=_df[['交易日期', f'{buy_method.replace("价", "")}价_复权', f'{buy_method.replace("价", "")}价']],
                  left_on='买入日期', right_on='交易日期', how='left')
    # 卖出的价格合并
    df = pd.merge(left=df, right=_df[['交易日期', '收盘价_复权', '收盘价']], left_on='卖出日期', right_on='交易日期', how='left')
    # 展示的买入卖出价为非复权价
    df.rename(columns={f'{buy_method.replace("价", "")}价': '买入价', '收盘价': '卖出价'}, inplace=True)
    # 收益率用复权价算
    df['收益率'] = df['收盘价_复权'] / df[f'{buy_method.replace("价", "")}价_复权'] - 1
    # 将收益率转为为百分比格式
    df['收益率'] = df['收益率'].apply(lambda x: str(round(100 * x, 2)) + '%')
    df = df[['买入日期', '卖出日期', '买入价', '卖出价', '收益率']]
    return df


def cal_next_period_returns(factor_data_path: Union[Path, str]) -> pd.DataFrame:
    '''
    计算下周期每天涨跌幅和下周期涨跌幅
    :param factor_data_path: 因子分析数据路径
    :return factor_data:返回因子分析所需的数据
    '''
    factor_data = pd.read_pickle(factor_data_path)
    factor_data.sort_values(['股票代码', '交易日期'], inplace=True)
    factor_data['收盘价_复权'] = factor_data.groupby('股票代码').apply(
        lambda x: x['复权因子'] * (x['收盘价'].iloc[0] / x['复权因子'].iloc[0])).reset_index(level=0, drop=True)
    factor_data['下周期涨跌幅'] = factor_data.groupby('股票代码')['收盘价_复权'].transform(
        lambda x: x.pct_change().shift(-1))
    return factor_data


def offset_grouping(df: pd.DataFrame, factor: str) -> pd.DataFrame:
    '''
    分组函数
    :param df: 原数据
    :param factor: 因子名
    :return:
        返回一个df数据，包含groups列
    '''
    # 根据factor计算因子的排名
    df['因子_排名'] = df.groupby(['交易日期'])[factor].rank(ascending=True, method='first')
    # 根据因子的排名进行分组
    df['groups'] = df.groupby(['交易日期'])['因子_排名'].transform(lambda x: pd.qcut(x, q=10, labels=False, duplicates='drop') + 1)
    return df


def IC_analysis(IC_data):
    '''
    整合各个offset的IC数据并计算相关的IC指标
    :param IC_data: IC数据，包含计算好的Rank IC值
    :return:
        返回IC数据、IC字符串
    '''
    IC = IC_data.sort_values('交易日期').reset_index(drop=True)
    IC['累计RankIC'] = IC['RankIC'].cumsum()

    # ===计算IC的统计值，包括IC均值、IC标准差、ICIR、IC胜率===
    IC_mean = float_num_process(IC['RankIC'].mean())
    IC_std = float_num_process(IC['RankIC'].std())
    ICIR = float_num_process(IC_mean / IC_std)

    # 计算IC胜率，如果累计IC为正，则计算IC为正的比例
    if IC['累计RankIC'].iloc[-1] > 0:
        IC_ratio = str(float_num_process((IC['RankIC'] > 0).sum() / len(IC) * 100)) + '%'
    # 计算IC胜率，如果累计IC为负，则计算IC为负的比例
    else:
        IC_ratio = str(float_num_process((IC['RankIC'] < 0).sum() / len(IC) * 100)) + '%'

    # 将上述指标合成一个字符串，加入到IC图中
    IC_info = f'IC均值：{IC_mean}，IC标准差：{IC_std}，ICIR：{ICIR}，IC胜率：{IC_ratio}'
    return IC, IC_info


def get_IC(df: pd.DataFrame, factor: str) -> pd.DataFrame:
    '''
    计算IC等一系列指标
    :param df: 数据
    :param factor: 因子列名，测试的因子名称
    :return:
        返回计算得到的IC数据
    '''
    print('正在进行因子IC分析...')
    IC = df.groupby('交易日期').apply(lambda x: x[factor].corr(x['下周期涨跌幅'], method='spearman')).to_frame()
    IC = IC.rename(columns={0: 'RankIC'}).reset_index()
    print(f'因子IC分析完成')
    return IC


def get_group_hold_value(df: pd.DataFrame, conf) -> pd.DataFrame:
    """
    针对分组数据进行分析，给出分组的资金曲线、分箱图以及各分组的未来资金曲线
    :param df: 输入的数据
    :param conf: 回测配置文件
    :return:
        返回分组资金曲线、分组持仓走势数据
    """
    print('正在进行因子分组分析...')

    # 由于会对原始的数据进行修正，所以需要把数据copy一份
    temp = df.copy()

    # 计算扣除手续费后的下周期每天净值
    temp['下周期净值'] = temp['下周期涨跌幅'] + 1
    free_rate = (1 - conf.c_rate) * (1 - conf.c_rate - conf.t_rate)
    temp['扣除手续费的下周期净值'] = temp['下周期净值'].apply(lambda x: x * free_rate)

    # 按照等权组合的方法构造分组的投资组合，计算得到每组的资金曲线
    group_nv = temp.groupby(['交易日期', 'groups'])['扣除手续费的下周期净值'].mean().reset_index()
    group_nv = group_nv.sort_values(by='交易日期').reset_index(drop=True)

    # 计算每个分组的累计净值
    group_nv['净值'] = group_nv.groupby('groups')['扣除手续费的下周期净值'].cumprod()

    # 计算最后持仓周期的分组净值
    max_date = group_nv['交易日期'].max()
    group_hold_value = group_nv[group_nv['交易日期'] == max_date].drop(['交易日期', '扣除手续费的下周期净值'], axis=1)
    group_hold_value.sort_values('groups', inplace=True)
    group_hold_value['分组'] = group_hold_value['groups'].apply(lambda x: f'第{x}组')

    print(f'因子分组分析完成')
    return group_hold_value
