"""plato-edge: Edge-optimized Cocapn fleet packages for ARM64 devices.

Pure-Python, stdlib-only bundles for resource-constrained environments
(Jetson Orin, 24 GB RAM, GPU). Zero external dependencies.
"""

__version__ = "0.1.0"

from .tile_spec import Tile, TileCodec, TileError
from .deadband import DeadbandGate, classify
from .flywheel import Flywheel, FlywheelError
from .keeper import Beacon, BeaconError
from .explain import Tracer, TraceError

__all__ = [
    "Tile",
    "TileCodec",
    "TileError",
    "DeadbandGate",
    "classify",
    "Flywheel",
    "FlywheelError",
    "Beacon",
    "BeaconError",
    "Tracer",
    "TraceError",
]
