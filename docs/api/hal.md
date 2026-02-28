# HAL API Reference

`optotwin.hal` -- Hardware Abstraction Layer. DAQ orchestration, laser control, photodiode, piezo stage, and temperature controllers.

> **Import rule:** Only this module may import `nidaqmx`, `pyvisa`, or `minimalmodbus`. No other package in OptoTwin-HIL should depend on vendor drivers directly.

```python
from optotwin.hal import (
    DAQOrchestrator,
    SimulatedDAQOrchestrator,
    LaserDriver,
    PhotoDiode,
    PiezoStage,
    AuberController,
    ThermocoupleReader,
)
```

---

## DAQ Orchestration

**Module:** `optotwin.hal.daq`

### `DAQOrchestrator`

Hardware-timed galvo + SPAD acquisition using the NI USB-6421. The analog output (AO) sample clock is routed to the counter input (CI) for zero-latency synchronisation.

#### Constructor

```python
DAQOrchestrator(
    ao_x_channel: str = "Dev1/ao0",
    ao_y_channel: str = "Dev1/ao1",
    ci_channel: str = "Dev1/ctr0",
    pfi_terminal: str = "/Dev1/PFI0",
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ao_x_channel` | `str` | `"Dev1/ao0"` | Analog output channel for X galvo mirror |
| `ao_y_channel` | `str` | `"Dev1/ao1"` | Analog output channel for Y galvo mirror |
| `ci_channel` | `str` | `"Dev1/ctr0"` | Counter input channel for SPAD photon counter |
| `pfi_terminal` | `str` | `"/Dev1/PFI0"` | Physical terminal for photon pulse input |

#### Methods

```python
def run(
    voltages: NDArray[np.float64],
    dwell_time: float,
) -> NDArray[np.uint32]
```

Drive galvo mirrors and acquire photon counts in a single hardware-timed operation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `voltages` | `NDArray[np.float64]` | Shape `(2, N)` -- row 0 = X voltages, row 1 = Y voltages |
| `dwell_time` | `float` | Seconds per sample |

**Returns:** `NDArray[np.uint32]` of shape `(N,)` containing **cumulative** photon counts.

> **Important:** The returned counts are cumulative. To get per-pixel counts:
> ```python
> per_pixel = np.insert(np.diff(cumulative), 0, cumulative[0])
> ```
> The `reconstruct_image()` function handles this automatically.

**Hardware sequence:**
1. Create AO task with two channels (X, Y) and finite sample clock
2. Create CI task using AO sample clock as its timebase
3. Write voltage waveform, start both tasks synchronously
4. Wait for completion, read counter data
5. Clean up both tasks

```python
def park(dwell_time: float = 0.01) -> None
```

Return both galvo mirrors to (0, 0) V.

---

### `SimulatedDAQOrchestrator`

Drop-in replacement for `DAQOrchestrator` that requires no hardware. Generates synthetic photon counts using a quadratic X-voltage response model.

#### Methods

```python
def run(
    voltages: NDArray[np.float64],
    dwell_time: float,
) -> NDArray[np.uint32]
```

Same signature as `DAQOrchestrator.run()`. The `dwell_time` parameter is accepted but ignored.

**Simulation model:** Cumulative counts increase by `voltages[0, i]²` at each sample, producing a parabolic intensity pattern in X.

```python
def park(dwell_time: float = 0.01) -> None
```

No-op (no hardware to park).

#### Example

```python
from optotwin.hal import SimulatedDAQOrchestrator
import numpy as np

daq = SimulatedDAQOrchestrator()
voltages = np.array([
    np.linspace(-1, 1, 100),  # X
    np.zeros(100),             # Y
])
counts = daq.run(voltages, dwell_time=1e-3)
# counts is (100,) cumulative uint32 array
```

---

## Laser Driver

**Module:** `optotwin.hal.laser`

### `LaserDriver`

VISA wrapper for the Coherent CLD1015 diode laser controller.

#### Constructor

