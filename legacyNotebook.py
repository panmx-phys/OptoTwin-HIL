# %% [markdown]
# ## Setting up

# %% [markdown]
# ### Essential & DAQ

# %%
import pyvisa
import time
import numpy as np
import xarray as xr
import os
import nidaqmx
import datetime

from nidaqmx.constants import READ_ALL_AVAILABLE, AcquisitionType, WAIT_INFINITELY, FrequencyUnits
from nidaqmx.constants import (AcquisitionType, Edge, CountDirection,
                               Level)

from nidaqmx import DaqError
from nidaqmx.constants import LogicFamily, TerminalConfiguration, UsageTypeAI
from nidaqmx.error_codes import DAQmxErrors
from nidaqmx.system import PhysicalChannel

from matplotlib import pyplot as plt

from IPython.display import display, clear_output

from qcodes.dataset import (
    Measurement,
    initialise_or_create_database_at,
    load_or_create_experiment,
    plot_dataset,
    load_by_id
)
from qcodes.parameters import Parameter

import minimalmodbus

os.chdir("C:\\Users\\JDSY-Optics\\Documents\\GitHub\\ConfocalMicroscope")
db_path = os.path.join(os.path.join(os.getcwd(), "data"), "imageDB.db")
initialise_or_create_database_at(db_path)

phys_chans = PhysicalChannel("Dev1/port0")
phys_chans.dig_port_logic_family = LogicFamily.ONE_POINT_EIGHT_V


# %% [markdown]
# ### Constants

# %%
NDPowerList = np.array([100,
                        16.852984,
                        0.978076,
                        0.478044667,
                        0.183115])*0.01

# %%
laserPower = (40 * NDPowerList[4] * NDPowerList[3] * NDPowerList[1])
laserPower/((70e-4)**2)

# %%
(1/(NDPowerList[3] * NDPowerList[1]))/4

# %%
laserPower = (40e-3 * NDPowerList[4] )
laserPower

# %% [markdown]
# ### Laser Driver Driver

# %%
rm = pyvisa.ResourceManager()

for device in rm.list_resources():
    if "M00959058" in device:
        port : str  = device

resource_manager = pyvisa.ResourceManager()
CLD1015 : pyvisa.resources.usb.USBInstrument = resource_manager.open_resource(port) # type: ignore
CLD1015.query("*IDN?") 

# %% [markdown]
# ### Piezo Stage

# %%
import MDT_COMMAND_LIB as mdt

# %% [markdown]
# ## Equipment Control

# %% [markdown]
# ### Laser and TEC ON

# %%
CLD1015.write("OUTPut2:STATe 1")
time.sleep(4)
CLD1015.write("OUTPut1:STATe 1")

# %% [markdown]
# ### Laser and TEC OFF

# %%
CLD1015.write("OUTPut2:STATe 0")
time.sleep(4)
CLD1015.write("OUTPut1:STATe 0")

# %% [markdown]
# ### Laser Status

# %%
int(CLD1015.query("OUTPut1:STATe?")[:-1]),int(CLD1015.query("OUTPut2:STATe?")[:-1])

# %% [markdown]
# ### Laser Current ON

# %%
assert int(CLD1015.query("OUTPut2:STATe?")[:-1]) == 1
CLD1015.write("OUTPut1:STATe 1")

# %% [markdown]
# ### Laser Current OFF

# %%
CLD1015.write("OUTPut1:STATe 0")

# %% [markdown]
# ### Piezo Connection (need to close serial port!)

# %%
serialNum = mdt.mdtListDevices()[0][0]
hdl = mdt.mdtOpen(serialNum, 115200, 3)

# %% [markdown]
# ### Close Piezo connection

# %%
mdt.mdtClose(hdl)

# %% [markdown]
# ### Auber PID

# %%
instrument:minimalmodbus.Instrument = minimalmodbus.Instrument('COM5', 3)  # port name, slave address (in decimal)
instrument.serial.baudrate = 9600 # type: ignore
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 0.5  # seconds
instrument.mode = minimalmodbus.MODE_RTU  # rtu or ascii mode
instrument.clear_buffers_before_each_call = True
instrument.close_port_after_each_call = True
instrument.debug = False  # Set to True to see debug output
instrument.serial.xonxoff = False  # disable software flow control
instrument.serial.rtscts = False  # disable hardware (RTS/CTS) flow control
instrument.serial.dsrdtr = False  # disable hardware (DSR/DTR) flow control
#instrument.close_port_after_each_call = True
temperature = instrument.read_register(1000, 0)  # Registernumber, number of decimals




# %% [markdown]
# ### Auber PID NI DAQ

# %%
import nidaqmx
from nidaqmx.constants import ThermocoupleType, TemperatureUnits

with nidaqmx.Task() as task:
    task.ai_channels.add_ai_thrmcpl_chan(
        "Dev1/ai0", units=TemperatureUnits.DEG_C, thermocouple_type=ThermocoupleType.K
    )

    data = task.read()
    print(f"Acquired data: {data:f}")

# %% [markdown]
# ## Functions

# %% [markdown]
# ### Laser Command

# %%
class LaserDriver:

    def getTemp() -> float:
        return float(CLD1015.query("SENSe2:DATA?")[:-1])
    
    def setTemp(temp:float):
        CLD1015.write("SOURce2:TEMP:SPO " + str(temp))
        return temp
    
    def getCurr() -> float:
        return float(CLD1015.query("SENSe3?")[:-1])
    
    def setCurr(current:float):
        CLD1015.write("SOURce1:CURR " + str(current))
        return current
    
    def getPDCurr() -> float:
        return float(CLD1015.query("SENSe1?")[:-1])

# %% [markdown]
# ### PD readings

# %%
class photoDiode:

    def getVoltage() -> float:
        """Read the voltage from the photodiode."""
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
            task.timing.cfg_samp_clk_timing(1000.0, sample_mode=AcquisitionType.FINITE, samps_per_chan=200)
            data = task.read(READ_ALL_AVAILABLE)

        return np.mean(data)

# %% [markdown]
# ### Galvo Rasterization

