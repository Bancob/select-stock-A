import akshare as ak
import pandas as pd
from pathlib import Path

DATA_DIR = Path('multimarket/sample_data/daily_bar')
DATA_DIR.mkdir(parents=True, exist_ok=True)

symbols = {
    '000001': '000001.SZ',
    '000333': '000333.SZ',
    '600519': '600519.SH',
}
frames = []
for raw_code, ts_code in symbols.items():
    df = ak.stock_zh_a_hist(
        symbol=raw_code,
        period='daily',
        start_date='20220101',
        end_date='20250101',
        adjust='qfq',
    )
    if df.empty:
        continue
    df = df.rename(
        columns={
            '日期': 'trade_date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
        }
    )
    df = df[['trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df['ts_code'] = ts_code
    frames.append(df)

if not frames:
    raise SystemExit('No data fetched')

full = pd.concat(frames, ignore_index=True)
full = full.sort_values(['trade_date', 'ts_code']).reset_index(drop=True)
full['trade_date'] = full['trade_date'].dt.strftime('%Y-%m-%d')
full.to_csv(DATA_DIR / 'cn_daily.csv', index=False)
print('saved', len(full), 'rows')
