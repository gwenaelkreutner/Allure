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

Status: v0, constants being calibrated against real rides.

License: MIT.
