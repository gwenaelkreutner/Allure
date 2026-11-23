"""Input parameters. Every default is a plain, documented constant: the model is
deterministic and never learns from history at run time."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class Rider:
    mass_kg: float
    ftp_w: float | None = None  # required for intensity modes, not for a raw power target


@dataclass(frozen=True)
class Equipment:
    bike_mass_kg: float = 8.5  # bike + bottles + tools
    cda_m2: float = 0.32  # road bike, hands on the hoods
    crr: float = 0.0045  # good road tyres on typical tarmac
    drivetrain_efficiency: float = 0.976
    wheel_inertia_kg: float = 1.4  # rotating wheels as equivalent mass (Martin 1998)


@dataclass(frozen=True)
class Environment:
    temperature_c: float = 15.0
    wind_speed_ms: float = 0.0
    wind_from_deg: float = 0.0  # meteorological convention: direction the wind comes FROM


@dataclass(frozen=True)
class Solo:
    pass


@dataclass(frozen=True)
class Group:
    """Riding in a group with mixed relays.

    front_share: fraction of the time spent at the front (full drag).
    draft_factor: remaining drag fraction while sheltered.
    Defaults depend on group size; override either if you know better.
    """

    size: int = 10
    front_share: float | None = None
    draft_factor: float | None = None
    regroup: bool = True  # club rides wait for each other after climbs; False for races

    def effective(self) -> tuple[float, float]:
        # Calibrated on real club rides and races with mixed relays: the effective
        # CdA multiplier is ~0.8 whatever the size (0.77-0.83 measured), much less
        # than the sheltered-only values of CFD studies (0.45-0.6).
        if max(2, self.size) <= 2:
            fs, k = 0.5, 0.62  # duo, sharing the work: 0.81
        else:
            fs, k = 0.2, 0.75  # club ride / peloton with relays: 0.80
        return (
            self.front_share if self.front_share is not None else fs,
            self.draft_factor if self.draft_factor is not None else k,
        )

    def cda_multiplier(self) -> float:
        fs, k = self.effective()
        return fs + (1.0 - fs) * k


Context = Solo | Group


class Mode(str, Enum):
    CHILL = "chill"
    TEMPO = "tempo"
    RACE = "race"


# Intensity factor (NP / FTP) per mode. RACE depends on the expected duration
# (hours -> IF, linearly interpolated). Starting values, to be calibrated against
# real rides — see docs/validation.md.
MODE_IF = {Mode.CHILL: 0.62, Mode.TEMPO: 0.76}
RACE_IF_BY_HOURS = ((1.0, 0.95), (2.0, 0.90), (3.0, 0.86), (4.0, 0.83), (6.0, 0.78))


@dataclass(frozen=True)
class PowerTarget:
    """Explicit power target. kind="np": normalized power; kind="avg": average power
    over moving time, coasting included."""

    watts: float
    kind: str = "np"

    def __post_init__(self):
        if self.kind not in ("np", "avg"):
            raise ValueError('kind must be "np" or "avg"')
        if self.watts <= 0:
            raise ValueError("watts must be positive")


@dataclass(frozen=True)
class Pacing:
    """How power varies with the terrain, relative to the power on the flat.

    climbs:   factor = 1 + climb_boost * (1 - exp(-grade / climb_scale))
    descents: factor = exp(grade / descent_scale)
    No pedalling above max_pedal_speed_kmh.

    Defaults fitted on ~150 h of real rides with power (solo and group, 2026):
    measured ratio vs flat ~1.35 at +2.5 %, ~1.65 at +5 %, ~1.85 at +10 %;
    ~0.55 at -3 %, ~0.3 at -5 %.
    """

    climb_boost: float = 1.0
    climb_scale: float = 0.055
    descent_scale: float = 0.045
    max_pedal_speed_kmh: float = 55.0


@dataclass(frozen=True)
class Handling:
    """Speed limits from cornering and braking (descents, hairpins, roundabouts)."""

    # Effective value fitted on real descents: lower than tyre grip allows, it also
    # absorbs GPS-smoothed corners and real-world caution (traffic, visibility).
    lateral_accel_ms2: float = 1.7
    brake_decel_ms2: float = 2.5
    max_speed_kmh: float = 75.0


@dataclass(frozen=True)
class Variability:
    """Real rides are more variable than the simulated profile (traffic, junctions,
    accelerations), so for a given NP less energy goes into speed. Expected
    VI_real / VI_sim = base + per_tight_turn_per_km * (turns tighter than
    tight_radius_m per km). Only used with NP targets (modes or kind="np")."""

    base: float = 1.069
    per_tight_turn_per_km: float = 0.672
    tight_radius_m: float = 20.0


@dataclass(frozen=True)
class Regrouping:
    """Time lost rolling slowly while a group regroups after a climb (club rides)."""

    seconds_per_climb: float = 45.0  # weak fit (8 club rides, very scattered)
    min_climb_gain_m: float = 40.0
    tolerance_m: float = 15.0


@dataclass(frozen=True)
class Settings:
    equipment: Equipment = field(default_factory=Equipment)
    environment: Environment = field(default_factory=Environment)
    pacing: Pacing = field(default_factory=Pacing)
    handling: Handling = field(default_factory=Handling)
    variability: Variability = field(default_factory=Variability)
    regrouping: Regrouping = field(default_factory=Regrouping)
