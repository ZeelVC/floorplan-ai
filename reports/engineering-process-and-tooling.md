# Engineering Process, Research and Tooling Record

This document supplements the six-page technical report with a fuller account of how `floorplan-ai` was developed, researched, implemented and validated. It is intended as reviewer evidence and process documentation rather than as a second accuracy claim.

## 1. Roles and responsibility

### Project author

The project author retained responsibility for the product problem, scope, architectural decisions, compliance interpretation, canonical data design, evaluation philosophy and acceptance criteria. The author decided that the downstream system must be source-independent, that physical ground truth must remain evaluation-only, that uncertainty is part of the product contract, and that published model performance must not be presented as project performance without measurement.

### Gemini and NotebookLM

Gemini and NotebookLM were used for technical research and literature synthesis. They were used to investigate candidate reconstruction, depth, correspondence, SLAM, plane-fitting, optimization and evaluation approaches; interpret implementation constraints; and compare alternative technical approaches. Their outputs informed candidate selection and implementation planning, but were not treated as benchmark measurements.

### ChatGPT

ChatGPT was used to translate the architectural direction and research findings into actionable engineering instructions. This included milestone plans, implementation plans, interface decisions, debugging analysis, test design, failure-trace interpretation and concrete repository-edit instructions.

### Codex

Codex was used for repository implementation: creating and modifying source files, adding tests, integrating dependencies, hardening code paths, committing changes and iterating from local test/runtime feedback. The implementation was reviewed through actual tests and generated run artifacts rather than accepted solely because code was generated.

## 2. Development sequence

### M4 — Canonical spatial data model

Established the source-independent `CanonicalWorldModel` contract. The model separates coordinate frames, captures, cameras, poses, observations, geometries, planes, rooms, walls, openings, relationships, measurements, scale estimates and provenance. This became the downstream data contract for both capture modalities.

### M5 — Benchmark and input organization

Introduced benchmark/dataset loading and input organization without allowing benchmark ground truth to become part of inference. The benchmark manifest records expected capture/ground-truth locations and validates required inputs.

### M6 — Photo and Video perception

Implemented source-specific Photo and Video frontends and the routing needed to normalize them into the canonical downstream pipeline. Image input hardening later expanded supported still-image formats to HEIC/HEIF as well as common JPEG/PNG/WebP inputs.

### M8 — Metric geometry and scale handling

Implemented metric-depth integration, geometric scale estimation, confidence/uncertainty propagation and conservative geometry reconciliation. The system was structured so that metric scale is an explicit evidence-backed estimate rather than an arbitrary post-hoc multiplier.

### M9 — Global stitching and property optimization

Implemented cross-room reconciliation, global property optimization and topology-aware placement so that the system could move beyond isolated room reconstructions toward a whole-property plan.

### M10 — Confidence and calibration

Added uncertainty propagation, measurement intervals and calibration-oriented evaluation. The system was made capable of distinguishing a precise measurement from a merely confident-looking one.

### M11 — Evaluation and benchmark execution

Added benchmark evaluation, repeatability measurements, benchmark reporting infrastructure and the mapping from challenge gates to evaluation outputs. Ground truth remained evaluation-only.

### M12 — Production hardening

Added packaged CLI behavior, model checking, clearer error reporting, routing/input hardening, and production-oriented artifact generation. Regression tests were expanded around the main interfaces.

### M13 — Deployment/readiness validation

Validated that the package could run through the intended local/offline flow and added readiness-oriented checks around final artifacts and reproducibility.

### M14 — Walk-in readiness

Focused on real capture robustness and end-to-end behavior. The real photo benchmark exposed a conventional COLMAP failure mode, which triggered the fallback work described below.

## 3. Major debugging and implementation events

### COLMAP initialization failure

The first real photo run failed with a generic message that no valid reconstructed frame had usable intrinsics and pose. The actual COLMAP logs showed the underlying cause: with four input images, COLMAP could not find a satisfactory initial image pair and discarded the sparse reconstruction.

The implementation was hardened so that frontend failure was surfaced explicitly instead of being obscured by a later metric-depth error. Retry logic was then added for relaxed mapper initialization and verified-pair/strongest-pair seeding. Real runs demonstrated that even explicit strongest-pair initialization could be rejected during bundle adjustment, so further blind relaxation was avoided.

