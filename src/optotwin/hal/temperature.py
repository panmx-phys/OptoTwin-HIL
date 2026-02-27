"""Temperature controller interfaces.

Two sources are supported:
1. Auber PID via ModBus RTU (COM5, slave 3) — primary setpoint controller.
2. K-type thermocouple via NI DAQ analog input — local cross-check.

Only this module (and other hal/ files) may import nidaqmx or minimalmodbus.

Legacy origin: Auber ModBus setup and K-type thermocouple channel in
legacyNotebook.py.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_MODBUS_AVAILABLE = True
try:
    import minimalmodbus
except ImportError:
    _MODBUS_AVAILABLE = False
    log.warning("minimalmodbus not installed — AuberController will raise on use.")

_NIDAQMX_AVAILABLE = True
try:
    import nidaqmx
    from nidaqmx.constants import (
        AcquisitionType,
        READ_ALL_AVAILABLE,
        TemperatureUnits,
        ThermocoupleType,
    )
except ImportError:
    _NIDAQMX_AVAILABLE = False


class AuberController:
    """ModBus RTU interface to an Auber PID temperature controller.

    Parameters
    ----------
    port:
        Serial port name, e.g. ``"COM5"`` (Windows) or ``"/dev/ttyUSB0"``.
    slave_address:
        ModBus slave address (default 3).
    """

    _TEMP_REGISTER = 1000

    def __init__(self, port: str = "COM5", slave_address: int = 3) -> None:
        if not _MODBUS_AVAILABLE:
            raise RuntimeError(
                "minimalmodbus is required for AuberController. "
                "Install it with: pip install minimalmodbus"
            )
        self._inst = minimalmodbus.Instrument(port, slave_address)
        self._inst.serial.baudrate = 9600
        self._inst.serial.bytesize = 8
        self._inst.serial.parity = minimalmodbus.serial.PARITY_NONE
        self._inst.serial.stopbits = 1
        self._inst.serial.timeout = 0.5
        self._inst.mode = minimalmodbus.MODE_RTU
        log.info("AuberController connected: port=%s slave=%d", port, slave_address)

    def get_temperature(self) -> float:
        """Read process temperature (°C) from register 1000."""
        return float(self._inst.read_register(self._TEMP_REGISTER, 0))


class ThermocoupleReader:
    """K-type thermocouple reader via NI DAQ analog input.

    Parameters
    ----------
    channel:
        NI thermocouple channel, e.g. ``"Dev1/ai0"``.
    """

    def __init__(self, channel: str = "Dev1/ai0") -> None:
        if not _NIDAQMX_AVAILABLE:
            raise RuntimeError(
                "nidaqmx is required for ThermocoupleReader. "
                "Install it with: pip install nidaqmx"
            )
        self._channel = channel

    def get_temperature(self) -> float:
        """Return a single temperature reading in °C."""
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_thrmcpl_chan(
                self._channel,
                units=TemperatureUnits.DEG_C,
                thermocouple_type=ThermocoupleType.K,
            )
            task.timing.cfg_samp_clk_timing(
                100.0,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=10,
            )
            data = task.read(READ_ALL_AVAILABLE)
        import numpy as np
        return float(np.mean(data))
