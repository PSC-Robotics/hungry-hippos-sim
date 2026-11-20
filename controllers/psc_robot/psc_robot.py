"""
Runs robot.py (in this folder) on the simulated robot, as the real robot runs the robot.py
on your USB stick. robot.py uses the PSC robot library as usual: here, sr.robot3 is the
simulated version in sr/robot3, wired as set in sim_wiring.py.
"""
import runpy
import sys
import traceback
from pathlib import Path

import sr.robot3 as sim

CODE = Path(__file__).with_name("robot.py")


def main() -> None:
    crashed = False
    try:
        runpy.run_path(str(CODE), run_name="__main__")
    except SystemExit:
        pass
    except Exception:
        crashed = True
        traceback.print_exc()
        print("Your code crashed", flush=True)
    robot = sim._INSTANCE
    if robot is None:
        return
    robot._finish()
    if crashed:
        robot._status.state = "finished"
        robot.brain.buzzer.buzz(sim.Note.C7, 0.4)
    print("Your code has finished", flush=True)
    # Keep the simulation running, with the motors stopped, until it's stopped or reset.
    while True:
        robot._step()


if __name__ == "__main__":
    sys.exit(main())