# %%
def daqDriver(Vset,dwell_time):
    """
    Function to perform a DAQ operation with the specified voltage setpoint and dwell time.
    The function writes the voltage data to the analog output and reads the photon counts from the counter input.
    The tasks are synchronized using the sample clock from the analog output task. 
    The function returns the photon counts read from the counter input.
    """

    # Active edge for counter (Edge.RISING or Edge.FALLING)
    counter_active_edge = Edge.RISING  # Change to Edge.FALLING if needed

    # Create tasks for analog output and counter input
    with nidaqmx.Task() as ao_task, nidaqmx.Task() as ci_task, nidaqmx.Task() as ai_task:

        # Add analog output channels for galvo mirrors
        ao_task.ao_channels.add_ao_voltage_chan(
            "Dev1/ao0", name_to_assign_to_channel='X_Galvo')
        ao_task.ao_channels.add_ao_voltage_chan(
            "Dev1/ao1", name_to_assign_to_channel='Y_Galvo')

        # Add counter input channel for photon counting
        ci_channel = ci_task.ci_channels.add_ci_count_edges_chan(
            "Dev1/ctr0", name_to_assign_to_channel='Photon_Count',
            initial_count=0, count_direction=CountDirection.COUNT_UP,
            edge=counter_active_edge)  # Set the active edge here

        # Add analog input channel for reading photodiode voltage
        # ai_task.ai_channels.add_ai_voltage_chan("Dev1/ai0", name_to_assign_to_channel='Photodiode_Voltage')

        # Configure timing for analog output task
        ao_task.timing.cfg_samp_clk_timing(
            rate=1/dwell_time,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=Vset.shape[1])

        # Configure timing for counter input task
        # Use the sample clock from the AO task to ensure synchronization
        ci_task.timing.cfg_samp_clk_timing(
            rate=1/dwell_time,
            source="/Dev1/ao/SampleClock",  # Use the AO task's sample clock
            active_edge=Edge.RISING,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=Vset.shape[1])
        
        '''
        # Configure timing for analog input task
        ai_task.timing.cfg_samp_clk_timing(
            rate=1/dwell_time,
            source="/Dev1/ao/SampleClock",  # Use the AO task's sample clock
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=Vset.shape[1])
        '''
        
        ci_channel.ci_count_edges_term = "/Dev1/PFI0"  # Set the counter input terminal

        """
        # Configure the CI task to wait for the AO start trigger
        ci_task.triggers.start_trigger.cfg_dig_edge_start_trig(
            trigger_source="/Dev1/ao/StartTrigger",
            trigger_edge=Edge.RISING
        )
        """
        
        # Write voltage data to the buffer for the AO task
        ao_task.write(Vset, auto_start=False)

        # Start the counter input task first
        ci_task.start()

        # Start the AO task
        ao_task.start()

        # Start the analog input task
        #ai_task.start()

        # Read the photon counts
        # Since counts are cumulative, we'll get an array of counts
        counts = ci_task.read(number_of_samples_per_channel=Vset.shape[1],timeout=-1)
        # Read the photodiode voltage
        #pd_voltage = ai_task.read(number_of_samples_per_channel=Vset.shape[1], timeout=-1)

        # Wait for tasks to complete
        ao_task.wait_until_done(timeout=-1)
        ci_task.wait_until_done(timeout=-1)
        #ai_task.wait_until_done(timeout=-1)

    return counts

# %%
def daqScan(x_px, y_px, xlims, ylims, dwell_time, accumulation = 1):


    v_x = np.linspace(xlims[0],xlims[1], x_px)
    v_y = np.linspace(ylims[0],ylims[1], y_px)
    Vx, Vy = np.meshgrid(v_x, v_y, indexing='xy')

    Vx[1::2] = np.fliplr(Vx[1::2])

    
    Vx = Vx.ravel()
    Vy = Vy.ravel()

    Vset = np.stack((Vx, Vy))

    # Repeat the scan for accumulation
    if accumulation > 1:
        VsetFull = np.zeros((2, x_px * y_px * accumulation))

        for i in range(accumulation):
            if i % 2 == 1:
                # Flip the x-axis for odd accumulations
                VsetFull[:, i * x_px * y_px:(i + 1) * x_px * y_px] = np.flip(Vset, axis=1)
            else:
                VsetFull[:, i * x_px * y_px:(i + 1) * x_px * y_px] = Vset       

        counts = daqDriver(VsetFull, dwell_time)
            
    else:
        counts = daqDriver(Vset, dwell_time)

    counts = np.insert(np.diff(counts),0,counts[0])

    # Reconstruct the counts array into images
    if accumulation > 1:
        newCounts = np.zeros((accumulation, x_px , y_px))
        for i in range(accumulation):
            
            if i % 2 == 1:
                # Flip the x-axis for odd accumulations
                frame = np.flip(counts[i * x_px * y_px:(i + 1) * x_px * y_px])
            else:
                frame = counts[i * x_px * y_px:(i + 1) * x_px * y_px]
            frame = frame.reshape(x_px, y_px)
            frame[1::2] = np.fliplr(frame[1::2])
            newCounts[i, :,:] = frame

        daqDriver(np.array([[0,0], [0,0]]), 0.01) # Reset the DAQ to zero
        return newCounts
    else:
        # Calculate counts per sample (counts at each position)
        counts = counts.reshape(x_px, y_px)
        counts[1::2] = np.fliplr(counts[1::2])
        counts[0,0] = 0
        
    daqDriver(np.array([[0,0], [0,0]]), 0.01) # Reset the DAQ to zero
    return counts

# %%

def simDaqDriver(Vset, dwell_time):
    """
    Simulated DAQ driver function for testing purposes.
    This function generates random counts based on the input voltage setpoint and dwell time.
    """
    # Simulate photon counts based on the voltage setpoint

    # + np.power(Vset[1,:],2)
    count = 0
    counts = np.zeros(Vset.shape[1])
    for i in range(Vset.shape[1]):
        counts[i] = count
        count += np.power(Vset[0,:],2)[i]
    return counts

# %% [markdown]
# ### Two Area Lock-in

