"""Example 01: Knife-edge diagnostic sweep.

Executes a 1-D voltage sweep across an edge and fits the Gaussian step-edge
model to verify SMF coupling symmetry and measure the beam waist.

Usage (with hardware attached):
    python examples/01_knife_edge_diag.py

Environment variables (optional):
    OT_AO_CHANNEL   e.g. Dev1/ao0:1  (default: Dev1/ao0:1)
    OT_CI_CHANNEL   e.g. Dev1/ctr0   (default: Dev1/ctr0)
    OT_SAMPLE_RATE  e.g. 5000        (default: 10000)
"""

from __future__ import annotations

import os

import numpy as np
import matplotlib.pyplot as plt

from optotwin.core.transforms import AffineTransform2D
from optotwin.hal.daq import DAQOrchestrator
from optotwin.trajectory import linspace_sweep
from optotwin.twin.optimizer import fit_edge

# --- Configuration -------------------------------------------------------
AO_CHANNEL  = os.getenv("OT_AO_CHANNEL",  "Dev1/ao0:1")
CI_CHANNEL  = os.getenv("OT_CI_CHANNEL",  "Dev1/ctr0")
SAMPLE_RATE = float(os.getenv("OT_SAMPLE_RATE", "10000"))

SWEEP_START  = -2.0   # volts
SWEEP_STOP   =  2.0   # volts
N_POINTS     = 500

# --- Build trajectory (no hardware needed yet) ---------------------------
voltages = linspace_sweep(SWEEP_START, SWEEP_STOP, N_POINTS, axis=0)

# --- Acquire (requires NI DAQ) -------------------------------------------
with DAQOrchestrator(AO_CHANNEL, CI_CHANNEL, SAMPLE_RATE) as daq:
    counts = daq.run(voltages)

positions = voltages[:, 0]

# --- Fit -----------------------------------------------------------------
result = fit_edge(positions, counts)
print(f"Edge position : {result.x0:.4f} V")
print(f"Beam radius   : {result.sigma*1e3:.1f} mV  (σ)")
print(f"Residual RMS  : {result.residual_rms:.2f} counts")

# --- Plot -----------------------------------------------------------------
x_fit = np.linspace(positions.min(), positions.max(), 1000)
from optotwin.twin.models import gaussian_step_edge
y_fit = gaussian_step_edge(x_fit, result.x0, result.sigma, result.i_low, result.i_high)

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(positions, counts, ".", ms=3, label="measured")
ax.plot(x_fit, y_fit, "-", lw=2, label=f"fit  σ={result.sigma*1e3:.1f} mV")
ax.axvline(result.x0, ls="--", c="grey", label=f"x₀={result.x0:.3f} V")
ax.set_xlabel("Galvo X voltage (V)")
ax.set_ylabel("Photon counts")
ax.set_title("Knife-edge diagnostic")
ax.legend()
plt.tight_layout()
plt.show()
