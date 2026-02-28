# Getting Started

## Prerequisites

- **Python >= 3.11**
- **pip** (or any PEP 621-compatible installer)
- **NI-DAQmx driver** -- required only for real hardware; simulation mode works without it

## Installation

### Basic install (editable mode)

```bash
git clone <repo-url> OptoTwin-HIL
cd OptoTwin-HIL
pip install -e "."
```

### With development tools (pytest, pytest-asyncio, matplotlib)

```bash
pip install -e ".[dev]"
```

### Optional extras

| Extra | What it adds | Install command |
|-------|-------------|-----------------|
| `dev` | pytest, pytest-asyncio, matplotlib | `pip install -e ".[dev]"` |
| `qcodes` | QCoDeS measurement database integration | `pip install -e ".[qcodes]"` |
| `jax` | JAX backend for optimizer (GPU-accelerated fitting) | `pip install -e ".[jax]"` |
| `gui` | DearPyGUI diagnostic dashboard | `pip install -e ".[gui]"` |

### Runtime dependencies (installed automatically)

| Package | Purpose |
|---------|---------|
| `numpy >= 1.26` | Array computation |
| `scipy >= 1.13` | Curve fitting, special functions |
| `xarray >= 2024.1` | Labelled N-D arrays |
| `matplotlib >= 3.8` | Plotting |
| `nidaqmx >= 0.9` | NI DAQ hardware communication |
| `pyvisa >= 1.13` | VISA instrument control (laser) |
| `minimalmodbus >= 2.1` | ModBus RTU (temperature controller) |

---

## Running Tests

All tests are hardware-agnostic and run without physical instruments:

```bash
pytest
```

Expected output: all tests in `tests/` pass, covering transforms, trajectories, raster reconstruction, and digital twin fitting.

---

## Your First Scan (Simulated)

Run a full 2-D confocal raster scan using the simulated DAQ:

```bash
OT_SIMULATE=1 python examples/01_confocal_scan.py
```

This will:
1. Generate a 100x100 bidirectional raster voltage pattern
2. Acquire simulated photon counts (quadratic X-voltage response)
3. Reconstruct and display the image with matplotlib

### Your first scan in code

```python
from optotwin.core import ScanConfig
from optotwin.hal import SimulatedDAQOrchestrator
from optotwin.trajectory import raster_voltages, reconstruct_image
import matplotlib.pyplot as plt

# 1. Configure
cfg = ScanConfig(x_px=100, y_px=100,
                 xlims=(-1.0, 1.0), ylims=(-1.0, 1.0),
                 dwell_time=1e-3)

# 2. Generate trajectory
voltages = raster_voltages(cfg.x_px, cfg.y_px, cfg.xlims, cfg.ylims)

# 3. Acquire
daq = SimulatedDAQOrchestrator()
counts = daq.run(voltages, cfg.dwell_time)

# 4. Reconstruct
image = reconstruct_image(counts, cfg.x_px, cfg.y_px)

# 5. Display
plt.imshow(image, cmap="hot", origin="lower")
plt.colorbar(label="Counts")
plt.title("Simulated Confocal Scan")
plt.show()
```

---

## Your First Scan (Real Hardware)

With a NI USB-6421 connected and the NI-DAQmx driver installed:

```python
from optotwin.core import ScanConfig
from optotwin.hal import DAQOrchestrator
from optotwin.trajectory import raster_voltages, reconstruct_image

cfg = ScanConfig(x_px=100, y_px=100,
                 xlims=(-1.0, 1.0), ylims=(-1.0, 1.0),
                 dwell_time=1e-3)

voltages = raster_voltages(cfg.x_px, cfg.y_px, cfg.xlims, cfg.ylims)

# Real hardware -- default channels: Dev1/ao0, Dev1/ao1, Dev1/ctr0
daq = DAQOrchestrator()
counts = daq.run(voltages, cfg.dwell_time)
daq.park()  # return galvos to (0, 0)

image = reconstruct_image(counts, cfg.x_px, cfg.y_px)
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OT_SIMULATE` | unset | Set to `1` to use `SimulatedDAQOrchestrator` in examples |
| `OT_AO_X` | `Dev1/ao0` | Override X-galvo analog output channel |
| `OT_AO_Y` | `Dev1/ao1` | Override Y-galvo analog output channel |
| `OT_CI` | `Dev1/ctr0` | Override counter input channel |

---

## Next Steps

- [Architecture](architecture.md) -- understand the module design
- [API Reference](api/core.md) -- detailed class and function docs
- [Examples](examples.md) -- walkthrough of all included scripts
- [Hardware Setup](hardware.md) -- wiring and instrument configuration
