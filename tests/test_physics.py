import math

import numpy as np
import pytest

from allure import Group, PowerTarget, Rider, Route, Settings, Solo, estimate, prepare
from allure.params import Equipment, Pacing

FLAT_PACING = Pacing(climb_boost=0.0, descent_scale=1e9)


def straight(length_m=10_000, grade=0.0, n=500):
    """Straight north-going route with constant grade."""
    d = np.linspace(0, length_m, n)
    lat = 45.0 + d / 111_195.0
    return Route.from_points(lat, np.full(n, 5.0), 100 + grade * d)


def test_flat_speed_matches_hand_computation():
    # 0.5*1.2*0.32*v^3 + 0.0045*76.5*g*v = 200*0.976  ->  v ~ 9.4 m/s (33.9 km/h)
    s = Settings(pacing=FLAT_PACING)
    res = estimate(straight(), Rider(68.0), power=PowerTarget(200, "avg"), settings=s)
    assert 33.0 < res.avg_speed_kmh < 35.0


def test_climb_7pct_300w():
    s = Settings(pacing=FLAT_PACING)
    res = estimate(straight(5000, 0.07), Rider(68.0), power=PowerTarget(300, "avg"), settings=s)
    assert 16.5 < res.avg_speed_kmh < 18.5


def test_group_is_faster_on_flat_than_on_climb_relative_to_solo():
    s = Settings(pacing=FLAT_PACING)
    rider, p = Rider(68.0), PowerTarget(200, "avg")
    flat_gain = (
        estimate(straight(), rider, power=p, context=Group(20), settings=s).avg_speed_kmh
        / estimate(straight(), rider, power=p, settings=s).avg_speed_kmh
    )
    climb_gain = (
        estimate(straight(5000, 0.07), rider, power=p, context=Group(20), settings=s).avg_speed_kmh
        / estimate(straight(5000, 0.07), rider, power=p, settings=s).avg_speed_kmh
    )
    assert flat_gain > 1.12
    assert 1.0 < climb_gain < flat_gain


def test_np_target_is_met():
    res = estimate(straight(20_000, 0.03), Rider(68.0, 280), mode="tempo")
    assert res.normalized_power_w == pytest.approx(0.78 * 280, rel=2e-3)


def test_hairpin_limits_descent_speed():
    # 2 km descent at -8 % ending with a tight U-turn and back.
    n = 400
    d = np.linspace(0, 2000, n)
    lat = list(45.0 + d / 111_195.0)
    lon = [5.0] * n
    r = 10.0
    for a in np.linspace(0, math.pi, 20)[1:]:
        lat.append(lat[n - 1] + r * math.sin(a) / 111_195.0)
        lon.append(5.0 + r * (1 - math.cos(a)) / (111_195.0 * math.cos(math.radians(45))))
    ele = list(300 - 0.08 * d) + [300 - 0.08 * 2000 - 0.08 * r * a for a in np.linspace(0, math.pi, 20)[1:]]
    course = prepare(Route.from_points(lat, lon, ele))
    res = estimate(course, Rider(68.0), power=PowerTarget(150, "avg"))
    assert res.trace.speed.max() < 75 / 3.6 + 1e-6
    assert res.trace.speed[-3:].min() < 35 / 3.6  # slowed for the hairpin
