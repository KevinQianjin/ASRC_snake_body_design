# Shared material data

[Project home](../../README.md) · [Model input sheet](../../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md)

- [module_stiffness.sqlite3](module_stiffness.sqlite3): module mass and stiffness database used by the active U4+M2 studies.
- [rope_materials.json](rope_materials.json): editable material catalogue used by the shared legacy rod models.
- [rope_materials.sqlite3](rope_materials.sqlite3): material/run database used by those models. Existing solver runs can write to this database; use a separate database for experiments when preserving it is required.
- [Previous stiffness database](history/module_stiffness_before_update.sqlite3): historical snapshot.

These files were relocated without changing their contents. Frozen study inputs stay beside their study source and may intentionally differ from this shared catalogue. Use the inputs recorded by a particular study when reproducing its results.
