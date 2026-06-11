"""Standalone native test GUI for the Basler acA1440-220um.

A quick OpenCV (highgui) harness to validate the driver in isolation: live
preview, exposure / frame-rate trackbars, snapshot, and record. Deliberately
dependency-light (no Qt) — throwaway bring-up tooling; the production UI will be
the web app in ``xsphere-camera-dock``.

Run with::

    python -m basler_acA1440.gui

Controls
--------
    exposure / fps : trackbars at the top of the window
    s              : snapshot   -> captures/
    r              : record on/off -> recordings/
    q or ESC       : quit

Captures land in ``captures/`` and recordings in ``recordings/`` next to the cwd.
"""

from __future__ import annotations

import os
from datetime import datetime
from time import perf_counter

import cv2
import numpy as np

from .camera import BaslerACA1440

WINDOW = "Basler acA1440-220um — test GUI"
STEPS = 1000              # trackbar integer resolution
EXP_CAP_US = 100_000.0    # upper end of the exposure slider (100 ms); spinless cap
FPS_CAP = 250.0           # upper end of the fps slider (camera real max ~220)


def _geom(lo: float, hi: float, frac: float) -> float:
    """Geometric (log) interpolation — good for the wide exposure range."""
    lo = max(lo, 1e-6)
    return lo * (hi / lo) ** max(0.0, min(1.0, frac))


def _geom_frac(lo: float, hi: float, value: float) -> float:
    import math
    lo = max(lo, 1e-6)
    return math.log(max(value, lo) / lo) / math.log(hi / lo)


def main() -> None:
    cam = BaslerACA1440()
    try:
        cam.connect()
    except Exception as exc:
        print(f"Could not connect to camera: {exc}")
        print("Is the Pylon Viewer (or another client) holding the camera?")
        return

    info = cam.device_info
    exp_lo, exp_hi = cam.exposure_range()
    fps_lo, fps_hi = cam.frame_rate_range()
    exp_cap = min(exp_hi, EXP_CAP_US)
    fps_cap = min(fps_hi, FPS_CAP)

    cam.set_exposure(min(2000.0, exp_hi))
    cam.set_frame_rate(min(60.0, fps_hi))

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, 960, 760)

    def on_exp(v: int) -> None:
        cam.set_exposure(_geom(exp_lo, exp_cap, v / STEPS))

    def on_fps(v: int) -> None:
        cam.set_frame_rate(max(fps_lo, fps_lo + (fps_cap - fps_lo) * v / STEPS))

    cv2.createTrackbar("exposure", WINDOW,
                       int(_geom_frac(exp_lo, exp_cap, cam.get_exposure()) * STEPS),
                       STEPS, on_exp)
    cv2.createTrackbar("fps", WINDOW,
                       int((cam.get_frame_rate() - fps_lo) / (fps_cap - fps_lo) * STEPS),
                       STEPS, on_fps)

    writer = None
    rec_path = ""
    cam.start()
    print(f"Live: {info['model']} s/n {info['serial']}  "
          f"({cam.sensor_size()[0]}x{cam.sensor_size()[1]}).  "
          f"s=snapshot  r=record  q/ESC=quit")

    count, t0, measured = 0, perf_counter(), 0.0
    try:
        while True:
            frame = cam.grab()  # mono uint8 HxW
            bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            if writer is not None:
                writer.write(bgr)

            count += 1
            now = perf_counter()
            if now - t0 >= 0.5:
                measured, count, t0 = count / (now - t0), 0, now

            disp = bgr.copy()
            status = (f"{measured:5.1f} fps   exp {cam.get_exposure():.0f} us"
                      f"   (target {cam.get_frame_rate():.1f} / resulting "
                      f"{cam.resulting_frame_rate():.1f})")
            cv2.putText(disp, status, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 255, 0), 1, cv2.LINE_AA)
            if writer is not None:
                cv2.putText(disp, "REC", (disp.shape[1] - 70, 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.imshow(WINDOW, disp)

            # window closed via the X button
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            elif key == ord("s"):
                os.makedirs("captures", exist_ok=True)
                name = datetime.now().strftime("captures/basler_%Y%m%d_%H%M%S_%f.tiff")
                cv2.imwrite(name, frame)
                print(f"snapshot -> {name}")
            elif key == ord("r"):
                if writer is None:
                    os.makedirs("recordings", exist_ok=True)
                    rec_path = datetime.now().strftime("recordings/basler_%Y%m%d_%H%M%S.avi")
                    size = (frame.shape[1], frame.shape[0])
                    fps = cam.resulting_frame_rate() or cam.get_frame_rate()
                    writer = _open_writer(rec_path, fps, size)
                    print(f"recording -> {rec_path}" if writer else "record: no codec available")
                else:
                    writer.release()
                    writer = None
                    print(f"recording stopped -> {rec_path}")
    finally:
        if writer is not None:
            writer.release()
        cam.stop()
        cam.disconnect()
        cv2.destroyAllWindows()


def _open_writer(path: str, fps: float, size):
    """Open a VideoWriter, preferring lossless FFV1, falling back to MJPG."""
    for codec in ("FFV1", "MJPG"):
        w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*codec), max(fps, 1.0), size, True)
        if w.isOpened():
            return w
    return None


if __name__ == "__main__":
    main()
