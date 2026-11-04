"""Draw the README charts from the tables in results/."""
import csv
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from settings import ROOT

RESULTS, FIGURES = ROOT / "results", ROOT / "figures"
INK, MUTED, GREY, GRID = "#0b0b0b", "#52514e", "#a8a7a2", "#e6e5e1"
BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#3a9b6a"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False,
                     "axes.titlelocation": "left", "axes.titlecolor": INK, "axes.titlesize": 12})
SOURCE = "Sources: Coin Metrics community data, blockchain.com, AWS Public Blockchain Data; model from Chiu & Koeppl (2022)."


def table(name):
    with (RESULTS / f"{name}.csv").open() as f:
        rows = list(csv.DictReader(f))
    return [{k: _number(v) for k, v in r.items()} for r in rows]


def _number(v):
    try:
        return float(v)
    except ValueError:
        return v


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 138)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def percent(ax, axis="y", digits=1):
    getattr(ax, f"{axis}axis").set_major_formatter(lambda v, _: f"{v:.{digits}f}%")


def same_year():
    bitcoin, ethereum, benchmark = table("same_year")
    rows = [("Bitcoin 2015\nChiu & Koeppl inputs", benchmark), ("Bitcoin 2020", bitcoin), ("Ethereum 2020", ethereum)]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.82, bottom=0.2)
    x = np.arange(len(rows))
    bottom = np.zeros(len(rows))
    for key, colour, label in (("mining", BLUE, "Mining"), ("delay", ORANGE, "Waiting for confirmations"),
                               ("wedge", GREEN, "Less trade from inflation and fees")):
        h = np.array([r[key] * 100 for _, r in rows])
        ax.bar(x, h, 0.5, bottom=bottom, color=colour, label=label, edgecolor="white", linewidth=1.5)
        bottom += h
    for xx, (_, r), top in zip(x, rows, bottom):
        ax.annotate(f"{r['cost'] * 100:.2f}%", (xx, top), xytext=(0, 5), textcoords="offset points", ha="center", color=INK)
    ax.set_xticks(x, [r[0] for r in rows])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of consumption")
    percent(ax)
    ax.set_ylim(0, bottom.max() * 1.15)
    ax.legend(loc="upper right")
    save(fig, "same_year.png", "Most of the cost is mining, and mining is revenue over volume",
         "Welfare cost by source, as a share of consumption.",
         "Mining cost is close to (issuance + fees) / transfer volume. Waiting costs more on Bitcoin because blocks are 10 minutes "
         "and large transfers need many of them. " + SOURCE)


def sensitivity():
    rows = table("sensitivity")
    short = ["Baseline", "Bitcoin on blockchain.com volume", "Bitcoin after May 2020 halving",
             "Own on-chain volume, both coins", "Bitcoin without transfers over 10,000",
             "Bitcoin without transfers over 1,000", "Ethereum top-level transactions only", "Bitcoin on Chiu & Koeppl's 2015 sizes",
             "Discount of 0.95 a year", "Discount of 0.99 a year", "Utility shifter b = 1e-30",
             "Utility shifter b = 1e-15", "Finer grid"]
    y = np.arange(len(rows))[::-1]
    fig, ax = plt.subplots(figsize=(10, 6.4))
    fig.subplots_adjust(left=0.34, right=0.96, top=0.85, bottom=0.16)
    for r, yy in zip(rows, y):
        ax.plot([r["bitcoin"] * 100, r["ethereum"] * 100], [yy, yy], color=GREY, lw=1.5, zorder=1)
    ax.scatter([r["bitcoin"] * 100 for r in rows], y, color=ORANGE, s=70, zorder=3, edgecolor="white", linewidth=1.2, label="Bitcoin 2020")
    ax.scatter([r["ethereum"] * 100 for r in rows], y, color=BLUE, marker="s", s=60, zorder=3, edgecolor="white", linewidth=1.2, label="Ethereum 2020")
    ax.set_yticks(y, short)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(left=0)
    percent(ax, "x")
    ax.set_xlabel("Welfare cost, share of consumption")
    ax.legend(loc="lower left")
    save(fig, "sensitivity.png", "The gap is small next to the choice of volume measure",
         "Same-year estimates under other choices. Ethereum is lower in all but one row.",
         "Each row changes one choice from the baseline. How much on-chain value counts as a payment moves both coins more than the model's other settings do. " + SOURCE)


