"""Forward simulation over a prepared course (Martin et al. 1998 power model,
energy balance per segment so momentum on rollers and descents is kept)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import uniform_filter1d

from .params import Settings
from .route import Course

G = 9.80665


def air_density(ele_m: np.ndarray, temperature_c: float) -> np.ndarray:
    pressure = 101_325.0 * (1.0 - 2.25577e-5 * ele_m) ** 5.25588
    return pressure / (287.05 * (temperature_c + 273.15))


@dataclass(frozen=True)
class Trace:
    dt: np.ndarray  # s per segment
    speed: np.ndarray  # mean m/s per segment
    power: np.ndarray  # W actually produced per segment

    @property
    def time_s(self) -> float:
        return float(self.dt.sum())

    @property
    def avg_power(self) -> float:
        return float((self.power * self.dt).sum() / self.dt.sum())

    @property
    def normalized_power(self) -> float:
        """Coggan NP on the simulated profile resampled at 1 Hz."""
        edges = np.cumsum(self.dt)
        t = np.arange(0.5, edges[-1], 1.0)
        p = self.power[np.minimum(np.searchsorted(edges, t), len(self.power) - 1)]
        if len(p) < 30:
            return float(p.mean())
        rolling = uniform_filter1d(p, 30, mode="nearest")
        return float(np.mean(rolling**4) ** 0.25)


class Simulator:
    """Precomputes everything that does not depend on the power level, so the
    outer loops (target NP, race duration) only re-run the integration."""

    def __init__(self, course: Course, total_mass: float, cda: float, settings: Settings):
        eq, env, pac, hd = settings.equipment, settings.environment, settings.pacing, settings.handling
        self.ds = course.ds.tolist()
        self.n = len(self.ds)
        theta = np.arctan(course.grade)
        self.grav = (total_mass * G * np.sin(theta)).tolist()
        self.roll = (eq.crr * total_mass * G * np.cos(theta)).tolist()
        self.k_aero = (0.5 * air_density(course.ele, env.temperature_c) * cda).tolist()
        rel = np.radians(env.wind_from_deg - course.heading_deg)
        self.headwind = (env.wind_speed_ms * np.cos(rel)).tolist()
        self.m_eff = total_mass + eq.wheel_inertia_kg
        self.eta = eq.drivetrain_efficiency
        self.v_pedal_max = pac.max_pedal_speed_kmh / 3.6

        g = course.grade
        factor = np.where(
            g >= 0,
            np.minimum(1.0 + pac.climb_gain * g, pac.max_climb_factor),
            np.clip(1.0 - g / pac.zero_power_grade, 0.0, 1.0),
        )
        self.factor = factor.tolist()

        # Node speed limits: cornering, absolute cap, then braking look-ahead.
        vmax = hd.max_speed_kmh / 3.6
        cap = np.minimum(np.sqrt(hd.lateral_accel_ms2 * course.radius_m), vmax)
        vlim = cap.copy()
        for i in range(self.n - 1, -1, -1):
            vlim[i] = min(cap[i], math.sqrt(vlim[i + 1] ** 2 + 2 * hd.brake_decel_ms2 * self.ds[i]))
        self.vlim = vlim.tolist()

    def _force(self, i: int, v: float) -> tuple[float, float]:
        va = v + self.headwind[i]
        f = self.k_aero[i] * va * abs(va) + self.roll[i] + self.grav[i]
        return f, 2.0 * self.k_aero[i] * abs(va)

    def _step(self, i: int, v0: float, p: float) -> float:
        """Speed at the end of segment i (implicit midpoint energy balance)."""
        ds, m, pe = self.ds[i], self.m_eff, p * self.eta
        v1 = max(v0, 1.0)
        for _ in range(30):
            vb = max(0.5 * (v0 + v1), 0.3)
            f, df = self._force(i, vb)
            h = 0.5 * m * (v1 * v1 - v0 * v0) - ds * (pe / vb - f)
            dh = m * v1 + ds * (pe / (2 * vb * vb) + 0.5 * df)
            nv = max(v1 - h / dh, 0.3)
            if abs(nv - v1) < 1e-6:
                return nv
            v1 = nv
        return v1

    def steady_speed(self, i: int, p: float) -> float:
        lo, hi = 0.3, 40.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            f, _ = self._force(i, mid)
            lo, hi = (mid, hi) if p * self.eta / mid > f else (lo, mid)
        return 0.5 * (lo + hi)

    def run(self, base_power: float) -> Trace:
        n = self.n
        dt, spd, pw = np.empty(n), np.empty(n), np.empty(n)
        v0 = min(self.steady_speed(0, base_power * self.factor[0]), self.vlim[0])
        for i in range(n):
            p = base_power * self.factor[i] if v0 < self.v_pedal_max else 0.0
            v1 = self._step(i, v0, p)
            lim = self.vlim[i + 1]
            if v1 > lim:
                coast = self._step(i, v0, 0.0) if p > 0 else v1
                v1 = lim
                if coast >= lim:
                    p = 0.0  # braking
                else:  # ease off just enough to arrive at the limit
                    vb = 0.5 * (v0 + v1)
                    f, _ = self._force(i, vb)
                    work = 0.5 * self.m_eff * (v1 * v1 - v0 * v0) / self.ds[i] + f
                    p = max(0.0, work * vb / self.eta)
            vb = max(0.5 * (v0 + v1), 0.3)
            dt[i], spd[i], pw[i] = self.ds[i] / vb, vb, p
            v0 = v1
        return Trace(dt, spd, pw)

    def run_for_target(self, watts: float, kind: str, tol: float = 1e-3) -> tuple[float, Trace]:
        """Find the base power whose simulated profile meets the target (NP or avg)."""
        base = watts
        trace = self.run(base)
        for _ in range(40):
            got = trace.normalized_power if kind == "np" else trace.avg_power
            if got <= 0:  # nothing to pedal (all steep descent): coasting is the answer
                break
            if abs(got / watts - 1.0) < tol:
                break
            base *= watts / got
            trace = self.run(base)
        return base, trace
