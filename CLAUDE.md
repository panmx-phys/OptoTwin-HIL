# OptoTwin-HIL — Claude Code Guide

## Project Purpose
Hardware-in-the-loop (HIL) framework for automating a confocal microscope as a metrology tool.

## Package Layout
```
src/optotwin/
  core/        # ABCs, coordinate transforms, Metrology Supervisor state machine
  hal/         # Hardware Abstraction Layer — only module allowed to import nidaqmx
  trajectory/  # Geometric path generation (sweeps, spirals, dithering)
  twin/        # Digital Twin: forward models + optimizers (SciPy / JAX)
tests/         # pytest suite — must run without physical hardware
examples/      # High-level entry-point scripts
```

## Key Rules
- **Only `hal/`** may import `nidaqmx`. Never import it in `core/`, `trajectory/`, or `twin/`.
- Tests must be hardware-agnostic and runnable in CI without a DAQ attached.
- Physical models live in `twin/`, not in `hal/` or `trajectory/`.
- Coordinate transforms are defined in `core/` and consumed everywhere else.

## Python Environment
- Python ≥ 3.11
- Managed via `pyproject.toml` (PEP 621)
- Install dev dependencies: `pip install -e ".[dev]"`
- Run tests: `pytest`

## Hardware Stack
- DAQ: NI USB-6421 via `nidaqmx`
- Actuators: X/Y Galvo Mirrors (Analog Output)
- Sensors: SPAD (Counter Input, hardware-timed via AO sample clock)
- Optics: Single-Mode Fiber spatial filtering
