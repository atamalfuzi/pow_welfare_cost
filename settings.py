"""One block per coin and year. Amounts are coins per day and supply is the yearly mean.

data.py rebuilds the yearly means from public sources and compares them with these values.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).parent

# Chiu & Koeppl's 2015 Bitcoin transfer size table: bin midpoints, with the top bin at its
# lower edge.
_btc_hi = [0.001, 0.1, 1, 10, 50, 100, 500, 5000, 20000, 50000]
_btc_lo = [0, 0.001, 0.1, 1, 10, 50, 100, 500, 5000, 20000]
CK_BTC_X = [(a + c) / 2 for a, c in zip(_btc_lo, _btc_hi)] + [50000]
CK_BTC_F = [0.168591758, 0.30049057, 0.213389126, 0.162366352, 0.08878155, 0.041791729,
            0.019093842, 0.004902712, 0.000436845, 0.000130762, 2.47546e-05]

# Discount per 10 minutes that gives 0.97 a year at 144 blocks a day.
CK_DELTA = 0.999999420487088


def histogram(coin, year, source, floor=1e-6):
    """Bin means and counts from results/hist_*.csv. Bins under `floor` coins are merged."""
    rows = []
    with (ROOT / "results" / f"hist_{coin}_{year}.csv").open() as f:
        for r in csv.DictReader(f):
            if r["source"] == source:
                rows.append((float(r["upper"]), int(r["count"]), float(r["sum"])))
    rows.sort()
    small = [r for r in rows if r[0] <= floor]
    rows = [r for r in rows if r[0] > floor]
    if small:
        rows.insert(0, (floor, sum(r[1] for r in small), sum(r[2] for r in small)))
    return dict(x=[r[2] / r[1] for r in rows], f=[r[1] for r in rows])


# --- Chiu & Koeppl's Bitcoin calibration: blockchain.info 2015 averages ----------------

BTC_2015_BENCHMARK = dict(
    name="Bitcoin 2015, Chiu & Koeppl inputs",
    blocks_per_day=144, supply=14342502.9452055, volume=1769.74429223744 * 144,
    mu=1 + 0.000001743 * 144, tau=0.000088129, beta=CK_DELTA**144, B=6873428.441,
    x=CK_BTC_X, f=CK_BTC_F)

# --- 2020 -------------------------------------------------------------------------------

BTC_2020 = dict(
    name="Bitcoin 2020",
    blocks_per_day=145.415, supply=18399864.311, issuance=1238.490, fees=71.889,
    volume=241313.643,  # Coin Metrics TxTfrValAdjNtv, from an archived community file
    transfers=307371.951,  # Coin Metrics TxCnt, as Chiu & Koeppl's average size uses
    hist=("btc", 2020, "nochange"))

ETH_2020 = dict(
    name="Ethereum 2020",
    blocks_per_day=6480.199, supply=111588736.557, issuance=13620.333, fees=4164.317,
    volume=3118464.646,  # Coin Metrics TxTfrValAdjNtv, from a May 2021 community file
    transfers=529213.656,  # Coin Metrics TxTfrCnt
    hist=("eth", 2020, "traces"))

# Bitcoin on the measure Chiu & Koeppl used, blockchain.com's estimated transaction value.
# It runs lower than Coin Metrics in 2020, and is the only one still public after May 2024.
BTC_2020_BLOCKCHAIN_COM = dict(BTC_2020, name="Bitcoin 2020, blockchain.com volume", volume=153241.999)

# The subsidy halved on 11 May 2020, so the calendar year mixes two rates. This is the
# stretch after it, on the same volume measure as BTC_2020.
BTC_2020_AFTER_HALVING = dict(
    name="Bitcoin 2020, after the May halving",
    blocks_per_day=144.877, supply=18480590.0, issuance=908.883, fees=94.029,
    volume=241613.4, transfers=309358.6,
    hist=("btc", 2020, "nochange"))

# Chiu & Koeppl's year on the Coin Metrics measure, to separate data source from period.
BTC_2015 = dict(
    name="Bitcoin 2015, Coin Metrics volume",
    blocks_per_day=148.825, supply=14343535.0, issuance=3720.616, fees=22.467,
    volume=312112.8, transfers=124994.293,
    x=CK_BTC_X, f=CK_BTC_F)

# --- Bitcoin after the April 2024 halving, 2025 calendar year ---------------------------

BTC_2025 = dict(
    name="Bitcoin 2025, blockchain.com volume",
    blocks_per_day=145.430, supply=19887063.072, issuance=454.469, fees=4.712,
    volume=98316.581, transfers=421056.214,
    hist=("btc", 2025, "nochange"))

BTC_SINCE_2024 = dict(
    BTC_2025, name="Bitcoin, April 2024 to October 2026, blockchain.com volume",
    blocks_per_day=144.912, supply=19897318.0, issuance=452.851, fees=11.351,
    volume=99335.815, transfers=520157.139)

BTC_2015_BLOCKCHAIN_COM = dict(BTC_2015, name="Bitcoin 2015, blockchain.com volume", volume=281502.398)

# --- Ethereum after the Merge, 2025 calendar year. See model.pos_bracket ----------------

ETH_2025 = dict(
    name="Ethereum 2025, after the Merge",
    blocks_per_day=7151.129, supply=120882760.313,
    # Net supply growth: issuance 2,636.792 less about 262.5 burned (issuance minus the
    # change in SplyCur). Fees actually kept by validators are total fees less the burn.
    issuance=2374.278, fees=470.797,
    validator_income=2636.792 + (470.797 - (2636.792 - 2374.278)),
    volume=None,  # filled in from histogram.py; Coin Metrics no longer publishes it
    transfers=1221377.238,
    hist=("eth", 2025, "traces"))


def with_hist(c):
    """Return the block with its histogram loaded."""
    return c if "x" in c else {**c, **histogram(*c["hist"])}


CALIBRATED = [BTC_2020, ETH_2020, BTC_2020_BLOCKCHAIN_COM, BTC_2020_AFTER_HALVING, BTC_2015, BTC_2015_BLOCKCHAIN_COM,
             BTC_2025, BTC_SINCE_2024]
