#!/usr/bin/env python3
"""Generate the Hungry Hippos Webots world and its textures.

All arena dimensions live here and come from the rule book (overleaf/main.tex).
Run it again after changing anything:  .venv/bin/python tools/build_arena.py

Rule book coordinates: (rx, ry) in metres from corner 0 (top left of the plan),
rx to the right, ry down. World coordinates: arena centre at the origin, +X to
the right of the plan, +Y to the top of the plan, +Z up.
"""
import math
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
WORLDS = ROOT / "worlds"
TEXTURES = WORLDS / "textures"

# --- Rule book values (metres) ------------------------------------------------
ARENA = 5.0
WALL_HEIGHT = 0.300
HOME_LEG = 1.400
ZONE = 0.250
ZONE_TAPE = 0.015
ZONE_GAP = 0.030
ZONE_WALL_GAP = 0.020
TOKEN = 0.130
TOKEN_MARKER = 0.080
TOKEN_GRID = (1.5, 2.5, 3.5)
WALL_MARKER = 0.150
WALL_MARKER_LIFT = 0.069
WALL_MARKER_SPACING = ARENA / 6  # the rule book's 833mm

# --- Not specified in the rule book (assumptions, change freely) --------------
WALL_THICKNESS = 0.020
TOKEN_MASS = 0.15
TOKEN_ID_SEED = 27  # token IDs are "in no particular order"

YELLOW, PINK = "#f4d43c", "#ea45cf"
FLOOR_GREY, TAPE_RED = "#c8c8c8", "#dc2a2a"
TOKEN_BLUE = "#9db8d9"


def world_xy(rx, ry):
    return rx - ARENA / 2, ARENA / 2 - ry


def tag_image(tag_id, px_per_cell):
    """Black-square tag36h11 marker (8 cells across) with a 1 cell white border."""
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    tag = cv2.aruco.generateImageMarker(dictionary, tag_id, 8 * px_per_cell, borderBits=1)
    return cv2.copyMakeBorder(tag, px_per_cell, px_per_cell, px_per_cell, px_per_cell,
                              cv2.BORDER_CONSTANT, value=255)


def square_texture(image, size=512):
    """Webots wants power of two textures. Nearest neighbour keeps the tag edges sharp."""
    return image.resize((size, size), Image.NEAREST)


def build_floor():
    size = 4096
    scale = size / ARENA
    image = Image.new("RGB", (size, size), FLOOR_GREY)
    draw = ImageDraw.Draw(image)

    def corner_points(points, corner):
        # Corner 1 is corner 0 rotated by 180 degrees about the arena centre.
        if corner == 1:
            points = [(ARENA - x, ARENA - y) for x, y in points]
        return [(x * scale, y * scale) for x, y in points]

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    for corner, home in ((0, YELLOW), (1, PINK)):
        draw.polygon(corner_points([(0, 0), (HOME_LEG, 0), (0, HOME_LEG)], corner), fill=home)
        for i in range(4):
            y0 = ZONE_WALL_GAP + i * (ZONE + ZONE_GAP)
            x0, x1, y1 = ZONE_WALL_GAP, ZONE_WALL_GAP + ZONE, y0 + ZONE
            draw.polygon(corner_points(rect(x0, y0, x1, y1), corner), fill=TAPE_RED)
            draw.polygon(corner_points(rect(x0 + ZONE_TAPE, y0 + ZONE_TAPE,
                                            x1 - ZONE_TAPE, y1 - ZONE_TAPE), corner), fill=home)
    image.save(TEXTURES / "floor.png", optimize=True)


def quad_face(corners, url):
    """A textured flat quad. corners are bottom-left, bottom-right, top-right, top-left."""
    coords = ", ".join(f"{x:.5f} {y:.5f} {z:.5f}" for x, y, z in corners)
    return f"""Shape {{
      appearance PBRAppearance {{
        baseColorMap ImageTexture {{ url [ "{url}" ] filtering 1 }}
        roughness 1
        metalness 0
      }}
      geometry IndexedFaceSet {{
        coord Coordinate {{ point [ {coords} ] }}
        texCoord TextureCoordinate {{ point [ 0 0, 1 0, 1 1, 0 1 ] }}
        coordIndex [ 0, 1, 2, 3, -1 ]
        texCoordIndex [ 0, 1, 2, 3, -1 ]
      }}
    }}"""