# %%
def twoAreaInterlacingDaqScan(px1, px2, xlims1, ylims1,xlims2, ylims2, dwell_time , ifSimulate=False):
    v_x1 = np.linspace(xlims1[0],xlims1[1], px1[0])
    v_y1 = np.linspace(ylims1[0],ylims1[1], px1[1])
    Vx1, Vy1 = np.meshgrid(v_x1, v_y1, indexing='xy')

    Vx1[1::2] = np.fliplr(Vx1[1::2]) #make into meandering path
    Vx1 = Vx1.ravel()
    Vy1 = Vy1.ravel()

    v_x2 = np.linspace(xlims2[0],xlims2[1], px2[0])
    v_y2 = np.linspace(ylims2[0],ylims2[1], px2[1])
    Vx2, Vy2 = np.meshgrid(v_x2, v_y2, indexing='xy')

    Vx2[1::2] = np.fliplr(Vx2[1::2]) #make into meandering path
    Vx2 = Vx2.ravel()
    Vy2 = Vy2.ravel()

    # interlace the two sets of voltages
    jointVx = np.empty(((Vx1.size + Vx2.size)*2,), dtype=Vx1.dtype)
    jointVx[0::4] = Vx1
    jointVx[1::4] = Vx1
    jointVx[2::4] = Vx2
    jointVx[3::4] = Vx2

    jointVy = np.empty(((Vy1.size + Vy2.size)*2,), dtype=Vy1.dtype)
    jointVy[0::4] = Vy1
    jointVy[1::4] = Vy1
    jointVy[2::4] = Vy2
    jointVy[3::4] = Vy2

    jointVx = np.append(jointVx, 0)
    jointVy = np.append(jointVy, 0)
    Vset = np.stack((jointVx, jointVy))

    if ifSimulate:
        counts = simDaqDriver(Vset, dwell_time)
        print("Simulated counts:", counts)
    else:
        counts = daqDriver(Vset, dwell_time)
    
    counts = counts[:-1]

    counts = np.insert(np.diff(counts),0,counts[0],axis=0)

    counts1 = counts[1::4]
    counts2 = counts[3::4]

    # Calculate counts per sample (counts at each position)
    counts1 = counts1.reshape(*px1)
    counts1[1::2] = np.fliplr(counts1[1::2])
    
    counts2 = counts2.reshape(*px2)
    counts2[1::2] = np.fliplr(counts2[1::2])
    return counts1,counts2

# %% [markdown]
# ### MISC

# %%
def calculate_square_pixels(xlims, ylims, base_px=100):
    x_range = abs(xlims[1] - xlims[0])
    y_range = abs(ylims[1] - ylims[0])
    
    if x_range > y_range:
        x_px = base_px
        y_px = int(base_px * (y_range / x_range))
    else:
        y_px = base_px
        x_px = int(base_px * (x_range / y_range))
    
    return x_px, y_px

# %%
def makeConfigSquare(config,base_px=100):
    xlims = config['xlims']
    ylims = config['ylims']
    
    x_px, y_px = calculate_square_pixels(xlims, ylims, base_px)
    
    config['x_px'] = x_px
    config['y_px'] = y_px
    
    return config

# %%
def timeOfConfig(config,multiplier=1):
    x_px = config['x_px']
    y_px = config['y_px']    
    dwell_time = config['dwell_time']
    accu = config['accumulation']

    time = (x_px * y_px) * dwell_time * accu * multiplier
    frameTime = (x_px * y_px) * dwell_time 
    
    print("Total time for scan: ", str(datetime.timedelta(seconds=time)))
    print("Frame Time: ", str(datetime.timedelta(seconds=frameTime)))

    return config

# %%
def rectToLims(rect,config):
    """
    Convert rectangle coordinates to limits.
    rect: (x1, y1, x2, y2)
    """
    (x1, y1), (x2, y2) = rect
    config['xlims'] = (x1, x2)
    config['ylims'] = (y1, y2)
    return config

# %% [markdown]
# ### Data Saving Wrapper

# %% [markdown]
# #### Parameters

# %%
laserCurrent = Parameter(name="diodeCurrent", label="Current", unit="A", set_cmd=LaserDriver.setCurr, get_cmd=LaserDriver.getCurr)
laserSPCurrent = Parameter(name="diodeCurrent", label="Current", unit="A", set_cmd=LaserDriver.setCurr, get_cmd=LaserDriver.getCurr)

laserTemp = Parameter(name="diodeTemp", label="Current", unit="V", set_cmd=LaserDriver.setTemp, get_cmd=LaserDriver.getTemp)
laserTemp = Parameter(name="diodeTemp", label="Current", unit="V", set_cmd=LaserDriver.setTemp, get_cmd=LaserDriver.getTemp)

laserPDCurr = Parameter(name="diodePDCurr", label="Current", unit="A", get_cmd=LaserDriver.getPDCurr)
extPDVoltage = Parameter(name="extPDVoltage", label="Voltage", unit="V", get_cmd=photoDiode.getVoltage)

# %% [markdown]
# #### Single Area Saved

# %%
def daqScanSaved(config: dict,bypass_check: bool = False):
    """
    Save confocal scan data with QCoDeS, including laser parameters.

    Parameters:
        counts (numpy.ndarray): The confocal scan data.
        laser_current (float): The laser current in Amperes.
        laser_temperature (float): The laser temperature in Celsius.
        experiment_name (str): The name of the experiment.
        sample_name (str): The name of the sample.
    """
    if not bypass_check:
        # make sure the SPAD is on
        assert np.sum(daqDriver(np.array([[0, 0], [0, 0]]), 0.001)).item() != 0
        # make sure the laser is on
        assert int(CLD1015.query("OUTPut1:STATe?")[:-1]) == 1, "Laser is not on. Please turn on the laser before running the scan."


    exp = load_or_create_experiment(experiment_name=config["experiment_name"], sample_name=config["sample_name"])

    countsPara = Parameter(name="counts", label="Photon Counts", unit="counts")

    # Create a measurement
    meas = Measurement(exp=exp, name=config["measurement_name"])
    meas.register_parameter(countsPara, paramtype = "array")
    meas.register_parameter(laserCurrent)
    meas.register_parameter(laserTemp)
    meas.register_parameter(laserPDCurr)
    meas.register_parameter(extPDVoltage)

    # Save the data
    with meas.run() as datasaver:
        # Get the laser current and temperature
        measLaserCurrent = laserCurrent.get()
        measLaserTemp = laserTemp.get()

        # Call daqScan function to get the counts

        counts = daqScan(config["x_px"], config["y_px"], config["xlims"], config["ylims"], config["dwell_time"],accumulation=config["accumulation"])

        datasaver.add_result(
            (countsPara, counts),
            (laserCurrent, measLaserCurrent),
            (laserTemp, measLaserTemp),
            (laserPDCurr, laserPDCurr.get()),
            (extPDVoltage, extPDVoltage.get())
            )

    for key in config.keys():
        if type(config[key]) is tuple or type(config[key]) is list:
            for i in range(len(config[key])):
                datasaver.dataset.add_metadata(key + str(i), config[key][i])
        else:
            datasaver.dataset.add_metadata(key, config[key])

    datasaver.dataset.add_metadata("laserCurrent", measLaserCurrent)
    datasaver.dataset.add_metadata("laserTemperature", measLaserTemp)
    
    print(f"Data saved to dataset {datasaver.dataset}")
    return datasaver.dataset

