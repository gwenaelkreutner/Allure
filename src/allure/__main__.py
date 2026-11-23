"""CLI: python -m allure route.gpx --mass 67 --ftp 288 --mode tempo [--group 15]"""
from __future__ import annotations

import argparse

from . import Group, Mode, PowerTarget, Rider, Solo, estimate, load_gpx


def _hms(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600}h{s % 3600 // 60:02d}"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="allure", description=__doc__)
    ap.add_argument("gpx")
    ap.add_argument("--mass", type=float, required=True, help="rider mass, kg")
    ap.add_argument("--ftp", type=float, help="FTP, W (needed with --mode)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--mode", choices=[m.value for m in Mode])
    g.add_argument("--np", type=float, help="target normalized power, W")
    g.add_argument("--avg", type=float, help="target average power, W")
    ap.add_argument("--group", type=int, metavar="SIZE", help="ride in a group of SIZE riders")
    a = ap.parse_args(argv)

    power = PowerTarget(a.np, "np") if a.np else PowerTarget(a.avg, "avg") if a.avg else None
    res = estimate(
        load_gpx(a.gpx),
        Rider(a.mass, a.ftp),
        mode=a.mode,
        power=power,
        context=Group(a.group) if a.group else Solo(),
    )
    print(
        f"{res.distance_km:.1f} km, D+ {res.elevation_gain_m:.0f} m -> {_hms(res.moving_time_s)} "
        f"@ {res.avg_speed_kmh:.1f} km/h (avg {res.avg_power_w:.0f} W, NP {res.normalized_power_w:.0f} W)"
    )
    for name, sp in res.splits.items():
        print(f"  {name:8s} {sp.distance_km:6.1f} km  {_hms(sp.time_s)}  {sp.speed_kmh:5.1f} km/h")


if __name__ == "__main__":
    main()
