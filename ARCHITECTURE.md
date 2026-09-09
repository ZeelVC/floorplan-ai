# Architecture — Milestone 3

## 1. System objective and scope

`floorplan-ai` is an Applied AI system intended to turn consumer phone-camera **photos** or a **video walkthrough** of indoor space into a dimensioned, stitched whole-property floor plan. The primary product surface is the stitched property plan: per-room geometry is valuable, but a result with individually plausible rooms and incorrect placement, connections, or adjacency is not a correct property reconstruction. Photo and Video therefore have independent, source-specific frontends but converge into one representation so that the same structural, topology, measurement, confidence, JSON, and rendering logic applies to either route.

The original challenge includes Photo, Video, and LiDAR capture tiers plus damage-related outputs. The active implementation scope is Photo and Video only. **LiDAR is explicitly out of current implementation scope** because no suitable LiDAR-capable device is available. **Damage detection, classification, measurement, concealed damage, and damage-derived scope items are explicitly out of current implementation scope.** These exclusions are compliance exceptions, not rewrites of the original requirements; full challenge compliance is not claimed. Physical laser/tape ground truth is **evaluation-only** and must never enter inference, scale determination, or calibration.

Terminology follows [`REQUIREMENTS.md`](REQUIREMENTS.md) and [`DELIVERABLES.md`](DELIVERABLES.md): challenge **requirements**, active **scope**, **out-of-scope** requirements, **evaluation-only** inputs, **candidate** technologies, literature results, internal experiments, and actual **measured results** remain distinct. This milestone reports no measured results.

## 2. End-to-end architecture

```text
┌───────────────────────────────────────────────────────────┐
│ INPUTS: PHOTO                 VIDEO            PHOTO+VIDEO │
└──────────┬─────────────────────┬────────────────────┬─────┘
           ▼                     ▼                    │
    ┌─────────────┐       ┌─────────────┐             │
    │ Photo       │       │ Video       │             │
    │ Frontend    │       │ Frontend    │             │
    └──────┬──────┘       └──────┬──────┘             │
           ▼                     ▼                    │
    ┌─────────────┐       ┌─────────────┐             │
    │ Photo World │       │ Video World │             │
    │ Model       │       │ Model       │             │
    └──────┬──────┘       └──────┬──────┘             │
           └──────────┬──────────┘                    │
                      ▼                               │
           ┌──────────────────────┐                   │
           │ Registration /       │◄──────────────────┘
           │ Cross-modal Fusion   │
           └──────────┬───────────┘
                      ▼
           ┌──────────────────────┐
           │ Canonical World Model│
           └──────────┬───────────┘
                      ▼
           ┌──────────────────────┐
           │ Structural Inference │ Floor, ceiling, walls,
           │                      │ rooms, openings
           └──────────┬───────────┘
                      ▼
           ┌──────────────────────┐
           │ Property Graph /     │ adjacency, connections,
           │ Spatial Relationships│ opening links
           └──────────┬───────────┘
                      ▼
           ┌──────────────────────┐
           │ Global Optimization  │ drift, scale consistency,
           │ / Stitching          │ room alignment
           └──────────┬───────────┘
                      ▼
           ┌──────────────────────┐
           │ Measurement Engine   │
           └──────────┬───────────┘
                      ▼
           ┌──────────────────────┐
           │ Confidence /         │
           │ Calibration          │
           └──────────┬───────────┘
                      ▼
                  ┌─────┴─────┐
                  ▼           ▼
                JSON      Rendered plan
```

**Architectural invariant:** everything before `CanonicalWorldModel` may be source-specific; everything after it must be source-agnostic. Frontends validate and normalize capture evidence. World models preserve each frontend's poses, geometry, uncertainty, and provenance. Registration aligns independently reconstructed sources when both exist. The canonical model is the contract for structural inference; the property graph records topology; global optimization reconciles constraints; the measurement engine derives dimensions; confidence/calibration describes reliability; JSON and the rendered plan expose one consistent result.

## 3. Source-specific frontends

### 3.1 Photo pipeline

```text
Images → preprocessing → camera estimation / metadata priors
→ multi-view reconstruction → 3D geometry → metric-depth / scale reasoning
→ Photo World Model → Canonical World Model
```

