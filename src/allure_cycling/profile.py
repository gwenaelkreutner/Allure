"""Route description: climbs (with Strava-style categories), main descents and checkpoints.

Climb category follows Strava's published rule, also used by Garmin ClimbPro: score =
length (m) x average grade (%); Cat 4 > 8,000, Cat 3 > 16,000, Cat 2 > 32,000,
Cat 1 > 64,000, HC > 80,000, for climbs of at least 500 m averaging at least 3 %
(https://support.strava.com/en-us/articles/15402015-how-does-strava-categorize-climbs).
Smaller rises that still matter on the bike (>= min_gain_m) are listed uncategorised.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .route import Course

CATEGORIES = ((80_000, "HC"), (64_000, "1"), (32_000, "2"), (16_000, "3"), (8_000, "4"))


@dataclass(frozen=True)
class Climb:
    start_km: float
    length_km: float
    gain_m: float
    avg_grade: float  # fraction, 0.05 = 5 %
    max_grade: float  # steepest stretch of the smoothed profile (~200 m)
    steepest_km_grade: float  # average grade of the hardest kilometre (whole climb if shorter)
    category: str | None  # "HC", "1".."4", or None for a small rise
    time_s: float | None = None  # predicted, filled from a simulation
    avg_power_w: float | None = None

    @property
    def speed_kmh(self) -> float | None:
        return self.length_km / self.time_s * 3600 if self.time_s else None


@dataclass(frozen=True)
class Descent:
    start_km: float
    length_km: float
    loss_m: float
    avg_grade: float  # negative fraction
    time_s: float | None = None


@dataclass(frozen=True)
class Checkpoint:
    km: float
    elevation_m: float
    elapsed_s: float | None = None


def node_elevation(course: Course) -> np.ndarray:
    """Elevation at the n+1 segment boundaries, consistent with the course grades."""
    start = course.ele[0] - course.grade[0] * course.ds[0] / 2
    return start + np.concatenate([[0.0], np.cumsum(course.grade * course.ds)])


def _rises(e: np.ndarray, min_gain: float, tolerance: float) -> list[tuple[int, int]]:
    """(bottom, top) node pairs of every rise of at least `min_gain`; a dip smaller
    than `tolerance` does not end a rise. A rise finishing the route is kept."""
    out, lo, hi = [], 0, 0
    for i in range(1, len(e)):
        if e[i] > e[hi]:
            hi = i
        elif e[hi] - e[i] > tolerance or e[i] < e[lo]:
            if e[hi] - e[lo] >= min_gain:
                out.append((lo, hi))
            lo = hi = i
    if e[hi] - e[lo] >= min_gain:
        out.append((lo, hi))
    return out


def _trim(e: np.ndarray, s: np.ndarray, a: int, b: int, flat: float = 0.01) -> tuple[int, int]:
    """Drop near-flat stretches at both ends so the averages describe the climb itself."""
    while b - a > 1 and (e[a + 1] - e[a]) / (s[a + 1] - s[a]) < flat:
        a += 1
    while b - a > 1 and (e[b] - e[b - 1]) / (s[b] - s[b - 1]) < flat:
        b -= 1
    return a, b


def _steepest(e: np.ndarray, s: np.ndarray, a: int, b: int, window_m: float) -> float:
    if s[b] - s[a] <= window_m:
        return (e[b] - e[a]) / (s[b] - s[a])
    ends = np.searchsorted(s, s[a:b + 1] + window_m)
    ok = ends <= b
    starts = np.arange(a, b + 1)[ok]
    return float(np.max((e[ends[ok]] - e[starts]) / (s[ends[ok]] - s[starts])))


def category(length_m: float, avg_grade: float) -> str | None:
    pct = avg_grade * 100
    if length_m < 500 or pct < 3:
        return None
    score = length_m * pct
    return next((name for threshold, name in CATEGORIES if score > threshold), None)


def describe(
    course: Course,
    dt: np.ndarray | None = None,
    power: np.ndarray | None = None,
    *,
    min_gain_m: float = 25.0,
    min_avg_grade: float = 0.025,
    min_descent_m: float = 50.0,
    tolerance_m: float = 10.0,
    checkpoint_every_km: float = 10.0,
) -> tuple[list[Climb], list[Descent], list[Checkpoint]]:
    """Climbs, main descents and checkpoints of `course`. With the per-segment times
    (`dt`) and power of a simulation, each item also gets its predicted time/power."""
    e = node_elevation(course)
    s = np.concatenate([[0.0], np.cumsum(course.ds)])
    seg_g = course.grade

    climbs = []
    for a, b in _rises(e, min_gain_m, tolerance_m):
        a, b = _trim(e, s, a, b)
        length, gain = s[b] - s[a], e[b] - e[a]
        if gain < min_gain_m or length < 300 or gain / length < min_avg_grade:
            continue
        t = float(dt[a:b].sum()) if dt is not None else None
        p = float((power[a:b] * dt[a:b]).sum() / dt[a:b].sum()) if dt is not None and power is not None else None
        climbs.append(Climb(
            start_km=float(round(s[a] / 1000, 1)), length_km=float(round(length / 1000, 2)), gain_m=round(float(gain)),
            avg_grade=float(round(gain / length, 3)), max_grade=round(float(seg_g[a:b].max()), 3),
            steepest_km_grade=round(_steepest(e, s, a, b, 1000.0), 3),
            category=category(length, gain / length), time_s=t, avg_power_w=p,
        ))

    descents = []
    for a, b in _rises(-e, min_descent_m, tolerance_m):
        a, b = _trim(-e, s, a, b)
        length, loss = s[b] - s[a], e[a] - e[b]
        if loss < min_descent_m or loss / length < min_avg_grade:
            continue  # a long false flat going down is not a descent
        descents.append(Descent(
            start_km=float(round(s[a] / 1000, 1)), length_km=float(round(length / 1000, 2)), loss_m=round(float(loss)),
            avg_grade=float(round(-loss / length, 3)), time_s=float(dt[a:b].sum()) if dt is not None else None,
        ))

    elapsed = np.concatenate([[0.0], np.cumsum(dt)]) if dt is not None else None
    step = checkpoint_every_km * 1000
    marks = [m for m in np.arange(step, s[-1], step) if s[-1] - m >= 1000] + [s[-1]]
    checkpoints = []
    for m in marks:
        i = int(min(np.searchsorted(s, m), len(s) - 1))
        checkpoints.append(Checkpoint(
            km=float(round(s[i] / 1000, 1)), elevation_m=round(float(e[i])),
            elapsed_s=float(elapsed[i]) if elapsed is not None else None,
        ))
    return climbs, descents, checkpoints
