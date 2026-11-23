# Allure — cycling moving-time estimation

Deterministic estimation of cycling **moving time / average speed** from a GPX route.

- Physics: Martin et al. (1998) road-cycling power model (aero, rolling, gravity, inertia),
  integrated segment by segment with an energy balance.
- Terrain-aware pacing (more power on climbs, none on steep descents), cornering and
  braking limits on descents.
- Solo or group riding with mixed relays (drafting lowers the effective CdA).
- Intensity as a mode (`chill`, `steady`, `tempo`, `race`, targeting NP/FTP) or an explicit power target
  (normalized or average power).

No history, no learning at run time: same inputs, same output.

```
pip install "allure-cycling[web] @ git+https://github.com/gwenaelkreutner/Allure@v0.2.0"
```

```python
from allure_cycling import load_gpx, load_url, estimate, Rider, Group

res = estimate(load_gpx("route.gpx"), Rider(mass_kg=67, ftp_w=288), mode="tempo", context=Group(15))
print(res.moving_time_s, res.avg_speed_kmh)
```

```
allure route.gpx --mass 67 --ftp 288 --mode steady --group 15
allure https://www.komoot.com/tour/228834917 --mass 67 --ftp 288 --mode race --race
```

Links: Komoot tours (public or with share token), RideWithGPS routes/trips, any URL
serving a GPX. Strava does not expose route geometry without login: export the GPX.

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
