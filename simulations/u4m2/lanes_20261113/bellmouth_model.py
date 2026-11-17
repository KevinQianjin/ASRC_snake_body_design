"""Install and inspect constrained bellmouth routing on the U4+M2 rod.

The 500 g payload, guide stations, stiffness and U-module routing are retained.
End bodies are rigid in their interface frames. Interface hole centres remain
ideal routing constraints; shared-bore sliding, friction and compliance are
not solved. Fillet forces are geometric reactions, not material strength data.
"""
import json
from pathlib import Path
import numpy as np
from end_bellmouth_kernel import span_geometry

RAYS = ('up', 'right', 'down', 'left')


def angle_difference_deg(new, old):
    """Shortest signed heading difference, invariant to an unwrap branch."""
    return float((new-old+180.)%360.-180.)


def apply_bellmouth(rod, design):
    if (rod.u_count, rod.m_count, rod.k) != (4, 2, 3):
        raise ValueError('Bellmouth model is scoped to U4+M2 with three anchor sets')
    if rod.anchors != [4,5,6] or abs(rod.payload-.5)>1e-12:
        raise ValueError('Bellmouth study requires anchors 4/5/6 and a 500 g head')
    if rod.sub % 8 or rod.guide_cells * 4 != rod.sub:
        raise ValueError('Bellmouth routing requires the four actual guide stations')
    if not np.allclose(rod.lane_radii_mm, (21., 24., 28.)):
        raise ValueError('Lane radii do not match the published bellmouth CAD')
    profiles = np.empty((2, 2, 5))
    for j, module in enumerate(('M5', 'M6')):
        for ei, end in enumerate(('proximal', 'distal')):
            ex = design['exits'][module + '/' + end]
            sign = 1 if ei == 0 else -1
            interface_z = -48. if ei == 0 else 48.
            depth = sign * (ex['face_z_mm'] - interface_z)
            expected_lanes = ['B', 'C'] if j == 0 else ['C']
            if ex['inboard_sign'] != sign or ex['lanes'] != expected_lanes:
                raise ValueError('End direction or routed lane set differs from CAD')
            profiles[j, ei] = [depth / 1000., ex['wall_radius_mm'] / 1000.,
                np.radians(ex['design_wrap_deg']), design['hole_diameter_mm'] / 2000.,
                design['rope_diameter_mm'] / 2000.]
            d, w, th, h, r = profiles[j, ei]
            if not (d > w * np.sin(th) > 0. and w > 0. and h > r > 0.):
                raise ValueError('Unsupported rigid bore or fillet dimensions')
    rod.bellmouth_profiles = profiles
    rod.bellmouth_design = design
    return rod


def sample_span(local_guide, sign, profile, max_step=2e-5):
    """Return an endpoint-complete local rope curve relative to the hole centre."""
    length, grad, ti, to, contact = span_geometry(local_guide, sign, profile)
    if not contact:
        n = max(1, int(np.ceil(length / max_step)))
        return np.linspace(np.zeros(3), local_guide, n + 1)
    depth, wall, td, hole, rope = profile
    s0 = depth - wall * np.sin(td)
    rc, cy = wall + rope, wall + hole
    rho = np.linalg.norm(local_guide[1:])
    axis = np.array([sign, 0., 0.])
    normal = np.array([0., local_guide[1] / rho, local_guide[2] / rho])
    centre = s0 * axis + cy * normal
    def arc(phi):
        return centre + rc * (np.sin(phi)[:, None] * axis - np.cos(phi)[:, None] * normal)
    ends = arc(np.array([ti, to]))
    first = np.linspace(np.zeros(3), ends[0], max(2, int(np.ceil(np.linalg.norm(ends[0]) / max_step)) + 1))
    mid = arc(np.linspace(ti, to, max(2, int(np.ceil(rc * (to - ti) / max_step)) + 1)))
    last = np.linspace(ends[1], local_guide, max(2, int(np.ceil(np.linalg.norm(local_guide - ends[1]) / max_step)) + 1))
    return np.vstack((first[:-1], mid[:-1], last))


