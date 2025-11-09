import pandas as pd
import numpy as np


def equity_signal(equity_df: pd.DataFrame, *args) -> pd.Series:
    """
    根据资金曲线，使用短期和长期均线择时信号
    :param equity_df: 包含 'equity_curve' 列的资金曲线 DataFrame
    :param args: 均线参数 args[0]=短期均线，args[1]=长期均线
    :return: 返回包含信号的 Series（1=做多，0=空仓）
    """
    # ===== 获取策略参数
    short_n = int(args[0])  # 短期均线窗口
    long_n = int(args[1])  # 长期均线窗口

    # ===== 计算均线
    ma_short = equity_df['净值'].rolling(short_n, min_periods=1).mean()
    ma_long = equity_df['净值'].rolling(long_n, min_periods=1).mean()

    # ===== 初始化信号 Series，默认空仓
    signals = pd.Series(np.nan, index=equity_df.index)

    # ===== 找出金叉买入信号
    condition_buy = (ma_short > ma_long) & (ma_short.shift(1) <= ma_long.shift(1))
    signals[condition_buy] = 1.0

    # ===== 找出死叉平仓信号
    condition_sell = (ma_short < ma_long) & (ma_short.shift(1) >= ma_long.shift(1))
    signals[condition_sell] = 0.0

    # ===== 持续持仓：将前一日信号延续到当前（信号填充）
    signals = signals.ffill().fillna(1)  # 默认开
    return signals
