# Technical Report — Consumer-Device Floorplan Reconstruction

**Project:** `floorplan-ai`  
**Repository:** `ZeelVC/floorplan-ai`  
**Baseline:** `main` at `78ec241a3f7a25493b7f9bf4d6ccb3cfed51f0d2`  
**Scope of this report:** engineering baseline, implementation method, evaluation architecture, reproducibility, tooling, process evidence, and known limitations.

## 1. Objective and scope

The system converts consumer phone-camera captures of indoor property into a dimensioned, stitched floorplan. The intended product surface is a whole-property plan containing per-room geometry, walls, wall lengths, openings, ceiling/floor information, measurements, topology/adjacency, confidence and provenance, with JSON plus rendered SVG/DXF output.

The architecture separates source-specific perception from a source-independent downstream pipeline. Photo and Video frontends produce evidence for a shared `CanonicalWorldModel`; structural inference, property relationships, stitching, measurement, confidence, evaluation and rendering consume that canonical representation.

The original challenge also defines a LiDAR tier and damage-related outputs. This implementation baseline deliberately limits active engineering scope to Photo and Video. LiDAR and damage detection/classification/concealed-damage/scope-item generation are recorded as explicit compliance exceptions rather than being silently represented as complete functionality. Laser/tape ground truth remains evaluation-only and is never used for inference, scale or calibration.

## 2. Architecture

```text
Photo / Video capture
        |
        v
Source-specific frontend
  - routing / normalization
  - camera + pose estimation
  - reconstruction / tracking
  - metric depth
        |
        v
CanonicalWorldModel
  - frames
  - cameras / poses
  - observations
  - 3D geometry / planes
  - rooms / walls / openings
  - relationships
  - measurements
  - scale / uncertainty / provenance
        |
        +--> structural inference
        +--> property graph / adjacency
        +--> stitching / reconciliation
        +--> global optimization / drift correction
        +--> measurement
        +--> confidence / calibration
        |
        v
JSON + SVG + DXF + diagnostics + provenance
```

The central architectural invariant is that everything before the canonical model can be source-specific, while everything after it is source-agnostic. This prevents separate Photo and Video implementations from drifting into incompatible wall, room, measurement and rendering semantics.

Geometry and relationships are deliberately separate. Observations represent evidence from sensors/models; structural beliefs represent inferred rooms, walls, openings and topology. Provenance connects the final claims to their supporting observations.

Metric scale is represented as an estimate with uncertainty, evidence and confidence rather than as an unquestioned scalar. EXIF/video metadata is treated as optional camera prior information, not as ground truth. Independent monocular reconstructions can use SE(3) when metric-consistent and Sim(3) when scale remains uncertain.

## 3. Reconstruction implementation

### Photo route

The Photo route accepts per-room image folders and routes all images into the shared downstream model. Input hardening was added for JPEG/PNG/WebP and HEIC/HEIF images while ignoring filesystem noise. Camera metadata and reconstruction-derived intrinsics are retained as evidence.

COLMAP was first used as an offline reconstruction baseline. The implementation added explicit failure reporting, retry logic, relaxed initialization, verified-pair diagnostics and strongest-seed attempts. The benchmark capture demonstrated that COLMAP could still reject the initial reconstruction after multiple valid initialization attempts, so the production Photo route gained a metric-depth-backed fallback rather than treating a failed mapper as a successful sparse reconstruction.

### Metric depth

Apple Depth Pro was integrated as the local metric-depth model. The integration explicitly resolves `auto` to CUDA/MPS/CPU, uses the model checkpoint supplied by the repository configuration, follows the native Depth Pro loading path, handles the native `focallength_px` output key, and passes focal length as a tensor where required by the native inference API.

The checkpoint is stored outside version control and is expected to be fetched or mounted locally. Runtime model downloading is intentionally disabled.

### Depth-odometry fallback

When the Photo reconstruction backend fails, the pipeline uses metric depth plus image correspondences to estimate relative pose. The current implementation uses SIFT features, descriptor matching, depth unprojection, `solvePnPRansac`, and chained camera-to-world transforms. Depth maps and confidence maps are cached for deterministic reuse, and the resulting reconstruction records a direct metric-depth provenance path.

This fallback was introduced because the actual benchmark photos produced COLMAP initialization failures. It allowed the end-to-end pipeline to complete and expose the resulting geometry for evaluation rather than failing at the frontend boundary.

### Geometry and structure

Metric depth is unprojected into 3D, combined with available sparse geometry, and fused into a metric point cloud. Plane fitting then provides candidate floor, ceiling and wall planes. Structural stages infer wall, room and opening entities while preserving confidence and provenance. Manhattan/orthogonality reasoning is treated as a relaxable prior rather than an assumption that every property is rectangular.

### Stitching and global optimization

The system separates room-local reconstruction from property-level placement. Cross-room relationships, shared geometry and topology are handled by stitching/reconciliation and a global property optimization layer. Drift correction is explicit in the architecture and can be ablated, rather than accepting raw sequential poses as final property geometry.

## 4. Measurements, uncertainty and outputs

The measurement layer derives wall lengths, opening dimensions where observable, ceiling height, floor area and related property measurements from canonical/structural geometry. Measurements carry uncertainty/confidence information; 95% intervals are part of the output contract where evidence permits.

Every run produces deterministic machine-readable and rendered artifacts, including:

- `floorplan.json` — canonical final model
- `floorplan.svg` — rendered plan
- `floorplan.dxf` — CAD-oriented rendering
- `diagnostics.json` — run-level health summary
- `provenance.json` — generation provenance
- reconstruction camera/pose artifacts
- correspondence evidence
- metric-depth and point-cloud artifacts
- intermediate COLMAP/depth-odometry logs and diagnostics

