# Hardware Setup

This guide covers wiring, channel assignments, and instrument configuration for the OptoTwin-HIL confocal microscopy system.

---

## System Overview

```
                    ┌──────────────────┐
                    │  Host PC (USB)   │
                    └──┬───┬───┬───┬──┘
                       │   │   │   │
          ┌────────────┘   │   │   └────────────┐
          ▼                ▼   ▼                ▼
   ┌─────────────┐  ┌─────────┐ ┌──────────┐  ┌───────────┐
   │ NI USB-6421 │  │CLD1015  │ │MDT Piezo │  │Auber PID  │
   │   (DAQ)     │  │ (Laser) │ │ (Focus)  │  │  (Temp)   │
   └──┬──┬──┬────┘  └─────────┘ └──────────┘  └───────────┘
      │  │  │
      │  │  └─── PFI0 ◄── SPAD photon pulses
      │  └────── AO1  ──► Y Galvo Mirror
      └───────── AO0  ──► X Galvo Mirror
```

---

## NI USB-6421 DAQ

The DAQ is the central synchronisation hub. It drives the galvo mirrors and counts photons from the SPAD detector.

### Channel Assignments

| Channel | Direction | Function | Default |
|---------|-----------|----------|---------|
| `Dev1/ao0` | Analog Out | X galvo mirror | ±10 V range |
| `Dev1/ao1` | Analog Out | Y galvo mirror | ±10 V range |
| `Dev1/ctr0` | Counter In | SPAD photon counter | Edge counting |
| `/Dev1/PFI0` | Digital In | SPAD pulse input terminal | 1.8 V logic |
| `Dev1/ai0` | Analog In | External photodiode (optional) | 0-10 V |
| `Dev1/port0` | Digital I/O | Logic family configuration | 1.8 V |

### Synchronisation

The AO sample clock is routed internally to the CI counter as its timebase. This ensures every counter bin corresponds exactly to one AO sample, providing zero-latency synchronisation without external wiring.

```
AO Task ─── sample clock ───► CI Task
  │                              │
  ├─ writes X voltage            ├─ counts rising edges on PFI0
  └─ writes Y voltage            └─ returns cumulative count per sample
```

### Overriding Channel Names

Use environment variables to target different devices or channels:

```bash
export OT_AO_X="Dev2/ao0"
export OT_AO_Y="Dev2/ao1"
export OT_CI="Dev2/ctr0"
```

### NI-DAQmx Driver