The Photo frontend supports image quality checks, feature/correspondence evidence, camera estimation, reconstruction, geometry, and uncertainty. **MASt3R is a candidate implementation to be experimentally evaluated.** COLMAP is a candidate offline baseline/benchmark for controlled comparison; other learned multi-view reconstruction approaches may also be tested. Candidate approaches may struggle with low-texture walls, repeated patterns, mirrors, glass and other reflective surfaces, low light, furniture occlusion, and monocular scale ambiguity. No model is selected as a production dependency; later milestones must validate technology choices experimentally.

### 3.2 Video pipeline

```text
Video → frame sampling / preprocessing → visual tracking / reconstruction
→ trajectory + geometry → metric-depth / scale reasoning → drift correction
→ Video World Model → Canonical World Model
```

The Video frontend defines capabilities rather than libraries:

```text
Video reconstruction
├── frame selection
├── correspondence / tracking
├── camera pose estimation
├── 3D reconstruction
├── trajectory estimation
└── uncertainty
```

VGGSfM, MASt3R-SLAM, and other learned tracking/SLAM approaches are replaceable candidates to be evaluated, not permanent dependencies. Sequential evidence can increase coverage but adds accumulated drift and motion/blur failure modes; raw sequential poses are never final output.

### 3.3 Metadata and cross-modal registration

EXIF and video metadata are optional evidence, following `metadata → camera prior → camera estimation / validation`, not ground-truth camera parameters. Missing, incomplete, inaccurate, or device-variable metadata must leave the system operational with wider uncertainty or alternate estimation. Metadata is useful only when validated against other evidence.

```text
Photo World Model → CrossModalRegistration ← Video World Model
CrossModalRegistration
├── correspondence
├── geometric verification
├── transformation estimation
└── refinement
```

This interface is source-independent. MASt3R, LightGlue, and other correspondence methods are candidate implementations only. For independently reconstructed monocular scenes, `X_video = s R X_photo + t`. Use Sim(3) when scale is uncertain; use SE(3) only when reconstructions are sufficiently metric-consistent. The system must not apply arbitrary scale when both inputs are already metric.

## 4. CanonicalWorldModel

`CanonicalWorldModel` is a source-independent conceptual representation, not a prematurely fixed class or file schema:

```text
CanonicalWorldModel
├── CoordinateFrame
├── Poses & Trajectory
├── 3D Metric Geometry
├── Structural Primitives
├── Spatial Relationships
└── Spatial Confidence & Provenance
```

- **CoordinateFrame** records world coordinates, gravity-aligned orientation, ground/floor-plane convention, metric units, and transforms/relationships between frames. Exact conventions remain experimentally open.
- **Poses & Trajectory** records camera poses, pose uncertainty, trajectories, capture/source identities, and coordinate-frame relationships.
- **3D Metric Geometry** records observed 3D points, depth observations, surfaces/point clouds, metric estimates, and uncertainty.
- **Structural Primitives** records inferred Floor, Ceiling, Wall, Room, and Opening entities.
- **Spatial Relationships** records `Room ↔ Room`, `Room ↔ Wall`, `Opening ↔ Wall`, `Opening ↔ Room`, `Wall ↔ Plane`, and `Plane ↔ Observation` links.
- **Spatial Confidence & Provenance** traces each important prediction through evidence and source observation/model to confidence and uncertainty.

Geometry answers where entities are; relationships answer how they connect and which evidence supports them. Keeping them separate supports adjacency, room stitching, opening connections, topology, debugging, and global optimization without treating a proximity heuristic as fact.

### 4.1 Observations versus structural beliefs

```text
Canonical World
       │
  ┌────┴────┐
  ▼         ▼
Observations  Structure
  │       inferred layer
  └────┬────┘
       ▼
 Measurements
```

**Observations** are what sensors/models actually produce: image observations, feature correspondences, depth and plane observations, camera/pose estimates, and reconstruction outputs. **Structural beliefs** are inferred claims: walls, rooms, floors, ceilings, doors/openings, adjacency, and structural geometry. This separation makes failures attributable: a wrong wall measurement may originate in depth, pose, plane extraction, structural inference, scale, or stitching rather than being hidden by one final geometry object.

### 4.2 Metric scale

```text
Metric depth + camera metadata + architectural priors + geometric consistency
                              ↓
                       scale estimation
                              ↓
ScaleEstimate { value, uncertainty / interval, source / evidence, confidence }
```