A readiness validator checks artifact presence, canonical schema validity, rooms/walls/measurements, measurement intervals, supported capture modalities, diagnostics and provenance.

## 5. Evaluation design and benchmark gates

The project contains benchmark/evaluation infrastructure for wall error, opening width, ceiling height, floor-area/footprint, repeatability, adjacency/topology, drift, stitching and confidence/calibration. Repeatability is evaluated using the challenge condition of wall agreement within 1 cm or 0.5%.

The challenge-specific gates include opening widths within 2 cm on at least 85% of openings, ceiling-height error within 1.5 cm, repeated ceiling spread within 1 cm, photo wall lengths within ±8%, video wall lengths within ±3%, photo whole-property footprint within ±8% with calibrated intervals, correct adjacency/no overlaps, and explicit drift correction evidence. The benchmark also requires a head-to-head comparison on two rooms against a consumer scanning application and a cold walk-in demonstration on an unseen property.

The repository does not claim these gates are passed without measured evidence. A representative photo run was executed end-to-end and committed to the repository as evidence of system behavior. That run produced 5 rooms, 16 walls, 10 openings and 3 stitching components with global optimization and drift-correction switches enabled. These outputs prove that the complete output chain executes, but they do not establish benchmark-gate success.

## 6. Validation, debugging and engineering hardening

The implementation was developed incrementally and validated at each major boundary. The main hardening sequence included:

1. Established the source-independent canonical spatial model and explicit spatial relationships.
2. Added benchmark loading and evaluation-only ground-truth handling.
3. Implemented Photo and Video perception frontends.
4. Added metric-depth and scale/uncertainty propagation.
5. Hardened photo input routing, including HEIC/HEIF handling.
6. Added explicit COLMAP failure reporting instead of allowing generic metric-depth errors to hide frontend failures.
7. Added COLMAP retry strategies using relaxed initialization and verified pair diagnostics.
8. Added a depth-odometry fallback after real benchmark captures repeatedly defeated sparse COLMAP initialization.
9. Integrated the native Apple Depth Pro checkpoint/loading path and device resolution.
10. Added regression tests around the Depth Pro adapter and depth-odometry fallback.
11. Fixed downstream canonical-output defects exposed only after real Depth Pro inference, including a missing `ScaleState` import and a ceiling-plane selection lambda bug.
12. Ran the complete test suite successfully at the final code baseline: 66 tests passed with 27 subtests.
13. Executed the full property reconstruction, retained its intermediate artifacts, and inspected the resulting pose/geometry/stitching evidence.

This process is reflected in the repository's incremental Git history rather than a single end-of-project code drop.

## 7. Tooling and development process

The development process intentionally separated architectural ownership from research and implementation execution.

**Architecture and product decisions — owner:** the project author. The author defined the system objective, scope, source-independent canonical architecture, evaluation principles, compliance boundaries, and major architectural decisions such as canonical convergence, observation-vs-belief separation, probabilistic scale, spatial relationships, local reconstruction plus global stitching, explicit drift handling, and evaluation independence.

**Research and literature synthesis:** Gemini and NotebookLM were used to research implementation approaches, compare candidate algorithms/models/libraries, and synthesize supporting technical information. Research findings were treated as candidate evidence, not as proof of project performance.

**Implementation planning/instructions:** ChatGPT was used to turn architectural goals and research findings into concrete milestone implementation instructions, debugging guidance, test strategies and repository changes.

**Code implementation:** Codex was used to implement the planned changes in the Git repository, add/modify tests, integrate libraries and harden the production path. Changes were reviewed through test results, runtime traces and generated artifacts.

This division is important for the review: the use of AI coding/research tools was explicit, but architectural responsibility remained with the project author. The repository's commit history provides process evidence.

## 8. Models and technology choices

The architecture deliberately keeps major model/library decisions replaceable. Candidate technologies evaluated or integrated include COLMAP for offline multi-view reconstruction, Apple Depth Pro for metric depth, Open3D/plane fitting and geometric reasoning for surfaces, and optimization/reconciliation layers for pose, topology and structural consistency. MASt3R, VGGSfM, MASt3R-SLAM, UniDepthV2 and GTSAM remain architectural candidates rather than being represented as validated benchmark winners unless supported by project measurements.

A key engineering decision was to prefer measured behavior on the actual benchmark over simply reproducing published model claims. This prevented a paper's headline accuracy from being presented as project evidence.

## 9. Current limitations and honest status

The final engineering baseline runs end-to-end and emits the expected principal artifacts, but the representative photo result exposes unresolved quality limitations in multi-view pose estimation and global stitching. Several reconstructed camera poses remain weakly constrained, and the property result remains split into multiple stitching components. Structural inference can therefore over-segment rooms or walls, and current measurements cannot be treated as proof of challenge-gate accuracy.

The current baseline should therefore be described as an executable, inspectable reconstruction system with implemented evaluation infrastructure, not as a demonstrated full-compliance winner. Remaining challenge work is primarily evidence/validation work and, where the measured gates fail, targeted fixes backed by the required before/after fix-loop evidence.

## 10. Reproducibility and submission posture

The repository is offline-first, exposes one-command reconstruction and evaluation entry points, records provenance and diagnostics, keeps large model weights outside Git, and preserves incremental development history. The final reviewer package should pair this technical report with the compliance matrix, capture/device protocol, reproduction bundle, benchmark report, fix-loop bundle and raw benchmark data required by the challenge.

The project intentionally distinguishes four kinds of statements: architectural decisions, literature expectations, internal implementation behavior, and measured benchmark results. Only the last category is used to claim a challenge gate.
