# Trajectory API Reference

`optotwin.trajectory` -- Pure-NumPy geometric path generators for galvo-scanned microscopy.

All functions in this module are hardware-agnostic. They produce voltage arrays consumed by `DAQOrchestrator.run()`.

```python
from optotwin.trajectory import (
    raster_voltages,
    reconstruct_image,
    interleaved_dual_raster,
    reconstruct_dual_images,
    linspace_sweep,
    sparse_spiral,
    extremum_dither,
)
```

---

## Raster Scanning

**Module:** `optotwin.trajectory.raster`

### `raster_voltages`

```python
def raster_voltages(
    x_px: int,
    y_px: int,
    xlims: tuple[float, float],
    ylims: tuple[float, float],
    accumulation: int = 1,
) -> NDArray[np.float64]
```

Generate a bidirectional (meandering) raster scan voltage pattern.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x_px` | `int` | -- | Pixels per row (horizontal resolution) |
| `y_px` | `int` | -- | Number of rows (vertical resolution) |
| `xlims` | `tuple[float, float]` | -- | X-axis voltage range (start, stop) |
| `ylims` | `tuple[float, float]` | -- | Y-axis voltage range (start, stop) |
| `accumulation` | `int` | `1` | Number of full-frame passes |

**Returns:** `NDArray[np.float64]` of shape `(2, x_px * y_px * accumulation)`
- Row 0: X voltages
- Row 1: Y voltages

**Scan pattern:**

```
Row 0:  ────────────►   (left to right)
Row 1:  ◄────────────   (right to left)
Row 2:  ────────────►
Row 3:  ◄────────────
        ...
```

For `accumulation > 1`, alternate frames are reversed so the beam always parks near its final position rather than flying back to the start.

#### Example

```python
voltages = raster_voltages(
    x_px=100, y_px=100,
    xlims=(-1.0, 1.0), ylims=(-1.0, 1.0),
    accumulation=4,
)
# voltages.shape == (2, 40000)
```

---

### `reconstruct_image`

```python
def reconstruct_image(
    cumulative_counts: NDArray[np.uint32],
    x_px: int,
    y_px: int,
    accumulation: int = 1,
) -> NDArray[np.float64]
```

Convert raw cumulative DAQ counts into a 2-D (or 3-D) image array.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cumulative_counts` | `NDArray[np.uint32]` | -- | Raw output from `DAQOrchestrator.run()` |
| `x_px` | `int` | -- | Pixels per row |
| `y_px` | `int` | -- | Number of rows |
| `accumulation` | `int` | `1` | Number of accumulated frames |

**Returns:**
- Single frame (`accumulation=1`): `NDArray[np.float64]` of shape `(y_px, x_px)`
- Multi-frame (`accumulation>1`): `NDArray[np.float64]` of shape `(accumulation, y_px, x_px)`

**Reconstruction steps:**
1. Differentiate cumulative counts to get per-pixel counts
2. Reshape into (y_px, x_px) per frame
3. Reverse odd rows to undo bidirectional flip
4. Zero the first pixel (counter initialisation artefact)

#### Example

```python
from optotwin.hal import SimulatedDAQOrchestrator
from optotwin.trajectory import raster_voltages, reconstruct_image

voltages = raster_voltages(100, 100, (-1, 1), (-1, 1))
counts = SimulatedDAQOrchestrator().run(voltages, 1e-3)
image = reconstruct_image(counts, 100, 100)
# image.shape == (100, 100)
```

---

### `interleaved_dual_raster`

```python
def interleaved_dual_raster(
    px1: tuple[int, int],
    px2: tuple[int, int],
    xlims1: tuple[float, float],
    ylims1: tuple[float, float],
    xlims2: tuple[float, float],
    ylims2: tuple[float, float],
) -> NDArray[np.float64]
```

Generate a voltage array that interleaves two raster scan regions for simultaneous signal + reference acquisition.

| Parameter | Type | Description |
|-----------|------|-------------|
| `px1` | `(int, int)` | (x_px, y_px) for region 1 (signal) |
| `px2` | `(int, int)` | (x_px, y_px) for region 2 (reference) |
| `xlims1`, `ylims1` | `(float, float)` | Voltage ranges for region 1 |
| `xlims2`, `ylims2` | `(float, float)` | Voltage ranges for region 2 |

**Returns:** `NDArray[np.float64]` of shape `(2, 4 * px1[0]*px1[1] + 1)`

