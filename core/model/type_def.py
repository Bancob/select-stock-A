"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import numba as nb
from numba.experimental import jitclass

# 北交所(理应拉黑) bjxxxxxx
BSE_MAIN = 0

# 上交所主板 sh60xxxx
SSE_MAIN = 1

# 上交所科创板 sh68xxxx
SSE_STAR = 2

# 深交所主板 sz00xxxx
SZSE_MAIN = 3

# 深交所创业板 sz30xxxx
SZSE_CHINEXT = 4


@jitclass
class StockMarketData:
    # 交易日零点时间戳，单位秒
    candle_begin_ts: nb.int64[:]

    # open pivot
    op: nb.float64[:, :]

    # close pivot
    cl: nb.float64[:, :]

    # preclose pivot
    pre_cl: nb.float64[:, :]

    types: nb.int16[:]

    def __init__(self, candle_begin_ts, op, cl, pre_cl, types):
        self.candle_begin_ts = candle_begin_ts
        self.op = op
        self.cl = cl
        self.pre_cl = pre_cl
        self.types = types


@jitclass
class SimuParams:
    init_cash: float
    commission_rate: float  # 券商佣金
    stamp_tax_rate: float  # 印花税率

    def __init__(self, init_cash, commission_rate, stamp_tax_rate):
        self.init_cash = init_cash
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate


def get_symbol_type(symbol: str) -> int:
    if symbol.startswith('bj'):
        return BSE_MAIN  # 北交所

    if symbol.startswith('sh'):
        if symbol.startswith('sh68'):
            return SSE_STAR  # 科创板
        else:
            return SSE_MAIN  # 上交所主板

    if symbol.startswith('sz'):
        if symbol.startswith('sz0'):
            return SZSE_MAIN  # 深交所主板
        else:
            return SZSE_CHINEXT  # 深交所创业板

    raise ValueError(f'Unknown stock {symbol}')
