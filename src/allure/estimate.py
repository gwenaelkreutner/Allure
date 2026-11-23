"""Public entry point: route + rider + intensity + context -> moving time."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .params import (
    MODE_IF,
    RACE_IF_BY_HOURS,
    Context,
    Group,
    Mode,
    PowerTarget,
    Rider,
    Settings,
    Solo,
)
from .route import Course, Route, prepare
from .simulate import Simulator, Trace

CLIMB, DESCENT = 0.03, -0.03


@dataclass(frozen=True)
class TerrainSplit:
    distance_km: float
    time_s: float

    @property
    def speed_kmh(self) -> float:
        return self.distance_km / self.time_s * 3600 if self.time_s else 0.0


@dataclass(frozen=True)
class Estimate:
    moving_time_s: float
    distance_km: float
    elevation_gain_m: float
    avg_power_w: float
    normalized_power_w: float
    intensity_factor: float | None
    splits: dict[str, TerrainSplit]  # "climb" (>3 %), "flat", "descent" (<-3 %)
    trace: Trace
    course: Course

    @property
    def avg_speed_kmh(self) -> float:
        return self.distance_km / self.moving_time_s * 3600


def race_if(hours: float) -> float:
    h, f = zip(*RACE_IF_BY_HOURS)
    return float(np.interp(hours, h, f))


def estimate(
    route: Route | Course,
    rider: Rider,
    *,
    mode: Mode | str | None = None,
    power: PowerTarget | None = None,
    context: Context = Solo(),
    settings: Settings = Settings(),
) -> Estimate:
    """Estimate moving time on `route`.

    Give either an intensity `mode` (needs `rider.ftp_w`; targets an intensity
    factor NP/FTP) or an explicit `power` target. `context` is `Solo()` or
    `Group(size=...)`; drafting lowers the effective CdA.
    """
    if (mode is None) == (power is None):
        raise ValueError("give exactly one of `mode` or `power`")
    course = route if isinstance(route, Course) else prepare(route)
    eq = settings.equipment
    cda = eq.cda_m2 * (context.cda_multiplier() if isinstance(context, Group) else 1.0)
    sim = Simulator(course, rider.mass_kg + eq.bike_mass_kg, cda, settings)

    if power is not None:
        _, trace = sim.run_for_target(power.watts, power.kind)
    else:
        mode = Mode(mode)
        if not rider.ftp_w:
            raise ValueError("intensity modes need rider.ftp_w")
        if mode is Mode.RACE:
            hours, trace = 2.0, None
            for _ in range(20):
                _, trace = sim.run_for_target(race_if(hours) * rider.ftp_w, "np")
                new = trace.time_s / 3600
                if abs(new - hours) * 3600 < 5:
                    break
                hours = new
        else:
            _, trace = sim.run_for_target(MODE_IF[mode] * rider.ftp_w, "np")

    g = course.grade
    splits = {}
    for name, mask in (
        ("climb", g > CLIMB),
        ("flat", (g >= DESCENT) & (g <= CLIMB)),
        ("descent", g < DESCENT),
    ):
        splits[name] = TerrainSplit(float(course.ds[mask].sum() / 1000), float(trace.dt[mask].sum()))

    np_w = trace.normalized_power
    return Estimate(
        moving_time_s=trace.time_s,
        distance_km=course.distance_m / 1000,
        elevation_gain_m=course.elevation_gain_m,
        avg_power_w=trace.avg_power,
        normalized_power_w=np_w,
        intensity_factor=np_w / rider.ftp_w if rider.ftp_w else None,
        splits=splits,
        trace=trace,
        course=course,
    )