# %% [markdown]
# #### Two Area Saved

# %%
twoAreaExampleConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (0.0114, 0.0591),
    "ylims1": (-0.0666, -0.0139), 
    "xlims2": (-0.0702, -0.0260),
    "ylims2": (-0.0368, 0.0108), 
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "Flake scan for locating",
    "comment": "test",
}

# %%
def twoAreaSaved(config):
    # Load or create the experiment
    exp = load_or_create_experiment(experiment_name=config["experiment_name"], sample_name=config["sample_name"])

    counts1Para = Parameter(name="counts1", label="Photon Counts", unit="counts")
    counts2Para = Parameter(name="counts2", label="Photon Counts", unit="counts")

    # Create a measurement
    meas = Measurement(exp=exp, name=config["measurement_name"])
    meas.register_parameter(counts1Para, paramtype = "array")
    meas.register_parameter(counts2Para, paramtype = "array")
    meas.register_parameter(laserCurrent)
    meas.register_parameter(laserTemp)


    # Save the data
    with meas.run() as datasaver:
        # Get the laser current and temperature
        measLaserCurrent = laserCurrent.get()
        measLaserTemp = laserTemp.get()

        # Call daqScan function to get the counts
        counts1,counts2 = twoAreaInterlacingDaqScan(
            config["px1"], config["px2"], 
            config["xlims1"], config["ylims1"],
            config["xlims2"],config["ylims2"],
            config["dwell_time"]
            )

        datasaver.add_result(
            (counts1Para, counts1),
            (counts2Para, counts2),
            (laserCurrent, measLaserCurrent),
            (laserTemp, measLaserTemp)
            )

    for key in config.keys():
        if type(config[key]) is tuple or type(config[key]) is list:
            if key != "laserSetpoints":
    
                for i in range(len(config[key])):
                    datasaver.dataset.add_metadata(key + str(i), config[key][i])
                
        else:
            datasaver.dataset.add_metadata(key, config[key])
            
    print(f"Data saved to dataset {datasaver.dataset}")
    return datasaver.dataset

# %% [markdown]
# #### Two area lock-in sweep

# %%
twoAreaSweepExampleConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (0.0114, 0.0591),
    "ylims1": (-0.0666, -0.0139), 
    "xlims2": (-0.0702, -0.0260),
    "ylims2": (-0.0368, 0.0108), 
    "laserSetpoints": [(15,0.2135,0.1),(15,0.1935,0.1),(15,0.1835,0.1)],
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "Flake scan for locating",
    "comment": "test",
}

# %%
def twoAreaSweepSaved(config):

    # make sure the SPAD is on
    assert np.sum(daqDriver(np.array([[0, 0], [0, 0]]), 0.001)).item() != 0

    # Load or create the experiment
    exp = load_or_create_experiment(experiment_name=config["experiment_name"], sample_name=config["sample_name"])

    counts1Para = Parameter(name="counts1", label="Photon Counts", unit="counts")
    counts2Para = Parameter(name="counts2", label="Photon Counts", unit="counts")

    # Create a measurement
    meas = Measurement(exp=exp, name=config["measurement_name"])
    meas.register_parameter(counts1Para, paramtype = "array")
    meas.register_parameter(counts2Para, paramtype = "array")
    meas.register_parameter(laserCurrent)
    meas.register_parameter(laserTemp)

    laserSeptpoints = config["laserSetpoints"]

    
    # Save the data
    with meas.run() as datasaver:

        for setPoint in laserSeptpoints:
            # Set the laser current and temperature
            setTemp(setPoint[0])
            setCurr(setPoint[1])
            time.sleep(setPoint[2])

            # Get the laser current and temperature
            measLaserCurrent = laserCurrent.get()
            measLaserTemp = laserTemp.get()

            # Call daqScan function to get the counts
            counts1,counts2 = twoAreaInterlacingDaqScan(
                config["px1"], config["px2"], 
                config["xlims1"], config["ylims1"],
                config["xlims2"],config["ylims2"],
                config["dwell_time"]
                )

            datasaver.add_result(
                (counts1Para, counts1),
                (counts2Para, counts2),
                (laserCurrent, measLaserCurrent),
                (laserTemp, measLaserTemp)
                )

    for key in config.keys():
        if type(config[key]) is tuple or type(config[key]) is list:
            if key != "laserSetpoints":
    
                for i in range(len(config[key])):
                    datasaver.dataset.add_metadata(key + str(i), config[key][i])
                
        else:
            datasaver.dataset.add_metadata(key, config[key])
            
    print(f"Data saved to dataset {datasaver.dataset}")
    return datasaver.dataset

# %% [markdown]
# #### Single Area Sweeping

# %%
def singleSweepSaved(config):

        # make sure the SPAD is on
    assert np.sum(daqDriver(np.array([[0, 0], [0, 0]]), 0.1)).item() != 0
    
    # make sure the laser is on
    assert int(CLD1015.query("OUTPut1:STATe?")[:-1]) == 1, "Laser is not on. Please turn on the laser before running the scan."

    # Load or create the experiment
    exp = load_or_create_experiment(experiment_name=config["experiment_name"], sample_name=config["sample_name"])

    countsPara = Parameter(name="counts", label="Photon Counts", unit="counts")

    # Create a measurement
    meas = Measurement(exp=exp, name=config["measurement_name"])
    meas.register_parameter(countsPara, paramtype = "array")
    meas.register_parameter(laserCurrent)
    meas.register_parameter(laserTemp)
    meas.register_parameter(laserPDCurr)
    meas.register_parameter(extPDVoltage)

    laserSeptpoints = config["laserSetpoints"]

    # Save the data
    with meas.run() as datasaver:

        for setPoint in laserSeptpoints:
            # Set the laser current and temperature
            LaserDriver.setTemp(setPoint[0])
            LaserDriver.setCurr(setPoint[1])
            time.sleep(setPoint[2])

            # Get the laser current and temperature
            measLaserCurrent = laserCurrent.get()
            measLaserTemp = laserTemp.get()

            # Call daqScan function to get the counts
            counts = daqScan(
                config["x_px"], config["y_px"], 
                config["xlims"], config["ylims"],
                config["dwell_time"]
                )

            datasaver.add_result(
                (countsPara, counts),
                (laserCurrent, measLaserCurrent),
                (laserTemp, measLaserTemp),
                (laserPDCurr, laserPDCurr.get()),
                (extPDVoltage, extPDVoltage.get())
                )

    for key in config.keys():
        if type(config[key]) is tuple or type(config[key]) is list:
            if key != "laserSetpoints":
    
                for i in range(len(config[key])):
                    datasaver.dataset.add_metadata(key + str(i), config[key][i])
                
        else:
            datasaver.dataset.add_metadata(key, config[key])
            
    print(f"Data saved to dataset {datasaver.dataset}")
    return datasaver.dataset

