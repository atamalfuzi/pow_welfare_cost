"""Run every scenario in the README and write the tables to results/."""
import csv

import numpy as np
import pandas as pd

import histogram
import model
import settings as s
from settings import ROOT, with_hist

FINE = dict(n_grid=1500, e_top=1e7)  # Wide enough for the largest measured transfers.
KEEP = ("name sigma mu_year beta_year tau interest_year reward_per_block cost cost_2pct multiple "
        "inflation_equivalent mining delay wedge mean_N weighted_N top_N N_max n_binding grid_binding").split()


def write(name, rows):
    with (ROOT / "results" / f"{name}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def solve(c, **kw):
    return model.solve(with_hist(c), **{**FINE, **kw})


def row(r, **extra):
    return {**extra, **{k: r[k] for k in KEEP}}


def same_year():
    """Bitcoin and Ethereum in 2020, with Chiu & Koeppl's Bitcoin 2015 inputs for reference."""
    rows = []
    for c in (s.BTC_2020, s.ETH_2020):
        r = row(solve(c))
        r["double_spend_gain"] = solve(c, n_grid=300, check_ds=True)["ds_gain"]
        r["revenue_over_volume"] = (c["issuance"] + c["fees"]) / c["volume"]
        rows.append(r)
    rows.append(row(model.solve(s.BTC_2015_BENCHMARK)))
    write("same_year", rows)
    return rows


def onchain(coin, source, year=2020):
    """Daily volume and count from the transfer histogram itself."""
    with (ROOT / "results" / f"hist_{coin}_{year}.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if r["source"] == source]
    days = int(rows[0]["days"])
    return dict(volume=sum(float(r["sum"]) for r in rows) / days,
                transfers=sum(int(r["count"]) for r in rows) / days,
                **s.histogram(coin, year, source))


def without_largest(c, cap):
    """The block with transfers of `cap` coins or more left out of the histogram."""
    h = with_hist(c)
    keep = [i for i, x in enumerate(h["x"]) if x < cap]
    return {**h, "x": [h["x"][i] for i in keep], "f": [h["f"][i] for i in keep]}


def sensitivity():
    b, e = s.BTC_2020, s.ETH_2020

    def beta(year):
        return dict(beta=year ** (1 / 365))

    cases = [
        ("Baseline", b, e, {}),
        ("Bitcoin on blockchain.com volume (Chiu & Koeppl's source)", s.BTC_2020_BLOCKCHAIN_COM, e, {}),
        ("Bitcoin after the May 2020 halving only", s.BTC_2020_AFTER_HALVING, e, {}),
        ("Own on-chain volume: Bitcoin without largest output, Ethereum all traces",
         {**b, **onchain("btc", "nochange")}, {**e, **onchain("eth", "traces")}, {}),
        ("Bitcoin without transfers of 10,000 coins or more", without_largest(b, 1e4), e, {}),
        ("Bitcoin without transfers of 1,000 coins or more", without_largest(b, 1e3), e, {}),
        ("Ethereum top-level transactions only, volume and sizes", b, {**e, **onchain("eth", "transactions")}, {}),
        ("Bitcoin on Chiu & Koeppl's 2015 transfer size table", {**b, "x": s.CK_BTC_X, "f": s.CK_BTC_F}, e, {}),
        ("Discount of 0.95 a year", {**b, **beta(0.95)}, {**e, **beta(0.95)}, {}),
        ("Discount of 0.99 a year", {**b, **beta(0.99)}, {**e, **beta(0.99)}, {}),
        ("Utility shifter b = 1e-30", b, e, dict(b=1e-30)),
        ("Utility shifter b = 1e-15", b, e, dict(b=1e-15)),
        ("Finer grid, 4000 points", b, e, dict(n_grid=4000)),
    ]
    rows = []
    for label, cb, ce, kw in cases:
        rb, re = solve(cb, **kw), solve(ce, **kw)
        rows.append(dict(case=label, bitcoin=rb["cost"], ethereum=re["cost"],
                         bitcoin_multiple=rb["multiple"], ethereum_multiple=re["multiple"],
                         bitcoin_inflation=rb["inflation_equivalent"], ethereum_inflation=re["inflation_equivalent"],
                         bitcoin_sigma=rb["sigma"], ethereum_sigma=re["sigma"]))
    write("sensitivity", rows)
    return rows


def sampling(draws=200, seed=1):
    """How much the histogram's days matter: resample days, keep totals of volume and fees."""
    rng = np.random.default_rng(seed)
    rows = []
    for c, path, step in ((s.BTC_2020, "btc_2020_nochange_daily.csv", 5), (s.ETH_2020, "eth_2020_traces_daily.csv", 1)):
        path = ROOT / "data" / path
        if not path.exists():  # Daily bins are not committed.
            return []
        d = pd.read_csv(path)
        d = d[d.day.isin(list(histogram.days("2020-01-01", "2020-12-31", step))) & ((d.k >= 0) | (step == 1))]
        d = d.assign(k=d.k.clip(lower=histogram.EDGES.index(5e-7)))  # Same floor as settings.histogram.
        table = d.pivot_table(index="day", columns="k", values=["count", "sum"], aggfunc="sum", fill_value=0.0)
        counts, sums = table["count"].to_numpy(), table["sum"].to_numpy()
        costs, delays = [], []
        for _ in range(draws):
            pick = rng.integers(len(table), size=len(table))
            n, v = counts[pick].sum(axis=0), sums[pick].sum(axis=0)
            keep = n > 0
            r = model.solve({**c, "x": v[keep] / n[keep], "f": n[keep]}, n_grid=400, e_top=1e7)
            costs.append(r["cost"])
            delays.append(r["delay"])
        rows.append(dict(name=c["name"], days=len(table), draws=draws, cost_low=np.quantile(costs, 0.025),
                         cost_high=np.quantile(costs, 0.975), delay_low=np.quantile(delays, 0.025),
                         delay_high=np.quantile(delays, 0.975)))
    write("sampling", rows)
    return rows


def sweeps():
    """Cost as rewards and fees change, holding volume and transfer sizes fixed."""
    rows = []
    for c in (s.BTC_2020, s.ETH_2020):
        c = with_hist(c)
        total = c["issuance"] + c["fees"]
        changes = [("reward", v, dict(issuance=c["issuance"] * v, fees=c["fees"] * v))
                   for v in np.geomspace(0.02, 4, 45)]
        changes += [("fee_share", v, dict(fees=v * c["volume"])) for v in np.linspace(0, 0.05, 26)]
        changes += [("fee_mix", v, dict(issuance=total * (1 - v), fees=total * v)) for v in np.linspace(0, 1, 11)]
        for sweep, value, change in changes:
            try:
                r = model.solve({**c, **change}, n_grid=500, e_top=1e7)
            except ValueError:  # The largest transfers cannot be made safe within a day.
                continue
            rows.append(dict(coin=c["name"], sweep=sweep, value=float(value), cost=r["cost"], mining=r["mining"],
                             delay=r["delay"], wedge=r["wedge"], weighted_N=r["weighted_N"],
                             reward_per_block=r["reward_per_block"], n_binding=r["n_binding"]))
    write("sweeps", rows)
    return rows


def halvings():
    """Bitcoin's subsidy schedule at 2025 volume and fees, on the blockchain.com measure."""
    c = with_hist(s.BTC_2025)
    rows = []
    for subsidy in (12.5, 6.25, 3.125, 1.5625, 0.78125, 0.390625, 0.1953125):
        try:
            r = model.solve({**c, "issuance": subsidy * c["blocks_per_day"]}, n_grid=500, e_top=1e7)
        except ValueError:
            continue
        rows.append(dict(subsidy=subsidy, cost=r["cost"], mining=r["mining"], delay=r["delay"], wedge=r["wedge"],
                         weighted_N=r["weighted_N"], top_N=r["top_N"], n_binding=r["n_binding"]))
    write("halvings", rows)
    return rows


def extensions():
    rows = [row(solve(c)) for c in (s.BTC_2015_BENCHMARK, s.BTC_2015, s.BTC_2015_BLOCKCHAIN_COM, s.BTC_2020,
                                    s.BTC_2020_BLOCKCHAIN_COM, s.BTC_2025, s.BTC_SINCE_2024)]
    write("bitcoin_over_time", rows)
    e = {**s.ETH_2025, **onchain("eth", "traces", 2025)}
    # Finality takes 2 epochs of 32 slots.
    bracket = {"name": e["name"], "volume_onchain": e["volume"], **model.pos_bracket(e, finality_blocks=64)}
    write("ethereum_after_merge", [bracket])
    return rows + [bracket]


if __name__ == "__main__":
    for fn in (same_year, sensitivity, sampling, sweeps, halvings, extensions):
        out = fn()
        if fn is not sweeps:
            print(f"--- {fn.__name__}")
            for r in out:
                print({k: f"{v:.4g}" if isinstance(v, float) else v for k, v in r.items()})
