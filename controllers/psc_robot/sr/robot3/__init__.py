"""
A simulated version of the PSC robot library (psc-sr-robot3), for the Webots arena.

Your code uses the same names as on the real robot:

    from sr.robot3 import Colour, Note, Robot

    robot = Robot()
    robot.brain.dc_motor(in1_pin=20, in2_pin=21).power = 0.5
    robot.brain.servo_driver(sda=17, scl=27).servos[0].position = 1
    robot.brain.led.colour = Colour.GREEN

Which pins drive which simulated part is set in sim_wiring.py. robot.camera.see() finds
markers with april_vision, as on the robot. Parts the simulator doesn't have yet (digital
pins, steppers, I2C devices, the battery sensor, gamepads) raise an error saying so.
"""
from __future__ import annotations

import math
import struct
import sys
import tempfile
import wave
from enum import Enum, IntEnum
from pathlib import Path
from typing import Optional, Union

from controller import Keyboard
from controller import Robot as WebotsRobot
from controller import Speaker as WebotsSpeaker

import sim_wiring

__all__ = [
    "BRAKE", "COAST", "COMP", "DEV", "INPUT", "INPUT_PULLUP", "OUTPUT", "LED_A", "LED_B",
    "LED_C", "Colour", "Note", "Robot",
]

_webots = WebotsRobot()
_TIMESTEP = int(_webots.getBasicTimeStep())

# Seconds from the start button to the end of a match, as the competition USB's
# game_timeout. The robot is stopped then, as in a real match. Set to None to turn it off.
GAME_TIMEOUT: Optional[float] = 150


class _MatchOver(SystemExit):
    """Raised inside your code when the match time is up, to stop it."""
_INSTANCE: Optional["Robot"] = None  # the Robot your code made, for the controller to stop


class MotorPower(IntEnum):
    BRAKE = 0
    COAST = -1024


BRAKE = MotorPower.BRAKE
COAST = MotorPower.COAST


class RobotMode(str, Enum):
    COMP = "COMP"
    DEV = "DEV"


COMP = RobotMode.COMP
DEV = RobotMode.DEV


class GPIOPinMode(str, Enum):
    INPUT = "INPUT"
    INPUT_PULLUP = "INPUT_PULLUP"
    OUTPUT = "OUTPUT"


INPUT = GPIOPinMode.INPUT
INPUT_PULLUP = GPIOPinMode.INPUT_PULLUP
OUTPUT = GPIOPinMode.OUTPUT
LED_A, LED_B, LED_C = 0, 1, 2


class Colour:
    """LED colours, as on Student Robotics' LEDs: (red, green, blue), each on or off."""
    OFF = (False, False, False)
    RED = (True, False, False)
    YELLOW = (True, True, False)
    GREEN = (False, True, False)
    CYAN = (False, True, True)
    BLUE = (False, False, True)
    MAGENTA = (True, False, True)
    WHITE = (True, True, True)


class Note(float, Enum):
    C6 = 1047
    D6 = 1175
    E6 = 1319
    F6 = 1397
    G6 = 1568
    A6 = 1760
    B6 = 1976
    C7 = 2093
    D7 = 2349
    E7 = 2637
    F7 = 2794
    G7 = 3136
    A7 = 3520
    B7 = 3951
    C8 = 4186


def _not_in_sim(what: str) -> NotImplementedError:
    return NotImplementedError(f"{what} isn't in the simulator yet")


def _check_pin(pin: object, name: str) -> int:
    if not isinstance(pin, int) or isinstance(pin, bool) or not 0 <= pin <= 27:
        raise ValueError(f"{name} must be a BCM GPIO number from 4 to 27")
    if pin in sim_wiring.RESERVED_PINS:
        raise ValueError(f"GPIO {pin} is used by {sim_wiring.RESERVED_PINS[pin]}")
    return pin


# ------------------------------------------------------------------------ LEDs
def _rgb(colour) -> tuple[int, int, int]:
    help_text = "A colour is (red, green, blue), each from 0 to 255"
    try:
        parts = tuple(colour)
    except TypeError:
        raise ValueError(help_text) from None
    if len(parts) != 3:
        raise ValueError(help_text)
    rgb = []
    for part in parts:
        if isinstance(part, bool):
            rgb.append(255 if part else 0)
        elif isinstance(part, int) and 0 <= part <= 255:
            rgb.append(part)
        else:
            raise ValueError(help_text)
    return rgb[0], rgb[1], rgb[2]


