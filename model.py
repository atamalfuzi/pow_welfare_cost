"""Chiu & Koeppl's Proof-of-Work payment model, calibrated from one settings block.

A Python re-implementation of the method in Chiu & Koeppl, "The Economics of
Cryptocurrencies: Bitcoin and Beyond" (Canadian Journal of Economics, 2022). Their
replication package is at https://doi.org/10.5683/SP3/3WEFMJ and is not copied here.

A day is one period with S blocks. A buyer with taste e picks a payment z and a confirmation
delay N. Double-spending is unprofitable while z <= N(N+1)R, with R the reward per block.
Transfer sizes pin down the distribution of e; welfare then follows from the buyers' choices.
All amounts are in coins.
"""
import numpy as np

BETA_YEAR = 0.97
DAYS_YEAR = 365


def inputs(c):
    """Turn a settings block into model parameters. Block values that are given win."""
    S = round(c["blocks_per_day"])
    Z = c["supply"]
    D = c["volume"]
    return dict(
        S=S,
        Z=Z,
        D=D,
        sig=D / Z,
        mu=c.get("mu", 1 + c.get("issuance", 0) / Z),
        tau=c.get("tau", c.get("fees", 0) / D),
        beta=c.get("beta", BETA_YEAR ** (1 / DAYS_YEAR)),
        B=c.get("B", Z / (D / c["transfers"]) if "transfers" in c else None),
        x=np.asarray(c["x"], float),
        f=np.asarray(c["f"], float) / np.sum(c["f"]),
    )


def grid(n, top, low=0.02):
    # Chiu & Koeppl's grid is n=100, top=1e5, low=0.02.
    return np.linspace(low, 1.01, n) ** 10 * top


def offers(p, e, b):
    """Buyer's best (N, z) at taste e, assuming no double-spend. Also returns the surplus."""
    S, sig, tau, mu, beta = p["S"], p["sig"], p["tau"], p["mu"], p["beta"]
    i, delta, R = mu / beta - 1, beta ** (1 / S), reward(p)
    N = np.arange(1, S)
    dl = delta**N
    d_bar = R * (N + 1) * N
    e_bar = (i + sig) / sig / dl / (1 - tau) * (d_bar * (1 - tau) / (1 + i) + b)
    d_tilde = sig * dl * e * (1 + i) / (i + sig) - (1 + i) * b / (1 - tau)
    z = np.where(e > e_bar, d_bar, d_tilde)
    with np.errstate(all="ignore"):
        u = np.log(z * (1 - tau) / (1 + i) + b) - np.log(b)
        surplus = -mu * z + mu * sig * dl * e * u + (1 - sig) * z * beta
    k = np.nanargmax(surplus)
    return N[k], z[k], surplus[k]


def reward(p):
    return (p["Z"] * (p["mu"] - 1) + p["D"] * p["tau"]) / p["S"]


def cash_welfare(p, e, f, inflation, b):
    """Welfare per buyer of a cash system with this annual inflation and no mining."""
    m = (1 + inflation) ** (1 / DAYS_YEAR)
    x = e / ((m / p["beta"] - 1) / p["sig"] + 1) - b
    return np.sum(p["sig"] * (e * (np.log(x + b) - np.log(b)) - x) * f)


def first_best(p, e, f, b):
    return np.sum(p["sig"] * (e * (np.log(e) - np.log(b)) - (e - b)) * f)


def consumption_cost(welfare, fb, p, e, f):
    """Share of consumption a planner would give up to move from first best to `welfare`.

    Closed form of the bisection in the original code: with x = (1-c)e and b near zero,
    welfare falls by sig*E[e]*log(1/(1-c)).
    """
    return 1 - np.exp(-(fb - welfare) / (p["sig"] * np.sum(e * f)))