def box_shape(size, color):
    return (f"Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 0.9 metalness 0 }} "
            f"geometry Box {{ size {size} }} }}")


def build_walls():
    half = ARENA / 2 + WALL_THICKNESS / 2
    length = ARENA + 2 * WALL_THICKNESS
    colour = "0.91 0.86 0.77"
    nodes = []
    for name, x, y, sx, sy in (("west", -half, 0, WALL_THICKNESS, length),
                               ("east", half, 0, WALL_THICKNESS, length),
                               ("north", 0, half, length, WALL_THICKNESS),
                               ("south", 0, -half, length, WALL_THICKNESS)):
        size = f"{sx} {sy} {WALL_HEIGHT}"
        nodes.append(f"""Solid {{
  translation {x} {y} {WALL_HEIGHT / 2}
  name "wall {name}"
  children [ {box_shape(size, colour)} ]
  boundingObject Box {{ size {size} }}
}}""")
    return nodes


def wall_marker_positions():
    """Yield (id, centre rx, ry, inward normal) anticlockwise from corner 0."""
    s = WALL_MARKER_SPACING
    for i in range(5):
        yield i, 0.0, (i + 1) * s, (1, 0)                  # left wall, going down
        yield 5 + i, (i + 1) * s, ARENA, (0, -1)           # bottom wall, going right
        yield 10 + i, ARENA, ARENA - (i + 1) * s, (-1, 0)  # right wall, going up
        yield 15 + i, ARENA - (i + 1) * s, 0.0, (0, 1)     # top wall, going left


def build_wall_markers():
    nodes = []
    panel = WALL_MARKER * 10 / 8  # the black square plus its white border
    bottom = WALL_MARKER_LIFT - WALL_MARKER / 8
    standoff = 0.001
    for tag_id, rx, ry, (nx, ny) in sorted(wall_marker_positions()):
        square_texture(Image.fromarray(tag_image(tag_id, 32))).save(
            TEXTURES / f"marker_{tag_id}.png", optimize=True)
        cx, cy = world_xy(rx, ry)
        # World normal: plan +ry is world -Y.
        wx, wy = nx, -ny
        cx, cy = cx + wx * standoff, cy + wy * standoff
        # A viewer facing the wall looks along -normal, so their right is (-normal) x up.
        right = (-wy, wx)
        h = panel / 2
        corners = [(cx - right[0] * h, cy - right[1] * h, bottom),
                   (cx + right[0] * h, cy + right[1] * h, bottom),
                   (cx + right[0] * h, cy + right[1] * h, bottom + panel),
                   (cx - right[0] * h, cy - right[1] * h, bottom + panel)]
        nodes.append(f"""Solid {{
  name "wall marker {tag_id}"
  children [
    {quad_face(corners, f"textures/marker_{tag_id}.png")}
  ]
}}""")
    return nodes


