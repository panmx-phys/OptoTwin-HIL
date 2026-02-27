"""Example 02: Closed-loop gradient-based edge locking.

Initiates the Metrology Supervisor in continuous dither-lock mode.
The supervisor repeatedly measures the edge position and feeds corrections
back to the galvo centre voltage via a simple proportional controller.

Usage (with hardware attached):
    python examples/02_active_tracking.py

Press Ctrl-C to stop.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import numpy as np

from optotwin.core.supervisor import MetrologySupervisor, SupervisorConfig
from optotwin.hal.daq import DAQOrchestrator
from optotwin.trajectory import linspace_sweep
from optotwin.twin.optimizer import fit_edge

# --- Configuration -------------------------------------------------------
AO_CHANNEL   = os.getenv("OT_AO_CHANNEL",  "Dev1/ao0:1")
CI_CHANNEL   = os.getenv("OT_CI_CHANNEL",  "Dev1/ctr0")
SAMPLE_RATE  = float(os.getenv("OT_SAMPLE_RATE", "10000"))

SWEEP_HALF_RANGE = 0.5   # volts around current centre
N_POINTS         = 200
KP               = 0.3   # proportional gain

_running = True


def _stop(*_):
    global _running
    _running = False
    print("\nStopping...")


signal.signal(signal.SIGINT, _stop)


async def tracking_loop(daq: DAQOrchestrator) -> None:
    config = SupervisorConfig(interlock_volts=9.5)
    supervisor = MetrologySupervisor(config)

    centre = 0.0

    while _running:
        sweep_start = centre - SWEEP_HALF_RANGE
        sweep_stop  = centre + SWEEP_HALF_RANGE
        voltages = linspace_sweep(sweep_start, sweep_stop, N_POINTS, axis=0)
        positions = voltages[:, 0]

        def acquire():
            return positions, daq.run(voltages)

        def fit(raw):
            pos, counts = raw
            return fit_edge(pos, counts)

        result = await supervisor.run_sweep(acquire, fit)

        error = result.x0 - centre
        centre -= KP * error
        print(
            f"edge={result.x0:+.4f} V  error={error:+.4f} V  "
            f"centre→{centre:+.4f} V  σ={result.sigma*1e3:.1f} mV"
        )

        await asyncio.sleep(0.05)


def main() -> None:
    with DAQOrchestrator(AO_CHANNEL, CI_CHANNEL, SAMPLE_RATE) as daq:
        asyncio.run(tracking_loop(daq))


if __name__ == "__main__":
    main()