# %% [markdown]
# #### Just Laser Sweep

# %%
def laserSweep(config):
    """
    Save laser sweep data with QCoDeS, without scanning.

    Parameters:
        config (dict): Configuration dictionary containing experiment parameters.
    """
    # make sure the laser is on
    assert int(CLD1015.query("OUTPut1:STATe?")[:-1]) == 1, "Laser is not on. Please turn on the laser before running the scan."

    # Load or create the experiment
    exp = load_or_create_experiment(experiment_name=config["experiment_name"], sample_name=config["sample_name"])

    # Create a measurement
    meas = Measurement(exp=exp, name=config["measurement_name"])
    meas.register_parameter(laserCurrent)
    meas.register_parameter(laserTemp)
    meas.register_parameter(laserPDCurr)
    meas.register_parameter(extPDVoltage)

    laserSetpoints = config["laserSetpoints"]
    
    # Save the data
    with meas.run() as datasaver:
        for setPoint in laserSetpoints:
            # Set the laser current and temperature
            LaserDriver.setTemp(setPoint[0])
            LaserDriver.setCurr(setPoint[1])
            time.sleep(setPoint[2])

            # Get the laser parameters
            measLaserCurrent = laserCurrent.get()
            measLaserTemp = laserTemp.get()

            datasaver.add_result(
                (laserCurrent, measLaserCurrent),
                (laserTemp, measLaserTemp),
                (laserPDCurr, laserPDCurr.get()),
                (extPDVoltage, extPDVoltage.get())
            )

    for key in config.keys():
        if type(config[key]) is tuple or type(config[key]) is list:
            if key != "laserSetpoints":
                for i in range(len(config[key])):
                    datasaver.dataset.add_metadata(key + str(i), config[key][i])
        else:
            datasaver.dataset.add_metadata(key, config[key])
            
    print(f"Data saved to dataset {datasaver.dataset}")
    return datasaver.dataset

# %% [markdown]
# ### Plotting

# %%
def live_plot(output_array):
    plt.clf()  # Clear the current figure
    plt.imshow(output_array, cmap='hot')
    plt.colorbar(label='Counts')
    plt.tight_layout()
    
    # Display the plot
    clear_output(wait=True)
    display(plt.gcf())

# %%
def quickLookData(counts):
    plt.clf()  # Clear the current figure
    plt.imshow(counts, cmap='hot')
    plt.colorbar(label='Counts')
    plt.tight_layout()

# %% [markdown]
# ## Config Library

# %% [markdown]
# ### Signle Scan

# %%
flakeConfig = {
    "x_px": 100, 
    "y_px": 100, 
    "xlims": (-1, 1),
    "ylims": (0, 0.27), 
    "dwell_time": 0.1,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated confocal scan",
    "sample_name": "S32",
    "measurement_name": "Background scan at RT",
    "comment": "90C",
}

midCircleConfig = {
    "x_px": 100, 
    "y_px": 100, 
    "xlims": (0.3711, 0.4099),
    "ylims": (-0.1578, -0.1005), 
    "dwell_time": 0.0001,
    "ND_Filter": [4,3,1],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "test",
    "comment": "test",
}

uciLogoConfig = {
    "x_px": 100, 
    "y_px": 100, 
    "xlims": (-0.0644, 0.0269),
    "ylims": (-0.1576, -0.0660), 
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "experiment_name": "Code test",
    "sample_name": "S32",
    "measurement_name": "test",
    "comment": "test",
}

FOVConfig = {
    "x_px": 100, 
    "y_px": 100, 
    "xlims": (-2, 2),
    "ylims": (-2, 2), 
    "dwell_time": 0.1,
    "ND_Filter": [4,3,2,1],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "after fiddling with focusing laser ",
    "comment": "",
}

# %% [markdown]
# ## Realtime SPAD

# %%
try:
    while True:
        dewell_time = 1
        counts = daqDriver(np.array([[0.5,0], [0.5,0]]), dewell_time)
        print(f"Counts/s : {np.average(counts[1:]) / dewell_time}", end="\r")
except KeyboardInterrupt:
    pass

# %%
laserTemp(15)

# %% [markdown]
# ## Region Select

# %%
%matplotlib widget

import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import numpy as np
from PIL import Image

# Load your image
try:
    image = shifted_counts
except FileNotFoundError:
    # Create a dummy image if 'your_image.png' is not found
    print("Dummy image created as 'your_image.png' was not found.")
    image = np.random.rand(200, 300, 3)

# Global variables to store the coordinates
selectionCoordinates = None

def onselect(eclick, erelease):
    """
    eclick and erelease are the press and release events.
    """
    global selectionCoordinates
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    selectionCoordinates = (x1, y1, x2, y2)
    print(f"Selected region coordinates (x1, y1, x2, y2): {selectionCoordinates}")

def toggle_selector(event):
    if event.key in ['q', 'Q']:
        if rectangle_selector.active:
            rectangle_selector.set_active(False)
            print("Rectangle selector deactivated.")
    if event.key in ['a', 'A']:
        rectangle_selector.set_active(True)
        print("Rectangle selector activated.")

fig, ax = plt.subplots()
ax.imshow(image, origin='lower', extent=[xd.attrs["xlims0"],xd.attrs["xlims1"], xd.attrs["ylims0"], xd.attrs["ylims1"]],cmap='hot', aspect='auto')

rectangle_selector = RectangleSelector(
    ax, onselect,
    useblit=True,
    button=[1],  # Left mouse button
    minspanx=5, minspany=5,
    spancoords='pixels',
    interactive=True
)

