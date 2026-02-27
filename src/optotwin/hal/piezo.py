"""MDT piezo stage controller (Y-axis focus).

Wraps the proprietary ``MDT_COMMAND_LIB`` serial library. Import errors are
handled gracefully so the rest of the package loads without the MDT driver.

Legacy origin: mdt piezo setup and z-stack scan in legacyNotebook.py.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_MDT_AVAILABLE = True
try:
    import MDT_COMMAND_LIB as mdt  # type: ignore[import]
except ImportError:
    _MDT_AVAILABLE = False
    log.warning(
        "MDT_COMMAND_LIB not found — PiezoStage will raise on use. "
        "Install the MDT driver from Thorlabs."
    )


class PiezoStage:
    """Serial interface to a Thorlabs MDT piezo stage.

    Parameters
    ----------
    baud_rate:
        Serial baud rate (default 115200).
    """

    def __init__(self, baud_rate: int = 115200) -> None:
        if not _MDT_AVAILABLE:
            raise RuntimeError(
                "MDT_COMMAND_LIB is required for PiezoStage. "
                "Install the Thorlabs MDT driver."
            )
        self._baud = baud_rate
        self._hdl: int | None = None

    def connect(self) -> None:
        """Open the first available MDT device."""
        devices = mdt.mdtListDevices()
        if not devices:
            raise RuntimeError("No MDT devices found.")
        serial = devices[0][0]
        self._hdl = mdt.mdtOpen(serial, self._baud, 3)
        log.info("PiezoStage connected: serial=%s", serial)

    def disconnect(self) -> None:
        """Close the serial connection."""
        if self._hdl is not None:
            mdt.mdtClose(self._hdl)
            self._hdl = None

    def set_y_voltage(self, voltage: float) -> None:
        """Set Y-axis (focus) voltage in volts."""
        if self._hdl is None:
            raise RuntimeError("Not connected. Call connect() first.")
        mdt.mdtSetYAxisVoltage(self._hdl, voltage)

    def get_y_voltage(self) -> float:
        """Read current Y-axis voltage in volts."""
        if self._hdl is None:
            raise RuntimeError("Not connected. Call connect() first.")
        result = [0.0]
        mdt.mdtGetYAxisVoltage(self._hdl, result)
        return float(result[0])

    def __enter__(self) -> PiezoStage:
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()
