#!/usr/bin/env python3
"""
Sets up the simulator. Run this once after downloading it, and again after updating it.

It:
1. creates a Python environment for the simulator in the venv folder,
2. installs the packages in requirements.txt into it,
3. checks they work,
4. tells Webots to run the robot's code with that Python (controllers/psc_robot/runtime.ini).

Your other Python projects aren't affected.

It needs Python 3.13. If you start it with another version, it finds Python 3.13 and uses
that instead. Double-click it on Windows, or in a terminal in this folder run
    python3.13 setup.py        (macOS and Linux)
    py -3.13 setup.py          (Windows)
"""
from __future__ import annotations

import os
import platform
import shutil
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

# The robot's packages need Python 3.13: on Windows, april_vision's camera packages
# (winrt) have no versions for Python 3.14 yet.
WANTED = (3, 13)
WANTED_TEXT = "3.13"
DOWNLOAD = "https://www.python.org/downloads/latest/python3.13/"


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def find_wanted_python() -> str | None:
    """Find a Python 3.13 on this computer, or None if there isn't one."""
    candidates: list[list[str]] = []
    if platform.system() == "Windows":
        candidates.append(["py", f"-{WANTED_TEXT}"])
    for name in (f"python{WANTED_TEXT}", "python3", "python"):
        if shutil.which(name):
            candidates.append([shutil.which(name)])
    for command in candidates:
        try:
            out = subprocess.run(
                command + ["-c", "import sys; print(sys.version_info[:2] == "
                                 f"{WANTED}); print(sys.executable)"],
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        lines = out.stdout.split()
        if out.returncode == 0 and len(lines) >= 2 and lines[0] == "True":
            return lines[1]
    return None


def pause() -> None:
    if sys.stdin.isatty():
        input("Press Enter to close.")


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
    if sys.version_info[:2] != WANTED:
        # Started with another Python, for example by double-clicking when a newer one is
        # installed too: run setup again with Python 3.13 if it's on this computer.
        if platform.system() == "Windows":
            os.system("")
        print(f"This is Python {platform.python_version()}, but the simulator needs "
              f"Python {WANTED_TEXT}.")
        wanted = find_wanted_python()
        if wanted is None:
            print(f"\n{RED}Python {WANTED_TEXT} isn't installed. Install it from {DOWNLOAD} "
                  f"then run setup.py again.{RESET}")
            pause()
            sys.exit(1)
        print(f"Running setup with Python {WANTED_TEXT} instead ({wanted})\n", flush=True)
        sys.exit(subprocess.call([wanted, str(Path(__file__).resolve())]))
    try:
        main()
    except Exception:
        traceback.print_exc()
        print(f"\n{RED}Setup failed: see the error above.{RESET}")
        pause()
        sys.exit(1)
    pause()
