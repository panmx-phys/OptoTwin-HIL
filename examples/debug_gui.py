#!/usr/bin/env python3
"""OptoTwin Debug GUI — Hardware diagnostics and single raster scan.

Usage:
    python examples/debug_gui.py
    OT_SIMULATE=1 python examples/debug_gui.py

Requires:  pip install -e ".[gui]"
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np

try:
    import dearpygui.dearpygui as dpg
except ImportError:
    raise SystemExit(
        "dearpygui is required for the debug GUI.\n"
        "Install with:  pip install -e '.[gui]'"
    )

import matplotlib.cm as cm
import matplotlib.colors as mcolors
from scipy.ndimage import zoom

from optotwin.core.config import ScanConfig
from optotwin.core.utils import calculate_square_pixels
from optotwin.hal.daq import DAQOrchestrator, SimulatedDAQOrchestrator
from optotwin.hal.laser import LaserDriver
from optotwin.hal.piezo import PiezoStage
from optotwin.hal.temperature import AuberController
from optotwin.trajectory.raster import raster_voltages, reconstruct_image

log = logging.getLogger("optotwin.gui")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEX_W, TEX_H = 512, 512
POLL_INTERVAL = 1.0
COLORMAPS = {
    "hot": cm.hot,
    "viridis": cm.viridis,
    "inferno": cm.inferno,
    "gray": cm.gray,
}

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


@dataclass
class AppState:
    simulate: bool = True
    daq: DAQOrchestrator | SimulatedDAQOrchestrator | None = None

    # Optional hardware handles — None until user clicks [Connect]
    laser: LaserDriver | None = None
    piezo: PiezoStage | None = None
    auber: AuberController | None = None

    # Scan
    scanning: bool = False
    abort_requested: threading.Event = field(default_factory=threading.Event)
    last_image: np.ndarray | None = None
    last_raw_counts: np.ndarray | None = None
    last_config: ScanConfig | None = None
    progress: float = 0.0
    scan_thread: threading.Thread | None = None

    # Internal bookkeeping
    _image_dirty: bool = False
    _counts_dirty: bool = False
    _scan_start: float = 0.0
    _scan_est_s: float = 1.0


state = AppState()

# ---------------------------------------------------------------------------
# Logging bridge → DPG text widget
# ---------------------------------------------------------------------------

_LOG_LINES: list[str] = []
_MAX_LOG = 500


class _DPGLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        _LOG_LINES.append(msg)
        if len(_LOG_LINES) > _MAX_LOG:
            _LOG_LINES.pop(0)


_handler = _DPGLogHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s  %(message)s", datefmt="%H:%M:%S"))
logging.getLogger("optotwin").addHandler(_handler)
logging.getLogger("optotwin").setLevel(logging.DEBUG)


def _log(msg: str) -> None:
    log.info(msg)


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _image_to_rgba(image: np.ndarray, cmap_name: str, auto_scale: bool) -> np.ndarray:
    """Convert a 2-D array to a flat RGBA float32 array sized for the texture."""
    vmin, vmax = (image.min(), image.max()) if auto_scale else (0, image.max() or 1)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = COLORMAPS.get(cmap_name, cm.hot)
    rgba = cmap(norm(image))  # (H, W, 4) float64

    zy = TEX_H / rgba.shape[0]
    zx = TEX_W / rgba.shape[1]
    rgba_resized = zoom(rgba, (zy, zx, 1), order=0)
    return rgba_resized.astype(np.float32).ravel()


# ---------------------------------------------------------------------------
# Config ↔ widget helpers
# ---------------------------------------------------------------------------


def _read_scan_config() -> ScanConfig:
    return ScanConfig(
        x_px=dpg.get_value("inp_x_px"),
        y_px=dpg.get_value("inp_y_px"),
        xlims=(dpg.get_value("inp_xmin"), dpg.get_value("inp_xmax")),
        ylims=(dpg.get_value("inp_ymin"), dpg.get_value("inp_ymax")),
        dwell_time=dpg.get_value("inp_dwell"),
        accumulation=dpg.get_value("inp_accum"),
        experiment_name=dpg.get_value("inp_expt"),
        sample_name=dpg.get_value("inp_sample"),
        measurement_name=dpg.get_value("inp_meas"),
    )


# ---------------------------------------------------------------------------
# Acquisition worker (runs in daemon thread)
# ---------------------------------------------------------------------------


def _acquisition_worker(config: ScanConfig) -> None:
    try:
        _log(f"Building trajectory: {config}")
        voltages = raster_voltages(
            config.x_px, config.y_px,
            config.xlims, config.ylims,
            config.accumulation,
        )

        if state.abort_requested.is_set():
            _log("Scan aborted before acquisition.")
            return

        _log(f"Acquiring {voltages.shape[1]} samples ...")
        state._scan_start = time.monotonic()
        state._scan_est_s = config.total_time_s or 1.0

        raw_counts = state.daq.run(voltages, config.dwell_time)

        if state.abort_requested.is_set():
            _log("Scan aborted after acquisition.")
            state.daq.park()
            return

        state.daq.park()

        image = reconstruct_image(raw_counts, config.x_px, config.y_px, config.accumulation)
        if image.ndim == 3:
            display_image = image.mean(axis=0)
        else:
            display_image = image

        # Per-pixel counts for the line plot
        per_pixel = np.insert(np.diff(raw_counts), 0, raw_counts[0]).astype(np.float64)

        state.last_image = display_image
        state.last_raw_counts = per_pixel
        state.last_config = config
        state.progress = 1.0
        state._image_dirty = True
        state._counts_dirty = True
        _log(f"Scan complete. Image shape: {display_image.shape}")

    except Exception as exc:
        _log(f"ERROR: {exc}")
        state.progress = 0.0
    finally:
        state.scanning = False


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def _cb_simulate_toggle(sender, value, user_data):
    state.simulate = value
    if value:
        state.daq = SimulatedDAQOrchestrator()
        dpg.set_value("txt_daq_status", "Simulated")
        _log("Switched to simulated DAQ")
    else:
        try:
            state.daq = DAQOrchestrator()
            dpg.set_value("txt_daq_status", "Dev1 connected")
            _log("Switched to real DAQ")
        except Exception as exc:
            state.daq = SimulatedDAQOrchestrator()
            state.simulate = True
            dpg.set_value("chk_simulate", True)
            dpg.set_value("txt_daq_status", "Simulated (HW failed)")
            _log(f"DAQ init failed, staying simulated: {exc}")


def _cb_scan(sender, value, user_data):
    if state.scanning:
        return
    if state.daq is None:
        _log("No DAQ initialised. Toggle simulation or connect hardware.")
        return

    config = _read_scan_config()
    if config.xlims[0] >= config.xlims[1] or config.ylims[0] >= config.ylims[1]:
        _log("Invalid limits: min must be < max.")
        return
    if config.dwell_time <= 0:
        _log("Dwell time must be > 0.")
        return

    state.scanning = True
    state.abort_requested.clear()
    state.progress = 0.0
    dpg.configure_item("btn_scan", enabled=False)
    dpg.configure_item("btn_abort", enabled=True)

    state.scan_thread = threading.Thread(target=_acquisition_worker, args=(config,), daemon=True)
    state.scan_thread.start()


def _cb_abort(sender, value, user_data):
    state.abort_requested.set()
    _log("Abort requested — will stop after current acquisition.")


def _cb_square_pixels(sender, value, user_data):
    xlims = (dpg.get_value("inp_xmin"), dpg.get_value("inp_xmax"))
    ylims = (dpg.get_value("inp_ymin"), dpg.get_value("inp_ymax"))
    base = dpg.get_value("inp_x_px")
    x_px, y_px = calculate_square_pixels(xlims, ylims, base)
    dpg.set_value("inp_x_px", x_px)
    dpg.set_value("inp_y_px", y_px)
    _cb_update_estimate(None, None, None)
    _log(f"Square pixels: {x_px} x {y_px}")


def _cb_update_estimate(sender, value, user_data):
    x = dpg.get_value("inp_x_px")
    y = dpg.get_value("inp_y_px")
    dwell = dpg.get_value("inp_dwell")
    acc = dpg.get_value("inp_accum")
    total = x * y * dwell * acc
    if total < 60:
        dpg.set_value("txt_time_est", f"Est: {total:.1f} s")
    else:
        dpg.set_value("txt_time_est", f"Est: {total / 60:.1f} min")


def _cb_cmap_change(sender, value, user_data):
    state._image_dirty = True


# -- Hardware connect callbacks (all optional) --------------------------------


def _cb_connect_laser(sender, value, user_data):
    try:
        state.laser = LaserDriver.connect()
        dpg.set_value("txt_laser_status", "Connected")
        dpg.configure_item("btn_connect_laser", label="Reconnect")
        _enable_laser_controls(True)
        _log("Laser driver connected")
    except Exception as exc:
        state.laser = None
        dpg.set_value("txt_laser_status", f"Error")
        _enable_laser_controls(False)
        _log(f"Laser connection failed: {exc}")


def _cb_connect_piezo(sender, value, user_data):
    try:
        stage = PiezoStage()
        stage.connect()
        state.piezo = stage
        dpg.set_value("txt_piezo_status", "Connected")
        dpg.configure_item("btn_connect_piezo", label="Reconnect")
        _enable_piezo_controls(True)
        _log("Piezo stage connected")
    except Exception as exc:
        state.piezo = None
        dpg.set_value("txt_piezo_status", "Error")
        _enable_piezo_controls(False)
        _log(f"Piezo connection failed: {exc}")


def _cb_connect_auber(sender, value, user_data):
    try:
        state.auber = AuberController()
        dpg.set_value("txt_auber_status", "Connected")
        dpg.configure_item("btn_connect_auber", label="Reconnect")
        _log("Auber temperature controller connected")
    except Exception as exc:
        state.auber = None
        dpg.set_value("txt_auber_status", "Error")
        _log(f"Auber connection failed: {exc}")


def _cb_laser_tec(sender, value, user_data):
    if state.laser:
        try:
            state.laser.set_tec(value)
        except Exception as exc:
            _log(f"Laser TEC error: {exc}")


def _cb_laser_output(sender, value, user_data):
    if state.laser:
        try:
            state.laser.set_output(value)
        except Exception as exc:
            _log(f"Laser output error: {exc}")


def _cb_laser_current(sender, value, user_data):
    if state.laser:
        try:
            state.laser.set_current(value)
            _log(f"Laser current set to {value:.4f} A")
        except Exception as exc:
            _log(f"Laser current error: {exc}")


def _cb_laser_temp_sp(sender, value, user_data):
    if state.laser:
        try:
            state.laser.set_temp(value)
            _log(f"TEC setpoint set to {value:.1f} C")
        except Exception as exc:
            _log(f"TEC setpoint error: {exc}")


def _cb_piezo_set(sender, value, user_data):
    if state.piezo:
        try:
            v = dpg.get_value("inp_piezo_v")
            state.piezo.set_y_voltage(v)
            _log(f"Piezo Y set to {v:.2f} V")
        except Exception as exc:
            _log(f"Piezo set error: {exc}")


def _cb_piezo_read(sender, value, user_data):
    if state.piezo:
        try:
            v = state.piezo.get_y_voltage()
            dpg.set_value("inp_piezo_v", v)
            dpg.set_value("txt_piezo_v", f"{v:.2f} V")
        except Exception as exc:
            _log(f"Piezo read error: {exc}")


def _cb_save_image(sender, value, user_data):
    if state.last_image is None:
        _log("No image to save.")
        return
    dpg.show_item("dlg_save")


def _cb_file_selected(sender, app_data, user_data):
    path = app_data.get("file_path_name", "")
    if not path:
        return
    try:
        if path.endswith(".npy"):
            np.save(path, state.last_image)
        else:
            import matplotlib.pyplot as plt
            plt.imsave(path, state.last_image, cmap="hot")
        _log(f"Saved image to {path}")
    except Exception as exc:
        _log(f"Save failed: {exc}")


# ---------------------------------------------------------------------------
# Enable/disable helpers
# ---------------------------------------------------------------------------


def _enable_laser_controls(on: bool) -> None:
    for tag in ("chk_tec", "chk_laser_out", "inp_laser_current", "inp_tec_sp"):
        dpg.configure_item(tag, enabled=on)


def _enable_piezo_controls(on: bool) -> None:
    for tag in ("inp_piezo_v", "btn_piezo_set", "btn_piezo_read"):
        dpg.configure_item(tag, enabled=on)


# ---------------------------------------------------------------------------
# Render-loop helpers
# ---------------------------------------------------------------------------

_last_poll = 0.0


def _poll_hardware() -> None:
    global _last_poll
    now = time.monotonic()
    if now - _last_poll < POLL_INTERVAL:
        return
    _last_poll = now

    if state.laser is not None:
        try:
            dpg.set_value("txt_laser_temp", f"{state.laser.get_temp():.1f} C")
            dpg.set_value("txt_laser_pd", f"{state.laser.get_pd_current() * 1e3:.3f} mA")
        except Exception:
            dpg.set_value("txt_laser_temp", "Error")
            dpg.set_value("txt_laser_pd", "Error")

    if state.piezo is not None:
        try:
            v = state.piezo.get_y_voltage()
            dpg.set_value("txt_piezo_v", f"{v:.2f} V")
        except Exception:
            dpg.set_value("txt_piezo_v", "Error")

    if state.auber is not None:
        try:
            dpg.set_value("txt_auber_temp", f"{state.auber.get_temperature():.1f} C")
        except Exception:
            dpg.set_value("txt_auber_temp", "Error")


def _frame_update() -> None:
    # Progress bar
    if state.scanning and state._scan_start > 0:
        elapsed = time.monotonic() - state._scan_start
        state.progress = min(elapsed / state._scan_est_s, 0.99)
    dpg.set_value("pb_scan", state.progress)

    # Re-enable buttons when scan finishes
    if not state.scanning:
        dpg.configure_item("btn_scan", enabled=True)
        dpg.configure_item("btn_abort", enabled=False)

    # Update image texture
    if state._image_dirty and state.last_image is not None:
        cmap_name = dpg.get_value("cmb_cmap")
        auto_scale = dpg.get_value("chk_autoscale")
        rgba = _image_to_rgba(state.last_image, cmap_name, auto_scale)
        dpg.set_value("tex_scan", rgba)

        img = state.last_image
        dpg.set_value("txt_stats", f"Min: {img.min():.1f}  Max: {img.max():.1f}  Mean: {img.mean():.1f}  Pixels: {img.size}")
        state._image_dirty = False

    # Update raw-counts line plot
    if state._counts_dirty and state.last_raw_counts is not None:
        counts = state.last_raw_counts
        xs = np.arange(len(counts), dtype=np.float64).tolist()
        ys = counts.tolist()
        dpg.set_value("line_counts", [xs, ys])
        dpg.fit_axis_data("ax_counts_x")
        dpg.fit_axis_data("ax_counts_y")
        state._counts_dirty = False

    # Update log console
    dpg.set_value("txt_log", "\n".join(_LOG_LINES))

    # Status bar
    if state.scanning:
        dpg.set_value("txt_status", "Scanning ...")
    elif state.last_image is not None:
        dpg.set_value("txt_status", "Ready — last scan available")
    else:
        dpg.set_value("txt_status", "Ready")


# ---------------------------------------------------------------------------
# GUI construction
# ---------------------------------------------------------------------------


def _build_config_panel() -> None:
    dpg.add_checkbox(label="Simulate", tag="chk_simulate", default_value=True, callback=_cb_simulate_toggle)
    dpg.add_separator()
    dpg.add_text("Scan Configuration")

    dpg.add_input_int(label="X pixels", tag="inp_x_px", default_value=100, min_value=2, max_value=1024, min_clamped=True, max_clamped=True, width=150, callback=_cb_update_estimate)
    dpg.add_input_int(label="Y pixels", tag="inp_y_px", default_value=100, min_value=2, max_value=1024, min_clamped=True, max_clamped=True, width=150, callback=_cb_update_estimate)
    dpg.add_input_float(label="X min (V)", tag="inp_xmin", default_value=-1.0, step=0.01, format="%.3f", width=150, callback=_cb_update_estimate)
    dpg.add_input_float(label="X max (V)", tag="inp_xmax", default_value=1.0, step=0.01, format="%.3f", width=150, callback=_cb_update_estimate)
    dpg.add_input_float(label="Y min (V)", tag="inp_ymin", default_value=-1.0, step=0.01, format="%.3f", width=150, callback=_cb_update_estimate)
    dpg.add_input_float(label="Y max (V)", tag="inp_ymax", default_value=1.0, step=0.01, format="%.3f", width=150, callback=_cb_update_estimate)
    dpg.add_input_float(label="Dwell (s)", tag="inp_dwell", default_value=0.001, step=0.0001, format="%.4f", width=150, callback=_cb_update_estimate)
    dpg.add_input_int(label="Accumulation", tag="inp_accum", default_value=1, min_value=1, max_value=100, min_clamped=True, max_clamped=True, width=150, callback=_cb_update_estimate)

    dpg.add_separator()
    dpg.add_text("Metadata")
    dpg.add_input_text(label="Experiment", tag="inp_expt", width=150)
    dpg.add_input_text(label="Sample", tag="inp_sample", width=150)
    dpg.add_input_text(label="Measurement", tag="inp_meas", width=150)

    dpg.add_separator()
    dpg.add_text("Est: --", tag="txt_time_est")
    dpg.add_button(label="Square Pixels", callback=_cb_square_pixels)

    dpg.add_spacer(height=8)
    with dpg.group(horizontal=True):
        dpg.add_button(label="SCAN", tag="btn_scan", callback=_cb_scan, width=100)
        dpg.add_button(label="ABORT", tag="btn_abort", callback=_cb_abort, width=100, enabled=False)


def _build_image_panel() -> None:
    dpg.add_text("Scan Image")
    dpg.add_image("tex_scan", width=TEX_W, height=TEX_H, tag="img_scan")

    dpg.add_spacer(height=4)
    dpg.add_text("Min: --  Max: --  Mean: --  Pixels: --", tag="txt_stats")

    with dpg.group(horizontal=True):
        dpg.add_combo(["hot", "viridis", "inferno", "gray"], tag="cmb_cmap", default_value="hot", width=100, callback=_cb_cmap_change)
        dpg.add_checkbox(label="Auto-scale", tag="chk_autoscale", default_value=True, callback=_cb_cmap_change)

    dpg.add_spacer(height=4)
    dpg.add_text("Raw Counts")
    with dpg.plot(label="##counts_plot", height=180, width=-1):
        dpg.add_plot_axis(dpg.mvXAxis, label="Sample", tag="ax_counts_x")
        dpg.add_plot_axis(dpg.mvYAxis, label="Counts", tag="ax_counts_y")
        dpg.add_line_series([], [], label="counts", parent="ax_counts_y", tag="line_counts")

    dpg.add_spacer(height=4)
    dpg.add_progress_bar(tag="pb_scan", default_value=0.0, width=-1)


def _build_hardware_panel() -> None:
    # -- DAQ status (always present) --
    dpg.add_text("Hardware Status")
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_text("DAQ:")
        dpg.add_text("Simulated", tag="txt_daq_status")

    # -- Laser --
    dpg.add_spacer(height=8)
    with dpg.collapsing_header(label="Laser", default_open=False):
        with dpg.group(horizontal=True):
            dpg.add_text("Status:")
            dpg.add_text("Not connected", tag="txt_laser_status")
        dpg.add_button(label="Connect", tag="btn_connect_laser", callback=_cb_connect_laser)
        dpg.add_separator()
        dpg.add_checkbox(label="TEC", tag="chk_tec", callback=_cb_laser_tec, enabled=False)
        dpg.add_input_float(label="TEC Setpoint (C)", tag="inp_tec_sp", default_value=25.0, step=0.1, format="%.1f", width=120, callback=_cb_laser_temp_sp, enabled=False)
        with dpg.group(horizontal=True):
            dpg.add_text("Temp:")
            dpg.add_text("--", tag="txt_laser_temp")
        dpg.add_checkbox(label="Output", tag="chk_laser_out", callback=_cb_laser_output, enabled=False)
        dpg.add_input_float(label="Current (A)", tag="inp_laser_current", default_value=0.0, step=0.001, format="%.4f", width=120, callback=_cb_laser_current, enabled=False)
        with dpg.group(horizontal=True):
            dpg.add_text("Monitor PD:")
            dpg.add_text("--", tag="txt_laser_pd")

    # -- Piezo --
    with dpg.collapsing_header(label="Piezo", default_open=False):
        with dpg.group(horizontal=True):
            dpg.add_text("Status:")
            dpg.add_text("Not connected", tag="txt_piezo_status")
        dpg.add_button(label="Connect", tag="btn_connect_piezo", callback=_cb_connect_piezo)
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_text("Y voltage:")
            dpg.add_text("--", tag="txt_piezo_v")
        dpg.add_input_float(label="Set Y (V)", tag="inp_piezo_v", default_value=0.0, step=0.1, format="%.2f", width=120, enabled=False)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Set", tag="btn_piezo_set", callback=_cb_piezo_set, enabled=False)
            dpg.add_button(label="Read", tag="btn_piezo_read", callback=_cb_piezo_read, enabled=False)

    # -- Temperature --
    with dpg.collapsing_header(label="Temperature", default_open=False):
        with dpg.group(horizontal=True):
            dpg.add_text("Status:")
            dpg.add_text("Not connected", tag="txt_auber_status")
        dpg.add_button(label="Connect", tag="btn_connect_auber", callback=_cb_connect_auber)
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_text("Temperature:")
            dpg.add_text("--", tag="txt_auber_temp")

    # -- Log console --
    dpg.add_spacer(height=12)
    dpg.add_text("Log")
    dpg.add_separator()
    dpg.add_input_text(tag="txt_log", multiline=True, readonly=True, height=200, width=-1, tracked=True, track_offset=1.0)


def build_gui() -> None:
    dpg.create_context()
    dpg.create_viewport(title="OptoTwin Debug GUI", width=1400, height=850)

    # Texture registry
    with dpg.texture_registry():
        dpg.add_raw_texture(TEX_W, TEX_H, default_value=[0.0] * (TEX_W * TEX_H * 4), format=dpg.mvFormat_Float_rgba, tag="tex_scan")

    # File save dialog (hidden by default)
    with dpg.file_dialog(
        directory_selector=False,
        show=False,
        callback=_cb_file_selected,
        tag="dlg_save",
        width=600,
        height=400,
    ):
        dpg.add_file_extension(".npy", color=(0, 255, 0, 255))
        dpg.add_file_extension(".png", color=(0, 255, 255, 255))

    # Primary window
    with dpg.window(tag="primary"):
        with dpg.menu_bar():
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="Save Image ...", callback=_cb_save_image)
                dpg.add_menu_item(label="Quit", callback=lambda: dpg.stop_dearpygui())
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=lambda: _log("OptoTwin Debug GUI v0.1"))

        with dpg.group(horizontal=True):
            # LEFT column
            with dpg.child_window(width=320, border=True):
                _build_config_panel()

            # CENTER column
            with dpg.child_window(width=-370, border=True):
                _build_image_panel()

            # RIGHT column
            with dpg.child_window(width=-1, border=True):
                _build_hardware_panel()

        dpg.add_text("Ready", tag="txt_status")

    dpg.set_primary_window("primary", True)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def _cleanup() -> None:
    if state.daq is not None:
        try:
            state.daq.park()
        except Exception:
            pass
    if state.laser is not None:
        try:
            state.laser.close()
        except Exception:
            pass
    if state.piezo is not None:
        try:
            state.piezo.disconnect()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    build_gui()

    # Initial DAQ based on env / default
    if os.getenv("OT_SIMULATE", "1") == "1":
        state.simulate = True
        state.daq = SimulatedDAQOrchestrator()
        dpg.set_value("chk_simulate", True)
        dpg.set_value("txt_daq_status", "Simulated")
    else:
        state.simulate = False
        dpg.set_value("chk_simulate", False)
        try:
            state.daq = DAQOrchestrator()
            dpg.set_value("txt_daq_status", "Dev1 connected")
        except Exception:
            state.daq = SimulatedDAQOrchestrator()
            state.simulate = True
            dpg.set_value("chk_simulate", True)
            dpg.set_value("txt_daq_status", "Simulated (HW failed)")

    _cb_update_estimate(None, None, None)

    atexit.register(_cleanup)
    _log("OptoTwin Debug GUI started")

    dpg.setup_dearpygui()
    dpg.show_viewport()

    while dpg.is_dearpygui_running():
        _poll_hardware()
        _frame_update()
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
