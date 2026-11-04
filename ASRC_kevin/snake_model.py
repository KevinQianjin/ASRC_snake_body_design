"""
craft_chain_model.py - planar elastic-chain model of a continuum body built from
CRAFT modules plus an optional rigid carrier.  All module data comes from
craft_data.py (the CRAFT preprint).  Quick design tool, NOT a replacement for
testing or FEA.

Model
-----
* Chain of rigid links, each with an elastic hinge at its base.
  Hinge stiffness = EI / module_length, separately for positive and negative
  rotation, so the direction-dependent EI of the directional module
  (X vs -X) is represented.  The first link is clamped.
* If the real robot rests on a floor/rib, clamp the model at the LAST support
  point and model only the free part.
* Large rotations, load stepping, equilibrium via scipy.optimize.root.
* Gravity on every link (mass at link midpoint) plus a point payload.
* A tendon = constant moment T*r on each joint in its span (straight tendon,
  no friction, no compression stiffening).

Stack syntax (string or list), base -> tip, AFTER the carrier:
    "3*high, 5*unidirectional:y, 3*directional:y, 1*low"
  name  : low | medium | high | directional | unidirectional | extensible
          (aliases: uni, dir, ext ...)
  :axis : in-plane bending axis, one of x, -x, y.  x = the module's X axis is
          in the bending plane and +X points toward positive joint rotation
          (up).  Use y to put the stiff axis of the uni-directional module
          along gravity.  Default x.

Scaling to another diameter (diameter_mm) assumes uniform geometric scaling
[ASSUMPTION, not in the paper]: EI, GJ ~ s^4, EA ~ s^2, mass ~ s^3, length ~ s.

Units: SI (m, kg, N, rad).
"""
import re
import numpy as np
from scipy.optimize import root, brentq

import craft_data as D

G = 9.81
_LEGACY = {"uni_stiff": "unidirectional:y", "uni_soft": "unidirectional:x"}


# ---------------------------------------------------------------- stack parse
def parse_stack(spec):
    """-> list of (module_key, axis)."""
    toks = spec if isinstance(spec, (list, tuple)) else spec.split(",")
    out = []
    for t in toks:
        t = t.strip()
        if not t:
            continue
        n = 1
        m = re.match(r"^(\d+)\s*\*\s*(.+)$", t)
        if m:
            n, t = int(m.group(1)), m.group(2).strip()
        t = _LEGACY.get(t.lower(), t)
        name, _, axis = t.partition(":")
        axis = (axis or "x").strip().lower()
        if axis not in ("x", "-x", "y", "-y"):
            raise ValueError(f"axis must be x, -x or y (got '{axis}')")
        out += [(D.canonical(name), axis)] * n
    return out


def module_props(key, axis="x", diameter_mm=D.MODULE_DIAMETER_MM, extras_g=0.0):
    """Stiffness/mass/length of one module (scaled to diameter_mm)."""
    m = D.MODULES[key]
    s = diameter_mm / D.MODULE_DIAMETER_MM
    pos_neg = {"x": (m["EI_x"], m["EI_negx"]), "-x": (m["EI_negx"], m["EI_x"]),
               "y": (m["EI_y"], m["EI_y"]), "-y": (m["EI_y"], m["EI_y"])}
    ei_pos, ei_neg = (v * s ** 4 for v in pos_neg[axis])
    return dict(length=D.MODULE_LENGTH_M * s, EI_pos=ei_pos, EI_neg=ei_neg,
                EA=m["EA"] * s ** 2, GJ=m["GJ"] * s ** 4,
                mass=D.module_mass_kg(key) * s ** 3 + extras_g / 1000.0)


