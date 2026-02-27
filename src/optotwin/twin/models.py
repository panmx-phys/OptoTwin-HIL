"""Physical forward models for the digital twin."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import erf


def gaussian_step_edge(
    x: ArrayLike,
    x0: float,
    sigma: float,
    i_low: float,
    i_high: float,
) -> NDArray[np.float64]:
    """Gaussian-convolved step-edge (knife-edge) response model.

    Models the detected intensity as a beam of width *sigma* crosses an
    absorbing edge at position *x0*:

        I(x) = (I_high - I_low) / 2 * [1 + erf((x - x0) / (sqrt(2) * sigma))]
               + I_low

    Parameters
    ----------
    x:
        Position array (same units as x0 and sigma).
    x0:
        Edge position.
    sigma:
        1/e² Gaussian beam radius (beam waist).
    i_low, i_high:
        Background and peak intensity levels.

    Returns
    -------
    NDArray[float64] same shape as *x*.
    """
    x = np.asarray(x, dtype=float)
    return (i_high - i_low) / 2.0 * (1.0 + erf((x - x0) / (np.sqrt(2.0) * sigma))) + i_low
