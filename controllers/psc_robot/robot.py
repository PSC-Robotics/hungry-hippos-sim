"""
Your robot code. It runs on the simulated robot the same way it would on a real robot
wired the same way.

The simulated robot is wired as in sim_wiring.py:
  - left wheel:  robot.brain.dc_motor(20, 21)   (motor pad A)
  - right wheel: robot.brain.dc_motor(19, 4)    (motor pad B)
  - grabber:     robot.brain.servo_driver(sda=17, scl=27), servos 0 (left) and 1 (right):
                 -1 is open, 1 is closed
  - camera:      robot.camera, on the front of the robot

Edit this file, save it, then press Reset Simulation in Webots to run it again.
SIMULATED_ROBOT.md describes everything the robot can do.
"""
from sr.robot3 import Colour, Note, Robot

robot = Robot()  # Waits for the start button: press S in the 3D view, or wait 2 seconds

left_wheel = robot.brain.dc_motor(20, 21)
right_wheel = robot.brain.dc_motor(19, 4)
grabber = robot.brain.servo_driver(sda=17, scl=27)

print(f"Starting in zone {robot.zone}")
robot.brain.led.colour = Colour.GREEN

# What can the camera see?
for marker in robot.camera.see():
    print(f"Marker {marker.id} is {marker.position.distance:.0f}mm away")

# Drive forwards for a second, then stop
left_wheel.power = 0.5
right_wheel.power = 0.5
robot.sleep(1)
left_wheel.power = 0
right_wheel.power = 0

# Open the grabber, then close it
for position in (-1, 1):
    grabber.servos[0].position = position
    grabber.servos[1].position = position
    robot.sleep(0.5)

robot.brain.buzzer.buzz(Note.C6, 0.2)
print("Done. Now write your own code here.")
