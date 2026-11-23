"""allure_cycling — deterministic cycling moving-time estimation from a GPX route."""
from .estimate import Estimate, TerrainSplit, estimate
from .profile import Checkpoint, Climb, Descent, describe
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
    "Checkpoint", "Climb", "Course", "Descent", "Environment", "Equipment", "Estimate", "Group", "Handling", "Mode",
    "Pacing", "PowerTarget", "Race", "Rider", "Route", "Settings", "Solo", "TerrainSplit",
    "RouteSourceError", "describe", "estimate", "load_gpx", "load_url", "prepare",
]
__version__ = "0.3.0"
