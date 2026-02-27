"""Example 01: Single-area confocal raster scan.

Performs a 2-D raster scan with the galvo mirrors, plots the result,
and optionally saves it with QCoDeS.

Usage (with hardware attached):
    python examples/01_confocal_scan.py

Set OT_SIMULATE=1 to run without hardware:
    OT_SIMULATE=1 python examples/01_confocal_scan.py
"""

from __future__ import annotations

import os

import matplotlib.pyplot as plt
import numpy as np

from optotwin.core.config import ScanConfig
from optotwin.core.utils import print_scan_time
from optotwin.trajectory.raster import raster_voltages, reconstruct_image

# --- Configuration -------------------------------------------------------
config = ScanConfig(
    x_px=100,
    y_px=100,
    xlims=(-1.0, 1.0),
    ylims=(-1.0, 1.0),
    dwell_time=0.001,          # 1 ms per pixel
    accumulation=1,
    experiment_name="ConfocalScan",
    sample_name="Sample",
    measurement_name="2D raster",
)

print(config)
print_scan_time(config)

# --- Choose real or simulated DAQ ----------------------------------------
if os.getenv("OT_SIMULATE", "0") == "1":
    from optotwin.hal.daq import SimulatedDAQOrchestrator
    daq = SimulatedDAQOrchestrator()
else:
    from optotwin.hal.daq import DAQOrchestrator
    daq = DAQOrchestrator(
        ao_x_channel=os.getenv("OT_AO_X", "Dev1/ao0"),
        ao_y_channel=os.getenv("OT_AO_Y", "Dev1/ao1"),
        ci_channel=os.getenv("OT_CI", "Dev1/ctr0"),
    )

# --- Build trajectory and acquire ----------------------------------------
voltages = raster_voltages(
    config.x_px, config.y_px, config.xlims, config.ylims, config.accumulation
)
raw_counts = daq.run(voltages, config.dwell_time)
daq.park()

image = reconstruct_image(raw_counts, config.x_px, config.y_px, config.accumulation)

# --- Display -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 6))
extent = [*config.xlims, *config.ylims]
im = ax.imshow(
    image,
    cmap="hot",
    origin="lower",
    extent=extent,
    aspect="auto",
)
plt.colorbar(im, ax=ax, label="Photon counts")
ax.set_xlabel("Galvo X (V)")
ax.set_ylabel("Galvo Y (V)")
ax.set_title(f"{config.measurement_name}  —  {config.sample_name}")
plt.tight_layout()
plt.show()
