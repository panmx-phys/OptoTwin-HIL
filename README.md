# Under unconstruction

# OptoTwin-HIL

OptoTwin HIL is a hardware-in-the-loop (HIL) framework that transforms a custom-built confocal microscope into a fully automated, high-throughput metrology tool.

## System Architecture

- Hardware Abstraction Layer (HAL): Interfaces with National Instruments DAQs to handle hardware-timed synchronization (e.g., routing Analog Output clocks to Counter Input tasks) for zero-latency data collection.

- Trajectory Engine: Generates geometric paths (1D sweeps, spirals, dithering) independent of the physical hardware.

- Digital Twin & Optimization: Streams raw photon counts into optimizer to fit physical models (like the Gaussian edge-response Error Function) and extract beam parameters.

- Metrology Supervisor: An asynchronous state machine that handles coordinate transformations, target acquisition, and system safety interlocks.

## Supported Hardware Stack

OptoTwin is architected to drive a fiber-coupled confocal microscope. While the software interfaces are abstract, the initial drivers are built for:

DAQ: National Instruments USB-6421 (via nidaqmx)

Actuators: X/Y Galvo Mirrors

Sensors: Single-Photon Avalanche Diode (SPAD)

Optics: Single-Mode Fiber (SMF) spatial filtering

## 📂 Project Layout

* **`optotwin-hil/`** *(Root Directory)*
  * `pyproject.toml` — Modern build system and dependency management (PEP 621).
  * `README.md` — Project architecture, hardware stack, and overview.
  * **`src/optotwin/`** — The core Python package.
    * **`core/`** — The foundational rules of the system. Contains Abstract Base Classes (ABCs), affine coordinate transformation matrices, and the Metrology Supervisor state machine.
    * **`hal/`** — Hardware Abstraction Layer. This is the only directory allowed to import `nidaqmx`. It contains the orchestrator for DAQ clock routing and hardware-timed synchronization.
    * **`trajectory/`** — Geometric path planning. Generates deterministic arrays for 1D sweeps, extremum-seeking dithering, and sparse spirals, completely agnostic of the hardware.
    * **`twin/`** — The Digital Twin engine. Contains the physical forward models (e.g., the Gaussian step-edge response) and the optimization algorithms (SciPy and JAX) to extract sub-pixel metrology data.
  * **`tests/`** — The `pytest` suite. Contains unit tests for trajectories and mathematical models that can run in a CI/CD pipeline without physical hardware attached.
  * **`examples/`** — High-level execution scripts serving as practical entry points.
    * `01_knife_edge_diag.py` — Script to execute a 1D sweep and verify single-mode fiber (SMF) coupling symmetry.
    * `02_active_tracking.py` — Script initiating closed-loop, gradient-based edge locking.