# Connect the key press event to the toggle_selector function
fig.canvas.mpl_connect('key_press_event', toggle_selector)

plt.show()

# %%
selectionCoordinates = ((float(selectionCoordinates[0]),float(selectionCoordinates[1])),(float(selectionCoordinates[2]),float(selectionCoordinates[3])))

# %% [markdown]
# ## Single Scan

# %%
flakeConfig =timeOfConfig( {"x_px": 100, "y_px": 100, 
    "xlims": (-1, 1),"ylims": (-1, 1), 
    "dwell_time": 0.001, "accumulation" : 1,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated confocal scan",
    "sample_name": "S32",
    "measurement_name": "Background scan at RT",
    "comment": "90C",
})

# %%
flakeConfig = rectToLims(selectionCoordinates,timeOfConfig( {"x_px": 30, "y_px": 30, 
    "xlims": (-1, 1),"ylims": (-1, 1), 
    "dwell_time": 0.01, "accumulation" : 10,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated confocal scan",
    "sample_name": "S32",
    "measurement_name": "Background scan at RT",
    "comment": "90C",
}))

# %%
flakeConfig = rectToLims(((0.589 -0.025,-0.125),(0.769+0.04,0.075)),timeOfConfig( {"x_px": 100, "y_px": 100, 
    "xlims": (-1, 1),"ylims": (-1, 1), 
    "dwell_time": 0.001, "accumulation" : 10,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated confocal scan",
    "sample_name": "S32",
    "measurement_name": "Background scan at RT",
    "comment": "90C",
}))

# %%
dataset = daqScan(500, 500, (-0.3, 0.5), (-0.25, 0.65), 0.001, accumulation=1)

# %%
plt.imshow(dataset, cmap='hot')
plt.show()

# %%
dataset = daqScanSaved(flakeConfig)

# %%
%matplotlib widget

#dataset = load_by_id(173)
logged = 0
averageOverAcc = 1
shiftCorrection = 2

xd = dataset.to_xarray_dataset()
# Extract raw data from the dataset

counts = xd['counts'].values.reshape(dataset.get_metadata("accumulation"),xd.attrs["x_px"], xd.attrs["y_px"])/dataset.get_metadata("dwell_time")

# Create a heatmap
plt.figure(figsize=(7, 5))
#counts = counts[1::2,:,:]
if averageOverAcc:
    shifted_counts = counts.copy()
    shifted_counts[1::2,0::2] = np.roll(shifted_counts[1::2,0::2], shift=shiftCorrection, axis=2)
    shifted_counts[0::2,1::2] = np.roll(shifted_counts[0::2,1::2], shift=shiftCorrection, axis=2)
    shifted_counts = np.average(shifted_counts,axis=0)
else:
    shifted_counts = counts[0].copy()
#shifted_counts[1::2] = np.roll(shifted_counts[1::2], shift=2, axis=1)
if logged:
    plt.imshow(np.log10(shifted_counts),extent=[xd.attrs["xlims0"],xd.attrs["xlims1"], xd.attrs["ylims0"], xd.attrs["ylims1"]], 
            origin='lower', cmap='hot', aspect='auto')
    plt.colorbar(label='Log10 Counts/s')
else:
    plt.imshow(shifted_counts, extent=[xd.attrs["xlims0"],xd.attrs["xlims1"], xd.attrs["ylims0"], xd.attrs["ylims1"]], 
            origin='lower', cmap='hot', aspect='auto',vmax=2000)
    plt.colorbar(label='Counts/s')    

plt.xlabel('X Position (V)')
plt.ylabel('Y Position (V)')
#plt.title('Heatmap of Photon Counts')
plt.tight_layout()
plt.show()

# %%
counts[1::2,:,:].shape

# %% [markdown]
# ## Single Sweep

# %%
flakeConfig = timeOfConfig({"x_px": 100, "y_px": 100, 
    "xlims": (0.2793, 0.3205),"ylims": (0.329, 0.3603), 
    "dwell_time": 0.001, "accumulation" : 10,
    "ND_Filter": [4],
    "experiment_name": "TIRF illuminated confocal scan",
    "sample_name": "S32",
    "measurement_name": "Background scan at RT",
    "comment": "100C",},multiplier=40)

def linearSweep(N = 5,waitTime = 0.5 ,config = flakeConfig, currentSPRange = (0.2,0.225), tempSPRange = (15,15)):

    if tempSPRange[0] == tempSPRange[1]:

        currentSetpoints = np.linspace(currentSPRange[0], currentSPRange[1], N)
        #currentSetpoints = np.array([0.2162,0.2154,0.2168,0.2214,0.2022])
        currentSetpoints = np.repeat(currentSetpoints, config["accumulation"])
        temperatureSetpoints = np.linspace(tempSPRange[0], tempSPRange[1], N)
        temperatureSetpoints = np.repeat(temperatureSetpoints, config["accumulation"])

        laserSetpoints = []
        for i in range(N*config["accumulation"]):
            laserSetpoints.append((temperatureSetpoints[i],currentSetpoints[i],waitTime))
        config["laserSetpoints"] = laserSetpoints
        
        return singleSweepSaved(config)

# %%
dataset = linearSweep()

# %%


# %%
xd = dataset.to_xarray_dataset()
# Extract raw data from the dataset 

counts = xd['counts'].values.reshape(xd.attrs["x_px"], xd.attrs["y_px"],1500)/dataset.get_metadata("dwell_time")

accCounts = np.average(counts,axis=(0,1))

laserCurr = xd['diodeCurrent'][~np.isnan(xd['diodeCurrent'])]
PDVolatge = xd['extPDVoltage'][~np.isnan(xd['extPDVoltage'])]

fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharex='all')

axes[0].plot(laserCurr, PDVolatge, marker='o')

axes[1].plot(laserCurr, accCounts, marker='o')


# %%
xd['extPDVoltage']

# %%
quickLookData(np.average(counts,2))

# %% [markdown]
# ## Rb Ref Sweep

# %%
RbRefConfig = {"experiment_name": "Rb Ref Lockin",
    "sample_name": "Ref",
    "measurement_name": "Rb Ref Lockin",
    "Cell_temperature_setpoint": 21,
    "comment": "90C"}

