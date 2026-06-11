"""Hardware smoke test for the Basler acA1440-220um driver.

Run with the camera plugged in and the Pylon runtime installed::

    python smoke_test.py

It enumerates devices, opens the camera, reports info/ranges, sets a modest
exposure + frame rate, grabs a short burst, and prints the measured frame rate.
No GUI, no files written.
"""

from __future__ import annotations

import time

import pypylon.pylon as pylon

from basler_acA1440 import BaslerACA1440


def list_devices() -> None:
    devices = pylon.TlFactory.GetInstance().EnumerateDevices()
    if not devices:
        print("No Pylon devices found.")
        return
    print(f"Found {len(devices)} device(s):")
    for d in devices:
        print(f"  - {d.GetModelName()}  serial={d.GetSerialNumber()}  ({d.GetVendorName()})")


def main() -> None:
    list_devices()

    with BaslerACA1440() as cam:
        print("\nConnected:", cam.device_info)
        print("Sensor size (w x h):", cam.sensor_size())
        print("Exposure range (us):", cam.exposure_range())
        print("Frame-rate range (fps):", cam.frame_rate_range())

        cam.set_exposure(2000.0)   # 2 ms
        cam.set_frame_rate(60.0)
        print(f"\nSet exposure -> {cam.get_exposure():.1f} us, "
              f"target fps -> {cam.get_frame_rate():.1f}, "
              f"resulting fps -> {cam.resulting_frame_rate():.1f}")

        n = 120
        print(f"\nGrabbing {n} frames...")
        cam.start()
        t0 = time.perf_counter()
        shape = None
        for i in range(n):
            frame = cam.grab()
            shape = frame.shape
        dt = time.perf_counter() - t0
        cam.stop()

        print(f"Grabbed {n} frames of shape {shape} in {dt:.3f} s "
              f"=> {n / dt:.1f} fps measured")
        print("\nSmoke test OK.")


if __name__ == "__main__":
    main()
