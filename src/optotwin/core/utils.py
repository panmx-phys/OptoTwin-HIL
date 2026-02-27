"""Miscellaneous utility functions.

Legacy origin: ``calculate_square_pixels``, ``makeConfigSquare``,
``timeOfConfig``, ``rectToLims`` in legacyNotebook.py.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from optotwin.core.config import ScanConfig


def calculate_square_pixels(
    xlims: tuple[float, float],
    ylims: tuple[float, float],
    base_px: int = 100,
) -> tuple[int, int]:
    """Return ``(x_px, y_px)`` that preserves the physical aspect ratio.

    The longer axis gets ``base_px`` pixels; the shorter axis is scaled
    proportionally.

    Parameters
    ----------
    xlims, ylims:
        ``(start_V, stop_V)`` for each axis.
    base_px:
        Pixel count assigned to the longer axis (default 100).

    Returns
    -------
    (x_px, y_px)
    """
    x_range = abs(xlims[1] - xlims[0])
    y_range = abs(ylims[1] - ylims[0])

    if x_range >= y_range:
        x_px = base_px
        y_px = max(1, int(base_px * (y_range / x_range)))
    else:
        y_px = base_px
        x_px = max(1, int(base_px * (x_range / y_range)))

    return x_px, y_px


def make_config_square(config: ScanConfig, base_px: int = 100) -> ScanConfig:
    """Set ``config.x_px`` / ``config.y_px`` to match the scan aspect ratio.

    Modifies *config* in-place and returns it.
    """
    x_px, y_px = calculate_square_pixels(config.xlims, config.ylims, base_px)
    config.x_px = x_px
    config.y_px = y_px
    return config


def print_scan_time(config: ScanConfig, multiplier: int = 1) -> None:
    """Print total scan time and per-frame time for *config*.

    Parameters
    ----------
    config:
        A ``ScanConfig`` instance.
    multiplier:
        Optional scale factor (e.g. number of laser setpoints).
    """
    total = datetime.timedelta(seconds=config.total_time_s * multiplier)
    frame = datetime.timedelta(seconds=config.frame_time_s)
    print(f"Total time : {total}")
    print(f"Frame time : {frame}")


def rect_to_lims(
    rect: tuple[tuple[float, float], tuple[float, float]],
    config: ScanConfig,
) -> ScanConfig:
    """Set ``config.xlims`` / ``config.ylims`` from a rectangle selection.

    Parameters
    ----------
    rect:
        ``((x1, y1), (x2, y2))`` corner coordinates in voltage units.
    config:
        ``ScanConfig`` to update in-place.

    Returns
    -------
    The modified *config*.
    """
    (x1, y1), (x2, y2) = rect
    config.xlims = (x1, x2)
    config.ylims = (y1, y2)
    return config
