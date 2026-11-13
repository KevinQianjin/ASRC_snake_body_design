"""Draw the end-disk faces of the lane modules (lane_disks.png) and list the holes in each disk."""
import numpy as np, trimesh, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
files = [('U_lane_pass.stl', 'U1-U3 (both disks)', -46.5), ('U4_lane_anchorA.stl', 'U4 distal disk: A anchored', 47.),
         ('M5_lane_anchorB.stl', 'M5 distal disk: B anchored', 47.), ('M6_lane_anchorC.stl', 'M6 distal disk: C anchored', 47.)]
fig, axs = plt.subplots(1, 4, figsize=(18, 5))
for ax, (f, t, z) in zip(axs, files):
    m = trimesh.load(f); s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    polys = s.to_planar()[0].polygons_full
    print(f, z, 'regions', len(polys), 'holes', sum(len(p.interiors) for p in polys))
    for P in s.discrete:
        ax.plot(P[:, 0], P[:, 1], 'k', lw=.6)
    outer = max(s.discrete, key=len); ax.fill(outer[:, 0], outer[:, 1], color=(.85, .88, .95), zorder=0)
    for r, c in ((21, '#f29a05'), (24, '#05a633'), (27, '#cc0d66')):
        for a in (0, 90, 180, 270): ax.plot(r * np.cos(np.radians(a)), r * np.sin(np.radians(a)), 'o', ms=3, color=c)
    ax.add_patch(plt.Circle((0, 0), 31.5, fill=False, ls='--', color='grey'))
    ax.set_title(f'{t}\nsection z={z:+.1f} mm', fontsize=9); ax.set_aspect('equal'); ax.set_xlim(-34, 34); ax.set_ylim(-34, 34)
    ax.text(0, 33, 'up (+Y)', ha='center', fontsize=7); ax.text(33, 0, 'left', fontsize=7, rotation=90, va='center'); ax.text(-33.5, 0, 'right', fontsize=7, rotation=90, va='center')
fig.suptitle('Solid lane end disks: dots = lane centres A 21 / B 24 / C 27 mm; dashed = 63 mm envelope; M centre bore 1.85 mm (rod 1.8)', fontsize=10)
plt.tight_layout(); plt.savefig('lane_disks.png', dpi=130)
