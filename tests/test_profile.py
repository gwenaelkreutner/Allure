import numpy as np
import pytest

from allure_cycling import PowerTarget, Rider, Route, estimate, prepare
from allure_cycling.profile import category, describe


def profile_route(segments, step=10.0):
    """Straight route from (length_m, grade) pieces."""
    d, e = [0.0], [100.0]
    for length, g in segments:
        for _ in range(int(length / step)):
            d.append(d[-1] + step)
            e.append(e[-1] + step * g)
    d = np.array(d)
    return Route.from_points(45 + d / 111_195.0, np.full(len(d), 5.0), e)


@pytest.mark.parametrize("length,grade,expected", [
    (2000, 0.05, "4"), (4000, 0.05, "3"), (8000, 0.05, "2"), (10000, 0.07, "1"),
    (15000, 0.07, "HC"), (1000, 0.05, None), (400, 0.10, None), (5000, 0.02, None),
])
def test_strava_categories(length, grade, expected):
    assert category(length, grade) == expected


def test_two_climbs_a_descent_and_checkpoints():
    route = profile_route([(3000, 0.0), (2000, 0.06), (2000, 0.0), (3000, -0.04), (2000, 0.0),
                           (5000, 0.04), (3000, 0.0)])
    climbs, descents, checkpoints = describe(prepare(route, elevation_sigma_m=20))
    assert len(climbs) == 2
    first, second = climbs
    assert first.start_km == pytest.approx(3.0, abs=0.2) and first.gain_m == pytest.approx(120, abs=8)
    assert second.gain_m == pytest.approx(200, abs=8) and second.category == "3"  # 5000 m x 4 % = 20000
    assert first.steepest_km_grade == pytest.approx(0.06, abs=0.005)
    assert len(descents) == 1 and descents[0].loss_m == pytest.approx(120, abs=8)
    assert [c.km for c in checkpoints] == [10.0, 20.0]


def test_estimate_carries_climb_times_tss_and_work():
    route = profile_route([(5000, 0.0), (3000, 0.06), (5000, 0.0)])
    res = estimate(route, Rider(68.0, 280), power=PowerTarget(200, "avg"))
    (climb,) = res.climbs
    assert 0 < climb.time_s < res.moving_time_s and climb.avg_power_w > 200  # more power uphill
    assert res.kilojoules == pytest.approx(200 * res.moving_time_s / 1000, rel=0.01)
    assert res.tss == pytest.approx(res.moving_time_s / 3600 * (res.normalized_power_w / 280) ** 2 * 100)
    assert res.checkpoints[-1].elapsed_s == pytest.approx(res.moving_time_s, rel=0.01)
