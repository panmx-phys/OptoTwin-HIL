# Legacy Notebook → OptoTwin-HIL Migration Guide

This document maps every section of `legacyNotebook.py` to its new home in
the `optotwin` package.  Code blocks show **before** (legacy) and **after**
(new package) so you can port existing notebooks cell-by-cell.

---

## 1. Imports & Setup (lines 1–46)

### Legacy
```python
import nidaqmx, pyvisa, minimalmodbus, ...
os.chdir("C:\\Users\\JDSY-Optics\\Documents\\GitHub\\ConfocalMicroscope")
db_path = ...
initialise_or_create_database_at(db_path)
phys_chans = PhysicalChannel("Dev1/port0")
phys_chans.dig_port_logic_family = LogicFamily.ONE_POINT_EIGHT_V
```

### New
```python
# No global nidaqmx/pyvisa imports needed — HAL handles them internally
from optotwin.core.config import ScanConfig, DualAreaScanConfig
from optotwin.core.utils import calculate_square_pixels, print_scan_time, rect_to_lims
from optotwin.hal.daq import DAQOrchestrator, SimulatedDAQOrchestrator
from optotwin.hal.laser import LaserDriver
from optotwin.hal.photodiode import PhotoDiode
from optotwin.hal.piezo import PiezoStage
from optotwin.hal.temperature import AuberController
from optotwin.trajectory.raster import (
    raster_voltages, reconstruct_image,
    interleaved_dual_raster, reconstruct_dual_images,
)
```

> **Key change:** Hardware libraries (`nidaqmx`, `pyvisa`, `minimalmodbus`,
> `MDT_COMMAND_LIB`) are only imported inside `hal/`.  Your notebooks and
> scripts never touch them directly.

---

## 2. Laser Driver (lines 70–125)

### Legacy
```python
rm = pyvisa.ResourceManager()
CLD1015 = resource_manager.open_resource(port)  # global VISA object
CLD1015.write("OUTPut2:STATe 1")  # TEC ON
CLD1015.write("OUTPut1:STATe 1")  # Laser ON

class LaserDriver:
    def getCurr() -> float:
        return float(CLD1015.query("SENSe3?")[:-1])
    def setCurr(current):
        CLD1015.write("SOURce1:CURR " + str(current))
    ...
```

### New — `hal/laser.py`
```python
from optotwin.hal.laser import LaserDriver

# Factory method handles VISA connection
laser = LaserDriver.connect(serial="M00959058")

laser.set_tec(True)
laser.set_output(True)

print(laser.get_current())       # was: LaserDriver.getCurr()
laser.set_current(0.2135)        # was: LaserDriver.setCurr(0.2135)
print(laser.get_temp())          # was: LaserDriver.getTemp()
print(laser.get_pd_current())    # was: LaserDriver.getPDCurr()

# Context manager for safe cleanup
with LaserDriver.connect() as laser:
    laser.set_output(True)
    ...
```

| Legacy | New |
|---|---|
| `LaserDriver.getCurr()` | `laser.get_current()` |
| `LaserDriver.setCurr(v)` | `laser.set_current(v)` |
| `LaserDriver.getTemp()` | `laser.get_temp()` |
| `LaserDriver.setTemp(v)` | `laser.set_temp(v)` |
| `LaserDriver.getPDCurr()` | `laser.get_pd_current()` |
| `CLD1015.write("OUTPut1:STATe 1")` | `laser.set_output(True)` |
| `CLD1015.write("OUTPut2:STATe 1")` | `laser.set_tec(True)` |

---

## 3. Piezo Stage (lines 86–138)

### Legacy
```python
import MDT_COMMAND_LIB as mdt
serialNum = mdt.mdtListDevices()[0][0]
hdl = mdt.mdtOpen(serialNum, 115200, 3)
mdt.mdtSetYAxisVoltage(hdl, piezoVy)
mdt.mdtClose(hdl)
```

### New — `hal/piezo.py`
```python
from optotwin.hal.piezo import PiezoStage

with PiezoStage() as piezo:
    piezo.set_y_voltage(32.5)
    print(piezo.get_y_voltage())
# serial connection is auto-closed on exit
```

---

## 4. Temperature Controller (lines 141–176)

### Legacy — Auber ModBus
```python
instrument = minimalmodbus.Instrument('COM5', 3)
instrument.serial.baudrate = 9600
...
temperature = instrument.read_register(1000, 0)
```

### Legacy — K-type Thermocouple via DAQ
```python
with nidaqmx.Task() as task:
    task.ai_channels.add_ai_thrmcpl_chan("Dev1/ai0", ...)
    data = task.read()
```

