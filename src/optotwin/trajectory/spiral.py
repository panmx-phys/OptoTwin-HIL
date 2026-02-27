"""Sparse Archimedean spiral trajectory for 2-D area scans."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def sparse_spiral(
    r_max: float,
    n_turns: int,
    n_points: int,
    center: tuple[float, float] = (0.0, 0.0),
) -> NDArray[np.float64]:
    """Return an Archimedean spiral as (N, 2) voltage samples.

    Parameters
    ----------
    r_max:
        Outer radius in volts.
    n_turns:
        Number of full revolutions.
    n_points:
        Total sample count.
    center:
        (u, v) centre voltage.

    Returns
    -------
    NDArray[float64] of shape (n_points, 2)
    """
    theta = np.linspace(0.0, 2 * np.pi * n_turns, n_points)
    r = r_max * theta / (2 * np.pi * n_turns)
    x = center[0] + r * np.cos(theta)
    y = center[1] + r * np.sin(theta)
    return np.column_stack([x, y])