def build_tokens():
    rng = random.Random(TOKEN_ID_SEED)
    ids = rng.sample(range(20, 101), 9)
    positions = [(x, y) for y in TOKEN_GRID for x in TOKEN_GRID]
    h = TOKEN / 2
    # Six faces, counter-clockwise from outside, each ordered so the texture is upright.
    faces = [
        [(h, -h, -h), (h, h, -h), (h, h, h), (h, -h, h)],
        [(-h, h, -h), (-h, -h, -h), (-h, -h, h), (-h, h, h)],
        [(h, h, -h), (-h, h, -h), (-h, h, h), (h, h, h)],
        [(-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h)],
        [(-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)],
        [(-h, h, -h), (h, h, -h), (h, -h, -h), (-h, -h, -h)],
    ]
    points = ", ".join(f"{x} {y} {z}" for face in faces for x, y, z in face)
    tex_points = ", ".join("0 0, 1 0, 1 1, 0 1" for _ in faces)
    index = ", ".join(f"{4 * i}, {4 * i + 1}, {4 * i + 2}, {4 * i + 3}, -1" for i in range(6))
    nodes = []
    cells = round(TOKEN / (TOKEN_MARKER / 8))  # 13 cells across a 130mm face
    px = 40
    for tag_id, (rx, ry) in zip(ids, positions):
        face = Image.new("RGB", (cells * px, cells * px), TOKEN_BLUE)
        tag = Image.fromarray(tag_image(tag_id, px)).convert("RGB")
        offset = (face.width - tag.width) // 2
        face.paste(tag, (offset, offset))
        square_texture(face).save(TEXTURES / f"token_{tag_id}.png", optimize=True)
        x, y = world_xy(rx, ry)
        nodes.append(f"""Solid {{
  translation {x} {y} {h}
  name "token {tag_id}"
  contactMaterial "token"
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColorMap ImageTexture {{ url [ "textures/token_{tag_id}.png" ] filtering 1 }}
        roughness 0.9
        metalness 0
      }}
      geometry IndexedFaceSet {{
        coord Coordinate {{ point [ {points} ] }}
        texCoord TextureCoordinate {{ point [ {tex_points} ] }}
        coordIndex [ {index} ]
        texCoordIndex [ {index} ]
      }}
    }}
  ]
  boundingObject Box {{ size {TOKEN} {TOKEN} {TOKEN} }}
  physics Physics {{ density -1 mass {TOKEN_MASS} }}
}}""")
    return nodes


def viewpoint_rotation(yaw, pitch):
    """Axis-angle for Rz(yaw) * Ry(pitch)."""
    cz, sz, cy, sy = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    r = np.array([[cz * cy, -sz, cz * sy], [sz * cy, cz, sz * sy], [-sy, 0, cy]])
    angle = math.acos((np.trace(r) - 1) / 2)
    axis = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]])
    axis = axis / (2 * math.sin(angle))
    return f"{axis[0]:.5f} {axis[1]:.5f} {axis[2]:.5f} {angle:.5f}"


def build_world():
    floor_half = ARENA / 2
    floor = quad_face([(-floor_half, -floor_half, 0), (floor_half, -floor_half, 0),
                       (floor_half, floor_half, 0), (-floor_half, floor_half, 0)],
                      "textures/floor.png")
    # Robot origin (axle centre) in the corner 0 home area, facing +X. A robot may start
    # anywhere in its home area; this is just a default clear of the scoring zones. The
    # footprint runs 0.15m behind the axle and 0.30m ahead of it.
    start_rx = 0.52
    start_ry = 0.27
    sx, sy = world_xy(start_rx, start_ry)
    nodes = [
        f"""#VRML_SIM R2025a utf8
# Hungry Hippos arena. Generated by tools/build_arena.py, do not edit by hand.

EXTERNPROTO "../protos/SimpleRobot.proto"

WorldInfo {{
  info [ "Hungry Hippos arena, PSC Robotics rule book." ]
  title "Hungry Hippos"
  basicTimeStep 16
  contactProperties [
    ContactProperties {{ material2 "caster" coulombFriction [ 0.01 ] }}
    ContactProperties {{ material2 "token" coulombFriction [ 0.5 ] }}
  ]
}}""",
        f"""Viewpoint {{
  orientation {viewpoint_rotation(math.pi / 2, math.radians(50))}
  position 0 -5.2 6.2
}}""",
        'Background { skyColor [ 0.86 0.88 0.9 ] }',
        'DirectionalLight { direction 0.3 0.4 -1 intensity 2.5 ambientIntensity 1 castShadows TRUE }',
        f"""Solid {{
  name "floor"
  children [
    {floor}
  ]
  boundingObject Plane {{ size {ARENA} {ARENA} }}
}}""",
        *build_walls(),
        *build_wall_markers(),
        *build_tokens(),
        f"""SimpleRobot {{
  translation {sx:.4f} {sy:.4f} 0
  name "robot corner 0"
  controllerArgs [ "0" ]
}}""",
    ]
    (WORLDS / "hungry_hippos.wbt").write_text("\n".join(nodes) + "\n")


if __name__ == "__main__":
    TEXTURES.mkdir(parents=True, exist_ok=True)
    build_floor()
    build_world()
    print(f"Wrote {WORLDS / 'hungry_hippos.wbt'}")