### New — `hal/temperature.py`
```python
from optotwin.hal.temperature import AuberController, ThermocoupleReader

auber = AuberController(port="COM5", slave_address=3)
print(auber.get_temperature())

tc = ThermocoupleReader(channel="Dev1/ai0")
print(tc.get_temperature())
```

---

## 5. Photodiode (lines 208–217)

### Legacy
```python
class photoDiode:
    def getVoltage() -> float:
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
            task.timing.cfg_samp_clk_timing(1000.0, ...)
            data = task.read(READ_ALL_AVAILABLE)
        return np.mean(data)
```

### New — `hal/photodiode.py`
```python
from optotwin.hal.photodiode import PhotoDiode

pd = PhotoDiode(channel="Dev1/ai0", sample_rate=1000.0, n_samples=200)
voltage = pd.get_voltage()
```

---

## 6. DAQ Driver — Core Acquisition (lines 223–309)

### Legacy
```python
def daqDriver(Vset, dwell_time):
    with nidaqmx.Task() as ao_task, nidaqmx.Task() as ci_task, ...:
        ao_task.ao_channels.add_ao_voltage_chan("Dev1/ao0", ...)
        ao_task.ao_channels.add_ao_voltage_chan("Dev1/ao1", ...)
        ci_channel.ci_count_edges_term = "/Dev1/PFI0"
        ...
    return counts  # cumulative

counts = daqDriver(Vset, 0.001)
```

### New — `hal/daq.py`
```python
from optotwin.hal.daq import DAQOrchestrator

daq = DAQOrchestrator(
    ao_x_channel="Dev1/ao0",
    ao_y_channel="Dev1/ao1",
    ci_channel="Dev1/ctr0",
    pfi_terminal="/Dev1/PFI0",
)

cumulative_counts = daq.run(voltages, dwell_time=0.001)  # same (2,N) input
daq.park()  # was: daqDriver(np.array([[0,0],[0,0]]), 0.01)
```

> **Same behaviour:** `.run()` returns cumulative counts, just like
> `daqDriver`.

---

## 7. Simulated DAQ (lines 372–385)

### Legacy
```python
def simDaqDriver(Vset, dwell_time):
    count = 0
    counts = np.zeros(Vset.shape[1])
    for i in range(Vset.shape[1]):
        counts[i] = count
        count += np.power(Vset[0,:],2)[i]
    return counts
```

### New — `hal/daq.py`
```python
from optotwin.hal.daq import SimulatedDAQOrchestrator

daq = SimulatedDAQOrchestrator()
counts = daq.run(voltages, dwell_time=0.001)  # same interface, no hardware
```

> **Tip:** Use `OT_SIMULATE=1` env var in example scripts to swap
> automatically.

---

## 8. Single-Area Raster Scan (lines 312–368)

### Legacy
```python
def daqScan(x_px, y_px, xlims, ylims, dwell_time, accumulation=1):
    v_x = np.linspace(xlims[0], xlims[1], x_px)
    v_y = np.linspace(ylims[0], ylims[1], y_px)
    Vx, Vy = np.meshgrid(v_x, v_y, indexing='xy')
    Vx[1::2] = np.fliplr(Vx[1::2])  # bidirectional
    ...
    counts = daqDriver(Vset, dwell_time)
    counts = np.insert(np.diff(counts), 0, counts[0])
    counts = counts.reshape(x_px, y_px)
    counts[1::2] = np.fliplr(counts[1::2])
    counts[0,0] = 0
    return counts

# One-liner call:
image = daqScan(100, 100, (-1, 1), (-1, 1), 0.001, accumulation=5)
```

### New — split into `trajectory/raster.py` + `hal/daq.py`
```python
from optotwin.trajectory.raster import raster_voltages, reconstruct_image
from optotwin.hal.daq import DAQOrchestrator

daq = DAQOrchestrator()

# Step 1: build trajectory (pure numpy, testable)
voltages = raster_voltages(100, 100, (-1, 1), (-1, 1), accumulation=5)

# Step 2: acquire (hardware I/O)
raw = daq.run(voltages, dwell_time=0.001)

# Step 3: reconstruct image (pure numpy, testable)
image = reconstruct_image(raw, 100, 100, accumulation=5)
# shape: (5, 100, 100) for accumulation=5, or (100, 100) for accumulation=1

daq.park()
```

> **Why the split?** Trajectory generation and image reconstruction are now
> unit-testable without hardware. The `SimulatedDAQOrchestrator` slots right
> in between steps 1 and 3 for testing.

---

## 9. Two-Area Interlaced Scan (lines 391–444)

### Legacy
```python
counts1, counts2 = twoAreaInterlacingDaqScan(
    px1, px2, xlims1, ylims1, xlims2, ylims2, dwell_time, ifSimulate=False)
```

