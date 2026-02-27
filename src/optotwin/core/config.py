"""ScanConfig: typed container for scan parameters.

Replaces the raw ``dict`` configs scattered through the legacy notebook
(``flakeConfig``, ``midCircleConfig``, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScanConfig:
    """Parameters for a single-area 2-D raster scan.

    Attributes
    ----------
    x_px, y_px:
        Pixel resolution.
    xlims, ylims:
        ``(start_V, stop_V)`` voltage range for each galvo axis.
    dwell_time:
        Seconds per pixel.
    accumulation:
        Number of full-frame passes (default 1).
    nd_filters:
        List of ND filter indices in the beam path (for metadata only).
    experiment_name, sample_name, measurement_name, comment:
        QCoDeS / metadata labels.
    """

    x_px: int
    y_px: int
    xlims: tuple[float, float]
    ylims: tuple[float, float]
    dwell_time: float
    accumulation: int = 1
    nd_filters: list[int] = field(default_factory=list)
    experiment_name: str = ""
    sample_name: str = ""
    measurement_name: str = ""
    comment: str = ""

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def n_pixels(self) -> int:
        return self.x_px * self.y_px

    @property
    def frame_time_s(self) -> float:
        return self.n_pixels * self.dwell_time

    @property
    def total_time_s(self) -> float:
        return self.frame_time_s * self.accumulation

    def __str__(self) -> str:
        import datetime
        return (
            f"ScanConfig({self.x_px}×{self.y_px} px, "
            f"dwell={self.dwell_time*1e3:.2f} ms, "
            f"acc={self.accumulation}, "
            f"total={datetime.timedelta(seconds=int(self.total_time_s))})"
        )


@dataclass
class DualAreaScanConfig:
    """Parameters for a two-area interlaced raster scan."""

    px1: tuple[int, int]
    px2: tuple[int, int]
    xlims1: tuple[float, float]
    ylims1: tuple[float, float]
    xlims2: tuple[float, float]
    ylims2: tuple[float, float]
    dwell_time: float
    nd_filters: list[int] = field(default_factory=list)
    experiment_name: str = ""
    sample_name: str = ""
    measurement_name: str = ""
    comment: str = ""
