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
    Race,
    Rider,
    Settings,
    Solo,
)
from .profile import Checkpoint, Climb, Descent, describe, node_elevation
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
    normalized_power_w: float  # expected real-world NP (simulated NP x variability correction)
    intensity_factor: float | None
    splits: dict[str, TerrainSplit]  # "climb" (>3 %), "flat", "descent" (<-3 %)
    regroup_s: float  # time added for regroupings (group rides), included in moving_time_s
    elevation_loss_m: float
    kilojoules: float  # mechanical work = avg power x moving time
    tss: float | None  # Coggan: hours x IF^2 x 100, from the expected NP; None without FTP
    climbs: list[Climb]  # each climb with its predicted time and power
    descents: list[Descent]
    checkpoints: list[Checkpoint]  # every 10 km, with elapsed moving time (regroupings excluded)
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
    `Group(size=...)` (club ride with relays and regroupings) or `Race(...)`
    (closed roads, peloton); drafting lowers the effective CdA.
    """
    if (mode is None) == (power is None):
        raise ValueError("give exactly one of `mode` or `power`")
    course = route if isinstance(route, Course) else prepare(route)
    eq = settings.equipment
    cda = eq.cda_m2 * (1.0 if isinstance(context, Solo) else context.cda_multiplier())
    sim = Simulator(course, rider.mass_kg + eq.bike_mass_kg, cda, settings)
    var = settings.variability
    if isinstance(context, Race):
        vi_corr = context.vi_correction
    else:
        vi_corr = var.base + var.per_tight_turn_per_km * course.tight_turns_per_km(var.tight_radius_m)

    def run_np(np_target: float) -> Trace:
        # the simulated profile is smoother than reality: aim for a lower simulated NP
        return sim.run_for_target(np_target / vi_corr, "np")[1]

    if power is not None:
        trace = run_np(power.watts) if power.kind == "np" else sim.run_for_target(power.watts, "avg")[1]
    else:
        mode = Mode(mode)
        if not rider.ftp_w:
            raise ValueError("intensity modes need rider.ftp_w")
        if mode is Mode.RACE:
            hours, trace = 2.0, None
            for _ in range(20):
                trace = run_np(race_if(hours) * rider.ftp_w)
                new = trace.time_s / 3600
                if abs(new - hours) * 3600 < 5:
                    break
                hours = new
        else:
            trace = run_np(MODE_IF[mode] * rider.ftp_w)

    g = course.grade
    splits = {}
    for name, mask in (
        ("climb", g > CLIMB),
        ("flat", (g >= DESCENT) & (g <= CLIMB)),
        ("descent", g < DESCENT),
    ):
        splits[name] = TerrainSplit(float(course.ds[mask].sum() / 1000), float(trace.dt[mask].sum()))

    regroup_s = 0.0
    if isinstance(context, Group) and context.regroup:
        rg = settings.regrouping
        regroup_s = rg.seconds_per_climb * course.climbs(rg.min_climb_gain_m, rg.tolerance_m)

    np_w = trace.normalized_power * vi_corr
    moving = trace.time_s + regroup_s
    climbs, descents, checkpoints = describe(course, trace.dt, trace.power)
    e = node_elevation(course)
    tss = moving / 3600 * (np_w / rider.ftp_w) ** 2 * 100 if rider.ftp_w else None
    return Estimate(
        moving_time_s=moving,
        distance_km=course.distance_m / 1000,
        elevation_gain_m=course.elevation_gain_m,
        avg_power_w=trace.avg_power,
        normalized_power_w=np_w,
        intensity_factor=np_w / rider.ftp_w if rider.ftp_w else None,
        splits=splits,
        regroup_s=regroup_s,
        elevation_loss_m=float(np.clip(-np.diff(e), 0, None).sum()),
        kilojoules=trace.avg_power * trace.time_s / 1000,
        tss=tss,
        climbs=climbs,
        descents=descents,
        checkpoints=checkpoints,
        trace=trace,
        course=course,
    )