def rewards():
    rows = table("sweeps")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), sharey=False)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.76, bottom=0.26, wspace=0.2)
    ax = axes[0]
    for coin, colour, marker in (("Bitcoin 2020", ORANGE, "o"), ("Ethereum 2020", BLUE, "s")):
        r = [x for x in rows if x["coin"] == coin and x["sweep"] == "reward"]
        ax.plot([x["value"] for x in r], [x["cost"] * 100 for x in r], color=colour, lw=2, label=coin)
        low = min(r, key=lambda x: x["cost"])
        ax.scatter([low["value"]], [low["cost"] * 100], color=colour, marker=marker, s=60, zorder=3, edgecolor="white", linewidth=1.2)
    ax.axvline(1, color=GREY, lw=1, ls="--")
    ax.annotate("Actual 2020", (1, 0.12), xytext=(5, 0), textcoords="offset points", color=MUTED, fontsize=10)
    ax.set_xscale("log")
    ax.set_xticks([0.02, 0.1, 0.5, 1, 4])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:g}×")
    ax.xaxis.set_minor_formatter(lambda v, _: "")
    ax.set_xlabel("Miner reward relative to actual (log scale)")
    ax.set_title("Rewards")
    ax.set_ylim(0, 2)
    ax.set_yticks(np.arange(0, 2.01, 0.5))
    percent(ax)
    ax.legend(loc="upper left")
    ax = axes[1]
    for coin, colour in (("Bitcoin 2020", ORANGE), ("Ethereum 2020", BLUE)):
        r = [x for x in rows if x["coin"] == coin and x["sweep"] == "fee_share"]
        ax.plot([x["value"] * 100 for x in r], [x["cost"] * 100 for x in r], color=colour, lw=2, label=coin)
    ax.set_xlabel("Fees as a share of transfer value")
    ax.set_title("Fees, with issuance unchanged")
    percent(ax)
    percent(ax, "x", 0)
    ax.legend(loc="upper left")
    save(fig, "rewards.png", "Lower rewards cut the cost until waiting takes over",
         "Welfare cost with volume and transfer sizes held at 2020 values. Dots mark each coin's lowest cost.",
         "Bitcoin's line stops where the largest transfers could no longer be made safe within a day, a limit the model sets. "
         "Volume would also respond in practice, and the model ignores network delays that shorter blocks bring. " + SOURCE)


def halvings():
    rows = table("halvings")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.8, bottom=0.3)
    x = np.arange(len(rows))
    bottom = np.zeros(len(rows))
    for key, colour, label in (("mining", BLUE, "Mining"), ("delay", ORANGE, "Waiting for confirmations"),
                               ("wedge", GREEN, "Less trade from inflation and fees")):
        h = np.array([r[key] * 100 for r in rows])
        ax.bar(x, h, 0.5, bottom=bottom, color=colour, label=label, edgecolor="white", linewidth=1.5)
        bottom += h
    for xx, r, top in zip(x, rows, bottom):
        ax.annotate(f"{r['cost'] * 100:.2f}%", (xx, top), xytext=(0, 5), textcoords="offset points", ha="center", color=INK)
    current = chr(10) + "(2024 to 2028)"
    ax.set_xticks(x, [f"{r['subsidy']:g}" + (current if r["subsidy"] == 3.125 else "") for r in rows])
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Bitcoin subsidy per block")
    percent(ax)
    ax.set_ylim(0, bottom.max() * 1.15)
    ax.set_yticks(np.arange(0, 2.01, 0.5))
    ax.legend(loc="upper right")
    save(fig, "halvings.png", "Further halvings help until waiting costs more than mining",
         "Bitcoin's welfare cost at each subsidy, with volume, fees and transfer sizes held at 2025 values.",
         "Below the smallest subsidy shown, the largest transfers could not be made safe within a day. Volume is blockchain.com's estimate, which is "
         "lower than Coin Metrics in 2020, so levels are not comparable with the 2020 baseline. " + SOURCE)


def histogram():
    fig, ax = plt.subplots(figsize=(10, 4.8))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.8, bottom=0.2)
    for key, source, colour, marker, label in ((("btc", 2020), "nochange", ORANGE, "o", "Bitcoin"),
                                               (("eth", 2020), "traces", BLUE, "s", "Ethereum")):
        with (RESULTS / f"hist_{key[0]}_{key[1]}.csv").open() as f:
            rows = [r for r in csv.DictReader(f) if r["source"] == source]
        hi = np.array([float(r["upper"]) for r in rows])
        count = np.array([int(r["count"]) for r in rows], float)
        total = np.array([float(r["sum"]) for r in rows])
        order = np.argsort(hi)
        ax.plot(hi[order], np.cumsum(total[order]) / total.sum() * 100, color=colour, lw=2, label=f"{label}, value")
        ax.plot(hi[order], np.cumsum(count[order]) / count.sum() * 100, color=colour, lw=1.3, ls="--", label=f"{label}, transfers")
    ax.set_xscale("log")
    ax.set_xlim(1e-6, 1e6)
    ax.set_xlabel("Transfer size in coins, up to (log scale)")
    ax.set_ylabel("Cumulative share")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.legend(loc="upper left")
    save(fig, "transfer_sizes.png", "Most transfers are small and most value is in large ones",
         "Cumulative share of transfers and of value by transfer size, 2020.",
         "Bins from AWS Public Blockchain Data, read with DuckDB without downloading the tables. Ethereum is all value transfers on every day of 2020. "
         "Bitcoin is transactions without their largest output, every 5th day. A coin of each differs in price, so compare shapes only.")


if __name__ == "__main__":
    FIGURES.mkdir(exist_ok=True)
    same_year()
    sensitivity()
    rewards()
    halvings()
    histogram()
