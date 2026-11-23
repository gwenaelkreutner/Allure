"""allure — deterministic cycling moving-time estimation from a GPX route."""
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

__all__ = [
    "Course", "Environment", "Equipment", "Estimate", "Group", "Handling", "Mode",
    "Pacing", "PowerTarget", "Race", "Rider", "Route", "Settings", "Solo", "TerrainSplit",
    "estimate", "load_gpx", "prepare",
]
__version__ = "0.1.0"
