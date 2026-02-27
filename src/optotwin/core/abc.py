"""Abstract Base Classes for all OptoTwin components."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray


class Scanner(ABC):
    """ABC for any device that positions the beam."""

    @abstractmethod
    def write_voltages(self, voltages: NDArray[np.float64]) -> None:
        """Write a (N, 2) array of (u, v) voltage samples."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class Detector(ABC):
    """ABC for any photon-counting or analog detector."""

    @abstractmethod
    def read_counts(self, n_samples: int) -> NDArray[np.uint32]:
        """Return an (N,) array of photon counts."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