**Interleave pattern:** `[A A B B A A B B ...]` with a trailing `(0, 0)` park sample.

This pattern allows drift compensation by comparing signal and reference regions acquired under near-identical conditions.

---

### `reconstruct_dual_images`

```python
def reconstruct_dual_images(
    cumulative_counts: NDArray[np.uint32],
    px1: tuple[int, int],
    px2: tuple[int, int],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]
```

Deinterleave and reconstruct two images from a dual-area acquisition.

| Parameter | Type | Description |
|-----------|------|-------------|
| `cumulative_counts` | `NDArray[np.uint32]` | Raw output from `DAQOrchestrator.run()` |
| `px1` | `(int, int)` | (x_px, y_px) for region 1 |
| `px2` | `(int, int)` | (x_px, y_px) for region 2 |

**Returns:** `(image1, image2)` -- two `NDArray[np.float64]` with shapes `(px1[1], px1[0])` and `(px2[1], px2[0])`.

**Reconstruction steps:**
1. Drop trailing park sample
2. Differentiate cumulative counts
3. Extract region 1 pixels at indices `[1::4]`, region 2 at `[3::4]`
4. Reshape and un-flip each region

---

## 1-D Sweeps

**Module:** `optotwin.trajectory.sweep`

### `linspace_sweep`

```python
def linspace_sweep(
    start: float,
    stop: float,
    n_points: int,
    axis: int = 0,
    fixed_voltage: float = 0.0,
) -> NDArray[np.float64]
```

Generate a 1-D linear voltage sweep along one galvo axis.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start` | `float` | -- | Start voltage |
| `stop` | `float` | -- | End voltage |
| `n_points` | `int` | -- | Number of samples |
| `axis` | `int` | `0` | Sweep axis: `0` = X, `1` = Y |
| `fixed_voltage` | `float` | `0.0` | Voltage on the stationary axis |

**Returns:** `NDArray[np.float64]` of shape `(n_points, 2)` -- columns are (X, Y).

#### Example

```python
# Sweep X from -2V to +2V, Y fixed at 0V
sweep = linspace_sweep(-2.0, 2.0, 500, axis=0)
# sweep.shape == (500, 2)
# sweep[:, 0] varies from -2 to +2
# sweep[:, 1] == 0.0
```

---

## Spiral Patterns

**Module:** `optotwin.trajectory.spiral`

### `sparse_spiral`

```python
def sparse_spiral(
    r_max: float,
    n_turns: int,
    n_points: int,
    center: tuple[float, float] = (0.0, 0.0),
) -> NDArray[np.float64]
```

Generate an Archimedean spiral scan pattern.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `r_max` | `float` | -- | Maximum radius in volts |
| `n_turns` | `int` | -- | Number of full revolutions |
| `n_points` | `int` | -- | Total sample count |
| `center` | `(float, float)` | `(0.0, 0.0)` | Centre voltage (u, v) |

**Returns:** `NDArray[np.float64]` of shape `(n_points, 2)`.

**Formula:**

```
θ = linspace(0, 2π × n_turns, n_points)
r = r_max × θ / (2π × n_turns)
x = center[0] + r × cos(θ)
y = center[1] + r × sin(θ)
```

The spiral starts at the center and expands outward, which is useful for wide-field survey scans.

---

## Dither Signals

**Module:** `optotwin.trajectory.dither`

### `extremum_dither`

```python
def extremum_dither(
    center: float,
    amplitude: float,
    n_points: int,
    dither_freq_ratio: float = 0.1,
    axis: int = 0,
    fixed_voltage: float = 0.0,
) -> NDArray[np.float64]
```

Generate a sinusoidal dither signal for extremum-seeking closed-loop control (edge locking).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `center` | `float` | -- | Nominal operating voltage |
| `amplitude` | `float` | -- | Peak dither amplitude in volts |
| `n_points` | `int` | -- | Samples per dither cycle |
| `dither_freq_ratio` | `float` | `0.1` | Frequency as fraction of sample rate (0 < f < 0.5) |
| `axis` | `int` | `0` | Dither axis: `0` = X, `1` = Y |
| `fixed_voltage` | `float` | `0.0` | Voltage on the stationary axis |

**Returns:** `NDArray[np.float64]` of shape `(n_points, 2)`.

**Formula:**

```
dither[t] = center + amplitude × sin(2π × dither_freq_ratio × t)
```

Demodulating the detector response at the dither frequency yields the slope of the signal, enabling lock-in detection of feature edges.