def _show(device, rgb: tuple[int, int, int]) -> None:
    device.set((rgb[0] << 16) | (rgb[1] << 8) | rgb[2])


class BrainLED:
    """robot.brain.led: the LED your code controls."""

    def __init__(self) -> None:
        self._device = _webots.getDevice("led")
        self._rgb = (0, 0, 0)
        _show(self._device, self._rgb)

    @property
    def colour(self):
        if all(part in (0, 255) for part in self._rgb):
            return tuple(part == 255 for part in self._rgb)
        return self._rgb

    @colour.setter
    def colour(self, value) -> None:
        self._rgb = _rgb(value)
        _show(self._device, self._rgb)

    def _channel(self, index: int):
        value = self._rgb[index]
        return value == 255 if value in (0, 255) else value

    def _set_channel(self, index: int, value) -> None:
        if isinstance(value, bool):
            value = 255 if value else 0
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError("A colour channel is True (on), False (off) or a number from 0 to 255")
        rgb = list(self._rgb)
        rgb[index] = value
        self.colour = (rgb[0], rgb[1], rgb[2])

    r = property(lambda self: self._channel(0), lambda self, v: self._set_channel(0, v))
    g = property(lambda self: self._channel(1), lambda self, v: self._set_channel(1, v))
    b = property(lambda self: self._channel(2), lambda self, v: self._set_channel(2, v))


class _StatusLED:
    """The status LED, which the robot drives: as on the real robot, code can't set it."""

    def __init__(self) -> None:
        self._device = _webots.getDevice("status led")
        self.state = "booting"

    def update(self, now: float) -> None:
        wave = (1 - math.cos(2 * math.pi * now / 2.5)) / 2
        level = 0.08 + 0.92 * wave * wave
        colour = {
            "booting": (0, 0, round(255 * level)),
            "waiting": (0, round(140 * level), 0),
            "running": (0, 255, 0),
            "finished": (60, 60, 60),
        }[self.state]
        _show(self._device, colour)


# ------------------------------------------------------------------------ motors
class DCMotor:
    """A DC motor through a two-input driver: power from -1 to 1, BRAKE or COAST."""

    def __init__(self, device, description: str) -> None:
        self._device = device
        self._description = description
        self._power: float = COAST
        device.setPosition(float("inf"))
        device.setVelocity(0.0)

    @property
    def power(self) -> float:
        return self._power

    @power.setter
    def power(self, value) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("power must be a number from -1 to 1, BRAKE or COAST")
        if value == COAST:
            self._device.setVelocity(0.0)
            self._power = COAST
            return
        if math.isnan(value) or not -1 <= value <= 1:
            raise ValueError("power must be a number from -1 to 1, BRAKE or COAST")
        self._device.setVelocity(value * sim_wiring.WHEEL_MAX_SPEED)
        self._power = float(value)

    def __repr__(self) -> str:
        return f"<DCMotor {self._description} power={self._power}>"


class _ReversedMotor(DCMotor):
    """A motor whose IN1 and IN2 are given the other way round: it turns the other way."""

    @DCMotor.power.setter
    def power(self, value) -> None:
        DCMotor.power.fset(self, value)  # check it, and remember it as given
        if self._power != COAST:
            self._device.setVelocity(-self._power * sim_wiring.WHEEL_MAX_SPEED)


