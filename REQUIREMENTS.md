# Requirements and Scope Contract

This document records the Applied AI challenge **requirements** separately from
the project's **active scope**. A requirement is something specified by the
challenge; active scope is something this project will implement. A challenge
requirement explicitly excluded by the HR/user clarification is **out of
scope**, not removed from the challenge record.

## 1. Challenge requirements

### Capture tiers

The challenge defines three mandatory input tiers. Every tier is expected to
produce the same output contract, with uncertainty widening as sensor
information becomes weaker.

| Challenge tier | Challenge capture requirement | Current project status |
| --- | --- | --- |
| Photos | 2–8 stills per room from an iPhone 15 or newer; no depth or poses are supplied. | **Active scope** — photo pipeline. |
| Video | Handheld walkthrough from an iPhone 15 or newer. | **Active scope** — video pipeline. |
| LiDAR | Depth, poses, and intrinsics from Pro-class devices. | **Out of scope — HR clarification** — no LiDAR implementation. |

The implemented photo and video routes will converge on a shared canonical
spatial representation. LiDAR remains documented as a challenge requirement;
its omission is a compliance exception, not a reinterpretation of the
challenge.

## 2. Output contract

The challenge output contract requires, for every capture tier:

- a dimensioned per-room plan;
- walls and wall lengths;
- ceiling height and floor area;
- openings;
- a stitched multi-room plan with correct room adjacency;
- a confidence interval for every measurement;
- JSON output and a rendered plan; and
- one command per capture.

The active implementation will deliver these floor-plan outputs for the photo
and video pipelines, including room and wall reconstruction, openings, ceiling
height, floor area, measurements, confidence intervals/calibration, stitching,
adjacency, drift correction, rendered plans, JSON, and evaluation/benchmark
infrastructure.

The challenge also includes damage-related output expectations (damage
detection/assessment, damage-region classification, concealed-damage detection,
and damage-based scope line items). Those challenge requirements are **out of
scope — HR clarification**. They are not part of the active implementation
architecture and will not be represented as planned functionality in this
milestone.

## 3. Product surface

The stitched whole-property floor plan is the primary product surface. The
photo pipeline is not a single-room-only system: folders of photos for
individual rooms must ultimately converge into the same whole-property
representation used by the other implemented tier. Per-room outputs are
intermediate and required views of that whole-property result, not the terminal
photo product.

## 4. Benchmark requirements

### Challenge-specified benchmark

The challenge benchmark requires:

- one multi-room capture with at least three rooms plus a connector;
- a furnished room;
- the same rooms captured across tiers in the original challenge;
- at least one room captured twice at the same tier;
- laser/tape ground truth; and
- submission of raw sensor data and measurements.

The original cross-tier requirement includes the LiDAR tier. Since LiDAR is out
of active scope, full three-tier benchmark compliance is not claimed.

### Current project benchmark

The currently available benchmark data is limited to:

- 24 images;
- 2 videos;
- Trial 1: horizontal orientation;
- Trial 2: vertical orientation;
- Room 1;
- Room 2;
- Room 3;
- Video 1;
- Video 2; and
- physical ground-truth measurements.

This list describes available data, not a measured result or a claim that all
challenge benchmark conditions have been satisfied. No additional images,
captures, rooms, sensors, or measurements are implied.

## 5. Accuracy gates

The following are challenge gates to be evaluated. They are requirements, not
results achieved by this project.

### Opening width

- Error must be ≤ 2 cm on ≥85% of openings.
- Missed openings and phantom openings count as failures.

### Ceiling height

- Error must be ≤ 1.5 cm per room.
- Where a room is captured more than once, spread across captures must be ≤1 cm.

### Repeatability

Two captures of the same room at the same tier must agree per wall within:

- 1 cm, or
- 0.5%.

### Drift

The system must address accumulated drift. The report must explain its
correction method, for example loop closure, a pose graph, plane-anchored
correction, or another justified method. Raw poses used as-is are an automatic
failure under the challenge.

### Photo whole-property stitch

Per-room photo folders must produce one stitched plan with correct adjacency,
no room overlaps, a footprint within ±8%, and calibrated confidence intervals.

### Photo wall lengths

Photo wall lengths must be within ±8%.

### Video wall lengths

Video wall lengths must be within ±3%.

### Calibration

Calibration/confidence is scored at every tier. Weak sensor input must result
in wider uncertainty rather than unjustified confidence. The LiDAR calibration
gate remains a challenge requirement but is out of active implementation scope.

## 6. Evaluation methodology

### Inference inputs

Inference inputs are only capture data used by the pipeline. In this project,
they are:

- photos; and
- video.

### Evaluation-only inputs

Evaluation-only information is used to assess the system and is never supplied
to inference. It includes:

- laser/tape measurements;
- physical ground truth; and
- benchmark reference measurements.

Ground truth must **never** be passed to the inference pipeline to determine
geometry or scale.

Terminology in benchmark reporting is strict: a **literature/research
expectation** is a result reported by external research and is not a project
benchmark result; a **measured result** is a result actually obtained from this
project's benchmark. This milestone reports no measured results and does not
claim any gate has passed.

## 7. Consumer application comparison

The original challenge specifies a consumer scanning-app comparison and uses
the LiDAR tier for that comparison. The original LiDAR head-to-head requirement
is **unimplemented / Out of scope — HR clarification**. This project does not
claim to have satisfied it. A later comparison using the available photo/video
tiers must be labelled an additional experiment, not presented as satisfaction
of the original LiDAR requirement.

## 8. Fix loop

For each improvement cycle, the challenge requires this regenerable process:

1. Identify the single worst-performing gate.
2. Record the failing number.
3. State the root-cause hypothesis.
4. Provide evidence.
5. Predict the post-fix number.
6. Ship the fix.
7. Produce before/after regenerable runs.
8. Include a readable diff.
9. Report honestly if the gate remains failed.

## 9. Process evidence

The challenge explicitly evaluates Git history. Implementation must therefore
be developed through meaningful incremental commits, rather than a one- or
two-commit repository produced at the deadline. AI coding tools are allowed by
the challenge; their use does not remove the need for reviewable process
evidence.

## 10. Walk-in test

The challenge requires the system to run on a previously unseen property using
their iPhone 15 or newer and to be evaluated against laser measurements during
the defense. Within this project's scope, only the implemented photo/video
routes are intended to be production-ready. Full three-tier readiness is not
claimed because LiDAR is out of scope.

## 11. Constraints

The challenge constraints are:

- handheld consumer capture;
- pretrained models are allowed with disclosure;
- dataset/API usage must be disclosed;
- execution must not depend on the developer's infrastructure;
- model weights and large binaries should be fetched by script or volume; and
- the system must account for difficult real-world surfaces, including mirrors,
  glass, wet-look surfaces, and low light.

These constraints apply to later implementation and evaluation work. This
documentation milestone adds no models, inference, reconstruction, or
benchmark results.
