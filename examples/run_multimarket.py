"""Entry point for running the multi-market backtester."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from examples.multimarket_config import platform_config  # noqa: E402
from multimarket.analytics.equity_curve import render_equity_html  # noqa: E402
from multimarket.runner import BacktestRunner  # noqa: E402


def execute(config, label: str) -> tuple[BacktestRunner, pd.Series]:
    runner = BacktestRunner(config)
    runner.prepare()
    cerebro, _ = runner.run()
    equity = runner.equity_curve()
    if not equity.empty:
        print(f"{label}累计净值: {equity.iloc[-1]:.4f}")
        print(f"{label}最终账户市值: {cerebro.broker.getvalue():,.2f}")
    else:
        print(f"{label}未生成资金曲线")
    return runner, equity


def main() -> None:
    output_dir = PROJECT_ROOT / "multimarket" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if platform_config.timing:
        base_config = replace(platform_config, timing=None)
        _, base_equity = execute(base_config, "原始策略")
        _, timed_equity = execute(platform_config, "择时策略")
        html_path = render_equity_html(
            base_curve=base_equity,
            timed_curve=timed_equity,
            output_path=output_dir / "再择时-资金曲线.html",
        )
    else:
        _, strategy_equity = execute(platform_config, platform_config.strategy.name)
        html_path = render_equity_html(
            base_curve=pd.Series(dtype=float),
            timed_curve=strategy_equity,
            output_path=output_dir / "再择时-资金曲线.html",
            base_label="参考资金曲线",
            timed_label="策略资金曲线",
        )

    print(f"Interactive equity report saved to {html_path}")


if __name__ == "__main__":
    main()
