"""Standalone test GUI for the Basler acA1440-220um.

Lightweight harness to validate the driver in isolation: live preview plus
exposure / frame-rate controls, snapshot, and record. The GUI framework is
intentionally left open pending the planning discussion in ``xsphere-daq``.

Run with::

    python -m basler_acA1440.gui
"""

from __future__ import annotations

from .camera import BaslerACA1440


def main() -> None:
    raise NotImplementedError("Test GUI not implemented yet — see development plan.")


if __name__ == "__main__":
    main()
