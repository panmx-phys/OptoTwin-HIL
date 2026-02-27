"""Raster-scan trajectory generation and count reconstruction.

All functions here are pure numpy — no hardware imports. This module
is responsible for:
  - Generating the (2, N) voltage arrays that ``DAQOrchestrator.run`` consumes.
  - Reconstructing raw cumulative counts back into 2-D (or 3-D) images.

The scan pattern uses a **bidirectional (meandering) raster**: even-indexed
rows are scanned left-to-right, odd-indexed rows right-to-left. The
reconstruction mirrors the same flip so the final image is always oriented
consistently.

Legacy origin: ``daqScan`` and ``twoAreaInterlacingDaqScan`` in
legacyNotebook.py.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Single-area raster
# ---------------------------------------------------------------------------

def raster_voltages(
    x_px: int,
    y_px: int,
    xlims: tuple[float, float],
    ylims: tuple[float, float],
    accumulation: int = 1,
) -> NDArray[np.float64]:
    """Build the (2, N) voltage array for a bidirectional raster scan.

    Parameters
    ----------
    x_px, y_px:
        Pixel resolution.
    xlims, ylims:
        ``(start, stop)`` voltage range for each axis.
    accumulation:
        Number of full-frame passes. For ``accumulation > 1`` alternate
        passes are reversed so the beam always parks at the last scanned
        position.

    Returns
    -------
    NDArray[float64] of shape ``(2, x_px * y_px * accumulation)``
        Row 0 = X voltages, row 1 = Y voltages.
    """
    v_x = np.linspace(xlims[0], xlims[1], x_px)
    v_y = np.linspace(ylims[0], ylims[1], y_px)
    Vx, Vy = np.meshgrid(v_x, v_y, indexing="xy")

    # Flip odd rows for bidirectional (meandering) pattern
    Vx[1::2] = np.fliplr(Vx[1::2])

    frame_x = Vx.ravel()
    frame_y = Vy.ravel()
    single_frame = np.stack((frame_x, frame_y))  # (2, x_px*y_px)

    if accumulation <= 1:
        return single_frame

    n_frame = x_px * y_px
    full = np.empty((2, n_frame * accumulation), dtype=np.float64)
    for i in range(accumulation):
        sl = slice(i * n_frame, (i + 1) * n_frame)
        if i % 2 == 1:
            full[:, sl] = np.flip(single_frame, axis=1)
        else:
            full[:, sl] = single_frame
    return full


def reconstruct_image(
    cumulative_counts: NDArray[np.uint32],
    x_px: int,
    y_px: int,
    accumulation: int = 1,
) -> NDArray[np.float64]:
    """Convert raw cumulative DAQ counts into a 2-D or 3-D image array.

    Parameters
    ----------
    cumulative_counts:
        1-D array of shape ``(x_px * y_px * accumulation,)`` as returned
        by ``DAQOrchestrator.run``.
    x_px, y_px:
        Pixel resolution (must match what was used to build the voltages).
    accumulation:
        Number of frames (default 1).

    Returns
    -------
    NDArray[float64]
        Shape ``(y_px, x_px)`` for single frame, or
        ``(accumulation, y_px, x_px)`` for multi-frame.
    """
    # Differentiate cumulative counter → per-pixel counts
    counts = np.insert(np.diff(cumulative_counts), 0, cumulative_counts[0]).astype(
        np.float64
    )

    n_frame = x_px * y_px

    if accumulation <= 1:
        image = counts.reshape(y_px, x_px)
        image[1::2] = np.fliplr(image[1::2])  # un-flip odd rows
        image[0, 0] = 0  # first pixel is always a counter artefact
        return image

    frames = np.empty((accumulation, y_px, x_px), dtype=np.float64)
    for i in range(accumulation):
        frame_counts = counts[i * n_frame : (i + 1) * n_frame]
        if i % 2 == 1:
            frame_counts = np.flip(frame_counts)
        frame = frame_counts.reshape(y_px, x_px)
        frame[1::2] = np.fliplr(frame[1::2])
        frames[i] = frame
    return frames


# ---------------------------------------------------------------------------
# Dual-area interlaced raster
# ---------------------------------------------------------------------------

def interleaved_dual_raster(
    px1: tuple[int, int],
    px2: tuple[int, int],
    xlims1: tuple[float, float],
    ylims1: tuple[float, float],
    xlims2: tuple[float, float],
    ylims2: tuple[float, float],
) -> NDArray[np.float64]:
    """Build a (2, N) voltage array that interleaves two raster regions.

    The interleave pattern is ``[A A B B A A B B …]`` (4× interlacing),
    matching the legacy ``twoAreaInterlacingDaqScan``. A trailing (0, 0)
    sample is appended so the counter always captures a final edge.

    Parameters
    ----------
    px1, px2:
        ``(x_px, y_px)`` for each region.
    xlims1, ylims1, xlims2, ylims2:
        Voltage limits for each region.

    Returns
    -------
    NDArray[float64] of shape ``(2, 4 * px1[0]*px1[1] + 1)``
        (assumes ``px1[0]*px1[1] == px2[0]*px2[1]``).
    """
    def _make_frame(px, xlims, ylims):
        vx = np.linspace(xlims[0], xlims[1], px[0])
        vy = np.linspace(ylims[0], ylims[1], px[1])
        Vx, Vy = np.meshgrid(vx, vy, indexing="xy")
        Vx[1::2] = np.fliplr(Vx[1::2])
        return Vx.ravel(), Vy.ravel()

    Vx1, Vy1 = _make_frame(px1, xlims1, ylims1)
    Vx2, Vy2 = _make_frame(px2, xlims2, ylims2)

    n = Vx1.size + Vx2.size
    joint_x = np.empty(n * 2, dtype=np.float64)
    joint_y = np.empty(n * 2, dtype=np.float64)
    joint_x[0::4] = Vx1
    joint_x[1::4] = Vx1
    joint_x[2::4] = Vx2
    joint_x[3::4] = Vx2
    joint_y[0::4] = Vy1
    joint_y[1::4] = Vy1
    joint_y[2::4] = Vy2
    joint_y[3::4] = Vy2

    # Trailing park sample
    joint_x = np.append(joint_x, 0.0)
    joint_y = np.append(joint_y, 0.0)
    return np.stack((joint_x, joint_y))


def reconstruct_dual_images(
    cumulative_counts: NDArray[np.uint32],
    px1: tuple[int, int],
    px2: tuple[int, int],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Split and reconstruct two images from an interleaved acquisition.

    Parameters
    ----------
    cumulative_counts:
        Raw counts from ``DAQOrchestrator.run`` on an interleaved voltage
        array produced by ``interleaved_dual_raster``.
    px1, px2:
        Pixel sizes matching those passed to ``interleaved_dual_raster``.

    Returns
    -------
    counts1, counts2 : tuple of NDArray[float64]
        Reconstructed images with shapes ``(px1[1], px1[0])`` and
        ``(px2[1], px2[0])`` respectively.
    """
    # Drop the trailing park sample
    raw = cumulative_counts[:-1]
    counts = np.insert(np.diff(raw), 0, raw[0]).astype(np.float64)

    counts1_flat = counts[1::4]
    counts2_flat = counts[3::4]

    def _reshape(flat, px):
        img = flat.reshape(px[1], px[0])
        img[1::2] = np.fliplr(img[1::2])
        return img

    return _reshape(counts1_flat, px1), _reshape(counts2_flat, px2)
