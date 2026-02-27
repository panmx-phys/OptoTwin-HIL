"""1-D sweep trajectory generator."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def linspace_sweep(
    start: float,
    stop: float,
    n_points: int,
    axis: int = 0,
    fixed_voltage: float = 0.0,
) -> NDArray[np.float64]:
    """Generate a 1-D sweep along one galvo axis.

    Parameters
    ----------
    start, stop:
        Voltage range for the moving axis.
    n_points:
        Number of sample points.
    axis:
        0 = X galvo, 1 = Y galvo.
    fixed_voltage:
        Voltage held on the stationary axis.

    Returns
    -------
    NDArray[float64] of shape (n_points, 2)
        Column 0 = X voltage, column 1 = Y voltage.
    """
    sweep = np.linspace(start, stop, n_points)
    fixed = np.full(n_points, fixed_voltage)
    if axis == 0:
        return np.column_stack([sweep, fixed])
    return np.column_stack([fixed, sweep])