```python
LaserDriver(resource: object)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `resource` | pyvisa Resource | Open VISA resource handle |

> Prefer the `connect()` class method for typical usage.

#### Class Methods

```python
@classmethod
LaserDriver.connect(
    serial: str = "M00959058",
    resource_manager: object | None = None,
) -> LaserDriver
```

Auto-discover and open the laser by USB serial number.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `serial` | `str` | `"M00959058"` | USB instrument serial number |
| `resource_manager` | `object \| None` | `None` | Existing pyvisa ResourceManager (creates one if None) |

#### Temperature Control

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_temp` | `() -> float` | Query TEC temperature in °C |
| `set_temp` | `(temp: float) -> None` | Set TEC setpoint in °C |

#### Current Control

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_current` | `() -> float` | Query drive current in A |
| `set_current` | `(current: float) -> None` | Set drive current in A |

#### Monitor Photodiode

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_pd_current` | `() -> float` | Query internal monitor PD current in A |

#### Output Control

| Method | Signature | Description |
|--------|-----------|-------------|
| `set_output` | `(on: bool) -> None` | Enable/disable laser output |
| `is_output_on` | `() -> bool` | Query output state |
| `set_tec` | `(on: bool) -> None` | Enable/disable TEC |

#### Resource Management

| Method | Signature | Description |
|--------|-----------|-------------|
| `close` | `() -> None` | Release VISA resource |
| `__enter__` | `() -> LaserDriver` | Context manager entry |
| `__exit__` | `(*_) -> None` | Calls `close()` |

#### Example

```python
with LaserDriver.connect(serial="M00959058") as laser:
    laser.set_tec(True)
    laser.set_temp(25.0)
    laser.set_current(0.050)  # 50 mA
    laser.set_output(True)

    print(f"Temperature: {laser.get_temp():.1f} °C")
    print(f"PD current:  {laser.get_pd_current():.3e} A")

    laser.set_output(False)
# laser.close() called automatically
```

---

## Photodiode

**Module:** `optotwin.hal.photodiode`

### `PhotoDiode`

Reads a voltage-output external photodiode via a DAQ analog input channel.

#### Constructor

```python
PhotoDiode(
    channel: str = "Dev1/ai0",
    sample_rate: float = 1000.0,
    n_samples: int = 200,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `channel` | `str` | `"Dev1/ai0"` | DAQ analog input channel |
| `sample_rate` | `float` | `1000.0` | Sampling rate in Hz |
| `n_samples` | `int` | `200` | Samples to average per reading |

#### Methods

```python
def get_voltage() -> float
```

Acquire `n_samples` at `sample_rate` and return the mean voltage.

---

## Piezo Stage

**Module:** `optotwin.hal.piezo`

### `PiezoStage`

Serial interface to a Thorlabs MDT piezo controller. The Y-axis is used for focus (Z) control.

#### Constructor

```python
PiezoStage(baud_rate: int = 115200)
```

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `connect` | `() -> None` | Open first available MDT device |
| `disconnect` | `() -> None` | Close serial connection |
| `set_y_voltage` | `(voltage: float) -> None` | Set Y-axis (focus) voltage |
| `get_y_voltage` | `() -> float` | Read current Y-axis voltage |

#### Context Manager

```python
with PiezoStage() as piezo:
    piezo.set_y_voltage(35.0)
    print(piezo.get_y_voltage())
# disconnect() called automatically
```

---

## Temperature Controllers

**Module:** `optotwin.hal.temperature`

### `AuberController`

ModBus RTU interface to an Auber PID temperature controller.

#### Constructor

```python
AuberController(port: str = "COM5", slave_address: int = 3)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `port` | `str` | `"COM5"` | Serial port |
| `slave_address` | `int` | `3` | ModBus slave address |

Communication settings: 9600 baud, 8 data bits, no parity, 1 stop bit, RTU mode.

#### Methods

```python
def get_temperature() -> float
```

Query process temperature in °C from ModBus register 1000.

---

### `ThermocoupleReader`

K-type thermocouple reader via NI DAQ analog input.

#### Constructor

```python
ThermocoupleReader(channel: str = "Dev1/ai0")
```

#### Methods

```python
def get_temperature() -> float
```

Acquire 10 samples at 100 Hz from a K-type thermocouple task and return the mean temperature in °C.
