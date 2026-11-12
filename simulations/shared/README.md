# Shared models and reference runs

[Simulation index](../README.md) · [Repository map](../../docs/repository_map.md)

- [H8U12 model group](h8u12_front5to8_payload500g/README.md) contains the rod kernel still read by the active U4+M2 model. Its frozen inputs and earlier studies remain together for provenance.
- [Legacy rod models](legacy_models/) contain the original sag, rear-backbone and rope models, their configurations, tests and reference outputs. The archived reach-extension study imports the rear-backbone solver here.
- [Legacy result viewer](legacy_models/robot_3d_viewer.html) opens saved result JSON files from the legacy model group.

Shared editable material data is in [data/materials](../../data/materials/README.md). Study-specific frozen catalogues remain in each study's `inputs/` directory. Keeping those snapshots preserves the assumptions used for earlier results.
