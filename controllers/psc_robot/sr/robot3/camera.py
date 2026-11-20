"""
The simulated robot's camera, detecting markers with april_vision exactly as the real
robot does: robot.camera.see() gives the same Marker objects (sr/robot3/marker.py).
"""
from __future__ import annotations

import math
from os import PathLike
from typing import TYPE_CHECKING, List, Optional

import cv2
import numpy as np
from april_vision import FrameSource, Processor

import sim_wiring

from .marker import Marker

if TYPE_CHECKING:
    from . import Robot


class _WebotsFrameSource(FrameSource):
    """Frames from the Webots camera, which gives BGRA images."""
    COLOURSPACE = cv2.COLOR_BGRA2GRAY

    def __init__(self, device, robot: "Robot", timestep: int) -> None:
        self._device = device
        self._robot = robot
        self._timestep = timestep
        self._enabled = False

    def read(self, fresh: bool = True) -> np.ndarray:
        if not self._enabled:
            # The camera only renders once enabled, so take one step to get a first image
            self._device.enable(self._timestep)
            self._enabled = True
            self._robot._step()
        width, height = self._device.getWidth(), self._device.getHeight()
        image = np.frombuffer(self._device.getImage(), np.uint8)
        return image.reshape((height, width, 4)).copy()


def _calibration(device) -> tuple[float, float, float, float]:
    """(fx, fy, cx, cy) for a perfect pinhole camera with the Webots camera's field of view."""
    width, height = device.getWidth(), device.getHeight()
    focal = (width / 2) / math.tan(device.getFov() / 2)  # Webots' field of view is horizontal
    return focal, focal, width / 2, height / 2


def _marker_sizes() -> dict[int, float]:
    sizes: dict[int, float] = {}
    for ids, size in sim_wiring.MARKER_SIZES.items():
        for marker_id in ids:
            sizes[marker_id] = size
    return sizes


class SimCamera:
    """
    robot.camera: the simulated camera. see() finds the markers it can see, as on the
    real robot; capture() gives the image.
    """

    def __init__(self, device, robot: "Robot", timestep: int) -> None:
        self._processor = Processor(
            _WebotsFrameSource(device, robot, timestep),
            calibration=_calibration(device),
            name="sim",
            mask_unknown_size_tags=True,
        )
        self._processor.set_marker_sizes(_marker_sizes())

    def see(self, *, frame: Optional[np.ndarray] = None,
            save: Optional[PathLike] = None) -> List[Marker]:
        """
        Capture an image and find the markers in it.

        :param frame: An image to look in, instead of capturing a new one.
        :param save: If given, save the annotated image to this path.
        :returns: The markers the camera can see.
        """
        if frame is None:
            frame = self._processor.capture()
        markers = self._processor.see(frame=frame)
        if save:
            self._processor.save(save, frame=frame, detections=markers)
        return [Marker.from_april_vision_marker(marker) for marker in markers]

    def capture(self, *, save: Optional[PathLike] = None) -> np.ndarray:
        """The camera's image, as on the real robot (BGRA here, from Webots)."""
        frame = self._processor.capture()
        if save:
            self._processor.save(save, frame=frame, annotated=False)
        return frame
