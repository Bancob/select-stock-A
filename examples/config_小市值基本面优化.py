"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
from pathlib import Path

start_date = '2009-01-01'
end_date = None  # 日期，为None时，代表使用到最新的数据，也可以指定日期，例如'2022-11-01'，但是指定日期

strategy = {
    'name': '小市值基本面优化',  # 策略名
    'hold_period': 'W',  # 持仓周期，W 代表周，M 代表月
    'select_num': 10,  # 选股数量，可以是整数，也可以是小数，比如 0.1 表示选取 10% 的股票
    "factor_list": [  # 选股因子列表
        # ** 因子格式说明 **
        # 因子名称（与 '因子库' 文件中的名称一致），排序方式（True 为升序，False 为降序），因子参数，因子权重
        ('归母净利润同比增速', False, 60, 1),
        ('市值', True, None, 1),
        # 可添加多个选股因子
    ],
    "filter_list": [  # 过滤因子列表
        # 因子名称（与 '因子库' 文件中的名称一致），因子参数，因子过滤规则，排序方式
        ('ROE', '单季', 'pct:<0.8', False),

        # ** 因子过滤规则说明 **
        # 支持三种过滤规则：`rank` 排名过滤、`pct` 百分比过滤、`val` 数值过滤
        # - `rank:<10` 仅保留前 10 名的数据；`rank:>=10` 排除前 10 名。支持 >、>=、<、<=、==、!=
        # - `pct:<0.8` 仅保留前 80% 的数据；`pct:>=0.8` 仅保留后 20%。支持 >、>=、<、<=、==、!=
        # - `val:<0.1` 仅保留小于 0.1 的数据；`val:>=0.1` 仅保留大于等于 0.1 的数据。支持 >、>=、<、<=、==、!=
        # 可添加多个过滤因子和规则，多个条件将取交集
    ]
}

# 💡运行提示：
# - 修改hold_period之后，需要执行step2因子计算，不需要再次准备数据
# - 修改select_num之后，只需要再执行step3选股即可，不需要准备数据和计算因子
# - 修改factor_list之后，需要执行step2因子计算，不需要再次准备数据
# - 修改filter_list之后，需要执行step2因子计算，不需要再次准备数据


# =====数据源的定义=====
# ** 股票日线数据 和 指数数据是必须的，其他的数据可以在 data_sources 中定义 **
# (必选) 股票日线数据，全量数据下载链接：https://www.quantclass.cn/data/stock/stock-trading-data
stock_data_path = r'/Users/lhc/Public/Frameworks/data/stock-trading-data-2024-11-11N'  # 参考：https://bbs.quantclass.cn/thread/39599
# (必选) 指数数据路径，全量数据下载链接：https://www.quantclass.cn/data/stock/stock-main-index-data
index_data_path = r'/Users/lhc/Public/Frameworks/data/stock-main-index-data-2024-11-12'
# (可选) 财务数据，全量数据下载链接：https://www.quantclass.cn/data/stock/stock-fin-data-xbx
fin_data_path = r'/Users/lhc/Public/Frameworks/data/stock-fin-data-xbx-2024-11-12'

# =====以下参数几乎不需要改动=====
initial_cash = 10_0000  # 初始资金10w
# 手续费
c_rate = 1.2 / 10000
# 印花税
t_rate = 1 / 1000
# 上市至今交易天数
days_listed = 250

# =====参数预检查=====
if Path(stock_data_path).exists() is False:
    print(f'股票日线数据路径不存在：{stock_data_path}，请检查配置或联系助教，程序退出')
    exit()
if Path(index_data_path).exists() is False:
    print(f'指数数据路径不存在：{index_data_path}，请检查配置或联系助教，程序退出')
    exit()
