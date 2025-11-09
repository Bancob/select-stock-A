"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import warnings
import datetime
from typing import Tuple

import pandas as pd

import tools.utils.pfunctions as PFun
import tools.utils.tfunctions as tFun

from core.utils.path_kit import get_file_path
from core.model.backtest_config import BacktestConfig, load_config

# ====================================================================================================
# ** 配置与初始化 **
# 设置必要的显示选项及忽略警告，以优化代码输出的阅读体验
# ====================================================================================================
warnings.filterwarnings('ignore')  # 忽略不必要的警告
pd.set_option('expand_frame_repr', False)  # 使数据框在控制台显示不换行
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)


def IC_GNV_analysis(data: pd.DataFrame, factor_name: str, conf: BacktestConfig) -> Tuple[pd.DataFrame, str, pd.DataFrame]:
    """
    IC、分组净值分析
    :param data: 因子分析需要的数据
    :param factor_name: 因子名称
    :param conf: 回测配置信息
    :return:
        IC、IC_info、分组净值
    """
    # 如果返回的数据为空，则跳过该hold_period继续读取下一个offset的数据
    data = data.dropna(subset=['交易日期', '股票代码', '股票名称', '交易天数', '市场交易天数', '下日_是否交易',
                               '下日_开盘涨停', '下日_是否ST', '下日_是否退市', '上市至今交易天数', '下周期涨跌幅'],
                       how='any')

    # 利用上述字段进行过滤，过滤掉ST/退市/交易天数不足等情况的股票
    data = tFun.filter_stock(data)

    # 将因子信息转换成float类型
    data[factor_name] = data[factor_name].astype(float)

    # 保留每个周期的股票数量大于limit的日期
    data['当周期股票数'] = data.groupby('交易日期')['交易日期'].transform('count')
    data = data[data['当周期股票数'] > 100].reset_index(drop=True)

    # 将数据按照交易日期和hold_period进行分组
    data = tFun.offset_grouping(data, factor_name)

    # 计算因子IC值
    IC_data = tFun.get_IC(data, factor_name)
    IC, IC_info = tFun.IC_analysis(IC_data)

    # 计算分组净值
    group_hold_value = tFun.get_group_hold_value(data, conf)

    return IC, IC_info, group_hold_value


def factor_analysis(conf: BacktestConfig, factor_name: str) -> None:
    """
    因子分析
    :param conf: 回测配置信息
    :param factor_name: 因子名称，需要再因子计算结果中有相应的字段，如反转策略中的'Ret_5'
    :return: None
    """
    factor_data_path = get_file_path('data', '运行缓存', '因子计算结果.pkl', auto_create=False)  # 因子计算结果的绝对路径

    print(f'✅ 开始分析{factor_name}因子')

    start_time = datetime.datetime.now()  # 记录因子开始时间

    data = tFun.cal_next_period_returns(factor_data_path)  # 计算下周期涨跌幅数据

    IC, IC_info, group_value = IC_GNV_analysis(data, factor_name, conf)  # IC、分组净值分析

    # 画IC走势图
    IC_save_path = get_file_path('data', '因子分析', f'{factor_name}因子IC图.html', auto_create=True)  # IC图像保存路径
    PFun.draw_ic_plotly(x=IC['交易日期'], y1=IC['RankIC'], y2=IC['累计RankIC'], title=f'{factor_name}因子RankIC图',
                        info=IC_info, save_path=IC_save_path)

    # 画分箱净值图
    nav_save_path = get_file_path('data', '因子分析', f'{factor_name}因子分箱净值图.html', auto_create=True)  # 净值图像保存路径
    PFun.draw_bar_plotly(x=group_value['分组'], y=group_value['净值'], title=f'{factor_name}因子分组净值',
                         save_path=nav_save_path)

    print(f'✅ {factor_name}因子分析完成, 总用时{(datetime.datetime.now() - start_time).total_seconds():.2f}秒')


if __name__ == '__main__':
    backtest_config = load_config()
    factor_analysis(backtest_config, factor_name='市值_None')
