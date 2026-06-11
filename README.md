# basler-acA1440

Driver/API + test GUI for the **Basler acA1440-220um** (USB3 Vision, mono, 1.6 MP, up to 220 fps).

This repo is a self-contained module: a thin Python driver around the camera plus a
small GUI used to exercise it. It is consumed as a git submodule by
[`xsphere-camera-dock`](https://github.com/Moore-Lab/xsphere-camera-dock), which combines
this and other camera modules into a single experiment-control surface.

## Goals

- **Driver (`basler_acA1440/camera.py`)** — connect, configure (exposure, frame rate),
  grab single frames, and stream frames continuously. Should expose the same conceptual
  interface as the other camera modules so the dock can treat them uniformly.
- **Test GUI (`basler_acA1440/gui.py`)** — live preview, exposure/frame-rate controls,
  snapshot, and record. Used to validate the camera in isolation before integration.

## Backend

Built on Basler's **pypylon** (Python bindings for the Pylon SDK). The Pylon runtime
must be installed separately (it ships with the Basler eval software you already use).

```bash
pip install -r requirements.txt
```

## Status

Driver + test GUI implemented; hardware validation pending. Development is tracked in
[`docs/session-log.md`](docs/session-log.md).