### New — `trajectory/raster.py`
```python
from optotwin.trajectory.raster import interleaved_dual_raster, reconstruct_dual_images

voltages = interleaved_dual_raster(
    px1=(30, 30), px2=(30, 30),
    xlims1=(0.01, 0.06), ylims1=(-0.07, -0.01),
    xlims2=(-0.07, -0.03), ylims2=(-0.04, 0.01),
)

raw = daq.run(voltages, dwell_time=0.01)
counts1, counts2 = reconstruct_dual_images(raw, px1=(30, 30), px2=(30, 30))
```

---

## 10. Utility Functions (lines 450–499)

| Legacy | New (`core/utils.py`) |
|---|---|
| `calculate_square_pixels(xlims, ylims, base_px)` | `calculate_square_pixels(xlims, ylims, base_px)` — same |
| `makeConfigSquare(config, base_px)` | `make_config_square(config, base_px)` — takes `ScanConfig` |
| `timeOfConfig(config, multiplier)` | `print_scan_time(config, multiplier)` |
| `rectToLims(rect, config)` | `rect_to_lims(rect, config)` |

---

## 11. Config Dicts → ScanConfig Dataclass (lines 880–936)

### Legacy
```python
flakeConfig = {
    "x_px": 100, "y_px": 100,
    "xlims": (-1, 1), "ylims": (0, 0.27),
    "dwell_time": 0.1, "accumulation": 1,
    "ND_Filter": [4, 3],
    "experiment_name": "TIRF illuminated confocal scan",
    "sample_name": "S32",
    "measurement_name": "Background scan at RT",
    "comment": "90C",
}
```

### New — `core/config.py`
```python
from optotwin.core.config import ScanConfig

config = ScanConfig(
    x_px=100, y_px=100,
    xlims=(-1.0, 1.0), ylims=(0.0, 0.27),
    dwell_time=0.1, accumulation=1,
    nd_filters=[4, 3],
    experiment_name="TIRF illuminated confocal scan",
    sample_name="S32",
    measurement_name="Background scan at RT",
    comment="90C",
)

print(config)                # ScanConfig(100×100 px, dwell=100.00 ms, acc=1, total=0:00:10)
print(config.total_time_s)   # 1000.0
print(config.frame_time_s)   # 1000.0
```

For dual-area scans:
```python
from optotwin.core.config import DualAreaScanConfig

config = DualAreaScanConfig(
    px1=(30, 30), px2=(30, 30),
    xlims1=(-0.07, -0.03), ylims1=(-0.04, 0.01),
    xlims2=(-0.03, 0.00), ylims2=(-0.03, -0.004),
    dwell_time=0.01,
)
```

---

## 12. QCoDeS Data Saving (lines 507–856)

The QCoDeS wrappers (`daqScanSaved`, `twoAreaSaved`, `twoAreaSweepSaved`,
`singleSweepSaved`, `laserSweep`) are **not** ported into the core package
because they combine acquisition, laser control, and database logging into
monolithic functions.  The new approach separates these concerns:

```python
# Instead of one call to daqScanSaved(config), you now compose the pieces:

# 1. Build voltages
voltages = raster_voltages(config.x_px, config.y_px, config.xlims, config.ylims,
                           config.accumulation)

# 2. Acquire
raw = daq.run(voltages, config.dwell_time)

# 3. Reconstruct
image = reconstruct_image(raw, config.x_px, config.y_px, config.accumulation)

# 4. (Optional) Save to QCoDeS — write this in your own script
from qcodes.dataset import Measurement, load_or_create_experiment
from qcodes.parameters import Parameter

exp = load_or_create_experiment(
    experiment_name=config.experiment_name,
    sample_name=config.sample_name,
)
counts_param = Parameter(name="counts", label="Photon Counts", unit="counts")
meas = Measurement(exp=exp, name=config.measurement_name)
meas.register_parameter(counts_param, paramtype="array")
with meas.run() as datasaver:
    datasaver.add_result((counts_param, image))
```

---

## 13. Plotting (lines 862–877)

### Legacy
```python
def live_plot(output_array):
    plt.clf()
    plt.imshow(output_array, cmap='hot')
    plt.colorbar(label='Counts')
    clear_output(wait=True)
    display(plt.gcf())
```

### New
Plotting stays in your notebooks and example scripts — it is not part of
the core library. See `examples/01_confocal_scan.py` for a reference
implementation.

---

## 14. Region Selection (lines 956–1013)

Interactive ROI selection via `matplotlib.widgets.RectangleSelector` is
**notebook-specific UI** and not included in the package. The coordinates
you get from the selector feed directly into `rect_to_lims`:

```python
from optotwin.core.utils import rect_to_lims

# After interactive selection:
selection = ((x1, y1), (x2, y2))
config = rect_to_lims(selection, config)
```

---

## 15. Continuous Imaging Loop (lines 1459–1491)

### Legacy
```python
while True:
    counts = daqScan(50, 50, (-1, 1), (-1, 1), 0.0005)
    plt.imshow(np.log10(counts / 0.0005), cmap='hot')
    clear_output(wait=True)
    display(plt.gcf())
```

### New
```python
from optotwin.trajectory.raster import raster_voltages, reconstruct_image
from optotwin.hal.daq import DAQOrchestrator

daq = DAQOrchestrator()
voltages = raster_voltages(50, 50, (-1, 1), (-1, 1))

try:
    while True:
        raw = daq.run(voltages, dwell_time=0.0005)
        image = reconstruct_image(raw, 50, 50)
        plt.clf()
        plt.imshow(np.log10(image / 0.0005), cmap='hot')
        plt.colorbar(label='Log10 Counts/s')
        clear_output(wait=True)
        display(plt.gcf())
except KeyboardInterrupt:
    daq.park()
```

> Note that `raster_voltages` is called **once** before the loop since the
> trajectory is identical each frame.

---

## 16. Piezo Z-Stack (lines 1493–1552)

### Legacy
```python
hdl = mdt.mdtOpen(serialNum, 115200, 3)
for piezoVy in np.linspace(30, 35, 30):
    mdt.mdtSetYAxisVoltage(hdl, piezoVy)
    time.sleep(1)
    counts = daqScan(...)
    countsSet += [counts]
mdt.mdtClose(hdl)
np.save("data/piezoScan.npy", np.stack(countsSet))
```

### New — see `examples/03_z_stack.py`
```python
from optotwin.hal.piezo import PiezoStage
from optotwin.hal.daq import DAQOrchestrator
from optotwin.trajectory.raster import raster_voltages, reconstruct_image

voltages = raster_voltages(50, 50, (-0.5, 0.5), (-0.5, 0.5))

with PiezoStage() as piezo, DAQOrchestrator() as daq:
    for z_v in np.linspace(30, 35, 30):
        piezo.set_y_voltage(z_v)
        time.sleep(1)
        raw = daq.run(voltages, dwell_time=0.001)
        stack.append(reconstruct_image(raw, 50, 50))
    daq.park()
```

---

## Quick-reference: Complete Legacy → Module Map

| Legacy function / object | New module | New name |
|---|---|---|
| `daqDriver(Vset, dwell_time)` | `hal/daq.py` | `DAQOrchestrator.run(voltages, dwell_time)` |
| `simDaqDriver(Vset, dwell_time)` | `hal/daq.py` | `SimulatedDAQOrchestrator.run(...)` |
| `daqScan(x_px, y_px, xlims, ylims, dwell_time, acc)` | `trajectory/raster.py` | `raster_voltages()` + `daq.run()` + `reconstruct_image()` |
| `twoAreaInterlacingDaqScan(...)` | `trajectory/raster.py` | `interleaved_dual_raster()` + `daq.run()` + `reconstruct_dual_images()` |
| `LaserDriver` (static methods + global) | `hal/laser.py` | `LaserDriver` (instance methods) |
| `photoDiode.getVoltage()` | `hal/photodiode.py` | `PhotoDiode.get_voltage()` |
| MDT piezo (`mdt.mdtOpen`, `mdtSetYAxisVoltage`, …) | `hal/piezo.py` | `PiezoStage` context manager |
| Auber ModBus (`instrument.read_register(1000, 0)`) | `hal/temperature.py` | `AuberController.get_temperature()` |
| K-type thermocouple via DAQ | `hal/temperature.py` | `ThermocoupleReader.get_temperature()` |
| `calculate_square_pixels(xlims, ylims)` | `core/utils.py` | `calculate_square_pixels(xlims, ylims)` |
| `makeConfigSquare(config)` | `core/utils.py` | `make_config_square(config)` |
| `timeOfConfig(config)` | `core/utils.py` | `print_scan_time(config)` |
| `rectToLims(rect, config)` | `core/utils.py` | `rect_to_lims(rect, config)` |
| `flakeConfig = {...}` (raw dict) | `core/config.py` | `ScanConfig(...)` dataclass |
| `twoAreaExampleConfig = {...}` | `core/config.py` | `DualAreaScanConfig(...)` dataclass |
| `daqScanSaved(config)` | *(not ported — compose manually)* | See §12 above |
| `live_plot(arr)` / `quickLookData(arr)` | *(not ported — stays in notebooks)* | `plt.imshow(...)` |
| `RectangleSelector` (ROI selection) | *(not ported — stays in notebooks)* | Use `rect_to_lims()` with coords |
