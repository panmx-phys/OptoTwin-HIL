"""Tests for digital twin models and optimizer — no hardware required."""

import numpy as np
import pytest

from optotwin.twin.models import gaussian_step_edge
from optotwin.twin.optimizer import fit_edge


class TestGaussianStepEdge:
    def test_midpoint_is_half_max(self):
        x = np.linspace(-5, 5, 1000)
        y = gaussian_step_edge(x, x0=0.0, sigma=1.0, i_low=0.0, i_high=1.0)
        mid = y[np.argmin(np.abs(x))]
        assert mid == pytest.approx(0.5, abs=0.01)

    def test_asymptotes(self):
        x = np.array([-100.0, 100.0])
        y = gaussian_step_edge(x, x0=0.0, sigma=1.0, i_low=10.0, i_high=90.0)
        assert y[0] == pytest.approx(10.0, abs=0.01)
        assert y[1] == pytest.approx(90.0, abs=0.01)


class TestFitEdge:
    def _synthetic(self, x0=0.5, sigma=0.3, i_low=5.0, i_high=95.0, noise=0.5):
        rng = np.random.default_rng(42)
        x = np.linspace(-2, 2, 200)
        y = gaussian_step_edge(x, x0=x0, sigma=sigma, i_low=i_low, i_high=i_high)
        y += rng.normal(0, noise, size=y.size)
        return x, y, dict(x0=x0, sigma=sigma, i_low=i_low, i_high=i_high)

    def test_recovers_x0(self):
        x, y, truth = self._synthetic()
        result = fit_edge(x, y)
        assert result.x0 == pytest.approx(truth["x0"], abs=0.05)

    def test_recovers_sigma(self):
        x, y, truth = self._synthetic()
        result = fit_edge(x, y)
        assert result.sigma == pytest.approx(truth["sigma"], rel=0.1)

    def test_residual_small(self):
        x, y, _ = self._synthetic(noise=0.1)
        result = fit_edge(x, y)
        assert result.residual_rms < 1.0