### Depth-odometry fallback

Because the benchmark photos could not always produce a valid sparse COLMAP model, a metric-depth-backed fallback was implemented. The fallback uses image correspondences, SIFT matching, depth unprojection and `solvePnPRansac` to estimate relative motion and build a trajectory, while caching depth and confidence maps.

This made the pipeline continue to the structural stages and produce inspectable outputs even when the sparse reconstruction frontend failed.

### Apple Depth Pro integration issues

The initial Depth Pro adapter failed because `auto` was passed directly to PyTorch as a device string. Device resolution was corrected to select CUDA, MPS or CPU.

The next failure came from Apple Depth Pro loading its default `./checkpoints/depth_pro.pt` rather than the repository's configured model path. The adapter was changed to use the native Depth Pro configuration with an overridden checkpoint URI and the official model-loading path.

A further API mismatch was found because Depth Pro exposes `focallength_px` and internally expects a tensor for `f_px`. The adapter was corrected for both behaviors and regression tests were added around device resolution and native checkpoint loading.

### Downstream runtime defects

Once real Depth Pro inference began succeeding, latent downstream defects became visible. A missing `ScaleState` import caused a runtime failure in direct metric-depth scale handling. After that was fixed, a separate ceiling-plane selection bug used `p.inlier_count` without binding `p`; this was corrected with an explicit lambda.

The full local suite then passed with 66 tests and 27 subtests.

## 4. Tests and validation philosophy

The test suite was used at two levels:

1. Unit/integration tests validate contracts, error handling, schema compatibility, geometry, scale propagation, routing, calibration, stitching and readiness behavior.
2. Real benchmark runs validate that the system behaves under actual external model/tool constraints and expose failures that synthetic tests may miss.

The second level is essential. Several of the most consequential changes were driven by real run failures that the existing unit suite could not expose, particularly COLMAP initialization, native Depth Pro loading and downstream metric-depth integration.

## 5. Technology and library decisions

The architecture intentionally kept model/library choices replaceable. Candidate technologies included MASt3R and COLMAP for photo reconstruction, VGGSfM and MASt3R-SLAM for video, Depth Pro and UniDepthV2 for metric depth, Open3D and geometric plane-fitting approaches for structure, and GTSAM/pose-graph/global optimization for reconciliation.

The actual production baseline integrated COLMAP where available, Apple Depth Pro for metric depth, OpenCV-based feature matching/PnP for the depth-odometry fallback, geometric plane extraction and the project's own canonical/stitching/measurement layers.

The selection principle was: research creates candidates; controlled experiments and actual runs determine implementation viability; benchmark measurements determine challenge claims.

## 6. Data and ground-truth handling

The supplied benchmark ground-truth workbook was converted into evaluation-oriented JSON structures containing room and wall measurements. Synthetic polygon scaffolding was used only where the workbook did not uniquely determine a full room polygon and was not treated as authoritative reconstruction geometry.

The pipeline architecture explicitly prevents laser/tape ground truth from participating in inference, metric scaling or calibration. Ground truth is reserved for post-run evaluation.

## 7. Current representative real run

The committed representative Photo property run generated the following top-level result counts:

- 5 rooms
- 16 walls
- 10 openings
- 32 measurements
- 3 stitching components
- drift correction enabled
- global property optimization enabled

At the room-reconstruction level the active fallback backend was `DEPTH_ODOMETRY`. The run generated metric-fused point clouds, depth maps, camera/pose artifacts, plane detections, JSON/SVG/DXF outputs and diagnostics.

These numbers demonstrate end-to-end execution but are not represented as proof that the benchmark accuracy gates have passed. The multiple stitching components and pose limitations are the current primary technical risks.

## 8. Why the process is auditable

The repository was developed as a sequence of milestone commits rather than as one final drop. Architectural decisions are recorded separately from candidate technology choices. Evaluation-only data is kept conceptually separate from inference. Generated runs include diagnostics, provenance and intermediate reconstruction evidence. Tests capture both expected behavior and previously encountered regressions.

This record is intended to let a reviewer distinguish what was designed by the project author, what was researched with AI research tools, what was translated into implementation instructions by ChatGPT, what was implemented with Codex, and what was ultimately verified by actual test/run evidence.
