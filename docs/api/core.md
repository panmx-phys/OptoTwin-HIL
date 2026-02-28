# Core API Reference

`optotwin.core` -- Configuration dataclasses, coordinate transforms, abstract base classes, utilities, and the metrology supervisor state machine.

```python
from optotwin.core import (
    AffineTransform2D,
    MetrologySupervisor, SupervisorConfig, State,
    ScanConfig, DualAreaScanConfig,
    calculate_square_pixels, make_config_square, print_scan_time, rect_to_lims,
)
```

---

## Abstract Base Classes

**Module:** `optotwin.core.abc`

### `Scanner` (ABC)

Interface for any device that positions the excitation beam.

| Method | Signature | Description |
|--------|-----------|-------------|
| `write_voltages` | `(voltages: NDArray[np.float64]) -> None` | Write (N, 2) array of (u, v) galvo samples |
| `close` | `() -> None` | Release hardware resources |

### `Detector` (ABC)

Interface for photon-counting or analog detectors.

| Method | Signature | Description |
|--------|-----------|-------------|
| `read_counts` | `(n_samples: int) -> NDArray[np.uint32]` | Return (N,) array of counts |
| `close` | `() -> None` | Release hardware resources |

---

## Coordinate Transforms

**Module:** `optotwin.core.transforms`

### `AffineTransform2D`

2-D affine coordinate mapping between physical (x, y) and actuator (u, v) spaces.

#### Constructor

