"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import pandas as pd


def equity_signal(equity_df: pd.DataFrame, *args) -> pd.Series:
    """
    根据资金曲线，动态调整杠杆
    :param equity_df: 资金曲线的DF
    :param args: 其他参数
    :return: 返回包含 leverage 的数据
    """

    # ===== 获取策略参数
    n = int(args[0])

    # ===== 计算指标
    # 计算均线
    ma = equity_df["净值"].rolling(n, min_periods=1).mean()

    # 默认空仓
    signals = pd.Series(0.0, index=equity_df.index)

    # equity 在均线之上，才持有
    above = equity_df["净值"] > ma
    signals.loc[above] = 1.0

    return signals
