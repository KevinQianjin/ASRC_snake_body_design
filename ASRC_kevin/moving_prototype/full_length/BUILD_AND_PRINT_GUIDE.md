# U4+M2 backbone prototype: print and buy guide

This is the current fit-and-motion prototype, not a load-rated robot. The 1.8 mm rods and tendon loads are simulation assumptions; the rod end attachments still need a physical design and test. Do not attach the 500 g camera or apply high tendon forces until those attachments and the printed parts have been checked.

## Open and export parts

Open [U4M2_backbone_assembly.scad](U4M2_backbone_assembly.scad) in OpenSCAD. Set `part` near the top (or in Customizer) to `assembly` to preview, or to one of `U1`, `U2`, `U3`, `U4`, `M1`, `M2`, `base`, or `head` to export that individual part. Press F6, then **File → Export → Export as STL**. Export the parts one at a time; do not print the `assembly` choice.

The assembly preview shows the 1.8 mm rods, but the rods are not included in the M1 or M2 STL exports. The M1 and M2 exports both include three printed support webs at 24 mm spacing. The webs are joined to the shell and keep the four tendon paths open.

## Print

For the complete front fit-check, print one each:

- U1, U2, U3, U4
- M1, M2 (both with backbone guide webs)
- Base interface, if you need to attach the front to a test stand
- Head placeholder only if you want a size mock-up; it is not the real camera/head mount

For the first experiment, print only U4 and M1 plus the base interface if needed. Check the joint, the cord paths, and that a 1.8 mm rod slides through the guides before printing the rest. Print each cylindrical module standing upright with its axis vertical to avoid supports inside the body. Check the slicer preview; add local support only under a joint feature if needed, and keep support material out of the central bore and tendon holes.

PETG is a reasonable low-force fit-check material. PLA is also suitable for an unloaded fit check. Neither material choice makes this design safe for the simulated camera load.

## Buy

- Five M3 × 30 mm bolts/pins and locking nuts for the five body joints. Add four more sets if you want to bolt the base interface to the U1 flange. Washers are optional for the low-force fit check.
- Four lengths of about 2 mm braided cord for the tendon paths. For the six-module body, start with about 1 m per cord so there is slack for routing and tying; trim only after assembly.
- Two pieces of straight-annealed NiTi wire, 1.8 mm diameter, one for each M module. About 150 mm per piece leaves trimming and test margin; do not cut to final length until the end attachment is designed.
- No servos are needed for the first test; pull the cords by hand.

Do not buy rod clamps yet. This model does not define a tested way to anchor the rod ends to the module disks. That attachment is required for the simulated backbone effect and must be designed and checked before force or payload testing. The actual camera head and telescopic rear are also not modeled here.

