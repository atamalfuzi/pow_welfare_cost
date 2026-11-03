"""Checks on the model and every settings block. They read committed files only."""
import numpy as np
import pytest

import model
import run
import settings as s
from settings import with_hist


def test_reproduces_chiu_koeppl_bitcoin_2015():
    r = model.solve(s.BTC_2015_BENCHMARK)
    assert r["cost"] == pytest.approx(0.0143, abs=5e-5)
    assert r["multiple"] == pytest.approx(480.8, abs=1)
    assert r["inflation_equivalent"] == pytest.approx(2.336, abs=0.005)


@pytest.mark.parametrize("c", s.CALIBRATED, ids=lambda c: c["name"])
def test_sigma_is_a_probability(c):
    assert 0 < model.inputs(with_hist(c))["sig"] <= 1


@pytest.mark.parametrize("c", s.CALIBRATED, ids=lambda c: c["name"])
def test_limits_do_not_bind_and_discount_is_annual(c):
    r = run.solve(c)
    assert not r["n_binding"]
    assert not r["grid_binding"]
    assert r["beta_year"] == pytest.approx(model.BETA_YEAR)


@pytest.mark.parametrize("c", [s.BTC_2020, s.ETH_2020], ids=lambda c: c["name"])
def test_no_buyer_gains_from_inviting_a_double_spend(c):
    assert run.solve(c, n_grid=300, check_ds=True)["ds_gain"] < 0


@pytest.mark.parametrize("c", [s.BTC_2020, s.ETH_2020], ids=lambda c: c["name"])
def test_grid_converges(c):
    assert run.solve(c)["cost"] == pytest.approx(run.solve(c, n_grid=4000)["cost"], abs=2e-5)


def test_parts_add_up_to_the_cost():
    r = run.solve(s.ETH_2020)
    assert r["mining"] + r["delay"] + r["wedge"] == pytest.approx(-np.log(1 - r["cost"]), rel=1e-6)


def test_closed_form_matches_bisection():
    # The original code finds the consumption loss by bisection on this expression.
    p = model.inputs(s.BTC_2015_BENCHMARK)
    b, e, f = 1e-60, np.array([1.0, 5.0, 50.0]), np.array([0.5, 0.3, 0.2])
    fb = model.first_best(p, e, f, b)
    target = 0.97 * fb
    c = model.consumption_cost(target, fb, p, e, f)
    x = (1 - c) * (e - b) + b
    w = np.sum(p["sig"] * (e * (np.log(x) - np.log(b)) - (e - b)) * f)
    assert w == pytest.approx(target, rel=1e-10)


def test_cost_tracks_miner_revenue_over_volume():
    for c in (s.BTC_2020, s.ETH_2020):
        share = (c["issuance"] + c["fees"]) / c["volume"]
        assert run.solve(c)["mining"] == pytest.approx(share, rel=0.02)


def test_staking_range_is_ordered():
    e = {**s.ETH_2025, **run.onchain("eth", "traces", 2025)}
    r = model.pos_bracket(e, finality_blocks=64)
    assert 0 < r["low"] < r["high"] < 1