Scale is not merely a scalar `s`. Door-height, ceiling-height, and camera-height expectations are probabilistic evidence, never hard ranges or mandatory truths. They may resolve ambiguity but must yield to contradictory observations and report uncertainty to prevent confidently wrong measurements. Ground-truth measurements are prohibited from scale inference.

## 5. Structural and property representation

### 5.1 Structural geometry

```text
Observations → planes → floor / ceiling / wall candidates
→ structural reasoning → rooms / walls / openings
```

Candidate capabilities include plane fitting, floor and ceiling extraction, wall-plane extraction, and BEV or equivalent representations. Structural optimization can combine observed geometry with a Manhattan/orthogonality prior to find the best explanation. Manhattan geometry is not a hard law: angled walls, irregular rooms, non-orthogonal geometry, and renovations remain valid when observations contradict the prior.

A **Room** has a unique ID, boundary geometry, associated walls, floor and ceiling associations, openings/connections, measurements, confidence, and provenance. It is inferred from structural evidence rather than a prescribed final segmentation algorithm. A **Wall** has a unique ID, geometry, supporting plane, endpoints/boundary, associated rooms/openings, measured length, uncertainty/confidence, and provenance. Furniture is observation/occlusion evidence, not automatic structural wall geometry. An **Opening** is structural—not simply an image detection—and has an ID, type/category when available, location, observable width/height, supporting wall, connected rooms, confidence, and provenance. Wardrobes, bookshelves, furniture gaps, mirrors, windows, and glass are potential false positives. Both missed and phantom openings are evaluation failures.

### 5.2 Property graph and stitching

```text
Property
├── Room A
│     └── Opening O1
│             └── Room B
├── Room B
└── Room C
```

The property graph records room adjacency, room-to-opening and wall-to-opening links, room connectivity, and property topology. Topology is distinct from raw geometry: correct shapes with wrong adjacency are still incorrect reconstruction.

Preferred design combines local geometry and global relationships:

```text
PROPERTY → Room-local geometry ─┐
         → Global topology      ├→ global property plan
           / relationships      ┘
```

Local room reconstruction can be robust without assuming every capture must become one monolithic scene. Stitching establishes relative placement, shared walls, openings, adjacency, topology, and a globally consistent frame.

### 5.3 Drift and global optimization

```text
Raw trajectory → drift detection → constraints / loop closures
→ global optimization → corrected trajectory
```

Drift correction is explicit and independently evaluable (drift correction OFF versus ON). Candidate mechanisms include loop closure, pose-graph optimization, plane constraints, structural constraints, and global optimization. The broader optimizer may consume reprojection, pose, loop-closure, cross-modal registration, plane, and structural constraints. Bundle adjustment optimizes cameras/geometry against reprojection; pose-graph optimization reconciles pose relations/loops; structural optimization reconciles planes, rooms, and topology. They are related but not interchangeable. GTSAM is a candidate tool, not an architectural dependency.

## 6. Measurement, confidence, and outputs

The source-agnostic measurement engine derives wall length, room dimensions, opening width/observable height, ceiling height, floor area, and whole-property footprint from canonical/structural geometry—not separate Photo and Video measurement systems.

```text
Measurement
├── value
├── unit
├── uncertainty interval
├── confidence
├── provenance
└── source geometry
```

Confidence is a first-class result: evidence quality drives uncertainty, which drives measurement confidence. Weak, conflicting, sparse, or unavailable evidence must widen intervals or yield a qualified/degraded result; confidence is not decorative. Later evaluation must assess calibration and reject unjustifiably narrow intervals.

```text
Canonical / Structural Model
├── JSON: property, rooms, walls, openings, relationships,
│         measurements, uncertainty, confidence, provenance
└── Rendered floor plan: stitched geometry and dimensions clearly communicated
```

## 7. Evaluation architecture and challenge gates

```text
Physical measurement / laser / tape → Evaluation only
                                  ✗ → inference / scale / calibration
```

Evaluation is independent from inference and will measure wall-length and relative-wall error, opening width error and precision/recall, ceiling-height error, floor-area and footprint error, room overlap, adjacency, repeatability, confidence calibration, drift, and stitching quality. No benchmark is run or claimed here. The evaluation framework must determine whether implementation satisfies the ±8% photo challenge gate (and all other gates), rather than assuming it.