def solve(c, b=1e-60, n_grid=100, e_top=1e5, low=0.02, check_ds=False):
    """Calibrate e from transfer sizes, then compute welfare. Returns a dict of results."""
    p = inputs(c)
    sig, tau, mu, beta, S = p["sig"], p["tau"], p["mu"], p["beta"], p["S"]
    delta, R = beta ** (1 / S), reward(p)
    B = p["B"]
    avg = p["Z"] / B

    # Buyer's offer along the taste grid, then invert x(e) at each transfer size.
    v_e = grid(n_grid, e_top, low)
    best = [offers(p, e, b) for e in v_e]
    v_N = np.array([r[0] for r in best], float)
    v_x = np.array([r[1] for r in best]) * (1 - tau)

    x_bin = p["x"] * avg / (p["x"] @ p["f"])
    ux, idx = np.unique(v_x, return_index=True)
    e = np.interp(x_bin, ux, v_e[idx], left=np.nan, right=np.nan)
    if np.isnan(e).any():
        raise ValueError(f"{c.get('name')}: transfer sizes outside the grid, x from {ux[0]:.3g} to {ux[-1]:.3g}")
    x = np.interp(e, v_e, v_x)
    N = np.interp(e, v_e, v_N)
    f = p["f"]

    # Per buyer, so B only enters through the average size. Mining cost is per buyer too.
    dl = delta**N
    u = dl * e * (np.log(x + b) - np.log(b))
    W_c = beta / mu * R * S / B
    W = sig * (u @ f) - sig * (x @ f) - W_c
    fb = first_best(p, e, f, b)
    cost = consumption_cost(W, fb, p, e, f)
    cost_2pct = consumption_cost(cash_welfare(p, e, f, 0.02, b), fb, p, e, f)

    # Where the loss comes from, in shares of consumption. They sum to about `cost`.
    scale = sig * np.sum(e * f)
    mining = W_c / scale
    delay = sig * np.sum(f * e * (1 - dl) * (np.log(x + b) - np.log(b))) / scale
    wedge = sig * np.sum(f * (e * np.log(e / x) - (e - x))) / scale

    out = dict(
        name=c.get("name", ""),
        sigma=sig,
        mu_year=mu**DAYS_YEAR - 1,
        beta_year=beta**DAYS_YEAR,
        tau=tau,
        interest_year=(mu / beta) ** DAYS_YEAR - 1,
        reward_per_block=R,
        cost=cost,
        cost_2pct=cost_2pct,
        multiple=cost / cost_2pct if cost_2pct > 0 else np.inf,
        inflation_equivalent=inflation_equivalent(p, e, f, W, b),
        mining=mining,
        delay=delay,
        wedge=wedge,
        mean_N=N @ f,
        weighted_N=np.sum(N * x * f) / (x @ f),
        top_N=N.max(),
        N_max=S - 1,
        x_top=x_bin.max(),
        grid_x_top=ux[-1],
    )
    # A grid or delay limit that binds would make the result an artefact of the limit.
    out["n_binding"] = bool(N.max() >= S - 1)
    out["grid_binding"] = bool(e.max() >= v_e[-2])
    if check_ds:
        out["ds_gain"] = double_spend_gain(p, e, b, v_e)
    return out


def inflation_equivalent(p, e, f, W, b, top=1000.0):
    """Annual inflation at which a cash system gives the same welfare. inf if above `top`."""
    if cash_welfare(p, e, f, top, b) > W:
        return np.inf
    lo, hi = -0.0, top
    if cash_welfare(p, e, f, lo, b) < W:
        return 0.0
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if cash_welfare(p, e, f, m, b) > W else (lo, m)
    return (lo + hi) / 2


def double_spend_gain(p, e_values, b, v_e):
    """Largest gain any buyer gets from a contract that invites double-spending.

    Chiu & Koeppl assume no-double-spend contracts are optimal and check it numerically.
    Above zero means the assumption fails for some buyer.
    """
    S, sig, tau, mu, beta = p["S"], p["sig"], p["tau"], p["mu"], p["beta"]
    i, delta, R = mu / beta - 1, beta ** (1 / S), reward(p)
    N = np.arange(1, S)[:, None]
    z = v_e[None, :]
    root = np.sqrt(z / R + N + 1)
    P = (root - (N + 1)) / root
    D0 = R * (root - (N + 1)) ** 2 / (1 + i)
    worst = -np.inf
    for e in e_values:
        with np.errstate(all="ignore"):
            u = np.log(z * (1 - P) * (1 - tau) / (1 + i) + b) - np.log(b)
        ds = -mu * z + mu * sig * (delta**N * e * u + D0) + (1 - sig) * beta * z
        ds = np.where(z > (N + 1) * N * R, ds, -np.inf)
        worst = max(worst, np.nanmax(ds) - offers(p, e, b)[2])
    return worst


def pos_bracket(c, finality_blocks, b=1e-60):
    """Rough range for a chain with no hash race. Not a result of Chiu & Koeppl's model.

    The double-spend limit and free-entry mining do not describe staking, so buyers here
    just wait a fixed time for finality and hold money at the net growth rate. The low end
    treats validator income as a pure transfer. The high end treats all of it as used up,
    as free entry does with mining rewards.
    """
    p = inputs(c)
    sig, tau, mu, beta, S = p["sig"], p["tau"], p["mu"], p["beta"], p["S"]
    i, dl = mu / beta - 1, beta ** (finality_blocks / S)
    f = p["f"]
    avg = p["Z"] / p["B"]
    x = p["x"] * avg / (p["x"] @ f)
    # Same demand as d_tilde above with no binding constraint, with b negligible.
    e = x / (sig * dl * (1 + i) * (1 - tau) / (i + sig))
    u = dl * e * (np.log(x + b) - np.log(b))
    fb = first_best(p, e, f, b)
    W = sig * (u @ f) - sig * (x @ f)
    low = consumption_cost(W, fb, p, e, f)
    high = consumption_cost(W - beta / mu * c["validator_income"] / p["B"], fb, p, e, f)
    return dict(low=low, high=high, sigma=sig, mu_year=mu**DAYS_YEAR - 1, tau=tau)