def RbRefLockinSweeep(N = 300,accuTime = 0.1,waitTime = 0.5 ,config = RbRefConfig, currentSPRange = (0.2,0.225), tempSPRange = (15,15)):

    if tempSPRange[0] == tempSPRange[1]:
        currentSetpoints = np.linspace(currentSPRange[0], currentSPRange[1], N)
        temperatureSetpoints = np.linspace(tempSPRange[0], tempSPRange[1], N)
        laserSetpoints = []
        for i in range(N):
            laserSetpoints.append((temperatureSetpoints[i],currentSetpoints[i],waitTime))
        config["laserSetpoints"] = laserSetpoints
        
        return laserSweep(config)

# %%
ds = RbRefLockinSweeep()

# %%
[0.2162,0.2154,0.2168,0.2214,0.2022]

# %%
ds = load_by_id(108)
xd = ds.to_xarray_dataset()
plt.cla()
plt.plot(xd["diodeCurrent"],xd['extPDVoltage'])
plt.xlabel('Diode Current (A)')
plt.ylabel('Photodiode Voltage (V)')
plt.title('Rb Reference Lock-in Sweep')
plt.show()

# %% [markdown]
# ## Two Area Single

# %%
(-0.0261,-0.0315)
(-0.0007,-0.004)

# %%
twoAreaExampleConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (0.0114, 0.0591),
    "ylims1": (-0.0666, -0.0139), 
    "xlims2": (-0.0702, -0.0260),
    "ylims2": (-0.0368, 0.0108), 
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "Flake scan for locating",
    "comment": "test",
}

# %%
circleAndBlankConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (-0.0702, -0.0260),
    "ylims1": (-0.0368, 0.0108),  
    "xlims2": (-0.0261, -0.0007),
    "ylims2": (-0.0315, -0.004), 
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "middle size circle and blank for contrast",
    "comment": "test",
}

# %%
testConfig = {
    "px1": (5, 5),
    "px2": (5, 5), 
    "xlims1": (1, 5),
    "ylims1": (1, 5), 
    "xlims2": (6, 10),
    "ylims2": (6, 10), 
    "dwell_time": 0.1,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "Flake scan for locating",
    "comment": "test",
}

# %%
dataset = twoAreaSaved(circleAndBlankConfig)

# %%
dataset_id = 31
dataset = load_by_id(dataset_id)
dataset.get_parameter_data()["diodeCurrent"]

# %%
counts1, counts2 = twoAreaInterlacingDaqScan(
    twoAreaExampleConfig["px1"], twoAreaExampleConfig["px2"], 
    twoAreaExampleConfig["xlims1"], twoAreaExampleConfig["ylims1"],
    twoAreaExampleConfig["xlims2"],twoAreaExampleConfig["ylims2"],
    twoAreaExampleConfig["dwell_time"],ifSimulate=False
    )

# %%
fig, axes = plt.subplots(1, 2, figsize=(8, 6))

# Plot the first figure
axes[0].imshow(dataset.get_parameter_data()["counts1"]["counts1"][0], cmap='hot')
axes[0].set_title('Counts1')
axes[0].set_xlabel('X Position')
axes[0].set_ylabel('Y Position')
axes[0].colorbar = plt.colorbar(axes[0].images[0], ax=axes[0], label='Counts')

# Plot the second figure
axes[1].imshow(dataset.get_parameter_data()["counts2"]["counts2"][0], cmap='hot')
axes[1].set_title('Counts2')
axes[1].set_xlabel('X Position')
axes[1].set_ylabel('Y Position')
axes[1].colorbar = plt.colorbar(axes[1].images[0], ax=axes[1], label='Counts')

plt.tight_layout()
plt.show()

# %% [markdown]
# ## Two Area Sweep

# %%
twoAreaSweepExampleConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (0.0114, 0.0591),
    "ylims1": (-0.0666, -0.0139), 
    "xlims2": (-0.0702, -0.0260),
    "ylims2": (-0.0368, 0.0108), 
    "laserSetpoints": [(15,0.2135,0.1),(15,0.1935,0.1),(15,0.1835,0.1)],
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "Flake scan for locating",
    "comment": "test",
}

# %%
circleAndBlankSweepConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (-0.0702, -0.0260),
    "ylims1": (-0.0368, 0.0108),  
    "xlims2": (-0.0261, -0.0007),
    "ylims2": (-0.0315, -0.004), 
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "laserSetpoints": [(15,0.2135,0.1),(15,0.1935,0.1),(15,0.1835,0.1)],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "middle size circle and blank for contrast",
    "comment": "test",
}

# %%
circleAndBlankSweep54CConfig = {
    "px1": (30, 30),
    "px2": (30, 30), 
    "xlims1": (-0.1044, -0.0717),
    "ylims1": (0.0159, 0.0503),  
    "xlims2": (-0.0593, -0.0317),
    "ylims2": (0.0199, 0.0434), 
    "dwell_time": 0.01,
    "ND_Filter": [4,3],
    "laserSetpoints": [(15,0.2135,0.1),(15,0.1935,0.1),(15,0.1835,0.1)],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "middle size circle and blank for contrast",
    "comment": "test",
}

# %%
zone1 = ((0.1050,0.0861),(0.1050,0.0861))
zone2 = ((0.1050,0.0861),(0.1050,0.0861))

circleAndBlankSweep90CConfig = {
    "px1": (2, 2),
    "px2": (2, 2), 
    "xlims1": (zone1[0][0], zone1[1][0]),
    "ylims1": (zone1[0][1],zone1[1][1]),  
    "xlims2": (zone2[0][0], zone2[1][0]),
    "ylims2": (zone2[0][1], zone2[1][1]), 
    "dwell_time": 1,
    "ND_Filter": [4,3,2],
    "laserSetpoints": [(15,0.2135,0.1),(15,0.1935,0.1),(15,0.1835,0.1)],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "single point sweep inside hexagon at 90C",
    "comment": "test",
}

# %%
zone1 = ((0.3356,-0.0419),(0.3356,-0.0419))
zone2 = ((0.3336,-0.0343),(0.3336,-0.0343))
circleAndBlankSweep110CConfig = {
    "px1": (2, 2),
    "px2": (2, 2), 
    "xlims1": (zone1[0][0], zone1[1][0]),
    "ylims1": (zone1[0][1],zone1[1][1]),  
    "xlims2": (zone2[0][0], zone2[1][0]),
    "ylims2": (zone2[0][1], zone2[1][1]), 
    "dwell_time": 2,
    "ND_Filter": [4,3,1],
    "laserSetpoints": [(15,0.2135,0.1),(15,0.1935,0.1),(15,0.1835,0.1)],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "single point sweep inside U at the back at 110C, extended sweep range",
    "comment": "test",
}