# ---------------------------------------------------------------- chain build
def build_chain(stack, carrier_len=0, n_carrier=9, carrier_EI=50.0,
                carrier_mass_per_m=0.4, diameter_mm=D.MODULE_DIAMETER_MM,
                extras_g=0.0):
    """Return a dict of per-link arrays (base -> tip).
    carrier_*  : rigid carrier ahead of the CRAFT stack [ASSUMPTION values];
                 set carrier_len=0 for a CRAFT-only chain.
    extras_g   : extra mass per module (rivets, glue, tendon), grams."""
    L, kp, kn, M, EA, lab = [], [], [], [], [], []
    if carrier_len > 0:
        seg = carrier_len / n_carrier
        for _ in range(n_carrier):
            L.append(seg); kp.append(carrier_EI / seg); kn.append(carrier_EI / seg)
            M.append(carrier_mass_per_m * seg); EA.append(np.inf); lab.append("carrier")
    for key, axis in parse_stack(stack):
        p = module_props(key, axis, diameter_mm, extras_g)
        L.append(p["length"]); kp.append(p["EI_pos"] / p["length"])
        kn.append(p["EI_neg"] / p["length"]); M.append(p["mass"])
        EA.append(p["EA"]); lab.append(f"{key}:{axis}")
    return dict(l=np.array(L), kp=np.array(kp), kn=np.array(kn), m=np.array(M),
                EA=np.array(EA), labels=lab, n_carrier=n_carrier if carrier_len > 0 else 0)


# ---------------------------------------------------------------------- solve
def _residual(phi, l, kp, kn, m, payload, payload_node, Mj):
    n = len(phi)
    d = np.diff(np.concatenate(([0.0], phi)))
    tau = np.where(d >= 0, kp * d, kn * d)              # hinge moments
    s = tau.copy()
    s[:-1] -= tau[1:]
    beyond = np.cumsum(m[::-1])[::-1] - m + 0.5 * m
    pay = np.zeros(n)
    pay[:payload_node] = payload
    g = G * l * np.cos(phi) * (beyond + pay)
    t = -Mj.copy()
    t[:-1] += Mj[1:]
    return s + g + t


def solve(chain, payload=0.0, payload_node=None, tendons=(), steps=30):
    """Static equilibrium.
    payload_node : node index carrying the payload (0..n; n = tip).
    tendons      : iterable of (first_link, last_link, tension_N, radius_m);
                   positive moment bends the chain up.
    """
    l, kp, kn, m = chain["l"], chain["kp"], chain["kn"], chain["m"]
    n = len(l)
    payload_node = n if payload_node is None else payload_node
    Mj = np.zeros(n)
    for (a, b, T, r) in tendons:
        Mj[a:b + 1] += T * r
    phi = np.zeros(n)
    for lam in np.linspace(1.0 / steps, 1.0, steps):
        sol = root(_residual, phi, args=(l, kp, kn, m * lam, payload * lam,
                                         payload_node, Mj * lam),
                   method="hybr", tol=1e-12)
        phi = sol.x
    pts = np.zeros((n + 1, 2))
    for i in range(n):
        pts[i + 1] = pts[i] + l[i] * np.array([np.cos(phi[i]), np.sin(phi[i])])
    return dict(pts=pts, phi=phi, joint_rot=np.diff(np.concatenate(([0.0], phi))),
                tip_drop=-pts[-1, 1], tip_x=pts[-1, 0], ok=sol.success,
                tendons=list(tendons))


def check_limits(chain, res):
    """Warn when the solution leaves the regime the paper tested."""
    msgs = []
    lim = D.FATIGUE["bend_angle_deg"]
    for i, (lab, th) in enumerate(zip(chain["labels"], res["joint_rot"])):
        if lab != "carrier" and abs(np.degrees(th)) > lim:
            msgs.append(f"link {i} ({lab}): {abs(np.degrees(th)):.0f} deg > "
                        f"{lim:.0f} deg reached in the paper's fatigue test")
    for (a, b, T, r) in res["tendons"]:
        if T > D.FATIGUE["max_tendon_force_N"]:
            msgs.append(f"tendon {T:.1f} N > {D.FATIGUE['max_tendon_force_N']} N "
                        "max force of the paper's fatigue test")
        for i in range(a, b + 1):
            if np.isfinite(chain["EA"][i]) and T / chain["EA"][i] > 0.05:
                msgs.append(f"link {i} ({chain['labels'][i]}): tendon compression "
                            f"{100*T/chain['EA'][i]:.0f} % of EA")
    return msgs


