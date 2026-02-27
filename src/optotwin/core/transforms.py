"""Affine coordinate transformation matrices (voltage space ↔ physical space)."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


class AffineTransform2D:
    """2-D affine transform: physical (x, y) ↔ actuator voltage (u, v).

    The mapping is:
        [u]   [a  b  tx] [x]
        [v] = [c  d  ty] [y]
        [1]   [0  0   1] [1]
    """

    def __init__(self, matrix: ArrayLike | None = None) -> None:
        if matrix is None:
            self._M = np.eye(3)
        else:
            M = np.asarray(matrix, dtype=float)
            if M.shape != (3, 3):
                raise ValueError("matrix must be 3×3")
            self._M = M

    @classmethod
    def from_scale_offset(
        cls,
        scale_x: float,
        scale_y: float,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> AffineTransform2D:
        M = np.array([
            [scale_x, 0.0, offset_x],
            [0.0, scale_y, offset_y],
            [0.0, 0.0, 1.0],
        ])
        return cls(M)

    def forward(self, xy: ArrayLike) -> np.ndarray:
        """Physical (x, y) → actuator (u, v). Input shape: (..., 2)."""
        xy = np.asarray(xy, dtype=float)
        ones = np.ones(xy.shape[:-1] + (1,))
        xyz = np.concatenate([xy, ones], axis=-1)
        return (self._M @ xyz.T).T[..., :2]

    def inverse(self, uv: ArrayLike) -> np.ndarray:
        """Actuator (u, v) → physical (x, y). Input shape: (..., 2)."""
        uv = np.asarray(uv, dtype=float)
        ones = np.ones(uv.shape[:-1] + (1,))
        uvw = np.concatenate([uv, ones], axis=-1)
        M_inv = np.linalg.inv(self._M)
        return (M_inv @ uvw.T).T[..., :2]

    @property
    def matrix(self) -> np.ndarray:
        return self._M.copy()
