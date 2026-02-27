"""Extremum-seeking dither trajectory for closed-loop edge locking."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def extremum_dither(
    center: float,
    amplitude: float,
    n_points: int,
    dither_freq_ratio: float = 0.1,
    axis: int = 0,
    fixed_voltage: float = 0.0,
) -> NDArray[np.float64]:
    """Sinusoidal dither around *center* on one axis.

    Parameters
    ----------
    center:
        Nominal operating voltage.
    amplitude:
        Peak dither amplitude in volts.
    n_points:
        Number of samples per dither cycle.
    dither_freq_ratio:
        Dither frequency as a fraction of the sample rate (0 < f < 0.5).
    axis:
        0 = X galvo, 1 = Y galvo.
    fixed_voltage:
        Voltage held on the stationary axis.

    Returns
    -------
    NDArray[float64] of shape (n_points, 2)
    """
    t = np.arange(n_points)
    dither = center + amplitude * np.sin(2 * np.pi * dither_freq_ratio * t)
    fixed = np.full(n_points, fixed_voltage)
    if axis == 0:
        return np.column_stack([dither, fixed])
    return np.column_stack([fixed, dither])