def tension_to_level_tip(chain, payload, payload_node, first, last, r,
                         t_max=60.0, n_scan=240):
    """Smallest tension [N] in ONE tendon over links first..last that brings the
    tip back to y = 0 (None if not found below t_max). A single tendon gives the
    same moment at every joint, so the levelled shape is curved; real robots use
    one tendon group per section."""
    f = lambda T: -solve(chain, payload, payload_node, [(first, last, T, r)],
                         steps=20)["tip_drop"]
    Ts = np.linspace(0.0, t_max, n_scan)
    pT, pf = Ts[0], f(Ts[0])
    for T in Ts[1:]:
        cur = f(T)
        if pf * cur <= 0:
            return brentq(f, pT, T, xtol=1e-4)
        pT, pf = T, cur
    return None


# ------------------------------------------- paper benchmark: wing-probe sag
def wing_benchmark(n_base=4, n_mid=4, n_dist=4, diameter_mm=32.0,
                   gravity_axis="y"):
    """Zero-tension self-weight sag of the paper's wing probe, original vs
    reconfigured. The paper does NOT give modules per segment, so n_* are
    inputs; compare the RATIO to the paper's 33/55 = 0.60 rather than the mm.
    gravity_axis: bending axis of the directional/uni modules along gravity
    (the paper does not give the orientation) [ASSUMPTION]."""
    w = D.WING_ROBOT
    def stack(cfg, mid_ax, dist_ax):
        return (f"{n_base}*{cfg['base']}, {n_mid}*{cfg['middle']}:{mid_ax}, "
                f"{n_dist}*{cfg['distal']}:{dist_ax}")
    out = {}
    for name, cfg in (("original", w["original"]), ("reconfigured", w["reconfigured"])):
        ch = build_chain(stack(cfg, gravity_axis if name == "reconfigured" else "x",
                               gravity_axis if name == "reconfigured" else "x"),
                         carrier_len=0, diameter_mm=diameter_mm)
        out[name] = solve(ch)["tip_drop"]
    out["ratio"] = out["reconfigured"] / out["original"]
    out["paper_ratio"] = w["sag_combined_mm_reconfigured"] / w["sag_combined_mm_original"]
    return out


# ------------------------------------------------------------------------ demo
if __name__ == "__main__":
    D.print_tables()

    # closed-form check (small load, uniform 'high' module, 40 links)
    n, Lc, EI = 40, 0.4, D.MODULES["high"]["EI_x"]
    ch = dict(l=np.full(n, Lc / n), kp=np.full(n, EI / (Lc / n)),
              kn=np.full(n, EI / (Lc / n)), m=np.zeros(n), EA=np.full(n, np.inf),
              labels=["x"] * n, n_carrier=0)
    P = 0.002
    print(f"\ncheck vs closed form: model {solve(ch, P)['tip_drop']*1e3:.2f} mm, "
          f"analytic {P*G*Lc**3/(3*EI)*1e3:.2f} mm")

    print("\nPaper benchmark (wing probe, zero tendon tension). Modules per "
          "segment are not given in the paper, so counts are inputs:")
    for nb, nm, nd in [(3, 3, 3), (4, 4, 4), (4, 6, 6), (6, 5, 5)]:
        b = wing_benchmark(nb, nm, nd)
        print(f"  base/mid/dist = {nb}/{nm}/{nd}: original {b['original']*1e3:6.0f} mm,"
              f" reconfigured {b['reconfigured']*1e3:6.0f} mm, ratio {b['ratio']:.2f}"
              f" (paper {b['paper_ratio']:.2f})")

    print("\nExample: 0 m rigid carrier + CRAFT stack, base clamped at the port")
    stacks = {
        "12 x medium": "12*medium",
        "graded 3 high/5 uni:y/3 dir:y/1 low":
            "3*high, 5*unidirectional:y, 3*directional:y, 1*low",
        "short: 4 high + 2 uni:y + 2 dir:y": "4*high, 2*unidirectional:y, 2*directional:y",
    }
    print(f"{'stack':40s} {'payload':>8s} {'at':>9s} {'tip drop [mm]':>14s}"
          f" {'max joint [deg]':>16s}")
    for name, st in stacks.items():
        ch = build_chain(st)
        for payload, where in [(0.0, "tip"), (0.1, "tip"), (0.5, "junction"), (0.5, "tip")]:
            node = len(ch["l"]) if where == "tip" else ch["n_carrier"]
            r = solve(ch, payload, node)
            print(f"{name:40s} {payload:7.2f}k {where:>9s} {r['tip_drop']*1e3:14.1f}"
                  f" {np.degrees(np.abs(r['joint_rot']).max()):16.1f}")