# ------------------------------------------------------------------------ servos
class DriverServo:
    """One servo on a PCA9685 servo driver: position from -1 to 1, or None to go limp."""

    def __init__(self, channel: int, wiring: Optional[tuple]) -> None:
        self._channel = channel
        self._position: Optional[float] = None
        self._duty_min, self._duty_max = 1000, 2000  # as on the real driver; no effect here
        self._warned = False
        self._device = self._sensor = None
        if wiring is not None:
            name, self._angle_minus, self._angle_plus = wiring
            self._device = _webots.getDevice(name)
            self._full_torque = self._device.getMaxTorque()
            self._sensor = _webots.getDevice(f"{name} sensor")
            self._sensor.enable(_TIMESTEP)

    def set_duty_limits(self, lower: int, upper: int) -> None:
        """Set the pulse lengths (µs) of positions -1 and 1. Checked as on the real robot,
        but the simulated servo always moves between its fitted angles."""
        message = "Servo pulse limits are ints in µs, in the range 500 to 4000"
        if not (isinstance(lower, int) and isinstance(upper, int)) or isinstance(lower, bool) \
                or isinstance(upper, bool):
            raise TypeError(message)
        if not (500 <= lower <= 4000 and 500 <= upper <= 4000):
            raise ValueError(message)
        self._duty_min, self._duty_max = lower, upper

    def get_duty_limits(self) -> tuple[int, int]:
        """The pulse lengths (µs) of positions -1 and 1."""
        return self._duty_min, self._duty_max

    def disable(self) -> None:
        """Stop sending pulses, so the servo goes limp."""
        self.position = None

    @property
    def position(self) -> Optional[float]:
        return self._position

    @position.setter
    def position(self, value: Optional[float]) -> None:
        if value is not None:
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or math.isnan(value) or not -1 <= value <= 1):
                raise ValueError("position must be a number from -1 to 1, or None")
            value = float(value)
        self._position = value
        if self._device is None:
            if not self._warned:
                self._warned = True
                print(f"Servo {self._channel} isn't connected to anything in the simulator "
                      "(see sim_wiring.py)", flush=True)
            return
        if value is None:  # Limp: no holding torque
            self._device.setAvailableTorque(0)
            return
        self._device.setAvailableTorque(self._full_torque)
        share = (value + 1) / 2
        self._device.setPosition(self._angle_minus + share * (self._angle_plus - self._angle_minus))


class ServoDriver:
    """A PCA9685 servo driver, with 16 servo channels: servos[0] to servos[15]."""

    def __init__(self, wiring: dict) -> None:
        self.servos = tuple(DriverServo(channel, wiring.get(channel)) for channel in range(16))


