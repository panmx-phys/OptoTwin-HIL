"""Example 03: Piezo Z-stack scan.

Steps the MDT piezo Y-axis (focus) through a voltage range while acquiring
a 2-D confocal image at each depth. Saves the stack as a .npy file and
exports an animated GIF.

Usage (with hardware attached):
    python examples/03_z_stack.py
"""

from __future__ import annotations

import time

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from optotwin.core.config import ScanConfig
from optotwin.hal.daq import DAQOrchestrator
from optotwin.hal.piezo import PiezoStage
from optotwin.trajectory.raster import raster_voltages, reconstruct_image

# --- Configuration -------------------------------------------------------
config = ScanConfig(
    x_px=50,
    y_px=50,
    xlims=(-0.5, 0.5),
    ylims=(-0.5, 0.5),
    dwell_time=0.001,
    accumulation=1,
)

PIEZO_START   = 30.0   # volts
PIEZO_STOP    = 35.0   # volts
PIEZO_STEPS   = 30
SETTLE_TIME_S = 1.0    # seconds to wait after each piezo move

# --- Build trajectory (once) --------------------------------------------
voltages = raster_voltages(config.x_px, config.y_px, config.xlims, config.ylims)
z_positions = np.linspace(PIEZO_START, PIEZO_STOP, PIEZO_STEPS)
stack = np.zeros((PIEZO_STEPS, config.y_px, config.x_px))

# --- Acquire -------------------------------------------------------------
with PiezoStage() as piezo, \
     DAQOrchestrator() as daq:

    for i, z_v in enumerate(z_positions):
        piezo.set_y_voltage(z_v)
        time.sleep(SETTLE_TIME_S)

        raw = daq.run(voltages, config.dwell_time)
        stack[i] = reconstruct_image(raw, config.x_px, config.y_px)
        print(f"Z step {i+1}/{PIEZO_STEPS}  piezo={z_v:.2f} V  "
              f"peak={stack[i].max():.0f} cts")

    daq.park()

# --- Save ----------------------------------------------------------------
np.save("data/z_stack.npy", stack)
print("Saved data/z_stack.npy")

# --- Animate -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(5, 5))
im = ax.imshow(stack[0], cmap="hot", origin="lower", aspect="auto")
title = ax.set_title("")

def update(frame):
    im.set_data(stack[frame])
    im.set_clim(0, stack[frame].max() or 1)
    title.set_text(f"Z = {z_positions[frame]:.2f} V  (frame {frame+1}/{PIEZO_STEPS})")
    return im, title

anim = FuncAnimation(fig, update, frames=PIEZO_STEPS, interval=100, blit=True)
anim.save("data/z_stack.gif", fps=10)
plt.show()
