# floorplan-ai

**Consumer-device 3D reconstruction → structural reasoning → dimensioned whole-property floorplan**

GitHub: https://github.com/ZeelVC/floorplan-ai

`floorplan-ai` is an offline-first engineering implementation that reconstructs an indoor property from consumer **Photo** or **Video** captures. The system does not treat floorplan generation as direct image-to-2D prediction. It reconstructs spatial evidence, converts that evidence into a source-independent `CanonicalWorldModel`, infers architectural structure and property topology, performs global reconciliation/stitching, and derives metric measurements with uncertainty and provenance.

> **Validation note:** the repository contains a working end-to-end reconstruction pipeline and real-capture artifacts, but the challenge accuracy gates are **not claimed as passed** without corresponding benchmark evidence.

## System architecture

```text
Consumer Photo / Video
        ↓
Source-specific reconstruction frontend
        ↓
Camera pose + depth + 3D geometry
        ↓
CanonicalWorldModel
        ↓
Structural inference
  ├── floor / ceiling
  ├── walls / corners
  ├── rooms
  └── openings
        ↓
Property graph / spatial relationships
        ↓
Global optimization + stitching + drift correction
        ↓
Metric measurement
        ↓
Confidence / uncertainty / provenance
        ↓
JSON + SVG + DXF
```

## Architectural invariant

Photo and Video have different source-specific frontends, but both converge into the same canonical spatial representation. **Everything before `CanonicalWorldModel` may be source-specific; everything after it is source-agnostic.**

The system also separates **observations** from **structural beliefs**: a detected plane is evidence, not automatically a wall; a geometric polygon is not automatically a room. This keeps structural claims traceable to the evidence supporting them.

## What is implemented

- Photo input routing for JPEG/PNG/WebP and HEIC/HEIF.
- Photo reconstruction with an offline COLMAP path, explicit failure diagnostics, retries, and verified-pair analysis.
- Metric-depth-backed Photo fallback using Apple Depth Pro.
- Depth-odometry reconstruction using RGB correspondences, depth unprojection, robust pose estimation, and chained transforms.
- Video frontend/reconstruction integration into the same canonical downstream model.
- Source-independent `CanonicalWorldModel` containing coordinate frame, poses/trajectory, 3D observations/geometry, structural primitives, spatial relationships, confidence, and provenance.
- Structural inference for floor/ceiling/wall candidates and room/opening geometry where supported by evidence.
- Property-level room/wall/opening relationships and whole-property stitching/reconciliation.
- Global optimization/drift-correction architecture rather than treating raw sequential poses as final property geometry.
- Metric measurements with 95% intervals where available from geometric evidence.
- Deterministic JSON, SVG, and DXF outputs.
- Diagnostics, provenance, readiness checks, evaluation utilities, and regression tests.

## Photo reconstruction strategy

The Photo route initially attempts classical multi-view reconstruction. Real indoor captures exposed a sparse-view failure mode in which COLMAP could not find a sufficiently strong initial pair. The system therefore surfaces the failure explicitly and can fall back to metric-depth-backed reconstruction rather than relying indefinitely on mapper-threshold relaxation.

```text
RGB image
   ↓
Metric depth
   ↓
3D points + RGB correspondences
   ↓
Relative camera transform
   ↓
Trajectory / world geometry
```

Sequential depth-odometry results are intermediate evidence because drift and degenerate registrations can occur. They feed later structural/global stages rather than being presented as guaranteed ground truth.

## Metric scale and uncertainty

Metric scale is represented as an evidence-backed estimate with confidence and uncertainty. Camera metadata is optional prior information, not unquestioned truth. Physical laser/tape measurements are evaluation-only and are never used for inference, scale estimation, or calibration.

Every important measurement is intended to carry:

`value + unit + confidence interval + confidence + provenance`

When evidence is weak, the system should widen uncertainty or return a qualified/degraded result rather than manufacture false precision.

## Outputs

A successful run produces inspectable artifacts such as:

- `floorplan.json` — canonical machine-readable result.
- `floorplan.svg` — rendered floorplan.
- `floorplan.dxf` — CAD-oriented rendering.
- `diagnostics.json` — run health and reconstruction evidence.
- `provenance.json` — output provenance.
- reconstruction cameras/poses, depth maps, correspondence evidence, and backend logs.

## Run locally

```bash
pip install -e '.[dev]'
floorplan-ai fetch-models --check

floorplan-ai reconstruct \
  --input ./capture \
  --output ./result

floorplan-ai reconstruct \
  --input ./walkthrough.mp4 \
  --output ./result

floorplan-ai evaluate \
  --prediction ./result/floorplan.json \
  --ground-truth ./ground-truth.json \
  --report-out ./result/report.json
```

Real Photo reconstruction requires the local Depth Pro checkpoint described by `models/manifest.json`. Large model weights are not committed to Git and runtime does not silently download them.

## Repository evidence

| Area | Location |
| --- | --- |
| Requirements / terminology | [`REQUIREMENTS.md`](REQUIREMENTS.md) |
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Design decisions | [`DECISIONS.md`](DECISIONS.md) |
| Deliverables / compliance posture | [`DELIVERABLES.md`](DELIVERABLES.md) |
| Technical report | [`reports/technical-report.md`](reports/technical-report.md) |
| Engineering process and tooling | [`reports/engineering-process-and-tooling.md`](reports/engineering-process-and-tooling.md) |
| Ground truth | [`data/ground_truth/property_01/ground-truth.json`](data/ground_truth/property_01/ground-truth.json) |
| Model manifest | [`models/manifest.json`](models/manifest.json) |

The commit history also records the incremental implementation and debugging process, including real reconstruction failures and the fixes introduced in response.

## Current validation status

The implementation has been exercised with the real Photo capture path and can complete the end-to-end artifact-generation chain. Automated regression coverage has also been added around major integration and failure modes.

The representative Photo reconstruction is **not** presented as a benchmark-gate result. It exposed unresolved limitations including weak/degenerate pose constraints, uncertain scale in some reconstructions, disconnected stitching components, sparse or suspicious 3D geometry in portions of the result, and room/wall over-generation relative to the available benchmark ground truth.

The next validation stage is quantitative benchmark evaluation plus targeted hardening of reconstruction, structural inference, global stitching, drift correction, and uncertainty calibration.

## Scope and honest limitations

### Active engineering scope

- Photo reconstruction.
- Video reconstruction.
- Canonical spatial representation.
- Walls / rooms / openings where supported by evidence.
- Metric measurements with uncertainty.
- Whole-property stitching/topology.
- JSON/SVG/DXF output.
- Diagnostics, provenance, and evaluation infrastructure.

### Explicitly not claimed

- **LiDAR tier:** not implemented/validated because suitable LiDAR-capable hardware was not available.
- **Damage detection/classification/metric damage extent:** not implemented/validated.
- **Concealed-damage inference and damage-derived scope items:** not implemented/validated.
- **Challenge accuracy gates:** not claimed as passed without benchmark evidence.

The project deliberately distinguishes architecture, literature/research expectations, implementation behavior, real-capture observations, and measured benchmark results. Only measured benchmark evidence is used to claim a challenge gate.
