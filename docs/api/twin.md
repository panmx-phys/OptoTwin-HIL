# Twin API Reference

`optotwin.twin` -- Digital twin forward models and curve fitting for confocal beam metrology.

```python
from optotwin.twin import gaussian_step_edge, fit_edge, EdgeFitResult
```

---

## Physical Models

**Module:** `optotwin.twin.models`

### `gaussian_step_edge`

```python
def gaussian_step_edge(
    x: ArrayLike,
    x0: float,
    sigma: float,
    i_low: float,
    i_high: float,
) -> NDArray[np.float64]
```

Gaussian-convolved step-edge (knife-edge) intensity response model.

This models the signal observed when a focused Gaussian beam of width `sigma` sweeps across an absorbing edge located at position `x0`. It is the standard model for beam profiling via the knife-edge technique.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | `ArrayLike` | Position array (volts or physical units) |
| `x0` | `float` | Edge position |
| `sigma` | `float` | 1/e² Gaussian beam radius (beam waist) |
| `i_low` | `float` | Background intensity (fully occluded) |
| `i_high` | `float` | Peak intensity (fully unoccluded) |

**Returns:** `NDArray[np.float64]` with same shape as `x`.

**Formula:**

```
I(x) = (I_high - I_low) / 2 × [1 + erf((x - x0) / (√2 × σ))] + I_low
```

**Physical interpretation:**

| Region | Value | Meaning |
|--------|-------|---------|
| x << x0 | ≈ I_low | Beam fully blocked by edge |
| x = x0 | (I_high + I_low) / 2 | Beam half-occluded (midpoint) |
| x >> x0 | ≈ I_high | Beam fully passes edge |

The transition width is governed by `sigma`: a tighter beam produces a sharper step.

#### Example

```python
import numpy as np
from optotwin.twin import gaussian_step_edge

x = np.linspace(-5, 5, 1000)
intensity = gaussian_step_edge(x, x0=0.0, sigma=1.0, i_low=100, i_high=5000)

# At x=0: intensity ≈ 2550 (midpoint)
# At x=-5: intensity ≈ 100  (background)
# At x=+5: intensity ≈ 5000 (peak)
```

---

## Curve Fitting

**Module:** `optotwin.twin.optimizer`

### `EdgeFitResult`

```python
@dataclass
class EdgeFitResult:
    x0: float           # Fitted edge position
    sigma: float        # Fitted beam 1/e² radius
    i_low: float        # Fitted background level
    i_high: float       # Fitted peak level
    residual_rms: float # RMS of fit residuals
```

All fields are populated by `fit_edge()`.

---

### `fit_edge`

```python
def fit_edge(
    positions: ArrayLike,
    counts: ArrayLike,
    p0: tuple[float, float, float, float] | None = None,
) -> EdgeFitResult
```

Fit the `gaussian_step_edge` model to measured photon counts using nonlinear least-squares (`scipy.optimize.curve_fit`).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `positions` | `ArrayLike` | -- | 1-D scan positions (same units as voltage or physical coords) |
| `counts` | `ArrayLike` | -- | 1-D measured photon counts (same length as positions) |
| `p0` | `tuple \| None` | `None` | Initial guess `(x0, sigma, i_low, i_high)`. Auto-estimated if `None`. |

**Returns:** `EdgeFitResult` dataclass.

**Auto-estimation heuristic** (when `p0=None`):
- `x0` ≈ midpoint of position range
- `sigma` ≈ range / 10
- `i_low` ≈ min(counts)
- `i_high` ≈ max(counts)

#### Example

```python
import numpy as np
from optotwin.twin import gaussian_step_edge, fit_edge

# Generate synthetic data
x = np.linspace(-3, 3, 200)
true_signal = gaussian_step_edge(x, x0=0.5, sigma=0.8, i_low=50, i_high=4000)
noise = np.random.normal(0, 30, size=x.shape)
measured = true_signal + noise

# Fit
result = fit_edge(x, measured)

print(f"Edge position: {result.x0:.3f}")     # ≈ 0.500
print(f"Beam radius:   {result.sigma:.3f}")   # ≈ 0.800
print(f"Background:    {result.i_low:.1f}")    # ≈ 50.0
print(f"Peak:          {result.i_high:.1f}")   # ≈ 4000.0
print(f"Residual RMS:  {result.residual_rms:.2f}")
```

---

## Workflow: Beam Profiling

A complete knife-edge beam profiling measurement:

```python
from optotwin.core import ScanConfig
from optotwin.hal import DAQOrchestrator
from optotwin.trajectory import linspace_sweep
from optotwin.twin import fit_edge
import numpy as np

# 1. Generate 1-D sweep across the edge
sweep = linspace_sweep(start=-2.0, stop=2.0, n_points=500, axis=0)

# 2. Acquire
daq = DAQOrchestrator()
cumulative = daq.run(sweep.T, dwell_time=1e-3)  # transpose to (2, N)
daq.park()

# 3. Convert cumulative → per-pixel
counts = np.insert(np.diff(cumulative), 0, cumulative[0])
positions = sweep[:, 0]  # X voltages

# 4. Fit edge model
result = fit_edge(positions, counts)

print(f"Edge at:      {result.x0:.4f} V")
print(f"Beam waist:   {result.sigma:.4f} V")
print(f"Residual RMS: {result.residual_rms:.1f} counts")
```