The gate-to-component mapping is intentionally traceable to [`REQUIREMENTS.md`](REQUIREMENTS.md), which remains the authoritative gate record:

| Challenge gate | Architecture components where evaluated |
| --- | --- |
| Photo / Video wall length | Measurement → Evaluation |
| Property footprint | Stitching → Measurement → Evaluation |
| Opening width | Opening → Measurement → Evaluation |
| Ceiling height | Structural inference → Measurement → Evaluation |
| Repeatability | Evaluation |
| Drift | Reconstruction → Optimization → Evaluation |
| Adjacency | Property Graph → Evaluation |
| Confidence | Confidence / calibration → Evaluation |

## 8. Failure modes and fallback/degradation

| Failure mode | What/where can fail | Revealing evidence | Candidate fallback or degradation |
| --- | --- | --- | --- |
| Low-texture walls; repeated textures | correspondence, pose, plane extraction | sparse/inconsistent matches; residuals | use complementary depth/planes or report reduced coverage/uncertainty |
| Mirrors, glass, reflective surfaces | false geometry/correspondence | inconsistent multi-view/depth evidence | down-weight/reject inconsistent evidence; preserve ambiguity |
| Low light | preprocessing/tracking | blur/noise/low feature quality | select usable frames/images; degrade confidence or fail clearly |
| Furniture | structural inference/openings | non-planar/temporary/object evidence | avoid promoting it to structure without corroboration |
| Missing/inaccurate EXIF | camera prior | absent/conflicting metadata | estimate without metadata; down-weight or reject the prior |
| Poor correspondence/reconstruction failure | frontend/registration | failed verification, residuals, low coverage | retain separate evidence, request/rely on alternate capture, or return qualified failure |
| Scale ambiguity | scale/registration | divergent scale evidence, broad posterior | use multiple soft evidence sources; use Sim(3) if needed; widen interval |
| Drift | video trajectory/stitching | loop inconsistency, room misalignment | loop/plane/structural constraints and global optimization |
| Incorrect room stitching | graph/optimization | overlaps, incompatible openings/adjacency | preserve competing hypotheses; flag/reduce confidence rather than force placement |
| Opening ambiguity | opening inference | weak wall support, conflicting views | retain unknown category or omit low-support belief with uncertainty |
| Non-Manhattan geometry | structural optimization | systematic residuals after orthogonal fit | relax Manhattan prior and retain observed angles |

These are architectural strategies to be validated, not confirmed implementation behavior.

## 9. Technology candidates and selection principle

| Capability | Candidates | Status |
| --- | --- | --- |
| Photo reconstruction | MASt3R; COLMAP offline baseline; other learned reconstruction | Candidates to evaluate |
| Video reconstruction/tracking | VGGSfM; MASt3R-SLAM; other learned tracking/SLAM | Candidates to evaluate |
| Metric depth | Depth Pro; UniDepthV2 | Candidates to evaluate |
| Geometry | Open3D; plane fitting; structural/Manhattan reasoning; BEV-style representations | Candidates to evaluate |
| Optimization | GTSAM; pose-graph optimization; global structural optimization | Candidates to evaluate |

**Major AI/model/library choices will be validated through incremental experiments rather than assumed from paper results.** A literature result motivates a candidate; an internal experiment supplies project evidence; a benchmark result is a measured result from this project; a challenge gate is passed only through its specified evaluation. Replacing any candidate must not violate the canonical-model contract.

## 10. Risks and unresolved questions

| Risk | Architectural mitigation / experiment question |
| --- | --- |
| Monocular scale ambiguity; confidence miscalibration | multi-evidence `ScaleEstimate`; calibration evaluation |
| Low texture; reflective/transparent surfaces; reconstruction failure | evidence provenance, quality checks, qualified degradation |
| Trajectory drift; multi-room alignment | explicit drift subsystem and global constraints |
| Topology/opening errors; furniture mistaken for structure | relationships, structural corroboration, precision/recall and adjacency evaluation |
| Over-constraining geometry | relaxable Manhattan prior and residual analysis |
| Overfitting current benchmark; unseen-property walk-in robustness | held-out/unseen-property evaluation in later milestones |

Unresolved implementation questions include the final Photo/Video/depth models; exact plane extraction, room segmentation, opening detection, optimization backend, confidence calibration, and rendering implementation. They are intentionally deferred to experimental milestones.
