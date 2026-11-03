"""Rebuild the yearly inputs in settings.py from public sources.

Writes results/inputs.csv and prints any value that differs from settings.py. Raw files stay
in data/, which is not committed: Coin Metrics community data is CC BY-NC.

Coin Metrics no longer serves adjusted transfer value (TxTfrValAdjNtv) to the community tier.
Bitcoin's comes from an archived copy of its community file, which ends in May 2024.
Ethereum's has no public archive; put a copy of a community eth.csv from before that change
at data/eth_coinmetrics_2021.csv. Without it the Ethereum volume stays as recorded in settings.py.
"""
import csv
import json
import urllib.request

import pandas as pd

import settings
from settings import ROOT

COMMUNITY = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={asset}"
             "&metrics=SplyCur,IssTotNtv,FeeTotNtv,BlkCnt,TxCnt,TxTfrCnt&start_time=2015-01-01"
             "&frequency=1d&page_size=10000&paging_from=start&format=csv")
ARCHIVED_BTC = ("https://web.archive.org/web/20240525015326id_/"
                "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv")
BLOCKCHAIN_COM = ("https://api.blockchain.info/charts/estimated-transaction-volume"
                  "?timespan={years}year&start={start}&format=json&sampled=false")
WINDOWS = {
    "btc_2015": ("btc", "2015-01-01", "2015-12-31"),
    "btc_2020": ("btc", "2020-01-01", "2020-12-31"),
    "btc_2020_after_halving": ("btc", "2020-05-11", "2020-12-31"),
    "eth_2020": ("eth", "2020-01-01", "2020-12-31"),
    "btc_2025": ("btc", "2025-01-01", "2025-12-31"),
    "btc_since_2024_halving": ("btc", "2024-04-20", "2026-10-31"),
    "eth_2025": ("eth", "2025-01-01", "2025-12-31"),
}
DATA = ROOT / "data"


def fetch(url, name):
    path = DATA / name
    if not path.exists():
        DATA.mkdir(exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as r:
            path.write_bytes(r.read())
    return path


def daily(path, time_col):
    d = pd.read_csv(path, low_memory=False)
    d[time_col] = pd.to_datetime(d[time_col].astype(str).str[:10])
    return d.set_index(time_col)


def blockchain_com():
    frames = []
    for start, years in (("2015-01-01", 1), ("2020-01-01", 1), ("2024-01-01", 3)):
        path = fetch(BLOCKCHAIN_COM.format(start=start, years=years), f"blockchain_com_{start}.json")
        values = json.loads(path.read_text())["values"]
        frames.append(pd.Series({pd.to_datetime(v["x"], unit="s"): v["y"] for v in values}))
    return pd.concat(frames).groupby(level=0).first()


def build():
    live = {a: daily(fetch(COMMUNITY.format(asset=a), f"{a}_community.csv"), "time") for a in ("btc", "eth")}
    adj = {"btc": daily(fetch(ARCHIVED_BTC, "btc_coinmetrics_2024.csv"), "time")["TxTfrValAdjNtv"]}
    eth_file = DATA / "eth_coinmetrics_2021.csv"
    if eth_file.exists():
        adj["eth"] = daily(eth_file, "date")["TxTfrValAdjNtv"]
    bc = blockchain_com()
    rows = []
    for name, (asset, start, end) in WINDOWS.items():
        s = live[asset].loc[start:end].astype(float, errors="ignore")
        n = len(s)
        row = dict(window=name, days=n, blocks_per_day=s["BlkCnt"].mean(), supply=s["SplyCur"].mean(),
                   issuance=s["IssTotNtv"].mean(), fees=s["FeeTotNtv"].mean(),
                   net_supply_growth=(s["SplyCur"].iloc[-1] - s["SplyCur"].iloc[0]) / (n - 1),
                   tx_count=s["TxCnt"].mean(), transfer_count=s["TxTfrCnt"].mean())
        if asset in adj and len(adj[asset].loc[start:end].dropna()) == n:
            row["volume_coin_metrics_adjusted"] = adj[asset].loc[start:end].mean()
        if asset == "btc" and len(bc.loc[start:end]) >= 0.98 * n:
            row["volume_blockchain_com"] = bc.loc[start:end].mean()
        rows.append(row)
    return pd.DataFrame(rows).set_index("window")


def compare(table):
    """Print settings values that drift from the fresh figures by more than 0.1%."""
    pairs = {"btc_2020": settings.BTC_2020, "eth_2020": settings.ETH_2020, "btc_2025": settings.BTC_2025}
    for window, block in pairs.items():
        for key in ("blocks_per_day", "supply", "issuance", "fees"):
            new, old = table.loc[window, key], block[key]
            if abs(new / old - 1) > 0.001:
                print(f"{window} {key}: settings {old}, fresh {new}")


if __name__ == "__main__":
    table = build()
    table.to_csv(ROOT / "results" / "inputs.csv", float_format="%.6f")
    print(table.T.to_string())
    compare(table)
