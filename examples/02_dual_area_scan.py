"""Example 02: Two-area interlaced lock-in scan.

Simultaneously images two regions of the sample by interleaving their
raster patterns. Useful for differential measurements (signal vs. reference).

Usage (with hardware attached):
    python examples/02_dual_area_scan.py

Set OT_SIMULATE=1 to run without hardware:
    OT_SIMULATE=1 python examples/02_dual_area_scan.py
"""

from __future__ import annotations

import os

import matplotlib.pyplot as plt

from optotwin.core.config import DualAreaScanConfig
from optotwin.trajectory.raster import interleaved_dual_raster, reconstruct_dual_images

# --- Configuration -------------------------------------------------------
config = DualAreaScanConfig(
    px1=(30, 30),
    px2=(30, 30),
    xlims1=(0.01, 0.06),
    ylims1=(-0.07, -0.01),
    xlims2=(-0.07, -0.03),
    ylims2=(-0.04, 0.01),
    dwell_time=0.01,
    experiment_name="TwoAreaScan",
    sample_name="Sample",
    measurement_name="Signal vs Reference",
)

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
voltages = interleaved_dual_raster(
    config.px1, config.px2,
    config.xlims1, config.ylims1,
    config.xlims2, config.ylims2,
)
raw_counts = daq.run(voltages, config.dwell_time)
daq.park()

counts1, counts2 = reconstruct_dual_images(raw_counts, config.px1, config.px2)

# --- Display -------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(14, 4))

kw = dict(cmap="hot", origin="lower", aspect="auto")
im1 = axes[0].imshow(counts1, **kw)
axes[0].set_title("Region 1 (signal)")
plt.colorbar(im1, ax=axes[0], label="counts")

im2 = axes[1].imshow(counts2, **kw)
axes[1].set_title("Region 2 (reference)")
plt.colorbar(im2, ax=axes[1], label="counts")

diff = counts1.mean(axis=(0, 1)) - counts2.mean(axis=(0, 1))
axes[2].bar(["R1 mean", "R2 mean", "Δ"], [counts1.mean(), counts2.mean(), diff])
axes[2].set_ylabel("counts")
axes[2].set_title("Differential signal")

plt.suptitle(config.measurement_name)
plt.tight_layout()
plt.show()
