"""Load a route from a link: Komoot tour, RideWithGPS route/trip, or any URL serving a GPX.

Requires the `web` extra (`pip install allure-cycling[web]`). Only public content is
fetched; nothing is sent besides the request for the route itself.
"""
from __future__ import annotations

import io
import re
from urllib.parse import parse_qs, urlparse

from .route import Route, load_gpx

USER_AGENT = "allure-cycling (+https://github.com/gwenaelkreutner/Allure)"
TIMEOUT_S = 30


class RouteSourceError(ValueError):
    """The link cannot be turned into a route (unsupported site, private, no elevation…)."""


def _http():
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise RouteSourceError("loading from a URL needs `pip install allure-cycling[web]`") from exc
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _get(url: str, **params):
    r = _http().get(url, params=params or None, timeout=TIMEOUT_S, allow_redirects=True)
    if r.status_code in (401, 403, 404):
        raise RouteSourceError(f"route not reachable ({r.status_code}): private, deleted or wrong link")
    r.raise_for_status()
    return r


def _komoot(url: str) -> Route:
    # /tour/<id> and /smarttour/e<id> are user tours; /smarttour/<id> is a Komoot-curated one.
    m = re.search(r"/(tour|smarttour)/(e?)(\d+)", url)
    if not m:
        raise RouteSourceError("Komoot link must point to a tour (…/tour/<id> or …/smarttour/<id>)")
    kind = "smart_tours" if m.group(1) == "smarttour" and not m.group(2) else "tours"
    token = parse_qs(urlparse(url).query).get("share_token", [None])[0]
    params = {"share_token": token} if token else {}
    data = _get(f"https://api.komoot.de/v007/{kind}/{m.group(3)}/coordinates", **params).json()
    items = data.get("items") or []
    if len(items) < 2:
        raise RouteSourceError("Komoot returned no coordinates (tour private? add its share link)")
    return Route.from_points(
        [p["lat"] for p in items], [p["lng"] for p in items], [p.get("alt") for p in items]
    )


def _ridewithgps(url: str) -> Route:
    m = re.search(r"/(routes|trips)/(\d+)", url)
    if not m:
        raise RouteSourceError("RideWithGPS link must point to a route or a trip")
    params = {"sub_format": "track"}
    key = parse_qs(urlparse(url).query).get("privacy_code", [None])[0]
    if key:
        params["privacy_code"] = key
    r = _http().get(f"https://ridewithgps.com/{m.group(1)}/{m.group(2)}.gpx", params=params, timeout=TIMEOUT_S)
    if r.status_code == 418:  # bot protection, seen from datacenter IPs
        raise RouteSourceError("RideWithGPS refused the download from this server: export the GPX and send the file")
    if r.status_code in (401, 403, 404):
        raise RouteSourceError(f"route not reachable ({r.status_code}): private, deleted or wrong link")
    r.raise_for_status()
    return load_gpx(io.StringIO(r.text))


def _strava(url: str) -> Route:
    raise RouteSourceError(
        "Strava does not share route geometry without login: open the route, use "
        "'Export GPX' and send the file instead"
    )


def load_url(url: str) -> Route:
    """Return the route behind `url`. Raises RouteSourceError with a human-readable reason."""
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("komoot.com") or host.endswith("komoot.de"):
        return _komoot(url)
    if host.endswith("ridewithgps.com"):
        return _ridewithgps(url)
    if host.endswith("strava.com") or host.endswith("strava.app.link"):
        return _strava(url)
    r = _get(url)
    text = r.text
    if "<gpx" not in text[:2000]:
        raise RouteSourceError("this link does not serve a GPX file (supported: Komoot, RideWithGPS, direct .gpx)")
    return load_gpx(io.StringIO(text))
