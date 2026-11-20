# The Simulated Robot

The simulator has a ready-made robot, which you program with the same robot library
(`sr.robot3`) and the same code as a real PSC robot. It's a two wheeled robot with a two
servo grabber, a camera and the brain board's LEDs. It finds its way with the camera, as
a real robot does: there's no GPS or compass.

Your code goes in `controllers/psc_robot/robot.py`. Save it, then press **Reset
Simulation** (⇧⌘T) in Webots to run it from the start. Your prints, buzzer notes and
any errors appear in the Webots **Console**.

## Attached boards

Everything is wired to the brain board, as on a real robot. The pins below are set in
`controllers/psc_robot/sim_wiring.py`, the simulator's version of the wires on the HAT.

| Part | Connected to | In your code |
|------|--------------|--------------|
| Left wheel motor | Motor pad A: GPIO 20 (IN1), GPIO 21 (IN2) | `robot.brain.dc_motor(in1_pin=20, in2_pin=21)` |
| Right wheel motor | Motor pad B: GPIO 19 (IN1), GPIO 4 (IN2) | `robot.brain.dc_motor(in1_pin=19, in2_pin=4)` |
| Servo driver (PCA9685) | SDA GPIO 17, SCL GPIO 27, address 0x40 | `robot.brain.servo_driver(sda=17, scl=27)` |
| Grabber, left jaw | Servo driver channel 0 | `grabber.servos[0].position` |
| Grabber, right jaw | Servo driver channel 1 | `grabber.servos[1].position` |
| Camera | USB | `robot.camera` |
| LED | The brain board | `robot.brain.led` |
| Buzzer | The brain board | `robot.brain.buzzer` |
| Start button | The brain board | `robot.brain.start_button` |

Using pins that aren't wired raises an error saying what is. The pins the robot uses
itself (the start button, buzzer and LEDs' pins, and GPIO 0 to 3, 14 and 15) are refused,
as on a real robot.

## Moving

Both wheels go forwards for positive power. Power is from `-1` to `1`, or `BRAKE` or
`COAST`:

```python
from sr.robot3 import Robot

robot = Robot()
left_wheel = robot.brain.dc_motor(in1_pin=20, in2_pin=21)
right_wheel = robot.brain.dc_motor(in1_pin=19, in2_pin=4)

left_wheel.power = 0.5      # Forwards
right_wheel.power = 0.5
robot.sleep(2)
left_wheel.power = 0.3      # Turn right on the spot
right_wheel.power = -0.3
robot.sleep(0.5)
left_wheel.power = 0
right_wheel.power = 0
```

At power `1` a wheel turns at 15 radians a second, which is 0.75 metres a second. Giving a
motor's pins the other way round, `dc_motor(in1_pin=21, in2_pin=20)`, turns it the other
way, as on a real robot.

## The grabber

Two jaws at the front, each on its own servo. Position `-1` is open and `1` is closed, for
both jaws. `None` lets a jaw go limp.

```python
grabber = robot.brain.servo_driver(sda=17, scl=27)
grabber.servos[0].position = 1     # Close both jaws
grabber.servos[1].position = 1
robot.sleep(0.5)                   # A jaw takes about 0.2 seconds to close
```

Open, the jaws make a funnel that guides a token into the middle. Closed, they hold a token
against the front of the robot, so it comes with the robot when it reverses or turns.

## Camera

`robot.camera.see()` finds the arena's markers with the same code as a real robot, and
gives the same `Marker` objects:

```python
for marker in robot.camera.see():
    print(marker.id, marker.position.distance, marker.position.horizontal_angle)
```

| | |
|---|---|
| Resolution | 640 × 480 |
| Field of view | 63° across (1.1 radians), 49° up and down |
| Position | 100mm in front of the axle, 260mm above the floor, facing straight ahead |
| Markers | Walls: IDs 0 to 19, 150mm. Tokens: IDs 20 to 100, 80mm |

Distances are within about 1% of the true distance. Because the camera faces straight
ahead from 260mm up, a token goes out of view below the camera when it's about 280mm away
along the floor, so drive the last part of the way to a token without looking.
`robot.camera.see(save="image.jpg")` saves what the camera saw, with the markers
outlined.

## LEDs

Two LEDs on top of the robot. The one on the left is the status LED, which the robot sets:
blue while it starts, pulsing green while it waits for the start button, green while your
code runs and grey when it's finished. The one on the right is yours:

```python
from sr.robot3 import Colour

robot.brain.led.colour = Colour.RED
robot.brain.led.colour = (255, 80, 0)   # Any colour
robot.brain.led.g = True                # One channel at a time: True, False or 0 to 255
```

## Start button and buzzer

The robot waits for the start button when it's created. Click the 3D view, then press
**S** to press the start button, or wait 2 seconds and it starts by itself. Once your code
has started, **S** works as `robot.brain.start_button`: `was_pressed()` and `is_pressed`.

As in a match, the robot is stopped 150 seconds after the start button: the Console says
"Match over", the motors stop and your code ends.

`robot.brain.buzzer.buzz()` plays the tone through the robot's speaker, and also prints the note in
the Console. As on the real robot, a new tone replaces the one playing. If you can't hear it,
check that sound isn't muted in Webots.

## The robot

| | |
|---|---|
| Size | 450mm long (150mm behind the axle to the jaws' tips 300mm ahead), 370mm wide, or 460mm across the tips of the open jaws |
| Wheels | 50mm radius, 340mm apart, on an axle across the middle of the body |
| Mass | About 3.3kg |
| Flag | On a pole at the back, in the robot's corner colour |

## Not simulated yet

These raise an error saying they aren't in the simulator yet: digital pins
(`robot.brain.pins`), stepper motors, I2C devices, the battery sensor, gamepads, the
Arduino and ultrasound sensors.

As on a real PSC robot, there are no Student Robotics boards: `robot.motor_boards` and
`robot.servo_boards` are empty, and `robot.motor_board` or `robot.servo_board` raises an
error pointing you to `robot.brain`. `robot.is_simulated` is `True`, so your code can tell
it's in the simulator. Servos also have `disable()`, `set_duty_limits()` and
`get_duty_limits()` as on the robot, although the duty limits don't change how far a
simulated servo moves.

## Differences from a real robot

- **Perfect sensors and motors.** There's no noise: the camera sees markers exactly, and
  the wheels never slip unless they're pushing something. Real readings will vary more.
- **Made-up sizes.** The robot's size, mass and wheels are assumptions. Wall thickness,
  token mass and token friction aren't in the rule book either, so they're guesses too.
- **Servo direction.** On a real robot, two mirrored servos turn opposite ways for the same
  position. In the simulator, both jaws close at `1`, which `sim_wiring.py` sets up.
