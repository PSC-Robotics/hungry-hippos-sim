#!/usr/bin/env python3
"""
Sets up the simulator. Run this once after downloading it, and again after updating it.

It:
1. creates a Python environment for the simulator in the venv folder,
2. installs the packages in requirements.txt into it,
3. checks they work,
4. tells Webots to run the robot's code with that Python (controllers/psc_robot/runtime.ini).

Your other Python projects aren't affected.

Run it with Python 3.13: double-click it on Windows, or in a terminal in this folder run
    python3.13 setup.py        (macOS and Linux)
    py -3.13 setup.py          (Windows)
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import traceback
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
REQUIREMENTS = ROOT / "requirements.txt"
RUNTIME_INI = ROOT / "controllers" / "psc_robot" / "runtime.ini"

RED, GREEN, RESET = "\x1b[31;1m", "\x1b[32m", "\x1b[0m"


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(*args: str) -> None:
    subprocess.check_call([str(a) for a in args], cwd=ROOT)


def write_runtime_ini(python: Path) -> None:
    """Point Webots at the simulator's Python, keeping any other settings in the file."""
    kept: list[str] = []
    in_python = False
    if RUNTIME_INI.exists():
        for line in RUNTIME_INI.read_text().splitlines():
            if line.strip() == "[python]":
                in_python = True
            elif in_python and line.strip().startswith("["):
                in_python = False
                kept.append(line)
            elif not in_python:
                kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    if kept:
        kept.append("")
    kept += ["[python]", f"COMMAND = {python}", ""]
    RUNTIME_INI.write_text("\n".join(kept))


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # keep our messages in order with pip's
    if platform.system() == "Windows":
        os.system("")  # lets the Windows console show the coloured messages
    print(f"Python {platform.python_version()} on {platform.platform()}")
    if sys.version_info[:2] != (3, 13):
        print(f"{RED}This simulator is set up for Python 3.13, but this is Python "
              f"{platform.python_version()}. It may still work, but if setup fails, "
              f"install Python 3.13 and run setup.py with it.{RESET}")

    print(f"\nCreating the simulator's Python environment in {VENV}")
    venv.create(VENV, with_pip=True, clear=True)
    python = venv_python()

    print("\nInstalling the packages it needs (this can take a few minutes)")
    run(python, "-m", "pip", "install", "--upgrade", "pip")
    run(python, "-m", "pip", "install", "--only-binary=:all:", "-r", REQUIREMENTS)

    print("\nChecking they work")
    run(python, "-c", "import cv2, numpy, april_vision")

    print(f"\nTelling Webots to use this Python ({RUNTIME_INI.relative_to(ROOT)})")
    write_runtime_ini(python)

    print(f"\n{GREEN}Setup complete. Open worlds/hungry_hippos.wbt in Webots to start.{RESET}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        print(f"\n{RED}Setup failed: see the error above.{RESET}")
        if sys.stdin.isatty():
            input("Press Enter to close.")
        sys.exit(1)
    if sys.stdin.isatty():
        input("Press Enter to close.")
