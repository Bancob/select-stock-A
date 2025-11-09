"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
from datetime import datetime
from itertools import product
from pathlib import Path
from types import ModuleType
from typing import Optional, List

import numpy as np
import pandas as pd

from core.model.strategy_config import StrategyConfig
from core.utils.factor_hub import FactorHub
from core.utils.path_kit import get_file_path, get_folder_path
from core.utils.strategy_hub import get_strategy_by_name
from core.market_essentials import get_trade_date, import_index_data
from core.model.timing_signal import EquityTiming


class BacktestConfig:
    def __init__(self, **config_dict: dict):
        self.start_date: Optional[str] = config_dict.get("start_date", None)  # 回测开始时间
        # 日期，为None时，代表使用到最新的数据，也可以指定日期，例如'2022-11-01'，但是指定日期
        self.end_date: Optional[str] = config_dict.get("end_date", None)

        self.strategy_raw: dict = config_dict.get("strategy", None)  # 策略配置
        self.strategy: Optional[StrategyConfig] = None  # 策略对象

        self.initial_cash: float = config_dict.get("initial_cash", 100_0000)  # 初始资金默认100万
        self.c_rate: float = config_dict.get("c_rate", 1.2 / 10000)  # 手续费，默认为0.002，表示万分之二
        self.t_rate: float = config_dict.get("t_rate", 1 / 1000)  # 印花税，默认为0.001

        data_center_path = config_dict.get("data_center_path", "not-provided")
        self.data_center_path = Path(data_center_path)
        if data_center_path != "not-provided":
            self.stock_data_path = self.data_center_path / "stock-trading-data"
            self.index_data_path = self.data_center_path / "stock-main-index-data"
            self.fin_data_path = self.data_center_path / "stock-fin-data-xbx"
        else:
            # 根据输入，进行一下重要中间变量的处理
            # 股票日线数据，全量数据下载链接：https://www.quantclass.cn/data/stock/stock-trading-data
            self.stock_data_path: Path = Path(str(config_dict["stock_data_path"]))
            # 指数数据路径，全量数据下载链接：https://www.quantclass.cn/data/stock/stock-main-index-data
            self.index_data_path: Path = Path(str(config_dict["index_data_path"]))
            # 其他的数据，全量数据下载链接：https://www.quantclass.cn/data/stock/stock-fin-data-xbx
            self.fin_data_path: Path = Path(str(config_dict.get("fin_data_path", "not-provided")))

        self.has_fin_data: bool = self.fin_data_path.exists()  # 是否使用财务数据

        self.factor_params_dict: dict = {}  # 缓存因子参数，用于后续的因子聚合
        self.fin_cols: list = []  # 缓存财务因子列

        # 缓存被排除的板块
        self.excluded_boards: list = config_dict.get("excluded_boards", [])

        # 资金曲线再择时配置，会在load_strategy中初始化
        self.equity_timing: Optional[EquityTiming] = None

        self.agg_rules = {}  # 缓存聚合规则
        self.report: pd.DataFrame = pd.DataFrame()  # 回测报告

        # 遍历标记：遍历的INDEX，0表示非遍历场景，从1、2、3、4、...开始表示是第几个循环，当然也可以赋值为具体名称
        self.iter_round: int | str = 0

    def load_strategy(self, strategy=None, equity_timing=None):
        if strategy is None:
            stg_dict: dict = self.strategy_raw
        else:
            self.strategy_raw = strategy
            stg_dict: dict = strategy
        strategy_name = stg_dict["name"]
        stg_dict["funcs"] = get_strategy_by_name(strategy_name)
        self.strategy = StrategyConfig.init(**stg_dict)

        # 针对当前策略的因子信息，整理之后的列名信息，并且缓存到全局
        fin_cols = set()
        for factor_config in self.strategy.all_factors:
            # 添加到并行计算的缓存中
            if factor_config.name not in self.factor_params_dict:
                self.factor_params_dict[factor_config.name] = set()
            self.factor_params_dict[factor_config.name].add(factor_config.param)

            new_cols = FactorHub.get_by_name(factor_config.name).fin_cols
            fin_cols = fin_cols.union(set(new_cols))

        self.fin_cols = list(fin_cols)

        if equity_timing is not None:
            self.equity_timing = EquityTiming.init(**equity_timing)

    def update_trading_date(self, tc_path):
        print("⚠️ 交易日历文件不存在，或者需要更新，从网络获取最新的交易日历数据。")
        index_data_all = import_index_data(self.index_data_path / "sh000001.csv")
        # 如果需要更新，从网络获取最新的交易日历数据
        try:
            tc_df = get_trade_date(index_data_all)
            tc_df.to_csv(tc_path, index=False)
            print(f'🔄 交易日历更新为：{tc_df["交易日期"].min()}~{tc_df["交易日期"].max()}')
            return tc_df
        except Exception as e:
            print(e)
            print("需要更新交易日历，但无法联网")
            return None

    def read_index_with_trading_date(self):
        """
        加载交易日历数据，并与指数数据合并

        参数:
        index_data (DataFrame): 指数数据
        prg_data_folder (str): 程序数据文件夹路径

        返回:
        index_data (DataFrame): 合并后的指数数据
        """
        # 获取今天的日期
        today = datetime.today()
        index_data = import_index_data(self.index_data_path / "sh000001.csv", [self.start_date, self.end_date])

        # 构建交易日历文件路径
        tc_path = get_file_path("data", "交易日历.csv")

        if tc_path.exists():
            tc_df = pd.read_csv(tc_path)
            if pd.to_datetime(tc_df["交易日期"].max()) - today <= pd.to_timedelta("30 days"):
                new_tc_df = self.update_trading_date(tc_path)
                if new_tc_df is not None:
                    tc_df = new_tc_df
        else:
            tc_df = self.update_trading_date(tc_path)

        # 检查文件是否存在，或者是否需要更新
        if tc_df is None:
            print("本地不存在交易日历，需要联网更新后继续，程序退出")
            exit()

        print(f'🌀 本地交易日历数据为：{tc_df["交易日期"].min()}~{tc_df["交易日期"].max()}')

        # 将交易日期列转换为datetime类型
        tc_df["交易日期"] = pd.to_datetime(tc_df["交易日期"])

        # 计算下个交易日
        tc_df["次交易日"] = tc_df["交易日期"].shift(-1)

        # 标记周频起始日
        con1 = tc_df["交易日期"].diff().dt.days != 1
        tc_df.loc[con1, "周频起始日"] = tc_df["交易日期"]

        # 处理只有一个交易日的周期
        con2 = tc_df["交易日期"].diff(-1).dt.days != -1
        tc_df.loc[con1 & con2, "周频起始日"] = np.nan
        tc_df["周频起始日"] = tc_df["周频起始日"].ffill()
        tc_df["周频终止日"] = tc_df["周频起始日"] != tc_df["周频起始日"].shift(-1)

        # 标记月频起始日
        con3 = tc_df["交易日期"].dt.month != tc_df["交易日期"].shift().dt.month
        tc_df.loc[con3, "月频起始日"] = tc_df["交易日期"]
        tc_df["月频起始日"] = tc_df["月频起始日"].ffill()
        tc_df["月频终止日"] = tc_df["月频起始日"] != tc_df["月频起始日"].shift(-1)

        # ==标记3D、5D、10D的开始和截止日期
        # 日频系列需要指定一个基础的交易日期，我们指定2007年第一个交易日期作为指定日期（2007-01-04）
        base_inx = tc_df[tc_df['交易日期'] == pd.to_datetime('2007-01-04')].index.min()
        if pd.isnull(base_inx):
            print(f'🚨 删除: {get_file_path("data", "交易日历.csv")}')
            raise Exception('交易日历至少需要从2007年1月4日开始，请删除data目录下的`交易日历.csv`，'
                            '并确保sh000001指数至少从2007年1月4日开始!'
                            '\n指数文件路径：%s' % self.index_data_path)
        # 计算不同周期的起始日期
        for n in [3, 5, 10]:
            con = (tc_df.index - base_inx) % n == 0
            tc_df.loc[con, f'{n}D起始日'] = tc_df['交易日期']
            tc_df[f'{n}D起始日'] = tc_df[f'{n}D起始日'].ffill()
            tc_df[f'{n}D终止日'] = tc_df[f'{n}D起始日'] != tc_df[f'{n}D起始日'].shift(-1)

        # 将交易日历数据与指数数据合并
        index_data = pd.merge(left=index_data, right=tc_df, on="交易日期", how="left")

        # 额外生成实盘需要的周期数据
        period_offset = tc_df[['交易日期']]
        for period, tag in {'周频': 'W_0', '月频': 'M_0', '3D': '3_0', '5D': '5_0', '10D': '10_0'}.items():
            period_offset[tag] = 0
            period_offset.loc[period_offset['交易日期'] == tc_df[f'{period}起始日'], tag] = 1
            period_offset[tag] = period_offset[tag].cumsum()

        period_offset_path = get_file_path("data", "period_offset.csv")
        period_offset.columns = pd.MultiIndex.from_tuples(
            zip(['数据由整理，对数据字段有疑问的，可以直接微信私信邢不行，微信号：xbx297'] + [''] * (
                    period_offset.shape[1] - 1), period_offset.columns))
        period_offset.to_csv(period_offset_path, encoding='gbk', index=False)
        return index_data

    def get_result_folder(self) -> Path:
        if self.iter_round == 0:
            strategy_name = self.strategy.name if self.strategy is not None else "strategy"
            return get_folder_path("data", "回测结果", strategy_name)
        else:
            return get_folder_path(
                "data",
                "遍历结果",
                self.strategy.name,
                f"参数组合_{self.iter_round}" if isinstance(self.iter_round, int) else self.iter_round,
                path_type=True,
            )

    def get_fullname(self):
        fullname = f"{self.strategy.get_fullname()}，初始资金￥{self.initial_cash:,.2f}"
        if self.equity_timing is not None:
            fullname += f"，再择时：{self.equity_timing.name, self.equity_timing.params}"
        return fullname

    def set_report(self, report: pd.DataFrame):
        report["param"] = self.get_fullname()
        self.report = report

    def get_strategy_config_sheet(self, with_factors=True) -> dict:
        factor_dict = {"持仓周期": self.strategy.hold_period, "选股数量": self.strategy.select_num}
        ret = {"策略": self.strategy.name, "策略详情": self.get_fullname()}
        if with_factors:
            for factor_config in self.strategy.all_factors:
                _name = f"#因子-{factor_config.name}"
                _val = factor_config.param
                factor_dict[_name] = _val
            ret.update(**factor_dict)

        return ret

    @classmethod
    def init_from_config(cls, load_strategy=True):
        import config

        # 提取自定义变量
        config_dict = {
            key: value
            for key, value in vars(config).items()
            if not key.startswith("__") and not isinstance(value, ModuleType)
        }
        conf = cls(**config_dict)
        if load_strategy:
            conf.load_strategy(equity_timing=getattr(config, "equity_timing", None))
        return conf


