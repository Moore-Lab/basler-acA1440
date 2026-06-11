# basler-acA1440 — Development Session Log

Running, chronological record of development for **this repo only** (`basler-acA1440`,
the Basler acA1440-220um driver/API + test GUI). Write here for any change to this
module; dock- or top-level changes go in their own repos' logs.

This is a low-level camera module: once the driver + GUI are validated against hardware
and stable, this log will largely stop accruing entries — development moves up to the
dock.

Newest entries first. Keep entries short and factual; convert relative dates to absolute.
See the [README](../README.md) for goals and backend setup.

---

## 2026-06-11 — Session log started; implementation baseline

**Context.** First logged session. Module is already implemented (last commit "Basler
bring-up"). Recording the baseline.

**Implemented:**

- `basler_acA1440/camera.py` — pypylon driver `BaslerACA1440`: connect/disconnect (Mono8,
  manual `AcquisitionFrameRateEnable`), device info, sensor size, exposure
  get/set/range, frame-rate get/set/range + `resulting_frame_rate()`, start/stop, one-shot
  **and** streaming `grab()` (one path whether or not continuous grab is running),
  `frames()` generator, context-manager support. Mirrors the dock's `CameraBase` surface.
- `basler_acA1440/gui.py` — standalone OpenCV (highgui) test GUI: live preview,
  geometric/log exposure slider + linear fps slider, snapshot (`s` → `captures/`, TIFF),
  record (`r` → `recordings/`, FFV1 → MJPG fallback), live measured-fps overlay. Qt-free,
  intentionally throwaway bring-up tooling.
- `smoke_test.py` — headless check: enumerate devices, open, report info/ranges, set
  modest exposure + 60 fps, grab a 120-frame burst, print measured fps.

**Open item — hardware not yet exercised this session.** Needs a real acA1440-220um +
Pylon runtime. **TODO:** run `smoke_test.py` and the GUI; log measured fps, any node-name
or firmware quirks (e.g. `ResultingFrameRate` vs `ResultingFrameRateAbs`), and codec
availability for recording.

**Next (basler):** hardware validation; then freeze the public surface so the dock can
depend on it.