def inspect_routing(rod, z, tensions, sample=False):
    """Return per-exit records and simultaneous per-guide forces/moments."""
    _, _, detail = rod.evaluate(z, tensions, detail=True)
    p, frames = detail['points'], detail['frames']
    exits, guides = [], []
    for j in (4, 5):
        nodes = j * rod.sub + np.array([0, rod.sub//4, 3*rod.sub//8,
                                       5*rod.sub//8, 3*rod.sub//4, rod.sub])
        for k in ((1, 2) if j == 4 else (2,)):
            for ray in range(4):
                off = rod.offsets3[k, ray]
                points = p[nodes] + np.einsum('nij,j->ni', frames[nodes], off)
                t = float(tensions[k, ray])
                directions = np.diff(points, axis=0)
                directions /= np.linalg.norm(directions, axis=1)[:, None]
                end_directions = {}
                for ei, end in enumerate(('proximal', 'distal')):
                    ii, ig, sign = (0, 1, 1.) if ei == 0 else (-1, -2, -1.)
                    f = frames[nodes[ii]]
                    delta = points[ig] - p[nodes[ii]]
                    local = f.T @ delta - off
                    profile = rod.bellmouth_profiles[j-4, ei]
                    ll, gradient, theta_in, theta_out, contact = span_geometry(local, sign, profile)
                    tangent_out = f @ gradient
                    rho = np.linalg.norm(local[1:])
                    n = np.r_[0., local[1:] / max(rho, 1e-30)]
                    tangent_in_local = np.array([sign*np.cos(theta_in), 0., 0.]) + np.sin(theta_in)*n
                    tangent_in = f @ tangent_in_local
                    force = t * (tangent_out - tangent_in) if contact else np.zeros(3)
                    moment = np.cross(delta, t*tangent_out) * 1000.
                    margin = float(np.degrees(profile[2]-theta_out))
                    record = dict(module=f'M{j+1}', end=end, set='ABC'[k], ray=RAYS[ray],
                        tension_n=t, contact=bool(contact), entry_angle_deg=float(np.degrees(theta_in)),
                        exit_angle_deg=float(np.degrees(theta_out)), wrap_deg=float(np.degrees(theta_out-theta_in)),
                        design_margin_deg=margin, margin_pass=bool(margin >= 1.-1e-9),
                        span_length_mm=float(ll*1000.), length_increase_mm=float((ll-np.linalg.norm(local))*1000.),
                        fillet_resultant_n=float(np.linalg.norm(force)), fillet_force_base_n=force.tolist(),
                        end_resultant_base_n=(t*tangent_out).tolist(), end_moment_base_nmm=moment.tolist(),
                        end_moment_nmm=float(np.linalg.norm(moment)))
                    if sample:
                        curve = sample_span(local, sign, profile)
                        record['curve_local_m'] = curve
                        record['curve_cad_mm'] = np.c_[-(curve[:,2]+off[2])*1000.,
                            (curve[:,1]+off[1])*1000., curve[:,0]*1000.+(-48. if ei==0 else 48.)]
                        record['endpoint_error_mm'] = float(np.linalg.norm(curve[-1]-local)*1000.)
                    exits.append(record)
                    end_directions[ei] = tangent_out
                # Physical force at each guide is the sum of the adjacent pulls.
                for gi in range(1, 5):
                    left = -end_directions[0] if gi == 1 else -directions[gi-1]
                    right = -end_directions[1] if gi == 4 else directions[gi]
                    force = t*(left+right)
                    lever = frames[nodes[gi]] @ off
                    guides.append(dict(module=f'M{j+1}', station_z_mm=(-24.,-12.,12.,24.)[gi-1],
                        set='ABC'[k], ray=RAYS[ray], tension_n=t, force_base_n=force.tolist(),
                        moment_base_nmm=(np.cross(lever, force)*1000.).tolist(), hole_force_n=float(np.linalg.norm(force))))
    return exits, guides


def mass_with_bellmouth(baseline, geometry_check):
    """Use the measured CAD volume removal with the existing PA12 density."""
    mass = json.loads(json.dumps(baseline))
    density = mass['densities_kg_per_mm3']['PA12']
    changes = []
    for j, name in ((4, 'M5_lane_anchorB.stl'), (5, 'M6_lane_anchorC.stl')):
        part = geometry_check['parts'][name]
        delta = density * (part['volume_mm3'] - part['source_volume_mm3'])
        mass['components'][j]['body_kg'] += delta
        mass['module_mass_kg'][j] += delta
        changes.append(delta*1000.)
    mass['scope'] = mass['scope'].replace(
        'V3 replaces only guide/cap/wire volumes; unchanged V2 body volumes and stiffness.',
        'V3 guide/cap/wire volumes are retained; M5/M6 body masses include the published bellmouth cuts. Homogenised stiffness is unchanged.')
    mass['scope'] += ' Bellmouth body volume removal is included; all other components are unchanged.'
    mass['bellmouth_mass_change_g'] = changes
    return mass
