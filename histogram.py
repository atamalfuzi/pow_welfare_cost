"""Transfer-value histograms from AWS's public blockchain bucket, without downloading it.

DuckDB reads only the needed Parquet columns over S3 with unsigned requests and returns
one count and one sum per bin. Daily bins go to data/ so a stopped run resumes; yearly
totals go to results/. About 15 minutes for an Ethereum year and an hour for a Bitcoin sample.

    python histogram.py eth 2020
    python histogram.py btc 2020
"""
import csv
import datetime as dt
import sys
from pathlib import Path

import duckdb

BUCKET = "s3://aws-public-blockchain/v1.0"
ROOT = Path(__file__).parent
# 1, 2 and 5 per decade.
EDGES = [m * 10.0**k for k in range(-9, 7) for m in (1, 2, 5)]

# A successful value-carrying call, contract creation or self-destruct. delegatecall
# repeats the parent's value without moving it and reward is issuance, so both stay out.
ETH_TRACES = """SELECT value/1e18 AS v FROM read_parquet('{url}/eth/traces/date={day}/*.parquet')
    WHERE value>0 AND status=1 AND (call_type='call' OR trace_type IN ('create','suicide'))"""
ETH_TXS = """SELECT value/1e18 AS v FROM read_parquet('{url}/eth/transactions/date={day}/*.parquet')
    WHERE value>0 AND receipt_status=1"""
# Bitcoin has no sender-labelled payment value. Dropping the largest output is a rough
# proxy for dropping change; a single-output transaction counts in full.
BTC_NOCHANGE = """SELECT CASE WHEN output_count>1 THEN output_value-m ELSE output_value END AS v
    FROM (SELECT output_value, output_count, list_max(list_transform(outputs, lambda o: o.value)) AS m
          FROM read_parquet('{url}/btc/transactions/date={day}/*.parquet')
          WHERE NOT is_coinbase) WHERE output_value>0"""
BTC_OUTPUTS = """SELECT output_value AS v FROM read_parquet('{url}/btc/transactions/date={day}/*.parquet')
    WHERE NOT is_coinbase AND output_value>0"""
# Bitcoin's nested outputs take about 40 seconds a day to read, so it is sampled. The file
# records how many days were read, so totals can be turned back into daily means.
DAY_STEP = {("btc", "2020"): 5, ("btc", "2025"): 10}
SOURCES = {
    "eth": {"traces": ETH_TRACES, "transactions": ETH_TXS},
    "btc": {"nochange": BTC_NOCHANGE, "outputs": BTC_OUTPUTS},
}


def days(start, end, step=1):
    d = dt.date.fromisoformat(start)
    while d <= dt.date.fromisoformat(end):
        yield d.isoformat()
        d += dt.timedelta(days=step)


def bins_for_day(con, query, day):
    """Return {lower edge index: (count, sum)} for one day. Index -1 is below the lowest edge."""
    rows = con.execute(
        f"""WITH t AS ({query.format(url=BUCKET, day=day)}),
                 b AS (SELECT CASE WHEN v < {EDGES[0]} THEN -1 ELSE
                      len(list_filter({EDGES}::DOUBLE[], lambda e: e <= v)) - 1 END AS k, v FROM t)
            SELECT k, count(*), sum(v) FROM b GROUP BY k""").fetchall()
    return {k: (n, s) for k, n, s in rows}


def run(coin, start, end, tag, step=1):
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-east-2';")
    out = {}
    for name, query in SOURCES[coin].items():
        path = ROOT / "data" / f"{coin}_{tag}_{name}_daily.csv"
        path.parent.mkdir(exist_ok=True)
        done = set()
        if path.exists():
            with path.open() as f:
                done = {r["day"] for r in csv.DictReader(f)}
        write_header = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["day", "k", "count", "sum"])
            wanted = list(days(start, end, step))
            for day in wanted:
                if day in done:
                    continue
                for k, (n, s) in bins_for_day(con, query, day).items():
                    w.writerow([day, k, n, repr(s)])
                f.flush()
                print(coin, name, day, flush=True)
        totals = {}
        with path.open() as f:
            for r in csv.DictReader(f):
                # Bitcoin's smallest unit is 1e-8, so its lowest bin holds only transactions
                # with nothing left once the largest output is dropped.
                if r["day"] not in wanted or (coin == "btc" and int(r["k"]) < 0):
                    continue
                n, s = totals.get(int(r["k"]), (0, 0.0))
                totals[int(r["k"])] = (n + int(r["count"]), s + float(r["sum"]))
        out[name] = totals
    dest = ROOT / "results" / f"hist_{coin}_{tag}.csv"
    with dest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "lower", "upper", "count", "sum", "days"])
        for name, totals in out.items():
            for k in sorted(totals):
                lo = 0.0 if k < 0 else EDGES[k]
                hi = EDGES[k + 1] if k + 1 < len(EDGES) else float("inf")
                w.writerow([name, lo, hi, totals[k][0], repr(totals[k][1]), len(wanted)])
    print("wrote", dest)


if __name__ == "__main__":
    coin, year = sys.argv[1], sys.argv[2]
    run(coin, f"{year}-01-01", f"{year}-12-31", year, DAY_STEP.get((coin, year), 1))