Install the NI-DAQmx driver from [ni.com/downloads](https://www.ni.com/en/support/downloads/drivers/download.ni-daq-mx.html). The Python `nidaqmx` package wraps this driver.

Verify the device is detected:

```python
import nidaqmx
system = nidaqmx.system.System.local()
for device in system.devices:
    print(device.name)  # Should show "Dev1"
```

---

## Galvo Mirrors (X/Y Scanning)

Two analog-output-driven galvanometer mirrors steer the excitation beam in X and Y.

| Axis | DAQ Channel | Typical Range | Purpose |
|------|-------------|---------------|---------|
| X | `Dev1/ao0` | ±5 V | Horizontal beam steering |
| Y | `Dev1/ao1` | ±5 V | Vertical beam steering |

### Safety

The `SupervisorConfig.interlock_volts` parameter (default: 9.5 V) provides a software interlock. The supervisor will fault if commanded voltages exceed this threshold, protecting the mirrors from over-travel.

### Parking

After every scan, call `daq.park()` to return both mirrors to (0, 0) V. This prevents thermal drift while the beam is stationary at an off-centre position.

---

## SPAD Detector

A Single-Photon Avalanche Diode provides the photon-counting signal.

| Parameter | Value |
|-----------|-------|
| Output | TTL pulses (one per photon) |
| Connection | PFI0 terminal on NI USB-6421 |
| Logic level | 1.8 V |
| DAQ mode | Counter input, edge counting |

The counter is configured for cumulative edge counting. Per-pixel counts are obtained by differentiating the cumulative trace:

```python
per_pixel = np.insert(np.diff(cumulative_counts), 0, cumulative_counts[0])
```

The `reconstruct_image()` function handles this automatically.

---

## CLD1015 Laser Controller

Coherent CLD1015 butterfly diode laser controller, connected via USB (VISA).

| Parameter | Value |
|-----------|-------|
| Interface | USB (VISA) |
| Serial number | `M00959058` |
| Protocol | SCPI |
| TEC control | Yes (temperature setpoint + readback) |
| Current control | Yes (drive current in amps) |
| Monitor PD | Yes (internal photodiode current readback) |

### Connection

```python
from optotwin.hal import LaserDriver

with LaserDriver.connect(serial="M00959058") as laser:
    laser.set_tec(True)
    laser.set_temp(25.0)
    laser.set_current(0.050)
    laser.set_output(True)
```

### SCPI Commands Used

| Method | SCPI Command |
|--------|-------------|
| `get_temp()` | `SENSe2:DATA?` |
| `set_temp(t)` | `SOURce2:TEMP:SPO {t}` |
| `get_current()` | `SENSe3?` |
| `set_current(i)` | `SOURce1:CURR {i}` |
| `get_pd_current()` | `SENSe1?` |
| `set_output(on)` | `OUTPut1:STATe {0\|1}` |
| `is_output_on()` | `OUTPut1:STATe?` |
| `set_tec(on)` | `OUTPut2:STATe {0\|1}` |

---

## Thorlabs MDT Piezo Stage

Piezo-driven focus stage for Z-axis control.

| Parameter | Value |
|-----------|-------|
| Interface | USB Serial |
| Baud rate | 115200 |
| Control axis | Y (used for focus/Z) |
| Voltage range | 0 -- 150 V (device dependent) |
| Library | `MDT_COMMAND_LIB` (Thorlabs SDK) |

### Connection

```python
from optotwin.hal import PiezoStage

with PiezoStage() as piezo:
    piezo.set_y_voltage(35.0)
    print(f"Focus voltage: {piezo.get_y_voltage():.1f} V")
```

### Prerequisites

Install the Thorlabs MDT Command Library from the Thorlabs software downloads page. The `MDT_COMMAND_LIB` Python bindings must be importable.

---

## Auber PID Temperature Controller

ModBus RTU temperature controller with K-type thermocouple input.

| Parameter | Value |
|-----------|-------|
| Interface | RS-485 via USB-Serial adapter |
| Port | `COM5` (default) |
| Slave address | 3 |
| Baud rate | 9600 |
| Register | 1000 (process temperature) |
| Protocol | ModBus RTU |

### Connection

```python
from optotwin.hal import AuberController

auber = AuberController(port="COM5", slave_address=3)
temp = auber.get_temperature()
print(f"Temperature: {temp:.1f} °C")
```

---

## K-Type Thermocouple (via DAQ)

Direct thermocouple reading through the NI DAQ analog input, as an alternative to the Auber controller.

```python
from optotwin.hal import ThermocoupleReader

tc = ThermocoupleReader(channel="Dev1/ai0")
temp = tc.get_temperature()
print(f"Temperature: {temp:.1f} °C")
```

---

## Optical Path

```
Laser (CLD1015)
    │
    ▼
Single-Mode Fiber ──► spatial filtering
    │
    ▼
Collimator
    │
    ▼
X Galvo Mirror (AO0)
    │
    ▼
Y Galvo Mirror (AO1)
    │
    ▼
Objective Lens
    │
    ▼
Sample ◄── Piezo Stage (focus)
    │
    ▼ (reflected/fluorescent photons)
Pinhole (confocal aperture)
    │
    ▼
SPAD Detector ──► PFI0 (TTL pulses)
```

The single-mode fiber acts as the illumination pinhole, providing spatial filtering. The detection pinhole rejects out-of-focus light, giving the system its confocal sectioning capability.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `nidaqmx.DaqError: device not found` | DAQ not connected or driver not installed | Check USB, install NI-DAQmx |
| All counts are zero | SPAD not powered, wrong PFI terminal, or logic level mismatch | Verify SPAD output, check 1.8 V logic on port0 |
| Image has diagonal stripes | Bidirectional raster flip not applied | Use `reconstruct_image()` instead of manual reshape |
| Image is mirrored | X or Y axis inverted | Swap `xlims` or `ylims` tuple order |
| `pyvisa.errors.VisaIOError` | Laser not connected or wrong serial | Check USB, verify serial number |
| Piezo not responding | MDT library not installed or device not found | Install Thorlabs MDT Command Library |
| ModBus timeout | Wrong COM port or slave address | Verify port and address with Auber documentation |
| Scan takes too long | Too many pixels or long dwell time | Check `cfg.total_time_s` before starting |
