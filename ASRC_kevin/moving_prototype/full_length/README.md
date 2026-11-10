# OpenSCAD prototype files

These are early fit and motion prototypes. They are not validated production parts or rated for the simulated 500 g inspection head.

## Full-length layout

- [00_full_assembly.scad](00_full_assembly.scad) — preview of the complete six-module U4+M2 front; needs module_common.scad in the same folder.
- [00_full_assembly_standalone.scad](00_full_assembly_standalone.scad) — same preview with shared geometry included; download this one file if you want to open the assembly by itself. Adjust joint_1 through joint_5 to change the preview pose.
- [01_U1_base.scad](01_U1_base.scad) — first U module with base flange.
- [02_U2.scad](02_U2.scad) — second U module.
- [03_U3.scad](03_U3.scad) — third U module.
- [04_U4.scad](04_U4.scad) — fourth U module.
- [05_M1.scad](05_M1.scad) — first M module.
- [06_M2_tip.scad](06_M2_tip.scad) — second M module and tip interface, without the new backbone supports.
- [07_base_interface.scad](07_base_interface.scad) — base interface envelope.
- [08_head_placeholder.scad](08_head_placeholder.scad) — placeholder envelope, not the real camera/head CAD.
- [M2_backbone_prototype.scad](M2_backbone_prototype.scad) — separate M-module concept with three internal printed guides and a preview of the 1.8 mm metal rod.
- [module_common.scad](module_common.scad) — shared geometry used by the numbered pieces and full assembly.

Open 00_full_assembly.scad for the complete pose preview. Open an individual numbered file to export that separate piece. The numbered assembly uses generic shells; it does not yet include the new backbone geometry. The backbone concept is currently shown separately in M2_backbone_prototype.scad.

In M2_backbone_prototype.scad, leave export_shell_only = false to view the rod in the assembly. Set it to true to export the printable M2 shell and guides without the metal rod or tendon display lines. The metal rod is a separate component; it is not printed.

## First joint prototype

- [../tendon_joint_prototype.scad](../tendon_joint_prototype.scad) — separate single-joint manual pull prototype, with one-axis bending.

All dimensions and material behavior are provisional. Review the geometry in OpenSCAD and check fits before printing; these models do not establish strength, fatigue life, tank clearance or performance.