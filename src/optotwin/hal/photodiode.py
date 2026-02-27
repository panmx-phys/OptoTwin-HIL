"""External photodiode reader via NI DAQ analog input.

Only this module (and other hal/ files) may import nidaqmx.

Legacy origin: ``photoDiode`` class in legacyNotebook.py.
"""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

_NIDAQMX_AVAILABLE = True
try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType, READ_ALL_AVAILABLE
except ImportError:
    _NIDAQMX_AVAILABLE = False
    log.warning("nidaqmx not installed — PhotoDiode will raise on use.")


class PhotoDiode:
    """Reads a voltage-output photodiode via a DAQ analog input channel.

    Parameters
    ----------
    channel:
        NI channel string, e.g. ``"Dev1/ai0"``.
    sample_rate:
        Sampling rate in Hz (default 1 kHz).
    n_samples:
        Number of samples to average per reading (default 200).
    """

    def __init__(
        self,
        channel: str = "Dev1/ai0",
        sample_rate: float = 1000.0,
        n_samples: int = 200,
    ) -> None:
        if not _NIDAQMX_AVAILABLE:
            raise RuntimeError(
                "nidaqmx is required for PhotoDiode. "
                "Install it with: pip install nidaqmx"
            )
        self._channel = channel
        self._rate = sample_rate
        self._n = n_samples

    def get_voltage(self) -> float:
        """Return the mean photodiode voltage over ``n_samples`` samples."""
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(self._channel)
            task.timing.cfg_samp_clk_timing(
                self._rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self._n,
            )
            data = task.read(READ_ALL_AVAILABLE)
        return float(np.mean(data))
