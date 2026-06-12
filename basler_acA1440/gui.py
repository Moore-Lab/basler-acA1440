"""Standalone test GUI for the Basler acA1440-220um.

Thin shell over the shared, camera-agnostic harness in ``camera_dock.preview`` —
so the test GUI, the dock, and the DAQ share one implementation (no duplication).
All the real logic (threaded acquisition, decoupled preview, hybrid recording at
full data rate, snapshot) lives in the dock and is driven here with the Basler
driver.

Run with::

    python -m basler_acA1440.gui

Controls: exposure/fps trackbars, ``s`` snapshot, ``r`` record, ``q``/ESC quit.
"""

from __future__ import annotations

import os
import sys

# The shared harness lives in the parent dock repo (xsphere-camera-dock/camera_dock).
# This package sits at .../xsphere-camera-dock/basler-acA1440/basler_acA1440, so the
# dock root is three directories up. Add it to the path so ``camera_dock`` imports
# when this camera repo is run inside the dock checkout (the normal layout). The
# driver itself never imports the dock — only this test shell does.
_DOCK_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _DOCK_ROOT not in sys.path:
    sys.path.insert(0, _DOCK_ROOT)

from .camera import BaslerACA1440

FPS_CAP = 250.0   # fps-slider top; camera real max ~227


def main() -> None:
    try:
        from camera_dock.preview import run
    except ImportError as exc:
        raise SystemExit(
            "Could not import the shared GUI (camera_dock.preview). Run this from "
            "within the xsphere-camera-dock checkout. Original error: " + str(exc))
    run(BaslerACA1440(), fps_cap=FPS_CAP)


if __name__ == "__main__":
    main()
