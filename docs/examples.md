# Examples & Tutorials

All example scripts are in the `examples/` directory. They demonstrate end-to-end workflows from configuration to image display.

---

## 01 — Single-Area Confocal Scan

**Script:** `examples/01_confocal_scan.py`

A standard 2-D raster confocal scan with image reconstruction and display.

### What it does

1. Creates a `ScanConfig` (100x100 pixels, ±1 V, 1 ms dwell)
2. Generates bidirectional raster voltages
3. Acquires photon counts via `DAQOrchestrator` (or simulated)
4. Reconstructs a 2-D image
5. Displays with matplotlib (`hot` colormap)

### Running

```bash
# With real hardware
python examples/01_confocal_scan.py

# Simulated (no DAQ needed)
OT_SIMULATE=1 python examples/01_confocal_scan.py
```

### Key concepts demonstrated

- `ScanConfig` for parameter management
- `raster_voltages()` for trajectory generation
- `reconstruct_image()` for bidirectional unflip + differentiation
- Environment-variable hardware switching

### Customising

Edit the `ScanConfig` at the top of the script:

```python
cfg = ScanConfig(
    x_px=200, y_px=200,           # higher resolution
    xlims=(-0.5, 0.5),            # narrower FOV
    ylims=(-0.5, 0.5),
    dwell_time=2e-3,              # longer integration
    accumulation=4,               # 4 accumulated frames
)
```

---

## 02 — Dual-Area Interlaced Scan

**Script:** `examples/02_dual_area_scan.py`

Simultaneous acquisition of two spatially separated regions for drift compensation.

### What it does

1. Defines two regions with `DualAreaScanConfig`:
   - Region 1 (signal): the area of interest
   - Region 2 (reference): a stable reference feature
2. Generates interleaved voltage pattern (`[A A B B A A B B ...]`)
3. Acquires in a single continuous DAQ run
4. Deinterleaves and reconstructs both images
5. Displays side-by-side: signal, reference, and differential mean

### Running

```bash
OT_SIMULATE=1 python examples/02_dual_area_scan.py
```

### Key concepts demonstrated

- `DualAreaScanConfig` for multi-region parameters
- `interleaved_dual_raster()` for temporal interleaving
- `reconstruct_dual_images()` for deinterleaving
- Drift compensation by subtracting reference from signal

### Why interlacing?

By rapidly alternating between signal and reference positions, both regions experience the same thermal drift, vibration, and laser power fluctuations. The differential signal cancels common-mode noise.

---

## 03 — Z-Stack (Focus Sweep)

**Script:** `examples/03_z_stack.py`

3-D volumetric imaging by stepping the piezo focus stage through a range of depths.

### What it does

1. Connects to the Thorlabs MDT piezo stage
2. Steps Y-axis voltage (which controls focus) through a defined range
3. At each depth, acquires a full 2-D raster image
4. Stacks all images into a 3-D array `(n_depths, y_px, x_px)`
5. Saves as `.npy` file
6. Exports an animated GIF using `matplotlib.animation.FuncAnimation`

### Running

```bash
# Requires real hardware (piezo + DAQ)
python examples/03_z_stack.py
```

> This example does not support simulation mode because it requires a physical piezo stage.

### Key concepts demonstrated

- `PiezoStage` context manager for safe hardware access
- Nested loop: outer = depth, inner = 2-D raster
- 3-D data management with NumPy
- Animation export

### Output

- `z_stack.npy` -- raw 3-D array
- `z_stack.gif` -- animated depth sweep

---

## Debug GUI

**Script:** `examples/debug_gui.py`

Interactive diagnostic dashboard built with DearPyGUI.

### Prerequisites

```bash
pip install -e ".[gui]"
```

### Features

| Panel | Description |
|-------|-------------|
| **Hardware Toggle** | Switch between real DAQ and simulated mode |
| **Scan Config** | Adjust X/Y pixels, voltage limits, dwell time, accumulation |
| **Image Display** | Live raster scan result with colormap and auto-scaling |
| **Raw Counts** | Per-pixel count histogram |
| **Laser Controls** | TEC on/off, output on/off, current setpoint |
| **Piezo Controls** | Y voltage set/read (focus adjustment) |
| **Temperature** | Live Auber controller reading |
| **Log Console** | Real-time acquisition and diagnostic messages |
| **Save Dialog** | Export `.npy` or `.png` |

### Running

```bash
python examples/debug_gui.py
```

### Architecture

- `AppState` dataclass tracks GUI state and hardware handles
- Acquisition runs in a daemon thread (non-blocking UI)
- DearPyGUI render loop calls `_poll_hardware()` and `_frame_update()` per frame
- Graceful fallback: if hardware initialisation fails, the GUI switches to simulation mode automatically

---

## Common Patterns

### Choosing real vs. simulated hardware

All examples follow this pattern:

```python
import os
from optotwin.hal import DAQOrchestrator, SimulatedDAQOrchestrator

if os.environ.get("OT_SIMULATE"):
    daq = SimulatedDAQOrchestrator()
else:
    daq = DAQOrchestrator()
```

### Override DAQ channels via environment

```bash
OT_AO_X=Dev2/ao0 OT_AO_Y=Dev2/ao1 OT_CI=Dev2/ctr0 python examples/01_confocal_scan.py
```

### Accumulation (frame averaging)

Multiple passes improve SNR at the cost of time:

```python
cfg = ScanConfig(x_px=100, y_px=100,
                 xlims=(-1, 1), ylims=(-1, 1),
                 dwell_time=1e-3,
                 accumulation=8)  # 8 frames

voltages = raster_voltages(cfg.x_px, cfg.y_px, cfg.xlims, cfg.ylims,
                           accumulation=cfg.accumulation)
counts = daq.run(voltages, cfg.dwell_time)
stack = reconstruct_image(counts, cfg.x_px, cfg.y_px, cfg.accumulation)
# stack.shape == (8, 100, 100) -- average with stack.mean(axis=0)
```

### Aspect-ratio-correct pixels

```python
from optotwin.core import ScanConfig, calculate_square_pixels, make_config_square

cfg = ScanConfig(x_px=100, y_px=100,
                 xlims=(-2, 2), ylims=(-1, 1),
                 dwell_time=1e-3)
cfg = make_config_square(cfg, base_px=200)
# cfg.x_px == 200, cfg.y_px == 100 (2:1 aspect ratio preserved)
```
