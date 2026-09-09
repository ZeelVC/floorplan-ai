# Architecture Decision Records — Milestone 3

These records freeze high-level architectural contracts while leaving unvalidated model and algorithm choices open. Status **Accepted** means the architectural boundary is adopted; it does not claim that an implementation experiment has succeeded. Terms and scope follow [`REQUIREMENTS.md`](REQUIREMENTS.md) and [`DELIVERABLES.md`](DELIVERABLES.md).

## Decision 1 — Source-independent CanonicalWorldModel
### Status
Accepted
### Context
Photo and Video need source-specific reconstruction but one stitched property product.
### Decision
Converge both into `CanonicalWorldModel`; everything downstream is source-agnostic.
### Rationale
Prevents divergent room, wall, measurement, and rendering systems.
### Alternatives Considered
Separate end-to-end Photo and Video stacks; a single source-specific frontend.
### Trade-offs
Requires a careful shared contract before implementation.
### Risks
An overly rigid schema could block useful evidence; exact data schema is deferred.
### Validation Plan
Run equivalent downstream/evaluation experiments from each frontend and joint captures.

## Decision 2 — Spatial Relationships
### Status
Accepted
### Context
Geometry alone cannot reliably express connections and topology.
### Decision
Make room, wall, opening, plane, and observation relationships first-class canonical data.
### Rationale
Supports adjacency, stitching, debugging, and optimization.
### Alternatives Considered
Infer relationships only from final geometric proximity.
### Trade-offs
Adds graph consistency work and uncertainty handling.
### Risks
Incorrect links can corrupt topology.
### Validation Plan
Evaluate adjacency, opening links, overlaps, and graph consistency.

## Decision 3 — Observations vs Structural Beliefs
### Status
Accepted
### Context
Model outputs are evidence, while rooms/walls are inferred claims.
### Decision
Represent observations separately from structural beliefs and retain provenance between them.
### Rationale
Enables diagnosis of depth, pose, plane, scale, inference, and stitching failures.
### Alternatives Considered
Store only final structural geometry.
### Trade-offs
More records and evidence-link management.
### Risks
Weak provenance would defeat traceability.
### Validation Plan
Use failure cases to trace erroneous measurements to supporting observations.

## Decision 4 — Probabilistic ScaleEstimate
### Status
Accepted
### Context
Monocular reconstruction has ambiguous metric scale.
### Decision
Represent scale with value, uncertainty/interval, evidence source, and confidence; combine depth, metadata, soft priors, and geometric consistency.
### Rationale
Avoids confidently wrong measurements and supports Sim(3) when appropriate.
### Alternatives Considered
A fixed scale factor; ground truth; hard architectural dimensions.
### Trade-offs
Requires uncertainty propagation and calibration work.
### Risks
Biased priors or overconfident fusion.
### Validation Plan
Evaluate scale error and interval calibration without ground truth entering inference.

## Decision 5 — EXIF as Camera Prior
### Status
Accepted
### Context
Metadata may be missing, incomplete, inaccurate, or device-variable.
### Decision
Use EXIF/video metadata as optional camera/intrinsic priors for estimation and validation, never ground truth.
### Rationale
Keeps the system operational without metadata.
### Alternatives Considered
Require EXIF; trust it as exact parameters; ignore it entirely.
### Trade-offs
Validation and fallback estimation are required.
### Risks
Bad metadata can bias reconstruction.
### Validation Plan
Compare metadata-present, absent, and perturbed-prior experiments.

## Decision 6 — Cross-modal Registration
### Status
Accepted
### Context
Photo and Video may observe overlapping property areas from independent reconstructions.
### Decision
Provide replaceable correspondence, verification, transform-estimation, and refinement capabilities between their world models.
### Rationale
Enables fusion without coupling architecture to MASt3R, LightGlue, or another library.
### Alternatives Considered
No fusion; hard-code one matching implementation.
### Trade-offs
Interface must carry uncertainty and failure states.
### Risks
False correspondence causes bad fusion.
### Validation Plan
Measure verified matches, alignment residuals, and stitch quality across candidates.

## Decision 7 — SE(3) vs Sim(3)
### Status
Accepted
### Context
Independent monocular reconstructions may disagree in scale.
### Decision
Use SE(3) for sufficiently metric-consistent inputs and Sim(3) when scale is uncertain.
### Rationale
Avoids arbitrary rescaling of already metric-consistent inputs.
### Alternatives Considered
Always SE(3); always Sim(3); blindly force a scale.
### Trade-offs
Requires scale-consistency assessment.
### Risks
Misclassification can distort geometry.
### Validation Plan
Compare transformations against held-out evaluation-only measurements and residuals.

