"""Driver/API for the Basler acA1440-220um (USB3 Vision, mono).

Wraps Basler's pypylon SDK behind a small, GUI-friendly interface:
connect, configure (exposure, frame rate), grab single frames, and stream.

The public surface here is intended to mirror the other camera modules so that
``xsphere-camera-dock`` can drive every camera through the same calls.
"""

from __future__ import annotations

from typing import Iterator, Optional

# import pypylon.pylon as pylon  # enable once the Pylon runtime + pypylon are installed


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
        self._camera = None  # will hold the pylon.InstantCamera

    # --- lifecycle ---------------------------------------------------------
    def connect(self) -> None:
        """Open the camera and prepare it for acquisition."""
        raise NotImplementedError

    def disconnect(self) -> None:
        """Stop acquisition (if running) and release the camera."""
        raise NotImplementedError

    # --- configuration -----------------------------------------------------
    def set_exposure(self, microseconds: float) -> None:
        """Set exposure time in microseconds."""
        raise NotImplementedError

    def set_frame_rate(self, fps: float) -> None:
        """Set the target acquisition frame rate in frames per second."""
        raise NotImplementedError

    # --- acquisition -------------------------------------------------------
    def grab(self):
        """Grab and return a single frame as a 2-D ``numpy`` array."""
        raise NotImplementedError

    def frames(self) -> Iterator:
        """Yield frames continuously while acquisition is running."""
        raise NotImplementedError

    # --- context manager ---------------------------------------------------
    def __enter__(self) -> "BaslerACA1440":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()
