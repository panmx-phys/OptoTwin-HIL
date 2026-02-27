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

## Project Layout

optotwin-hil/
├── pyproject.toml             # Modern build system & dependencies
├── README.md                  # Project overview
├── src/
│   └── optotwin/              # Core Python package
│       ├── core/              # ABC interfaces, affine mapping, state machine
│       ├── hal/               # NI-DAQ orchestrator and clock routing
│       ├── trajectory/        # Path planning generators
│       └── twin/              # Forward models (SciPy/JAX)
├── tests/                     # Pytest suite
└── examples/                  # High-level execution scripts (e.g., Knife-Edge Test)