## Decision 8 — Local Reconstruction + Global Stitching
### Status
Accepted
### Context
A giant monolithic reconstruction can be fragile across rooms.
### Decision
Prefer room-local geometry combined with global topology, relationships, and stitching.
### Rationale
Separates robust local evidence from property-level placement.
### Alternatives Considered
Always reconstruct one monolithic scene; emit isolated rooms only.
### Trade-offs
Requires cross-room association and optimization.
### Risks
Room alignment/topology errors.
### Validation Plan
Evaluate overlap, footprint, shared walls, openings, and adjacency.

## Decision 9 — Manhattan as Prior
### Status
Accepted
### Context
Many interiors are approximately orthogonal, but not all are.
### Decision
Use Manhattan/orthogonality as a relaxable structural prior, not a hard constraint.
### Rationale
It can stabilize weak evidence without erasing angled walls or renovations.
### Alternatives Considered
Force every wall to 90 degrees; never use structural priors.
### Trade-offs
Optimization must balance observations and priors.
### Risks
Over- or under-regularization.
### Validation Plan
Test orthogonal and non-orthogonal properties and compare residuals/errors.

## Decision 10 — Global Optimization
### Status
Accepted
### Context
Reprojection, pose, loop, plane, and structural constraints have different meanings.
### Decision
Use a broader global-optimization architecture that distinguishes bundle adjustment, pose-graph optimization, and structural optimization.
### Rationale
Prevents calling all optimization “bundle adjustment” and supports proper constraints.
### Alternatives Considered
One undifferentiated optimizer; only local adjustment.
### Trade-offs
More explicit interfaces and experiment design.
### Risks
Incompatible or overweighted constraints.
### Validation Plan
Ablate constraint families and measure geometry, drift, topology, and calibration; GTSAM remains only a candidate backend.

## Decision 11 — Drift Correction
### Status
Accepted
### Context
Raw sequential video poses accumulate error and are challenge-inadequate.
### Decision
Make drift detection/correction explicit using candidates such as loop closures, pose graphs, plane/structural constraints, and global optimization.
### Rationale
Makes correction observable rather than implicit.
### Alternatives Considered
Use raw poses as final; hide correction inside tracking.
### Trade-offs
Needs loop/constraint verification.
### Risks
False loop closures or excessive correction.
### Validation Plan
Measure drift correction OFF versus ON and report stitching impact.

## Decision 12 — Source-agnostic Downstream Pipeline
### Status
Accepted
### Context
Duplicated downstream systems would yield inconsistent outputs.
### Decision
Structural inference, property graph, stitching, measurement, confidence, JSON, and rendering consume the canonical representation only.
### Rationale
Provides one product contract and comparable evaluation.
### Alternatives Considered
Separate per-source downstream systems.
### Trade-offs
Canonical adapter quality becomes critical.
### Risks
Lossy adaptation or unclear source provenance.
### Validation Plan
Verify identical output semantics and provenance for Photo, Video, and fused inputs.

## Decision 13 — Evaluation Independence
### Status
Accepted
### Context
Physical laser/tape data is available as ground truth.
### Decision
Keep ground truth strictly evaluation-only; never use it for inference geometry, scale, or calibration.
### Rationale
Protects defensible benchmark evidence.
### Alternatives Considered
Use reference measurements to set scale or tune each capture.
### Trade-offs
Harder inference and fewer shortcuts.
### Risks
Accidental data leakage.
### Validation Plan
Audit provenance/input manifests and enforce blind evaluation protocol.

## Decision 14 — Experimental Technology Selection
### Status
Accepted
### Context
Published performance does not prove project performance on this benchmark or an unseen property.
### Decision
Keep MASt3R, COLMAP, VGGSfM, MASt3R-SLAM, Depth Pro, UniDepthV2, Open3D, GTSAM, and alternatives as candidates until incremental experiments validate them.
### Rationale
Architecture should survive candidate replacement and challenge gates require project evidence.
### Alternatives Considered
Select tools from literature before experiments.
### Trade-offs
Delays final dependency commitment.
### Risks
Experiment cost and indecision.
### Validation Plan
Record literature expectation → candidate → internal experiment → measured benchmark result → challenge-gate evidence.

# Deferred / Not Yet Decided

The following are deliberately not selected in Milestone 3: final Photo reconstruction model; final Video reconstruction model; final metric-depth model; exact plane extraction algorithm; exact room segmentation algorithm; exact opening detection model; exact optimization backend; exact confidence-calibration method; and exact rendering implementation. These will be resolved through later milestones and controlled experiments. No candidate is an experimentally validated production choice, and no challenge gate or full challenge compliance is claimed.
