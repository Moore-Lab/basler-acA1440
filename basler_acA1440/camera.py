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

    # --- acquisition -------------------------------------------------------
    def start(self) -> None:
        """Begin continuous grabbing (latest-image-only strategy)."""
        cam = self._require()
        if not cam.IsGrabbing():
            cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

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
