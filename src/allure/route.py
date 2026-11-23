"""Route loading (gpxpy) and preparation: resampling, elevation smoothing, grade,
heading and turn radius."""
from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from typing import IO

import gpxpy
import numpy as np
from scipy.ndimage import gaussian_filter1d

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class Route:
    """Ordered points with elevation (degrees, degrees, metres)."""

    lat: np.ndarray
    lon: np.ndarray
    ele: np.ndarray

    @classmethod
    def from_points(cls, lat, lon, ele) -> "Route":
        lat, lon, ele = (np.asarray(a, dtype=float) for a in (lat, lon, ele))
        if not (lat.shape == lon.shape == ele.shape):
            raise ValueError("lat, lon and ele must have the same length")
        ok = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(ele)
        if ok.sum() < 2:
            raise ValueError("a route needs at least two points with elevation")
        return cls(lat[ok], lon[ok], ele[ok])


def load_gpx(source: str | PathLike | IO) -> Route:
    """Load track points, or route points if the file has no track."""
    if isinstance(source, (str, PathLike)):
        with open(source, encoding="utf-8") as f:
            gpx = gpxpy.parse(f)
    else:
        gpx = gpxpy.parse(source)
    pts = [p for t in gpx.tracks for s in t.segments for p in s.points]
    if len(pts) < 2:
        pts = [p for r in gpx.routes for p in r.points]
    pts = [p for p in pts if p.elevation is not None]
    if len(pts) < 2:
        raise ValueError("no track or route points with elevation found in GPX")
    return Route.from_points(
        [p.latitude for p in pts], [p.longitude for p in pts], [p.elevation for p in pts]
    )


@dataclass(frozen=True)
class Course:
    """Route resampled into fixed-length segments.

    Per segment (n): ds, grade, ele, heading_deg. Per node (n+1): radius_m.
    """

    ds: np.ndarray
    grade: np.ndarray
    ele: np.ndarray
    heading_deg: np.ndarray
    radius_m: np.ndarray

    @property
    def distance_m(self) -> float:
        return float(self.ds.sum())

    @property
    def elevation_gain_m(self) -> float:
        return float((self.grade.clip(min=0) * self.ds).sum())


def _local_xy(route: Route) -> tuple[np.ndarray, np.ndarray]:
    lat0 = np.radians(route.lat.mean())
    x = np.radians(route.lon - route.lon[0]) * np.cos(lat0) * EARTH_RADIUS_M
    y = np.radians(route.lat - route.lat[0]) * EARTH_RADIUS_M
    return x, y


def prepare(
    route: Route,
    *,
    step_m: float = 10.0,
    elevation_sigma_m: float = 40.0,
    position_sigma_m: float = 15.0,
    curvature_baseline_m: float = 40.0,
    max_grade: float = 0.30,
) -> Course:
    """Resample every `step_m` and derive the per-segment quantities.

    Elevation is Gaussian-smoothed (sigma in metres along the route): GPS/DEM
    elevation noise is the main source of error in grade-based models. Positions
    are smoothed before computing headings; the turn radius is the arc length of
    `curvature_baseline_m` divided by the heading change over it.
    """
    x, y = _local_xy(route)
    step = np.hypot(np.diff(x), np.diff(y))
    keep = np.concatenate([[True], step > 1e-6])
    x, y, e = x[keep], y[keep], route.ele[keep]
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    total = s[-1]
    if total < step_m:
        raise ValueError("route is shorter than one resampling step")

    nodes = np.arange(0.0, total, step_m)
    nodes = np.append(nodes, total) if total - nodes[-1] > 1e-6 else nodes
    rx, ry, re = (np.interp(nodes, s, a) for a in (x, y, e))

    re = gaussian_filter1d(re, elevation_sigma_m / step_m, mode="nearest")
    rx = gaussian_filter1d(rx, position_sigma_m / step_m, mode="nearest")
    ry = gaussian_filter1d(ry, position_sigma_m / step_m, mode="nearest")

    ds = np.diff(nodes)
    grade = np.clip(np.diff(re) / ds, -max_grade, max_grade)
    ele = (re[1:] + re[:-1]) / 2
    heading = np.unwrap(np.arctan2(np.diff(rx), np.diff(ry)))

    # Heading change over a centred window of segments -> radius at each node.
    k = max(1, int(round(curvature_baseline_m / step_m / 2)))
    n = len(ds)
    idx = np.arange(n + 1)
    a, b = np.clip(idx - k, 0, n - 1), np.clip(idx + k - 1, 0, n - 1)
    dtheta = np.abs(heading[b] - heading[a])
    length = np.maximum(nodes[b] - nodes[a], step_m)
    with np.errstate(divide="ignore"):
        radius = np.where(dtheta > 1e-6, length / dtheta, np.inf)

    return Course(ds, grade, ele, np.degrees(heading) % 360.0, radius)
