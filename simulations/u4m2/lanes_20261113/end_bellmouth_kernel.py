"""Constrained, frictionless rope contact with the actual convex end fillet.

The interface hole centre remains a prescribed routing point. Between that
point and the adjacent guide, the rope is either straight or tangent to the
rope-radius offset of the circular fillet. Rigid end orientation is inherited
from the interface frame. This is not a sliding-through-joints contact model.
All kernel inputs and returned lengths are in metres and radians.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def span_geometry(local_guide, sign, profile):
    """Return length, local endpoint gradient, entry/exit angles and contact.

    profile = [inboard depth, wall radius, design wrap, hole radius, rope radius].
    The offset circle centre is (s0, hole_radius + wall_radius), with
    s0 = depth - wall_radius*sin(design_wrap). The incoming tangent is solved
    from the fixed interface centre, and the outgoing tangent meets the actual
    guide. Contact beyond the trimmed design arc is calculated but must fail
    the independent wrap acceptance check.
    """
    depth, wall, design_wrap, hole, rope = profile
    x = sign * local_guide[0]
    rho = np.sqrt(local_guide[1] ** 2 + local_guide[2] ** 2)
    direct = np.sqrt(x * x + rho * rho)
    if x <= 0. or direct <= 1e-12:
        raise ValueError('End guide must lie in front of its rigid end interface')
    s0 = depth - wall * np.sin(design_wrap)
    radius = wall + rope
    cy = wall + hole
    d0 = np.sqrt(s0 * s0 + cy * cy)
    theta_in = np.arccos(radius / d0) - np.arctan2(s0, cy)
    alpha = np.arctan2(rho, x)
    gradient = local_guide / direct
    if alpha <= theta_in or rho < 1e-14:
        return direct, gradient, alpha, alpha, False
    dx, dy = x - s0, rho - cy
    d1 = np.sqrt(dx * dx + dy * dy)
    if dx <= 0. or d1 <= radius:
        raise ValueError('Guide lies outside the supported bellmouth tangent domain')
    theta_out = np.arctan2(dy, dx) + np.arcsin(radius / d1)
    incoming = np.sqrt(d0 * d0 - radius * radius)
    outgoing = np.sqrt(d1 * d1 - radius * radius)
    length = incoming + radius * (theta_out - theta_in) + outgoing
    gradient = np.array([sign * np.cos(theta_out),
                         np.sin(theta_out) * local_guide[1] / rho,
                         np.sin(theta_out) * local_guide[2] / rho])
    return length, gradient, theta_in, theta_out, True


@njit(cache=True)
def span_end_loads(end_point, end_frame, guide_point, offset, sign, profile):
    """Length and derivatives with respect to the guide, end position/frame."""
    delta = guide_point - end_point
    local = end_frame.T @ delta - offset
    length, local_gradient, _, _, _ = span_geometry(local, sign, profile)
    guide_gradient = end_frame @ local_gradient
    # This frame derivative is restricted to orthonormal frame variations.
    # It includes the moment of the rigid fillet, not only the lane offset.
    end_frame_gradient = np.outer(delta, local_gradient)
    return length, guide_gradient, end_frame_gradient