# %%
config = circleAndBlankSweep110CConfig
N = 200


currentSetpoints = np.linspace(0.24, 0.18, N)
temperatureSetpoints = np.linspace(15, 15, N)
laserSetpoints = []
for i in range(N):
    laserSetpoints.append((temperatureSetpoints[i],currentSetpoints[i],0.1))
config["laserSetpoints"] = laserSetpoints
dataset = twoAreaSweepSaved(config)

# %%
laserCurrent()

# %%
config = circleAndBlankSweep68CConfig

zone1 = ((-0.0207,0.0211),(-0.0092,0.0390))
zone2 = ((-0.0098,-0.0141),(0.0071,0.0107))

circleAndBlankSweep68CConfig = {
    "px1": (20, 20),
    "px2": (20, 20), 
    "xlims1": (zone1[0][0], zone1[1][0]),
    "ylims1": (zone1[0][1],zone1[1][1]),  
    "xlims2": (zone2[0][0], zone2[1][0]),
    "ylims2": (zone2[0][1], zone2[1][1]), 
    "dwell_time": 0.1,
    "ND_Filter": [4,3,2],
    "laserSetpoints": [(15,0.2135,0.1), (15,0.2135,0.1), (15,0.2235,0.1),(15,0.1835,0.1)],
    "experiment_name": "TIRF illuminated RT confocal scan",
    "sample_name": "S32",
    "measurement_name": "middle size circle and blank for contrast at 68C",
    "comment": "test",
}

dataset = twoAreaSweepSaved(config)

# %%
fig, axes = plt.subplots(2, 2, figsize=(10, 5))

# Plot the first figure
axes[0,0].imshow(dataset.get_parameter_data()["counts1"]["counts1"][1], cmap='hot')
axes[0,0].set_title('Counts1')
axes[0,0].set_xlabel('X Position')
axes[0,0].set_ylabel('Y Position')
#axes[0,0].colorbar = plt.colorbar(axes[0].images[0], ax=axes[0], label='Counts')

# Plot the second figure
axes[0,1].imshow(dataset.get_parameter_data()["counts2"]["counts2"][1], cmap='hot')
axes[0,1].set_title('Counts2')
axes[0,1].set_xlabel('X Position')
axes[0,1].set_ylabel('Y Position')
#axes[0,1].colorbar = plt.colorbar(axes[1].images[0], ax=axes[1], label='Counts')

axes[1,0].scatter(currentSetpoints,np.average(dataset.get_parameter_data("counts1")["counts1"]["counts1"]/3,axis=(1,2)))
axes[1,0].set_xlabel("Laser Current (A)")
axes[1,0].set_ylabel("Average Counts per second")

axes[1,1].scatter(currentSetpoints,np.average(dataset.get_parameter_data("counts2")["counts2"]["counts2"]/3,axis=(1,2)))
axes[1,1].set_xlabel("Laser Current (A)")
axes[1,1].set_ylabel("Average Counts per second")

plt.tight_layout()
plt.show()

# %%
plt.figure(figsize=(7, 5))
plt.scatter(currentSetpoints,np.average(dataset.get_parameter_data("counts1")["counts1"]["counts1"],axis=(1,2)) - np.average(dataset.get_parameter_data("counts2")["counts2"]["counts2"],axis=(1,2)))

# %% [markdown]
# ## Continuous imaging

# %%
try:
    total_read = 0
    while True:
        dewell_time = 0.0005
        counts = daqScan(50, 50,(-1, 1),(-1, 1),dewell_time)
        plt.clf()  # Clear the current figure
        plt.imshow(np.log10(counts/dewell_time), cmap='hot')
        plt.colorbar(label='Counts')
        plt.tight_layout()
        # Display the plot
        clear_output(wait=True)
        display(plt.gcf())
except KeyboardInterrupt:
    pass
finally:
    print(f"\nAcquired {total_read} total samples.")
#mdt.mdtSetYAxisVoltage(hdl,0)


# %%
counts = daqScan(100, 100,(-0.0325, -0.015),(0.0175, 0.035), 0.001)
live_plot(counts)

# %%
counts = daqScan(1000, 1000,(-0.17, 0.12),(-0.19, 0.1), 0.01)
#live_plot(counts)

# %%
plt.imshow(counts,vmax=2300, cmap='hot')
plt.colorbar(label='Counts')
plt.tight_layout()

# %% [markdown]
# ## Piezo Scan

# %%
a = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
mdt.mdtGetYAxisVoltage(hdl,a)
a

# %%
piezoFocus = np.linspace(30,35,30)

# Set up the figure
plt.figure(figsize=(10, 6))


countsSet = []

for piezoVy in piezoFocus:
    mdt.mdtSetYAxisVoltage(hdl,piezoVy)
    time.sleep(1)
    counts = daqScan(uciLogoConfig["x_px"], uciLogoConfig["y_px"], uciLogoConfig["xlims"], uciLogoConfig["ylims"], uciLogoConfig["dwell_time"])
    countsSet += [counts]



plt.imshow(counts, cmap='hot')
plt.colorbar()
plt.title(f'Photon Counts at {(20/75)*20} depth')
plt.show()

# %%
mdt.mdtClose(hdl)

# %%
import matplotlib.animation
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams["animation.html"] = "jshtml"
plt.rcParams['figure.dpi'] = 150  
plt.ioff()
fig, ax = plt.subplots()

def animate(t):
    plt.cla()
    shifted_counts = countsSet[t].copy()
    shifted_counts[1::2] = np.roll(shifted_counts[1::2], shift=2, axis=1)
    plt.imshow(shifted_counts, cmap='hot',  vmax=800)
    #plt.colorbar()
    plt.title(f'Photon Counts at {piezoFocus[t]/75 * 20} um depth')

anim = matplotlib.animation.FuncAnimation(fig, animate, frames= 30,interval = 500)

# %%
from matplotlib.animation import FuncAnimation, PillowWriter

anim.save("TLI.gif", dpi=300, writer=PillowWriter(fps=2))

# %%
np.save(f"data/piezoScan.npy", np.stack(countsSet))


