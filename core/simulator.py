"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import numba as nb
import numpy as np
from numba.experimental import jitclass

"""
# 新语法小讲堂
通过操作对象的值而不是更换reference，来保证所有引用的位置都能同步更新。

`self.target_lots[:] = target_lots`
这个写法涉及 Python 中的切片（slice）操作和对象的属性赋值。

`target_lots: nb.int64[:]  # 目标持仓手数`，self.target_lots 是一个列表，`[:]` 是切片操作符，表示对整个列表进行切片。

>>>>>>>>>>>>>>>>>> 4rku <<<<<<<<<<<<<<<<<<<<<

### 详细解释：

1. **`self.target_lots[:] = target_lots`**:
   - `self.target_lots` 是对象的一个属性，通常是一个列表（或者其它支持切片操作的可变序列）。
   - `[:]` 是切片操作符，表示对整个列表进行切片。具体来说，`[:]` 是对列表的所有元素进行选择，这种写法可以用于复制列表或对整个列表内容进行替换。

2. **具体操作**：
   - `self.target_lots[:] = target_lots` 不是直接将 `target_lots` 赋值给 `self.target_lots`，而是将 `target_lots` 中的所有元素替换 `self.target_lots` 中的所有元素。
   - 这种做法的一个好处是不会改变 `self.target_lots` 对象的引用，而是修改它的内容。这在有其他对象引用 `self.target_lots` 时非常有用，确保所有引用者看到的列表内容都被更新，而不会因为重新赋值而改变列表的引用。

### 举个例子：

```python
a = [1, 2, 3]
b = a
a[:] = [4, 5, 6]  # 只改变列表内容，不改变引用

print(a)  # 输出: [4, 5, 6]
print(b)  # 输出: [4, 5, 6]，因为 a 和 b 引用的是同一个列表，修改 a 的内容也影响了 b
```

如果直接用 `a = [4, 5, 6]` 替换 `[:]` 操作，那么 `b` 就不会受到影响，因为 `a` 重新指向了一个新的列表对象。
> 4rku
"""


@jitclass
class Simulator:
    cash: float  # 账户现金余额, 单位人民币元
    pos_values: nb.float64[:]  # 仓位价值，单位人民币元

    commission_rate: float  # 券商佣金
    stamp_tax_rate: float  # 印花税率

    last_prices: nb.float64[:]  # 最新价格

    def __init__(self, init_capital, commission_rate, stamp_tax_rate, init_pos_values):
        """
        初始化
        :param init_capital: 初始资金
        :param commission_rate: 券商佣金
        :param stamp_tax_rate: 印花税率
        """
        self.cash = init_capital  # 初始现金余额
        self.commission_rate = commission_rate  # 交易成本
        self.stamp_tax_rate = stamp_tax_rate  # 最小下单金额

        n = len(init_pos_values)

        # 合约面值
        self.pos_values = np.zeros(n, dtype=np.float64)
        self.pos_values[:] = init_pos_values

        # 前收盘价
        self.last_prices = np.zeros(n, dtype=np.float64)

    def fill_last_prices(self, prices):
        mask = np.logical_not(np.isnan(prices))
        self.last_prices[mask] = prices[mask]

    def settle_pos_values(self, prices):
        """
        计算当前仓位价值
        :param prices: 当前价格
        :return:
        """

        mask = np.logical_and(self.pos_values > 1e-6, np.logical_not(np.isnan(prices)))

        self.pos_values[mask] *= prices[mask] / self.last_prices[mask]

    def get_pos_value(self):
        return np.sum(self.pos_values)

    def sell_all(self, exec_prices):
        # 根据调仓价和前最新价（开盘价），结算当前仓位价值
        self.settle_pos_values(exec_prices)

        # 卖出则卖出所有
        pos_values_total = np.sum(self.pos_values)

        # 印花税（仅卖出时收取）
        stamp_tax = pos_values_total * self.stamp_tax_rate

        # 券商佣金
        commission = pos_values_total * self.commission_rate

        # 卖出所得扣除印花税和佣金，加入现金余额
        self.cash += pos_values_total - stamp_tax - commission

        # 仓位清空
        self.pos_values[:] = 0

        # 最新价为调仓价
        self.fill_last_prices(exec_prices)

        # 返回印花税，和佣金
        return stamp_tax, commission

    def buy_stocks(self, exec_prices, target_pos):
        """
        模拟: K 线开盘时刻 -> 调仓时刻
        :param exec_prices:  执行价格
        :param target_pos:   目标仓位
        :return:            调仓后的账户权益、调仓后的仓位名义价值
        """

        # 根据调仓价和前最新价（开盘价），结算当前仓位价值
        self.settle_pos_values(exec_prices)

        # commission = 0.

        # 买入仓位价值
        mask = target_pos > 0
        buy_values = exec_prices[mask] * target_pos[mask]
        buy_values_total = np.sum(buy_values)

        self.pos_values[mask] = buy_values

        # 券商佣金
        commission = np.sum(self.pos_values * self.commission_rate)

        # 账户现金扣除买入仓位价值和佣金
        self.cash -= buy_values_total + commission

        # 最新价为调仓价
        self.fill_last_prices(exec_prices)

        # 返回和佣金
        return commission
