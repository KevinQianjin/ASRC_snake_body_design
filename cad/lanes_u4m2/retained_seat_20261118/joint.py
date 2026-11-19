"""Dimensions of the M5 retained-seat prototype, in mm and degrees."""

import numpy as np

STATIONS = (-12, 12)
ANGLES = (-22.5, 67.5, 157.5, 247.5)
R_PIVOT = 19.229
WEB_WIDTH = 1.50
HALF_THICKNESS = 1.50
PIN = 0.30  # shaft radius
HOLE_CLEARANCE = 0.04  # diametral at the waist
RELIEF_SLOPE = 0.18
CROWN_RADIUS = 1.00
THRUST_GAP = 0.020  # radial separation of concentric thrust spheres
THRUST_OUTER = 0.72
THRUST_FILLET = 0.060
PATCH = 0.92
BLEND = 1.13
HUB_R = 11.25
FORK_RADIAL_LIMIT = 24.60
FORK_Y = -2.73
HUB_FASTENER_X = 9.68
CHEEK = 3.75
GATE_TOP = 4.13
PLATE_HALF = 1.60
LAND = 0.30
WALL_GAP = 0.20
FLARE = 0.25


def web_axes(station):
    slope = np.sign(station) * 1.4706
    s = np.array([slope, 0.0, 1.0]) / np.hypot(slope, 1.0)
    n = np.array([0.0, -1.0, 0.0])
    return np.column_stack((s, np.cross(n, s), n))


def hole_radius(y, diametral=HOLE_CLEARANCE, crown_radius=CROWN_RADIUS):
    u = np.abs(y)
    alpha = np.arctan(RELIEF_SLOPE)
    transition = crown_radius * np.sin(alpha)
    inner = crown_radius - np.sqrt(
        np.maximum(crown_radius**2 - np.minimum(u, transition) ** 2, 0)
    )
    return PIN + diametral / 2 + inner + RELIEF_SLOPE * np.maximum(u - transition, 0.0)


def face_height(r):
    r = np.asarray(r)
    spherical = np.sqrt(np.maximum(0.0, HALF_THICKNESS**2 - np.minimum(r, PATCH) ** 2))
    w = np.clip((r - PATCH) / (BLEND - PATCH), 0.0, 1.0)
    return spherical + (HALF_THICKNESS - spherical) * w


def thrust_rim():
    radius = HALF_THICKNESS + THRUST_GAP
    rc = THRUST_OUTER - THRUST_FILLET
    centre = np.array([rc, np.sqrt((radius + THRUST_FILLET) ** 2 - rc**2)])
    tangent = centre * radius / (radius + THRUST_FILLET)
    return centre, tangent


def thrust_height(r):
    r = np.asarray(r)
    centre, tangent = thrust_rim()
    sphere = np.sqrt((HALF_THICKNESS + THRUST_GAP) ** 2 - r**2)
    blend = centre[1] - np.sqrt(np.maximum(THRUST_FILLET**2 - (r - centre[0]) ** 2, 0))
    return np.where(r <= tangent[0], sphere, blend)


def profile_gap(s):
    return WALL_GAP + FLARE * np.maximum(np.abs(s) - LAND / 2, 0.0)
