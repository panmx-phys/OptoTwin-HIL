"""Trajectory: hardware-agnostic geometric path generation."""

from optotwin.trajectory.sweep import linspace_sweep
from optotwin.trajectory.spiral import sparse_spiral
from optotwin.trajectory.dither import extremum_dither
from optotwin.trajectory.raster import (
    raster_voltages,
    reconstruct_image,
    interleaved_dual_raster,
    reconstruct_dual_images,
)

__all__ = [
    "linspace_sweep",
    "sparse_spiral",
    "extremum_dither",
    "raster_voltages",
    "reconstruct_image",
    "interleaved_dual_raster",
    "reconstruct_dual_images",
]
