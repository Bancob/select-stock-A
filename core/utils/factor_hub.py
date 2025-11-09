"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import importlib

import pandas as pd


class FactorInterface:
    """
    ！！！！抽象因子对象，仅用于代码提示！！！！
    """
    # 财务因子列：此列表用于存储财务因子相关的列名称
    fin_cols = []  # 财务因子列，配置后系统会自动加载对应的财务数据

    @staticmethod
    def add_factor(df: pd.DataFrame, param=None, **kwargs) -> (pd.DataFrame, dict):
        """
        计算并将新的因子列添加到股票行情数据中，并返回包含计算因子的DataFrame及其聚合方式。

        工作流程：
        1. 根据提供的参数计算股票的因子值。
        2. 将因子值添加到原始行情数据DataFrame中。
        3. 定义因子的聚合方式，用于周期转换时的数据聚合。

        :param df: pd.DataFrame，包含单只股票的K线数据，必须包括市场数据（如收盘价等）。
        :param param: 因子计算所需的参数，格式和含义根据因子类型的不同而有所不同。
        :param kwargs: 其他关键字参数，包括：
            - col_name: 新计算的因子列名。
            - fin_data: 财务数据字典，格式为 {'财务数据': fin_df, '原始财务数据': raw_fin_df}，其中fin_df为处理后的财务数据，raw_fin_df为原始数据，后者可用于某些因子的自定义计算。
            - 其他参数：根据具体需求传入的其他因子参数。
        :return: tuple
            - pd.DataFrame: 包含新计算的因子列，与输入的df具有相同的索引。
            - dict: 聚合方式字典，定义因子在周期转换时如何聚合（例如保留最新值、计算均值等）。

        注意事项：
        - 如果因子的计算涉及财务数据，可以通过`fin_data`参数提供相关数据。
        - 聚合方式可以根据实际需求进行调整，例如使用'last'保留最新值，或使用'mean'、'max'、'sum'等方法。
        """

        # ======================== 参数处理 ===========================
        # 从kwargs中提取因子列的名称，这里使用'col_name'来标识因子列名称
        col_name = kwargs['col_name']

        # ======================== 计算因子 ===========================
        """
        [abstract]
        目前这个接口中并没有实现任何的计算逻辑，只是提供一个接口，用于提示
        需要在这个位置实现计算逻辑，并且在 `df` 中添加一个新的因子列，列名为 col_name
        """

        # ======================== 因子聚合 ===========================
        # 定义因子聚合方式，这里选择获取最新的因子值
        agg_dict = {
            col_name: 'last'  # last表示，在后续交易周期转换的时候，保留周期内最新的值，作为聚合后的因子数值。默认都是使用last
            # 当然可以选择常见的聚合函数，如
            # - mean：计算均值，比如我们计算平均市值的时候
            # - max：计算最大值，比如我们计算近期最大涨幅的时候
            # - min：计算最小值，比如我们计算近期最大跌幅的时候
            # - sum：计算和，比如我们计算成交量的时候
        }

        # 我们只返回因子的列信息，以及周期转换时候因子列的聚合方式
        return df[[col_name]], agg_dict

    def add_factors(self, df: pd.DataFrame, params=(), **kwargs) -> (pd.DataFrame, dict):
        """
        批量计算多个参数下的因子数值
        """
        raise NotImplementedError


class FactorHub:
    _factor_cache = {}

    # noinspection PyTypeChecker
    @staticmethod
    def get_by_name(factor_name) -> FactorInterface:
        if factor_name in FactorHub._factor_cache:
            return FactorHub._factor_cache[factor_name]

        try:
            # 构造模块名
            module_name = f"因子库.{factor_name}"

            # 动态导入模块
            factor_module = importlib.import_module(module_name)

            # 创建一个包含模块变量和函数的字典
            factor_content = {
                name: getattr(factor_module, name) for name in dir(factor_module)
                if not name.startswith("__")
            }

            if 'fin_cols' not in factor_content:
                factor_content['fin_cols'] = []

            # 创建一个包含这些变量和函数的对象
            factor_instance = type(factor_name, (), factor_content)

            # 缓存策略对象
            FactorHub._factor_cache[factor_name] = factor_instance

            return factor_instance
        except ModuleNotFoundError:
            raise ValueError(f"Factor {factor_name} not found.")
        except AttributeError:
            raise ValueError(f"Error accessing factor content in module {factor_name}.")
