# OptoTwin-HIL Documentation

**Hardware-in-the-loop framework for automating a confocal microscope as a precision metrology tool.**

OptoTwin-HIL provides a modular Python toolkit for controlling galvo-scanned confocal microscopy systems, acquiring photon-counting data, generating scan trajectories, and fitting physical models to measured edge profiles.

---

## Documentation Guide

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Installation, first scan, running without hardware |
| [Architecture](architecture.md) | Package design, module boundaries, data flow |
| [Hardware Setup](hardware.md) | Wiring, DAQ channels, instrument configuration |
| **API Reference** | |
| [Core](api/core.md) | Config dataclasses, coordinate transforms, state machine, utilities |
| [HAL](api/hal.md) | DAQ orchestrator, laser, photodiode, piezo, temperature |
| [Trajectory](api/trajectory.md) | Raster, sweep, spiral, dither path generators |
| [Twin](api/twin.md) | Gaussian edge model, curve fitting |
| [Examples & Tutorials](examples.md) | Walkthrough of included example scripts |

---

## Quick Links

```bash
# Install (editable, with dev tools)
pip install -e ".[dev]"

# Run tests (no hardware needed)
pytest

# Run a simulated scan
OT_SIMULATE=1 python examples/01_confocal_scan.py
```

## Feature Overview

- **Hardware Abstraction** -- DAQ, laser, piezo, photodiode, and temperature controllers behind clean Python interfaces
- **Drop-in Simulation** -- `SimulatedDAQOrchestrator` lets you develop and test without physical hardware
- **Trajectory Generation** -- Bidirectional raster, 1-D sweeps, Archimedean spirals, extremum-seeking dither
- **Digital Twin** -- Gaussian knife-edge forward model with SciPy curve fitting
- **Async Supervisor** -- State machine for sequencing acquire-fit workflows
- **Dual-Area Interlacing** -- Simultaneous reference + signal acquisition for drift compensation
- **Diagnostic GUI** -- DearPyGUI dashboard for live scanning and hardware control

## Requirements

- Python >= 3.11
- NI USB-6421 DAQ (or simulation mode)
- See [Getting Started](getting-started.md) for full dependency list
