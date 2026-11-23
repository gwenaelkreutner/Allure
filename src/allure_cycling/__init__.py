"""allure_cycling — deterministic cycling moving-time estimation from a GPX route."""
from .estimate import Estimate, TerrainSplit, estimate
from .params import (
    Environment,
    Equipment,
    Group,
    Handling,
    Mode,
    Pacing,
    PowerTarget,
    Race,
    Rider,
    Settings,
    Solo,
)
from .route import Course, Route, load_gpx, prepare
from .sources import RouteSourceError, load_url

__all__ = [
    "Course", "Environment", "Equipment", "Estimate", "Group", "Handling", "Mode",
    "Pacing", "PowerTarget", "Race", "Rider", "Route", "Settings", "Solo", "TerrainSplit",
    "RouteSourceError", "estimate", "load_gpx", "load_url", "prepare",
]
__version__ = "0.2.0"
