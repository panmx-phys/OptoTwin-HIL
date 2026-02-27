"""Tests for AffineTransform2D."""

import numpy as np
import pytest

from optotwin.core.transforms import AffineTransform2D


class TestAffineTransform2D:
    def test_identity(self):
        t = AffineTransform2D()
        pts = np.array([[1.0, 2.0], [-3.0, 4.0]])
        np.testing.assert_allclose(t.forward(pts), pts)

    def test_scale_offset_roundtrip(self):
        t = AffineTransform2D.from_scale_offset(2.0, -1.0, 0.5, -0.5)
        pts = np.array([[0.0, 0.0], [1.0, 1.0], [-1.0, 0.5]])
        np.testing.assert_allclose(t.inverse(t.forward(pts)), pts, atol=1e-12)

    def test_bad_matrix_raises(self):
        with pytest.raises(ValueError):
            AffineTransform2D(np.eye(2))

    def test_single_point(self):
        t = AffineTransform2D.from_scale_offset(scale_x=3.0, scale_y=3.0)
        result = t.forward(np.array([1.0, 2.0]))
        np.testing.assert_allclose(result, [3.0, 6.0])
