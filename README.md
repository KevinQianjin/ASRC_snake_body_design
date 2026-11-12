# ASRC fuel tank inspection robot

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 12 November 2026

An externally supported telescopic rear with a tendon-driven U4+M2 flexible front: continuous 96 mm modules, a 63 mm envelope, and a nominal 500 g inspection head. Current studies add a 1.8 mm NiTi backbone along each M module.

## Start here

| Find | Open |
|---|---|
| Current design and assumptions | [Current design](docs/current_design.md) · [Model data sheet](ASRC_kevin/telescopic_planar_study/backbone_20261108/model_data/MODEL_DATA.md) |
| Latest results and animations | [Closed-loop report](ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/REPORT.md) · [All reports](reports/README.md) |
| CAD sources and preview | [U/M STEP files](CAD/) · [STEP-derived U4+M2 preview](ASRC_kevin/moving_prototype/final_u4m2/) |
| Run a simulation | [Simulation index and commands](simulations/README.md) |
| Remaining work | [Limitations](docs/limitations.md) · [Roadmap](docs/roadmap.md) |
| Find an older study or moved file | [Repository map](docs/repository_map.md) · [Research history](docs/history.md) |

## Current result

The quasi-static closed-loop study completes five cases with 1,069 reference samples each. All 5,345 corrected settled states meet the selected 1-degree angle criterion and settled-state checks; the worst angular error is 0.699 degrees.

**The complete control sequence is not yet validated.** Seven feedforward arrival states fall below 0.95 N tension (minimum 0.568 N), the feedback target is 1.5 N rather than the 3 N operating recommendation, and the maximum corrected-path sample motion is 6.822 mm. Physical dynamics, sensing delay/noise, friction and integrated hardware still need validation.

[Full-cycle MP4](ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/E75_full_cycle.mp4) · [3D steering GIF](ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/E75_steering.gif) · [Feedback correction GIF](ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/payload550g_feedback_convergence.gif)

## CAD status

Use the original [STEP modules](CAD/) and their [geometry preview](ASRC_kevin/moving_prototype/final_u4m2/). The preview does not validate backbone installation, module interfaces or tendon continuity. The [old full-length prototype](ASRC_kevin/moving_prototype/full_length/NOT_THE_SIMULATED_DESIGN.md) is marked **not the simulated design**; retain its [cleanup review](ASRC_kevin/moving_prototype/full_length/CLEANUP_REVIEW_CONFIRMATION.md) when planning replacement work.

## Repository organisation

`docs/` holds the design, limitations, roadmap and research history. `reports/` holds daily PDFs and weekly presentations. `simulations/README.md` indexes active and reference studies. Existing simulation sources, inputs and result folders retain their paths during this first organisation stage; see the [move map](docs/repository_map.md#path-changes) for the files relocated now.