```python
AffineTransform2D(matrix: ArrayLike | None = None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `matrix` | `ArrayLike \| None` | `None` | 3x3 homogeneous transform matrix. `None` = identity. |

Raises `ValueError` if matrix is not shape (3, 3).

#### Class Methods

```python
@classmethod
AffineTransform2D.from_scale_offset(
    scale_x: float,
    scale_y: float,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> AffineTransform2D
```

Factory for diagonal scaling + offset transforms:

```
| scale_x   0      offset_x |
|   0     scale_y  offset_y |
|   0       0         1     |
```

#### Instance Methods

```python
def forward(xy: ArrayLike) -> np.ndarray
```

Map physical (x, y) to actuator (u, v). Input shape `(..., 2)`.

```python
def inverse(uv: ArrayLike) -> np.ndarray
```

Map actuator (u, v) to physical (x, y). Input shape `(..., 2)`.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `matrix` | `np.ndarray` | Copy of the 3x3 transformation matrix |

#### Example

```python
t = AffineTransform2D.from_scale_offset(2.0, -1.5, offset_x=0.1)
uv = t.forward([1.0, 2.0])   # [2.1, -3.0]
xy = t.inverse(uv)            # [1.0, 2.0]  (round-trip)
```

---

## Configuration

**Module:** `optotwin.core.config`

### `ScanConfig`

Dataclass for single-area 2-D raster scan parameters.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x_px` | `int` | -- | Horizontal pixel count |
| `y_px` | `int` | -- | Vertical pixel count |
| `xlims` | `tuple[float, float]` | -- | X-axis voltage range (start, stop) |
| `ylims` | `tuple[float, float]` | -- | Y-axis voltage range (start, stop) |
| `dwell_time` | `float` | -- | Seconds per pixel |
| `accumulation` | `int` | `1` | Number of full-frame passes |
| `nd_filters` | `list[int]` | `[]` | ND filter indices (metadata) |
| `experiment_name` | `str` | `""` | QCoDeS experiment label |
| `sample_name` | `str` | `""` | QCoDeS sample label |
| `measurement_name` | `str` | `""` | QCoDeS measurement label |
| `comment` | `str` | `""` | Free-form annotation |

#### Computed Properties

| Property | Type | Description |
|----------|------|-------------|
| `n_pixels` | `int` | `x_px * y_px` |
| `frame_time_s` | `float` | `n_pixels * dwell_time` |
| `total_time_s` | `float` | `frame_time_s * accumulation` |

#### Example

```python
cfg = ScanConfig(
    x_px=200, y_px=200,
    xlims=(-2.0, 2.0), ylims=(-2.0, 2.0),
    dwell_time=0.5e-3,
    accumulation=4,
)
print(cfg)
# ScanConfig(200x200 px, dwell=0.50 ms, acc=4, total=80.00 s)
```

---

### `DualAreaScanConfig`

Dataclass for two-area interlaced raster scan parameters.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `px1` | `tuple[int, int]` | (x_px, y_px) for region 1 |
| `px2` | `tuple[int, int]` | (x_px, y_px) for region 2 |
| `xlims1`, `ylims1` | `tuple[float, float]` | Voltage ranges for region 1 |
| `xlims2`, `ylims2` | `tuple[float, float]` | Voltage ranges for region 2 |
| `dwell_time` | `float` | Seconds per pixel |
| `nd_filters` | `list[int]` | ND filter indices (metadata) |
| `experiment_name`, `sample_name`, `measurement_name`, `comment` | `str` | Labels |

---

## Utilities

**Module:** `optotwin.core.utils`

### `calculate_square_pixels`

```python
def calculate_square_pixels(
    xlims: tuple[float, float],
    ylims: tuple[float, float],
    base_px: int = 100,
) -> tuple[int, int]
```

Compute (x_px, y_px) that preserves the physical aspect ratio. The longer axis gets `base_px` pixels; the shorter axis is scaled proportionally.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `xlims` | `tuple[float, float]` | -- | X-axis voltage range |
| `ylims` | `tuple[float, float]` | -- | Y-axis voltage range |
| `base_px` | `int` | `100` | Pixel count for the longer axis |

**Returns:** `(x_px, y_px)`

---

### `make_config_square`

```python
def make_config_square(config: ScanConfig, base_px: int = 100) -> ScanConfig
```

Modify a `ScanConfig` so its pixel counts match the aspect ratio of its voltage ranges. Returns the modified config.

---

### `print_scan_time`

```python
def print_scan_time(config: ScanConfig, multiplier: int = 1) -> None
```

Print total and per-frame scan times to stdout.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `ScanConfig` | -- | Scan configuration |
| `multiplier` | `int` | `1` | Scale factor (e.g., number of laser setpoints) |

---

### `rect_to_lims`

```python
def rect_to_lims(
    rect: tuple[tuple[float, float], tuple[float, float]],
    config: ScanConfig,
) -> ScanConfig
```

Set `config.xlims` and `config.ylims` from rectangle corner coordinates.

| Parameter | Type | Description |
|-----------|------|-------------|
| `rect` | `((x1, y1), (x2, y2))` | Two corners of a rectangle in voltage space |
| `config` | `ScanConfig` | Config to modify |

**Returns:** Modified config with updated limits.

---

## Metrology Supervisor

**Module:** `optotwin.core.supervisor`

### `State` (Enum)

```python
class State(enum.Enum):
    IDLE = "idle"
    ACQUIRING = "acquiring"
    FITTING = "fitting"
    LOCKED = "locked"
    FAULT = "fault"
```

### `SupervisorConfig`

```python
@dataclass
class SupervisorConfig:
    max_retries: int = 3
    interlock_volts: float = 9.5
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_retries` | `int` | `3` | Max retry attempts before fault |
| `interlock_volts` | `float` | `9.5` | Hard stop if \|voltage\| exceeds this |

### `MetrologySupervisor`

Async state machine that sequences trajectory, acquisition, and fitting stages.

#### Constructor

```python
MetrologySupervisor(config: SupervisorConfig | None = None)
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `state` | `State` | Current supervisor state |

#### Methods

```python
def on_state_change(cb: Callable[[State], None]) -> None
```

Register a callback invoked on every state transition.

```python
async def run_sweep(
    acquire_fn: Callable[[], tuple],
    fit_fn: Callable[[tuple], dict],
) -> dict
```

Execute an acquire-then-fit cycle:

1. Transition to `ACQUIRING`, call `acquire_fn()` in a thread
2. Transition to `FITTING`, call `fit_fn(raw_data)` in a thread
3. Return the fit results dict
4. On success: return to `IDLE`
5. On error: transition to `FAULT`, re-raise the exception

#### Example

```python
import asyncio

supervisor = MetrologySupervisor()
supervisor.on_state_change(lambda s: print(f"State: {s.value}"))

async def main():
    result = await supervisor.run_sweep(
        acquire_fn=lambda: (positions, counts),
        fit_fn=lambda raw: {"x0": fit_edge(*raw).x0},
    )
    print(result)

asyncio.run(main())
```
