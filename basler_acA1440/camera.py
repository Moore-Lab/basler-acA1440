"""Driver/API for the Basler acA1440-220um (USB3 Vision, mono).

Wraps Basler's pypylon SDK behind a small, GUI-friendly interface:
connect, configure (exposure, frame rate), grab single frames, and stream.

The public surface here is intended to mirror the other camera modules so that
``xsphere-camera-dock`` can drive every camera through the same calls
(``connect`` / ``disconnect`` / ``set_exposure`` / ``set_frame_rate`` /
``grab`` / ``frames``).

Requires the Pylon runtime (installed with the Basler software) and ``pypylon``::

    pip install pypylon numpy
"""

from __future__ import annotations

from typing import Iterator, Optional, Tuple

import pypylon.pylon as pylon


def _snap(value: float, inc: int, lo: int, hi: int) -> int:
    """Clamp ``value`` to ``[lo, hi]`` and snap to the nearest ``inc`` step from ``lo``."""
    inc = inc or 1
    v = max(lo, min(hi, int(value)))
    return min(hi, lo + int(round((v - lo) / inc)) * inc)


class BaslerACA1440:
    """Thin driver around a single Basler acA1440-220um.

    Parameters
    ----------
    serial:
        Serial number of the target camera. If ``None``, the first device found
        is used.
    """

    def __init__(self, serial: Optional[str] = None) -> None:
        self.serial = serial
        self._camera: Optional[pylon.InstantCamera] = None

    # --- lifecycle ---------------------------------------------------------
    def connect(self) -> None:
        """Open the camera and prepare it for acquisition (Mono8)."""
        factory = pylon.TlFactory.GetInstance()
        if self.serial:
            info = pylon.CDeviceInfo()
            info.SetSerialNumber(str(self.serial))
            device = factory.CreateDevice(info)
        else:
            device = factory.CreateFirstDevice()

        self._camera = pylon.InstantCamera(device)
        self._camera.Open()

        # acA1440-220um is a mono sensor; make the pixel format explicit so
        # grabbed arrays are predictable 2-D uint8.
        try:
            self._camera.PixelFormat.SetValue("Mono8")
        except Exception:
            pass  # already Mono8 or node unavailable on this firmware

        # Allow manual control of the acquisition frame rate.
        try:
            self._camera.AcquisitionFrameRateEnable.SetValue(True)
        except Exception:
            pass

        # Disable auto exposure/gain so manual (slider / numeric) values stick.
        for node_name in ("ExposureAuto", "GainAuto"):
            try:
                getattr(self._camera, node_name).SetValue("Off")
            except Exception:
                pass

    def disconnect(self) -> None:
        """Stop acquisition (if running) and release the camera."""
        if self._camera is None:
            return
        try:
            if self._camera.IsGrabbing():
                self._camera.StopGrabbing()
            if self._camera.IsOpen():
                self._camera.Close()
        finally:
            self._camera = None

    @property
    def is_connected(self) -> bool:
        return self._camera is not None and self._camera.IsOpen()

    def _require(self) -> pylon.InstantCamera:
        if self._camera is None or not self._camera.IsOpen():
            raise RuntimeError("Camera is not connected. Call connect() first.")
        return self._camera

    # --- device info -------------------------------------------------------
    @property
    def device_info(self) -> dict:
        cam = self._require()
        di = cam.GetDeviceInfo()
        return {
            "model": di.GetModelName(),
            "serial": di.GetSerialNumber(),
            "vendor": di.GetVendorName(),
        }

    def sensor_size(self) -> Tuple[int, int]:
        """Return ``(width, height)`` of the current image region."""
        cam = self._require()
        return int(cam.Width.GetValue()), int(cam.Height.GetValue())

    # --- configuration -----------------------------------------------------
    def set_exposure(self, microseconds: float) -> None:
        """Set exposure time in microseconds (clamped to the valid range)."""
        node = self._require().ExposureTime
        lo, hi = node.GetMin(), node.GetMax()
        node.SetValue(float(min(max(microseconds, lo), hi)))

    def get_exposure(self) -> float:
        return float(self._require().ExposureTime.GetValue())

    def exposure_range(self) -> Tuple[float, float]:
        node = self._require().ExposureTime
        return float(node.GetMin()), float(node.GetMax())

    def set_frame_rate(self, fps: float) -> None:
        """Set the target acquisition frame rate in frames per second."""
        cam = self._require()
        try:
            cam.AcquisitionFrameRateEnable.SetValue(True)
        except Exception:
            pass
        node = cam.AcquisitionFrameRate
        lo, hi = node.GetMin(), node.GetMax()
        node.SetValue(float(min(max(fps, lo), hi)))

    def get_frame_rate(self) -> float:
        """Target frame rate (what we asked for)."""
        return float(self._require().AcquisitionFrameRate.GetValue())

    def frame_rate_range(self) -> Tuple[float, float]:
        node = self._require().AcquisitionFrameRate
        return float(node.GetMin()), float(node.GetMax())

    def resulting_frame_rate(self) -> float:
        """Frame rate the camera can actually achieve given current settings.

        Limited by exposure time, readout, and bandwidth. Reads the
        ``ResultingFrameRate`` node when present, else falls back to the target.
        """
        cam = self._require()
        for name in ("ResultingFrameRate", "ResultingFrameRateAbs"):
            node = getattr(cam, name, None)
            if node is not None:
                try:
                    return float(node.GetValue())
                except Exception:
                    continue
        return self.get_frame_rate()

    # --- gain --------------------------------------------------------------
    def _gain_node(self):
        cam = self._require()
        for name in ("Gain", "GainRaw"):
            node = getattr(cam, name, None)
            if node is not None:
                return node
        return None

    def set_gain(self, value: float) -> None:
        """Set gain in the camera's native units (dB for ``Gain``, raw for ``GainRaw``)."""
        node = self._gain_node()
        if node is None:
            return
        lo, hi = node.GetMin(), node.GetMax()
        v = min(max(value, lo), hi)
        try:
            node.SetValue(float(v))
        except Exception:
            node.SetValue(int(round(v)))   # GainRaw is integer-valued

    def get_gain(self) -> float:
        node = self._gain_node()
        return float(node.GetValue()) if node is not None else 0.0

    def gain_range(self) -> Tuple[float, float]:
        """``(min, max)`` gain; ``(0, 0)`` if the camera exposes no gain node."""
        node = self._gain_node()
        if node is None:
            return (0.0, 0.0)
        return (float(node.GetMin()), float(node.GetMax()))

    # --- region of interest / binning --------------------------------------
    # ROI is expressed uniformly as (offset_x, offset_y, width, height). Must be
    # set while not grabbing (the dock stops the engine first).
    def roi_range(self) -> dict:
        cam = self._require()
        return {
            "w_min": int(cam.Width.GetMin()), "w_max": int(cam.Width.GetMax()),
            "w_inc": int(cam.Width.GetInc()),
            "h_min": int(cam.Height.GetMin()), "h_max": int(cam.Height.GetMax()),
            "h_inc": int(cam.Height.GetInc()),
            "x_inc": int(cam.OffsetX.GetInc()), "y_inc": int(cam.OffsetY.GetInc()),
        }

    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        """Set a centred-or-placed ROI, snapping to the camera's pixel increments."""
        cam = self._require()
        # Zero offsets first so the new size always fits, then size, then offsets.
        cam.OffsetX.SetValue(0)
        cam.OffsetY.SetValue(0)
        cam.Width.SetValue(_snap(w, cam.Width.GetInc(), cam.Width.GetMin(), cam.Width.GetMax()))
        cam.Height.SetValue(_snap(h, cam.Height.GetInc(), cam.Height.GetMin(), cam.Height.GetMax()))
        cam.OffsetX.SetValue(_snap(x, cam.OffsetX.GetInc(), cam.OffsetX.GetMin(), cam.OffsetX.GetMax()))
        cam.OffsetY.SetValue(_snap(y, cam.OffsetY.GetInc(), cam.OffsetY.GetMin(), cam.OffsetY.GetMax()))

    def get_roi(self) -> Tuple[int, int, int, int]:
        cam = self._require()
        return (int(cam.OffsetX.GetValue()), int(cam.OffsetY.GetValue()),
                int(cam.Width.GetValue()), int(cam.Height.GetValue()))

    def reset_roi(self) -> None:
        """Restore the full sensor region."""
        cam = self._require()
        cam.OffsetX.SetValue(0)
        cam.OffsetY.SetValue(0)
        cam.Width.SetValue(int(cam.Width.GetMax()))
        cam.Height.SetValue(int(cam.Height.GetMax()))

    def binning_range(self) -> Tuple[int, int]:
        cam = self._require()
        bx = getattr(cam, "BinningHorizontal", None)
        by = getattr(cam, "BinningVertical", None)
        return (int(bx.GetMax()) if bx is not None else 1,
                int(by.GetMax()) if by is not None else 1)

    def set_binning(self, bx: int, by: int) -> None:
        """Set horizontal/vertical binning (resets ROI to the new full frame)."""
        cam = self._require()
        for node, val in ((getattr(cam, "BinningHorizontal", None), bx),
                          (getattr(cam, "BinningVertical", None), by)):
            if node is not None:
                node.SetValue(int(min(max(val, node.GetMin()), node.GetMax())))
        self.reset_roi()

    def get_binning(self) -> Tuple[int, int]:
        cam = self._require()
        bx = getattr(cam, "BinningHorizontal", None)
        by = getattr(cam, "BinningVertical", None)
        return (int(bx.GetValue()) if bx is not None else 1,
                int(by.GetValue()) if by is not None else 1)

    # --- acquisition -------------------------------------------------------
    def start(self, max_throughput: bool = False) -> None:
        """Begin continuous grabbing.

        ``max_throughput=True`` uses a queued (one-by-one) strategy so **no frames
        are dropped** — for recording at the full data rate. ``False`` uses
        latest-image-only for low-latency preview, where frames produced faster
        than they are consumed are skipped.
        """
        cam = self._require()
        if not cam.IsGrabbing():
            strategy = (pylon.GrabStrategy_OneByOne if max_throughput
                        else pylon.GrabStrategy_LatestImageOnly)
            cam.StartGrabbing(strategy)

    def stop(self) -> None:
        """Stop continuous grabbing."""
        cam = self._require()
        if cam.IsGrabbing():
            cam.StopGrabbing()

    @property
    def is_grabbing(self) -> bool:
        return self._camera is not None and self._camera.IsGrabbing()

    def grab(self, timeout_ms: int = 5000):
        """Grab and return a single frame as a 2-D ``numpy`` array (uint8, mono).

        Works whether or not a continuous grab is already running: if not
        grabbing it performs a one-shot capture, otherwise it pulls the latest
        frame from the running stream.
        """
        cam = self._require()
        if not cam.IsGrabbing():
            result = cam.GrabOne(timeout_ms)
            try:
                if not result.GrabSucceeded():
                    raise RuntimeError(result.GetErrorDescription())
                return result.GetArray().copy()
            finally:
                result.Release()

        result = cam.RetrieveResult(timeout_ms, pylon.TimeoutHandling_ThrowException)
        try:
            if not result.GrabSucceeded():
                raise RuntimeError(result.GetErrorDescription())
            return result.GetArray().copy()
        finally:
            result.Release()

    def frames(self, timeout_ms: int = 5000) -> Iterator:
        """Yield frames continuously while acquisition is running.

        Starts grabbing if not already started. Stops when :meth:`stop` is
        called (or the camera otherwise leaves the grabbing state).
        """
        cam = self._require()
        self.start()
        while cam.IsGrabbing():
            result = cam.RetrieveResult(timeout_ms, pylon.TimeoutHandling_ThrowException)
            try:
                if result.GrabSucceeded():
                    yield result.GetArray().copy()
            finally:
                result.Release()

    # --- context manager ---------------------------------------------------
    def __enter__(self) -> "BaslerACA1440":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()