class BacktestConfigFactory:
    """
    遍历参数的时候，动态生成配置
    """

    def __init__(self):
        # ====================================================================================================
        # ** 参数遍历配置 **
        # 可以指定因子遍历的参数范围
        # ====================================================================================================
        # 存储生成好的config list和strategy list
        self.config_list: List[BacktestConfig] = []

    @property
    def result_folder(self) -> Path:
        return get_folder_path("data", "遍历结果", path_type=True)

    def generate_all_factor_config(self):
        """
        产生一个conf，拥有所有策略的因子，用于因子加速并行计算
        """
        import config

        backtest_config = BacktestConfig.init_from_config(load_strategy=False)
        factor_list = []
        filter_list = []
        for conf in self.config_list:
            factor_list += conf.strategy_raw["factor_list"]
            filter_list += conf.strategy_raw["filter_list"]
        backtest_config.load_strategy(
            {
                **config.strategy,  # 默认策略
                "factor_list": factor_list,  # 覆盖因子列表
                "filter_list": filter_list,  # 覆盖过滤列表
            }
        )
        return backtest_config

    def get_name_params_sheet(self) -> pd.DataFrame:
        rows = []
        for config in self.config_list:
            rows.append(config.get_strategy_config_sheet())

        sheet = pd.DataFrame(rows)
        sheet.to_excel(self.config_list[-1].get_result_folder().parent / "策略回测参数总表.xlsx", index=False)
        return sheet

    def generate_by_strategies(self, strategies, equity_signals=(None,)) -> List[BacktestConfig]:
        config_list = []
        iter_round = 0

        for strategy, equity_signal in product(strategies, equity_signals):
            iter_round += 1
            backtest_config = BacktestConfig.init_from_config(load_strategy=False)
            backtest_config.load_strategy(strategy, equity_signal)
            backtest_config.iter_round = iter_round

            config_list.append(backtest_config)

        self.config_list = config_list

        return config_list


def load_config() -> BacktestConfig:
    return BacktestConfig.init_from_config()


def create_factory(strategies, re_timing_strategies=(None,)):
    factory = BacktestConfigFactory()
    factory.generate_by_strategies(strategies, re_timing_strategies)

    return factory
