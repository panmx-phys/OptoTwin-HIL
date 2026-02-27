"""Curve-fitting routines to extract beam parameters from raw photon counts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import curve_fit

from optotwin.twin.models import gaussian_step_edge


@dataclass
class EdgeFitResult:
    x0: float          # edge position
    sigma: float       # beam 1/e² radius
    i_low: float       # background level
    i_high: float      # peak level
    residual_rms: float


def fit_edge(
    positions: ArrayLike,
    counts: ArrayLike,
    p0: tuple[float, float, float, float] | None = None,
) -> EdgeFitResult:
    """Fit a Gaussian knife-edge model to measured photon counts.

    Parameters
    ----------
    positions:
        1-D array of scan positions (volts or physical units).
    counts:
        1-D array of measured photon counts, same length as *positions*.
    p0:
        Initial guess (x0, sigma, i_low, i_high). If None, a heuristic
        estimate is used.

    Returns
    -------
    EdgeFitResult
    """
    x = np.asarray(positions, dtype=float)
    y = np.asarray(counts, dtype=float)

    if p0 is None:
        x0_guess = x[np.argmin(np.abs(y - (y.max() + y.min()) / 2))]
        p0 = (x0_guess, (x[-1] - x[0]) / 10, float(y.min()), float(y.max()))

    popt, _ = curve_fit(gaussian_step_edge, x, y, p0=p0, maxfev=10_000)
    residual_rms = float(np.sqrt(np.mean((y - gaussian_step_edge(x, *popt)) ** 2)))

    return EdgeFitResult(
        x0=popt[0],
        sigma=popt[1],
        i_low=popt[2],
        i_high=popt[3],
        residual_rms=residual_rms,
    )
