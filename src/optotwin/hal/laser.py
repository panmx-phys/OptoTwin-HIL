"""Laser driver interface for the CLD1015 diode laser controller.

Communicates via PyVISA (USB/USBTMC). Only this module (and other hal/
files) may use pyvisa for instrument control.

Legacy origin: ``LaserDriver`` class and ``CLD1015`` VISA resource.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_PYVISA_AVAILABLE = True
try:
    import pyvisa
except ImportError:
    _PYVISA_AVAILABLE = False
    log.warning("pyvisa not installed — LaserDriver will raise on use.")


class LaserDriver:
    """VISA wrapper for the CLD1015 laser diode controller.

    Parameters
    ----------
    resource:
        An open ``pyvisa.resources.Resource`` object for the instrument.
    """

    def __init__(self, resource: object) -> None:
        self._res = resource

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def connect(
        cls,
        serial: str = "M00959058",
        resource_manager: object | None = None,
    ) -> LaserDriver:
        """Open a connection to the CLD1015 by USB serial number.

        Parameters
        ----------
        serial:
            USB serial number string as reported by ``pyvisa``.
        resource_manager:
            Existing ``pyvisa.ResourceManager``; one is created if None.
        """
        if not _PYVISA_AVAILABLE:
            raise RuntimeError("pyvisa is required. Install with: pip install pyvisa")
        if resource_manager is None:
            resource_manager = pyvisa.ResourceManager()
        resource = resource_manager.open_resource(f"USB::INSTR::{serial}")
        log.info("Connected to laser driver serial=%s", serial)
        return cls(resource)

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    def get_temp(self) -> float:
        """Query TEC temperature (°C)."""
        return float(self._res.query("SENSe2:DATA?")[:-1])

    def set_temp(self, temp: float) -> None:
        """Set TEC temperature setpoint (°C)."""
        self._res.write(f"SOURce2:TEMP:SPO {temp}")

    # ------------------------------------------------------------------
    # Current
    # ------------------------------------------------------------------

    def get_current(self) -> float:
        """Query laser drive current (A)."""
        return float(self._res.query("SENSe3?")[:-1])

    def set_current(self, current: float) -> None:
        """Set laser drive current (A)."""
        self._res.write(f"SOURce1:CURR {current}")

    # ------------------------------------------------------------------
    # Monitor photodiode
    # ------------------------------------------------------------------

    def get_pd_current(self) -> float:
        """Query internal monitor photodiode current (A)."""
        return float(self._res.query("SENSe1?")[:-1])

    # ------------------------------------------------------------------
    # Output enable
    # ------------------------------------------------------------------

    def set_output(self, on: bool) -> None:
        """Enable (True) or disable (False) laser output."""
        self._res.write(f"OUTPut1:STATe {1 if on else 0}")

    def is_output_on(self) -> bool:
        """Return True if laser output is currently enabled."""
        return int(self._res.query("OUTPut1:STATe?")[:-1]) == 1

    def set_tec(self, on: bool) -> None:
        """Enable (True) or disable (False) the TEC."""
        self._res.write(f"OUTPut2:STATe {1 if on else 0}")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release the VISA resource."""
        self._res.close()

    def __enter__(self) -> LaserDriver:
        return self

    def __exit__(self, *_) -> None:
        self.close()