# ------------------------------------------------------------------------ buzzer, button
class Buzzer:
    """robot.brain.buzzer: plays its tones through the robot's speaker, and prints them in the
    Console. As on the real robot, a new tone replaces the one playing."""

    _RATE = 22050  # samples a second

    def __init__(self, robot: "Robot") -> None:
        self._robot = robot
        try:
            self._speaker = _webots.getDevice("buzzer")
        except Exception:
            self._speaker = None
        self._folder = Path(tempfile.gettempdir()) / "psc-sim-buzzer"
        self._playing: Optional[str] = None

    def _tone_file(self, frequency: float, duration: float) -> str:
        """A WAV file of a buzzer tone: a square wave, faded in and out to avoid clicks."""
        path = self._folder / f"{frequency:.1f}Hz-{round(duration * 1000)}ms.wav"
        if not path.exists():
            self._folder.mkdir(parents=True, exist_ok=True)
            count = max(1, round(duration * self._RATE))
            fade = min(count // 2, round(0.005 * self._RATE))
            frames = bytearray()
            for i in range(count):
                level = 1.0 if math.sin(2 * math.pi * frequency * i / self._RATE) >= 0 else -1.0
                envelope = min(1.0, i / fade if fade else 1.0, (count - 1 - i) / fade if fade else 1.0)
                frames += struct.pack("<h", int(9000 * level * envelope))
            temp = path.with_suffix(".tmp")
            with wave.open(str(temp), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(self._RATE)
                out.writeframes(bytes(frames))
            temp.replace(path)
        return str(path)

    def buzz(self, frequency: float, duration: float, *, blocking: bool = False,
             volume: Optional[float] = None) -> None:
        if not 8 <= float(frequency) <= 10_000:
            raise ValueError("Frequency must be between 8 and 10000Hz")
        if not 0 <= float(duration) <= 60:
            raise ValueError("Duration is a float in seconds between 0 and 60")
        if volume is not None and not 0 <= float(volume) <= 1:
            raise ValueError("Volume must be from 0 (silent) to 1 (loudest)")
        name = frequency.name if isinstance(frequency, Note) else f"{float(frequency):g}Hz"
        print(f"Buzzer: {name} for {float(duration):g}s", flush=True)
        if self._speaker is not None:
            if self._playing is not None:
                self._speaker.stop(self._playing)
                self._playing = None
            if float(duration) > 0 and (volume is None or float(volume) > 0):
                sound = self._tone_file(float(frequency), float(duration))
                WebotsSpeaker.playSound(self._speaker, self._speaker, sound,
                                        1.0 if volume is None else float(volume), 1.0, 0.0, False)
                self._playing = sound
        if blocking:
            self._robot.sleep(float(duration))


class StartButton:
    """robot.brain.start_button: press S in the 3D view (click it first) to press it."""

    def __init__(self) -> None:
        self._keyboard = _webots.getKeyboard()
        self._keyboard.enable(_TIMESTEP)
        self.is_pressed = False
        self._presses = 0
        self._seen = 0

    def _poll(self) -> None:
        held = False
        key = self._keyboard.getKey()
        while key != -1:
            if key in (ord("S"), ord("S") | Keyboard.SHIFT):
                held = True
            key = self._keyboard.getKey()
        if held and not self.is_pressed:
            self._presses += 1
        self.is_pressed = held

    def was_pressed(self) -> bool:
        pressed = self._presses > self._seen
        self._seen = self._presses
        return pressed

    def _forget_presses(self) -> None:
        self._seen = self._presses


# ------------------------------------------------------------------------ the brain
class _Pins:
    def __getitem__(self, pin: int):
        _check_pin(pin, "pin")
        raise _not_in_sim("robot.brain.pins")


class Brain:
    """robot.brain: everything on the brain board."""

    def __init__(self, robot: "Robot") -> None:
        self.led = BrainLED()
        self.buzzer = Buzzer(robot)
        self.start_button = StartButton()
        self.pins = _Pins()
        self._motors: dict = {}
        self._drivers: dict = {}
        self._claims: dict[int, str] = {}

    def _claim(self, pins: tuple, owner: str) -> None:
        for pin in pins:
            if self._claims.get(pin, owner) != owner:
                raise ValueError(f"GPIO {pin} is already used by {self._claims[pin]}")
        for pin in pins:
            self._claims[pin] = owner

    def dc_motor(self, in1_pin: int, in2_pin: int) -> DCMotor:
        _check_pin(in1_pin, "in1_pin")
        _check_pin(in2_pin, "in2_pin")
        if in1_pin == in2_pin:
            raise ValueError("in1_pin and in2_pin must be different")
        key = (in1_pin, in2_pin)
        if key not in self._motors:
            self._claim(key, "another motor")
            description = f"IN1=GPIO {in1_pin} IN2=GPIO {in2_pin}"
            if key in sim_wiring.DC_MOTORS:
                motor = DCMotor(_webots.getDevice(sim_wiring.DC_MOTORS[key]), description)
            elif key[::-1] in sim_wiring.DC_MOTORS:
                motor = _ReversedMotor(_webots.getDevice(sim_wiring.DC_MOTORS[key[::-1]]),
                                       description)
            else:
                wired = ", ".join(f"({a}, {b})" for a, b in sim_wiring.DC_MOTORS)
                raise ValueError(f"No motor is wired to GPIO {in1_pin} and {in2_pin} in the "
                                 f"simulator. Motors are on {wired}: see sim_wiring.py")
            self._motors[key] = motor
        return self._motors[key]

    def servo_driver(self, *, sda: int, scl: int, address: int = 0x40) -> ServoDriver:
        _check_pin(sda, "sda")
        _check_pin(scl, "scl")
        key = (sda, scl, address)
        if key not in self._drivers:
            if key not in sim_wiring.SERVO_DRIVERS:
                wired = ", ".join(f"sda={a}, scl={b}, address={c:#x}"
                                  for a, b, c in sim_wiring.SERVO_DRIVERS)
                raise ValueError(f"No servo driver is wired to SDA=GPIO {sda}, SCL=GPIO {scl} "
                                 f"at address {address:#x} in the simulator. It has: {wired}")
            self._claim((sda, scl), f"an I2C bus (SDA=GPIO {sda}, SCL=GPIO {scl})")
            self._drivers[key] = ServoDriver(sim_wiring.SERVO_DRIVERS[key])
        return self._drivers[key]

    def stepper(self, *args, **kwargs):
        raise _not_in_sim("robot.brain.stepper")

    def stepper_move(self, *args, **kwargs):
        raise _not_in_sim("robot.brain.stepper_move")

    def i2c_bus(self, *args, **kwargs):
        raise _not_in_sim("robot.brain.i2c_bus")

    @property
    def battery_sensor(self):
        raise _not_in_sim("robot.brain.battery_sensor")


# ------------------------------------------------------------------------ the robot
class Robot:
    """The robot. Waits for the start button unless wait_for_start=False."""

    def __init__(self, *, wait_for_start: bool = True, **_ignored) -> None:
        global _INSTANCE
        _INSTANCE = self
        self._status = _StatusLED()
        self._brain = Brain(self)
        args = sys.argv[1:]
        self._zone = int(args[0]) if args else 0
        self._started = False
        self._start_time: Optional[float] = None
        self._match_over = False
        from .camera import SimCamera
        self._camera = SimCamera(_webots.getDevice("camera"), self, _TIMESTEP)
        print(f"Simulated robot in zone {self._zone}", flush=True)
        self.sleep(0.5)  # booting
        if wait_for_start:
            self.wait_start()
        else:
            self._start_time = _webots.getTime()

    @property
    def brain(self) -> Brain:
        return self._brain

    @property
    def buzzer(self) -> Buzzer:
        return self._brain.buzzer

    def _step(self) -> None:
        if _webots.step(_TIMESTEP) == -1:
            raise SystemExit(0)  # The simulation was stopped or reset
        self._brain.start_button._poll()
        self._status.update(_webots.getTime())
        if (GAME_TIMEOUT is not None and self._start_time is not None and not self._match_over
                and _webots.getTime() - self._start_time >= GAME_TIMEOUT):
            self._match_over = True
            print(f"Match over: {GAME_TIMEOUT:g} seconds since the start button. The robot "
                  "has been stopped, as the competition USB would stop it.", flush=True)
            raise _MatchOver(0)

    def sleep(self, secs: float) -> None:
        """Wait in simulated time. Everything else (motors, servos) carries on."""
        end = _webots.getTime() + max(0.0, float(secs))
        self._step()
        while _webots.getTime() < end - 1e-9:
            self._step()

    def time(self) -> float:
        """Simulated seconds since the simulation started."""
        return _webots.getTime()

    def wait_start(self) -> None:
        """Wait for the start button: press S in the 3D view, or wait 2 seconds."""
        self._status.state = "waiting"
        print("Waiting for the start button: press S in the 3D view (click it first), or it "
              "starts by itself in 2 seconds", flush=True)
        self.buzzer.buzz(Note.A6, 0.1)
        self._brain.start_button._forget_presses()
        deadline = _webots.getTime() + 2.0
        while _webots.getTime() < deadline and not self._brain.start_button.was_pressed():
            self._step()
        self._brain.start_button._forget_presses()
        self._status.state = "running"
        self._started = True
        self._start_time = _webots.getTime()
        print("Started", flush=True)

    @property
    def zone(self) -> int:
        return self._zone

    @property
    def is_simulated(self) -> bool:
        return True

    @property
    def usbkey(self):
        raise _not_in_sim("robot.usbkey")

    # Student Robotics boards. The PSC kit has none, so, as on a real PSC robot, these are
    # empty and asking for "the" board says so.
    @property
    def motor_boards(self) -> dict:
        return {}

    @property
    def servo_boards(self) -> dict:
        return {}

    @property
    def arduinos(self) -> dict:
        return {}

    @property
    def bus_servo_adapters(self) -> dict:
        return {}

    @property
    def raw_serial_devices(self) -> dict:
        return {}

    @property
    def motor_board(self):
        raise RuntimeError("No motor boards are connected. On the PSC kit, motors use the "
                           "brain board: robot.brain.dc_motor(20, 21)")

    @property
    def servo_board(self):
        raise RuntimeError("No servo boards are connected. On the PSC kit, servos use a "
                           "servo driver: robot.brain.servo_driver(sda=17, scl=27).servos[0]")

    @property
    def power_board(self):
        raise RuntimeError("No power board is connected. The PSC kit uses the brain board: "
                           "robot.brain")

    @property
    def bus_servo_adapter(self):
        raise _not_in_sim("robot.bus_servo_adapter")

    @property
    def mode(self) -> RobotMode:
        return DEV

    @property
    def arena(self) -> str:
        return "A"

    @property
    def camera(self):
        """The robot's camera: robot.camera.see() for the markers it can see."""
        return self._camera

    @property
    def cameras(self) -> dict:
        """Every camera, by name: the simulated robot has one, "sim"."""
        return {"sim": self._camera}

    @property
    def arduino(self):
        raise _not_in_sim("robot.arduino")

    @property
    def gamepad(self):
        raise _not_in_sim("robot.gamepad")

    @property
    def gamepads(self):
        raise _not_in_sim("robot.gamepads")

    def wait_for_gamepad(self, *args, **kwargs):
        raise _not_in_sim("robot.wait_for_gamepad")

    @property
    def kch(self):
        raise RuntimeError("This robot has no Student Robotics KCH hat: use robot.brain.led")

    def _finish(self) -> None:
        for motor in self._brain._motors.values():
            motor.power = COAST
        self._brain.led.colour = Colour.OFF
        self._status.state = "finished"
        self._step()
