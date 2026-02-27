"""Tests for trajectory generators — no hardware required."""

import numpy as np
import pytest

from optotwin.trajectory import linspace_sweep, sparse_spiral, extremum_dither


class TestLinspaceSweep:
    def test_shape(self):
        traj = linspace_sweep(-1.0, 1.0, 100)
        assert traj.shape == (100, 2)

    def test_axis0_varies_x(self):
        traj = linspace_sweep(-1.0, 1.0, 50, axis=0, fixed_voltage=0.5)
        assert traj[0, 0] == pytest.approx(-1.0)
        assert traj[-1, 0] == pytest.approx(1.0)
        assert np.all(traj[:, 1] == pytest.approx(0.5))

    def test_axis1_varies_y(self):
        traj = linspace_sweep(-1.0, 1.0, 50, axis=1, fixed_voltage=-0.3)
        assert np.all(traj[:, 0] == pytest.approx(-0.3))


class TestSparseSpiral:
    def test_shape(self):
        traj = sparse_spiral(r_max=2.0, n_turns=3, n_points=500)
        assert traj.shape == (500, 2)

    def test_starts_at_center(self):
        traj = sparse_spiral(r_max=2.0, n_turns=3, n_points=500, center=(0.1, -0.2))
        assert traj[0, 0] == pytest.approx(0.1, abs=1e-9)
        assert traj[0, 1] == pytest.approx(-0.2, abs=1e-9)

    def test_stays_within_radius(self):
        r_max = 1.5
        traj = sparse_spiral(r_max=r_max, n_turns=2, n_points=300)
        radii = np.hypot(traj[:, 0], traj[:, 1])
        assert np.all(radii <= r_max + 1e-9)


class TestExtremumDither:
    def test_shape(self):
        traj = extremum_dither(center=0.0, amplitude=0.05, n_points=200)
        assert traj.shape == (200, 2)

    def test_amplitude_bound(self):
        center, amp = 1.0, 0.1
        traj = extremum_dither(center=center, amplitude=amp, n_points=100, axis=0)
        assert np.all(traj[:, 0] >= center - amp - 1e-9)
        assert np.all(traj[:, 0] <= center + amp + 1e-9)
