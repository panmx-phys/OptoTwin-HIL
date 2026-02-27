"""Tests for raster trajectory generation and count reconstruction."""

import numpy as np
import pytest

from optotwin.trajectory.raster import (
    raster_voltages,
    reconstruct_image,
    interleaved_dual_raster,
    reconstruct_dual_images,
)
from optotwin.hal.daq import SimulatedDAQOrchestrator


class TestRasterVoltages:
    def test_shape_single(self):
        v = raster_voltages(10, 8, (-1.0, 1.0), (-0.5, 0.5))
        assert v.shape == (2, 80)

    def test_shape_accumulation(self):
        v = raster_voltages(10, 8, (-1.0, 1.0), (-0.5, 0.5), accumulation=3)
        assert v.shape == (2, 240)

    def test_x_range(self):
        v = raster_voltages(5, 4, (-1.0, 1.0), (0.0, 0.5))
        assert v[0].min() >= -1.0 - 1e-9
        assert v[0].max() <= 1.0 + 1e-9

    def test_y_range(self):
        v = raster_voltages(5, 4, (-1.0, 1.0), (0.0, 0.5))
        assert v[1].min() >= 0.0 - 1e-9
        assert v[1].max() <= 0.5 + 1e-9


class TestReconstructImage:
    def _run_sim(self, x_px=10, y_px=8, accumulation=1):
        daq = SimulatedDAQOrchestrator()
        v = raster_voltages(x_px, y_px, (-1.0, 1.0), (-0.5, 0.5), accumulation)
        counts = daq.run(v, dwell_time=0.001)
        return counts, x_px, y_px, accumulation

    def test_shape_single(self):
        counts, x_px, y_px, acc = self._run_sim()
        img = reconstruct_image(counts, x_px, y_px)
        assert img.shape == (y_px, x_px)

    def test_shape_accumulation(self):
        counts, x_px, y_px, acc = self._run_sim(accumulation=3)
        img = reconstruct_image(counts, x_px, y_px, accumulation=3)
        assert img.shape == (3, y_px, x_px)

    def test_non_negative(self):
        counts, x_px, y_px, acc = self._run_sim()
        img = reconstruct_image(counts, x_px, y_px)
        # sim counts are cumulative differences — all should be >= 0
        assert np.all(img >= 0)


class TestInterleavedDualRaster:
    def test_shape(self):
        px1, px2 = (5, 4), (5, 4)
        v = interleaved_dual_raster(
            px1, px2, (-1.0, 0.0), (-0.5, 0.5), (0.0, 1.0), (-0.5, 0.5)
        )
        expected_n = 4 * px1[0] * px1[1] + 1
        assert v.shape == (2, expected_n)

    def test_parks_at_zero(self):
        px1, px2 = (5, 4), (5, 4)
        v = interleaved_dual_raster(
            px1, px2, (-1.0, 0.0), (-0.5, 0.5), (0.0, 1.0), (-0.5, 0.5)
        )
        np.testing.assert_allclose(v[:, -1], [0.0, 0.0])


class TestReconstructDualImages:
    def test_shapes(self):
        px1, px2 = (5, 4), (5, 4)
        daq = SimulatedDAQOrchestrator()
        v = interleaved_dual_raster(
            px1, px2, (-1.0, 0.0), (-0.5, 0.5), (0.0, 1.0), (-0.5, 0.5)
        )
        raw = daq.run(v, dwell_time=0.001)
        img1, img2 = reconstruct_dual_images(raw, px1, px2)
        assert img1.shape == (px1[1], px1[0])
        assert img2.shape == (px2[1], px2[0])
