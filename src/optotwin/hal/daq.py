"""DAQ Orchestrator: NI USB-6421 hardware-timed galvo scanning and photon counting.

Only this module (and other files inside hal/) may import nidaqmx.

The core acquisition primitive (`run`) is a direct port of the legacy
`daqDriver` function. Higher-level scan helpers live in `trajectory.raster`.
"""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

log = logging.getLogger(__name__)

_NIDAQMX_AVAILABLE = True
try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType, CountDirection, Edge
except ImportError:
    _NIDAQMX_AVAILABLE = False
    log.warning("nidaqmx not installed — DAQOrchestrator will raise on use.")


class DAQOrchestrator:
    """Hardware-timed acquisition: AO sample clock routed to CI counter.

    The AO task drives the X/Y galvo mirrors; the CI task counts SPAD
    photon pulses, clocked by the same AO sample clock for zero-latency
    synchronisation.

    Parameters
    ----------
    ao_x_channel:
        NI channel for the X galvo, e.g. ``"Dev1/ao0"``.
    ao_y_channel:
        NI channel for the Y galvo, e.g. ``"Dev1/ao1"``.
    ci_channel:
        NI channel string for the SPAD counter, e.g. ``"Dev1/ctr0"``.
    pfi_terminal:
        Physical terminal for photon pulse input, e.g. ``"/Dev1/PFI0"``.
    """

    def __init__(
        self,
        ao_x_channel: str = "Dev1/ao0",
        ao_y_channel: str = "Dev1/ao1",
        ci_channel: str = "Dev1/ctr0",
        pfi_terminal: str = "/Dev1/PFI0",
    ) -> None:
        if not _NIDAQMX_AVAILABLE:
            raise RuntimeError(
                "nidaqmx is required for DAQOrchestrator. "
                "Install it with: pip install nidaqmx"
            )
        self._ao_x = ao_x_channel
        self._ao_y = ao_y_channel
        self._ci_ch = ci_channel
        self._pfi = pfi_terminal
        device = ao_x_channel.split("/")[0]
        self._ao_clk_src = f"/{device}/ao/SampleClock"

    def run(
        self,
        voltages: NDArray[np.float64],
        dwell_time: float,
    ) -> NDArray[np.uint32]:
        """Write galvo voltages and return cumulative photon counts.

        Direct port of the legacy ``daqDriver`` function.

        Parameters
        ----------
        voltages:
            Shape ``(2, N)`` — row 0 = X voltages, row 1 = Y voltages.
        dwell_time:
            Seconds per sample point. Sets the hardware sample rate to
            ``1 / dwell_time`` Hz.

        Returns
        -------
        NDArray[uint32] of shape ``(N,)``
            *Cumulative* photon counts from the counter. Differentiate to
            get per-pixel counts:
            ``np.insert(np.diff(counts), 0, counts[0])``.
        """
        n_samples = voltages.shape[1]
        rate = 1.0 / dwell_time

        with nidaqmx.Task() as ao_task, nidaqmx.Task() as ci_task:
            # Analog outputs: X and Y galvo mirrors
            ao_task.ao_channels.add_ao_voltage_chan(
                self._ao_x, name_to_assign_to_channel="X_Galvo"
            )
            ao_task.ao_channels.add_ao_voltage_chan(
                self._ao_y, name_to_assign_to_channel="Y_Galvo"
            )
            ao_task.timing.cfg_samp_clk_timing(
                rate=rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=n_samples,
            )

            # Counter input: SPAD photon counts, clocked by AO sample clock
            ci_ch = ci_task.ci_channels.add_ci_count_edges_chan(
                self._ci_ch,
                name_to_assign_to_channel="Photon_Count",
                initial_count=0,
                count_direction=CountDirection.COUNT_UP,
                edge=Edge.RISING,
            )
            ci_ch.ci_count_edges_term = self._pfi
            ci_task.timing.cfg_samp_clk_timing(
                rate=rate,
                source=self._ao_clk_src,
                active_edge=Edge.RISING,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=n_samples,
            )

            ao_task.write(voltages, auto_start=False)
            ci_task.start()
            ao_task.start()

            counts = ci_task.read(
                number_of_samples_per_channel=n_samples, timeout=-1
            )
            ao_task.wait_until_done(timeout=-1)
            ci_task.wait_until_done(timeout=-1)

        log.debug("DAQ run: %d samples @ %.1f Hz", n_samples, rate)
        return np.asarray(counts, dtype=np.uint32)

    def park(self, dwell_time: float = 0.01) -> None:
        """Return galvos to (0, 0) V — call after any scan."""
        self.run(np.zeros((2, 2), dtype=np.float64), dwell_time)


class SimulatedDAQOrchestrator:
    """Drop-in replacement for ``DAQOrchestrator`` that synthesises counts.

    Simulates a quadratic X-voltage response, matching the legacy
    ``simDaqDriver`` function.  Use for unit tests and offline development.
    """

    def run(
        self,
        voltages: NDArray[np.float64],
        dwell_time: float,  # noqa: ARG002
    ) -> NDArray[np.uint32]:
        n = voltages.shape[1]
        cumulative = 0.0
        counts = np.zeros(n, dtype=np.float64)
        for i in range(n):
            cumulative += float(voltages[0, i] ** 2)
            counts[i] = cumulative
        return counts.astype(np.uint32)

    def park(self, dwell_time: float = 0.01) -> None:  # noqa: ARG002
        pass
