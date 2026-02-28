# Architecture

## Design Philosophy

OptoTwin-HIL follows a strict **layered architecture** that separates hardware access from physics, trajectory planning, and orchestration. This enables:

- **Testability** -- every layer above `hal/` runs without physical instruments
- **Portability** -- swap DAQ vendors by replacing only `hal/` implementations
- **Composability** -- mix and match trajectories, detectors, and models freely

---

## Package Layout

```
src/optotwin/
  core/        # ABCs, coordinate transforms, config, state machine, utilities
  hal/         # Hardware Abstraction Layer (only module with hardware imports)
  trajectory/  # Pure-NumPy geometric path generation
  twin/        # Physical forward models + curve fitting
tests/         # pytest suite (hardware-agnostic)
examples/      # Entry-point scripts and diagnostic GUI
```

---

## Module Dependency Graph

```
                    ┌─────────────┐
                    │   examples   │  (entry points)
                    └──────┬──────┘
                           │ imports
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
      ┌──────────┐  ┌────────────┐  ┌──────────┐
      │   core   │  │ trajectory │  │   twin   │
      └──────────┘  └────────────┘  └──────────┘
            │              │              │
            │    (pure numpy, no HW)      │
            │                             │
            ▼                             ▼
      ┌──────────┐                  ┌──────────┐
      │   hal    │                  │  scipy   │
      └──────────┘                  └──────────┘
            │
            ▼
    ┌───────────────┐
    │ nidaqmx/pyvisa│  (vendor drivers)
    │ minimalmodbus  │
    └───────────────┘
```

### Import Rules

| Module | May import | Must NOT import |
|--------|-----------|-----------------|
| `core` | `numpy`, stdlib | `nidaqmx`, `pyvisa`, `minimalmodbus` |
| `hal` | `nidaqmx`, `pyvisa`, `minimalmodbus`, `numpy` | (unrestricted) |
| `trajectory` | `numpy` | `nidaqmx`, `pyvisa`, anything from `hal` |
| `twin` | `numpy`, `scipy` | `nidaqmx`, `pyvisa`, anything from `hal` |

---

## Data Flow

A typical single-area raster acquisition follows this pipeline:

```
ScanConfig              raster_voltages()          DAQOrchestrator.run()
(x_px, y_px,    ──►    generates (2, N)   ──►     drives galvos,
 xlims, ylims,          voltage array              reads SPAD counter
 dwell_time)                                       returns cumulative
                                                   counts (N,)
                                                        │
                                                        ▼
                        reconstruct_image()         matplotlib /
                        undoes bidir flip,   ──►    xarray / analysis
                        differentiates counts,
                        returns 2-D image
```

### Dual-Area Interlaced Flow

```
DualAreaScanConfig
        │
        ▼
interleaved_dual_raster()     DAQOrchestrator.run()
generates interleaved  ──►    single continuous
(2, N) voltages               acquisition
[A A B B A A B B ...]              │
                                   ▼
                          reconstruct_dual_images()
                          deinterleaves, returns
                          (image_signal, image_reference)
```

---

## Key Design Patterns

### 1. Hardware Isolation

Only `hal/` imports vendor-specific packages (`nidaqmx`, `pyvisa`, `minimalmodbus`). This boundary is enforced by convention and checked in code review.

### 2. Drop-In Simulation

`SimulatedDAQOrchestrator` shares the same interface as `DAQOrchestrator`:

```python
# Production
daq = DAQOrchestrator()

# Testing / CI
daq = SimulatedDAQOrchestrator()

# Same call signature
counts = daq.run(voltages, dwell_time)
```

The `OT_SIMULATE=1` environment variable selects the simulator in example scripts.

### 3. Dataclass Configuration

`ScanConfig` and `DualAreaScanConfig` replace ad-hoc dictionaries with typed, validated objects:

```python
cfg = ScanConfig(x_px=200, y_px=200,
                 xlims=(-2.0, 2.0), ylims=(-2.0, 2.0),
                 dwell_time=0.5e-3, accumulation=4)

print(cfg)           # ScanConfig(200x200 px, dwell=0.50 ms, acc=4, total=80.00 s)
print(cfg.n_pixels)  # 40000
print(cfg.total_time_s)  # 80.0
```

### 4. Bidirectional Raster

To reduce flyback overhead, even rows scan left-to-right and odd rows scan right-to-left. The reconstruction step mirrors this flip to produce a correctly oriented image:

```
Row 0:  ────────────►
Row 1:  ◄────────────
Row 2:  ────────────►
Row 3:  ◄────────────
```

### 5. Hardware-Timed Synchronisation

The DAQ analog output (AO) sample clock is routed to the counter input (CI) as its sample clock source. This ensures zero-latency synchronisation between galvo position and photon counting -- every count bin corresponds exactly to one AO sample.

### 6. Context Managers

Hardware resources use Python context managers for safe cleanup:

```python
with LaserDriver.connect() as laser:
    laser.set_current(0.05)
    laser.set_output(True)
# laser.close() called automatically

with PiezoStage() as piezo:
    piezo.set_y_voltage(35.0)
# piezo.disconnect() called automatically
```

### 7. Async State Machine

`MetrologySupervisor` orchestrates multi-step workflows:

```
IDLE ──► ACQUIRING ──► FITTING ──► IDLE
              │              │
              └──► FAULT ◄───┘
```

State change callbacks allow GUI or logging hooks without coupling.

---

## Testing Strategy

- **No hardware in CI** -- all tests use `SimulatedDAQOrchestrator` or pure-NumPy inputs
- **Shape tests** -- verify output array dimensions for all trajectory generators
- **Round-trip tests** -- `AffineTransform2D` forward/inverse preserve points
- **Model recovery** -- `fit_edge` recovers known parameters from synthetic data
- **Bound tests** -- trajectories stay within specified voltage/radius limits

---

## Extending the Framework

### Adding a new trajectory type

1. Create `src/optotwin/trajectory/your_pattern.py`
2. Implement function returning `NDArray[np.float64]` with shape `(2, N)` or `(N, 2)`
3. Export from `src/optotwin/trajectory/__init__.py`
4. Add tests in `tests/test_trajectory.py`
5. Do NOT import any hardware modules

### Adding a new instrument

1. Create `src/optotwin/hal/your_instrument.py`
2. Implement class with `connect()`, `close()`, and `__enter__`/`__exit__`
3. Export from `src/optotwin/hal/__init__.py`
4. Hardware imports (`nidaqmx`, `pyvisa`, etc.) are allowed only here

### Adding a new physical model

1. Add model function to `src/optotwin/twin/models.py`
2. Add corresponding fit function to `src/optotwin/twin/optimizer.py`
3. Add tests with synthetic data in `tests/test_twin.py`
4. Do NOT import any hardware modules
