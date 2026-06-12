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

## 2026-06-12 — No-drop start(); GUI is now a shared shell

- `start(max_throughput=False)` added: `True` uses `GrabStrategy_OneByOne` (queued,
  **no-drop**) for full-rate recording; `False` keeps `LatestImageOnly` for
  low-latency preview. Used by the dock's `AcquisitionEngine`.
- `gui.py` reduced from a standalone GUI to a **thin shell** over
  `camera_dock.preview.run(BaslerACA1440())` — all GUI logic now lives once in the dock
  (no duplication). The driver itself still never imports the dock (smoke test remains
  standalone); only the GUI shell does, via a sys.path insert to the dock root.
- Validated through the shared engine: **227.8 fps** acquisition while recording,
  456/456 frames, **0 dropped** (see the dock log for full Stage 1 details).

## 2026-06-11 — Hardware validation PASS

**Context.** Ran the module against real hardware, closing the baseline's open TODO.
Environment: anaconda3 base, Python 3.13.5, pypylon OK, numpy 2.1.3, cv2 4.12.0.

**Camera:** acA1440-220um, s/n 40103621, Basler. Sensor 1440×1080, Mono8.
Exposure range 21 µs – 10 s. Frame-rate node range 0.0063 – 1e6 fps (the 1e6 is a
nominal node max, not physically achievable — the real ceiling is bandwidth/readout).

**`smoke_test.py`:** PASS. Exposure 2000 µs, target 60 fps → resulting 60.0 → **60.3 fps
measured** over a 120-frame burst.

**Max-fps check** (200 µs exposure, requested 1000 fps, full ROI): driver clamped to the
achievable rate; `resulting_frame_rate()` estimated **227.7 fps** and the streaming
`grab()` path **measured 227.7 fps** over 400 frames with no drops — at/above the spec
"up to 220 fps." `ResultingFrameRate` node is present on this firmware (no Abs-suffix
fallback needed); its estimate matched reality exactly.

**Loose end resolved:** the crashed session had left an orphaned `python -m
basler_acA1440.gui` process (PID 22636, started 1:32 PM) holding the camera
*exclusively* — `connect()` failed with "Device is exclusively opened by another client"
until it was terminated. Worth knowing: a crashed GUI keeps the USB3 camera locked until
its process is killed.

**Verdict:** driver validated end-to-end (connect, info, exposure/fps get/set/range,
resulting-fps, streaming grab at full rate). Public surface is safe for the dock to
depend on.

**Next (basler):** GUI snapshot/record paths still only exercised by import, not a
confirmed file write — optionally verify `s`/`r` produce valid TIFF/AVI. Otherwise this
module is effectively done; activity moves up to the dock.

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
