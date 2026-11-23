# allure

Deterministic estimation of cycling **moving time / average speed** from a GPX route.

- Physics: Martin et al. (1998) road-cycling power model (aero, rolling, gravity, inertia),
  integrated segment by segment with an energy balance.
- Terrain-aware pacing (more power on climbs, none on steep descents), cornering and
  braking limits on descents.
- Solo or group riding with mixed relays (drafting lowers the effective CdA).
- Intensity as a mode (`chill`, `steady`, `tempo`, `race`, targeting NP/FTP) or an explicit power target
  (normalized or average power).

No history, no learning at run time: same inputs, same output.

```python
from allure import load_gpx, estimate, Rider, Group

res = estimate(load_gpx("route.gpx"), Rider(mass_kg=67, ftp_w=288), mode="tempo", context=Group(15))
print(res.moving_time_s, res.avg_speed_kmh)
```

```
python -m allure route.gpx --mass 67 --ftp 288 --mode race --race
```

## Validation

Constants are calibrated on one rider's real rides with a power meter (74 road rides,
~150 h, solo, club groups and races, 2026), then frozen. Moving-time error:

| Input | Route | Median error | Within ±5 % |
|---|---|---|---|
| real average power | planned route (DEM elevation, points every 50 m) | 3.2 % | 76 % |
| real NP | planned route | 4.0 % | 68 % |
| intensity mode only (FTP + mode + context) | planned route | 3.9 % | 89 % (n=9 labelled rides) |

Group and race constants rest on few rides (8 club rides, 2 races): treat them as
provisional. More validation data from other riders is welcome.

License: MIT.
