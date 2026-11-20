"""
How the simulated robot is wired: which pins each part is connected to.

This is the simulator's version of the wiring on a real robot. Your code uses the same
pins as on the real robot, and this table says which simulated part each one drives.
To wire something differently, change it here, as you would move the wires on the HAT.
"""

# DC motors, through motor drivers on the HAT's motor pads, as on the real brain board:
#   robot.brain.dc_motor(in1_pin=20, in2_pin=21)  ->  the left wheel
#   robot.brain.dc_motor(in1_pin=19, in2_pin=4)   ->  the right wheel
# Swapping in1_pin and in2_pin in your code turns the wheel the other way, as on the robot.
DC_MOTORS = {
    (20, 21): "left wheel motor",
    (19, 4): "right wheel motor",
}

# PCA9685 servo drivers, by the GPIO pins their SDA and SCL are wired to, and their I2C
# address, with the servo plugged into each of the driver's channels:
#   robot.brain.servo_driver(sda=17, scl=27).servos[0]  ->  the grabber's left jaw
#   robot.brain.servo_driver(sda=17, scl=27).servos[1]  ->  the grabber's right jaw
# For each servo: its device in the robot model, and its angle (radians) at position -1
# and at position 1. Both jaws are fitted so that -1 is open and 1 is closed.
SERVO_DRIVERS = {
    (17, 27, 0x40): {
        0: ("grabber left servo", 0.6, -0.6),
        1: ("grabber right servo", -0.6, 0.6),
    },
}

# The pins the robot uses itself, as on the real robot (see the Brain GPIO API docs).
RESERVED_PINS = {
    0: "the HAT's EEPROM", 1: "the HAT's EEPROM",
    2: "I2C (SDA), with the battery sensor", 3: "I2C (SCL), with the battery sensor",
    5: "the start button: use robot.brain.start_button",
    13: "the buzzer: use robot.brain.buzzer.buzz()",
    14: "the serial port (bus servos)", 15: "the serial port (bus servos)",
    18: "the LEDs (WS2812 data): use robot.brain.led",
}

# The wheels' top speed, in radians per second, at power 1 (the robot model's maxVelocity).
WHEEL_MAX_SPEED = 15.0

# The arena's markers, for the camera: their IDs and sizes (the black square, in metres),
# as built by tools/build_arena.py from the rule book.
MARKER_SIZES = {
    range(0, 20): 0.150,    # wall markers
    range(20, 101): 0.080,  # tokens
}
