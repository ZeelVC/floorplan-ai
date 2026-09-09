# Deliverables and Compliance Plan

This checklist plans the final Applied AI challenge artifacts. Statuses are
planning statuses only: no artifact is marked complete because a repository
scaffold exists.

## Final deliverables checklist

| Deliverable | Required content | Planned repository location | Status |
| --- | --- | --- | --- |
| 1. Compliance matrix | Requirement-by-requirement traceability from challenge source through implementation, evidence, and evaluation; explicit exceptions. | `DELIVERABLES.md` and future `reports/compliance-matrix.md` | Planned |
| 2. Capture route + device matrix | Supported capture routes, device requirements, supplied sensor data, output route, and scope exceptions. | Future `docs/capture-route-device-matrix.md` | Planned |
| 3. Repository + README | Reproducible source repository, setup/run instructions, disclosures, and links to evidence. | Repository root and `README.md` | Planned |
| 4. Reproduction bundle | Commands, configuration, dependency/model acquisition instructions, inputs, and regenerable outputs. | Future `reproduction/` | Not started |
| 5. Benchmark report | Protocol, evaluation-only ground truth handling, gate calculations, calibration, limitations, and measured results. | Future `reports/benchmark-report.md` | Not started |
| 6. Fix loop bundle | Worst-gate record, hypothesis, evidence, predicted and observed before/after results, regenerable runs, and readable diff. | Future `reports/fix-loop/` | Not started |
| 7. Technical report (maximum 6 pages) | Method, scope, evaluation, results, limitations, disclosures, and required challenge discussion. | Future `reports/technical-report.pdf` | Not started |
| 8. Raw benchmark data | Raw captures, raw available sensor data, laser/tape measurements, and submitted measurement records. | Future `benchmark/raw/` | Not started |

## Eventual compliance matrix

The eventual compliance matrix must use the following columns. Each row must
make the chain **requirement → implementation → evidence → evaluation**
auditable.

| Requirement | Challenge source | Active scope | Planned file/path | Artifact/evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Photos: 2–8 stills per room, iPhone 15 or newer, no depth/poses | Challenge capture tiers; `REQUIREMENTS.md` §1 | Photo pipeline | Future photo capture/pipeline documentation and code | Capture manifest, rendered plan, JSON, benchmark evaluation | Planned |
| Video: handheld walkthrough, iPhone 15 or newer | Challenge capture tiers; `REQUIREMENTS.md` §1 | Video pipeline | Future video capture/pipeline documentation and code | Capture manifest, rendered plan, JSON, benchmark evaluation | Planned |
| LiDAR: depth, poses, and intrinsics on Pro-class devices | Challenge capture tiers; `REQUIREMENTS.md` §1 | Out of scope | No implementation path | Scope record only; no implementation/evaluation evidence claimed | Out of scope — HR clarification |
| Per-room and stitched whole-property plan, adjacency, and no photo-room overlap | Challenge output/stitch gates; `REQUIREMENTS.md` §§2, 3, 5 | Photo and video spatial representation, reconstruction, stitching, adjacency | Future `src/floorplan_ai/`, `reports/benchmark-report.md` | JSON/rendered plans and stitch/adjacency evaluation | Planned |
| Walls, wall lengths, ceiling height, floor area, openings, and measurement confidence intervals | Challenge output/accuracy gates; `REQUIREMENTS.md` §§2, 5 | Photo/video reconstruction, measurements, calibration | Future `src/floorplan_ai/`, `reports/benchmark-report.md` | JSON/rendered plans, gate calculations, calibration evidence | Planned |
| Drift correction with documented method; raw poses not used as-is | Challenge drift gate; `REQUIREMENTS.md` §5 | Drift correction for implemented routes | Future implementation and `reports/technical-report.pdf` | Method description and before/after benchmark evidence | Planned |
| One command per capture; JSON output and rendered plan | Challenge output contract; `REQUIREMENTS.md` §2 | Photo/video CLI and outputs | Future CLI/output documentation and code | Command transcript, JSON, rendered plan | Planned |
| Damage assessment, damage-region classification, concealed damage, and damage-based scope line items | Challenge damage-related output expectations; `REQUIREMENTS.md` §2 | Out of scope | No implementation path | Scope record only; no implementation/evaluation evidence claimed | Out of scope — HR clarification |
| Consumer scanning-app comparison using LiDAR | Challenge consumer-app comparison; `REQUIREMENTS.md` §7 | Out of scope | No implementation path | Compliance exception; any photo/video comparison is only an additional experiment | Out of scope — HR clarification |
| Benchmark composition, raw-data submission, and laser/tape ground truth | Challenge benchmark requirements; `REQUIREMENTS.md` §4 | Evaluation/benchmark infrastructure (subject to available data) | Future `benchmark/`, `reports/benchmark-report.md` | Raw-data inventory, protocol, and evaluation records | Planned |
| Ground truth is evaluation-only and never used for inference geometry or scale | Challenge evaluation methodology; `REQUIREMENTS.md` §6 | Evaluation/benchmark infrastructure | Future evaluation documentation and tests | Input provenance and evaluation protocol | Planned |
| Fix-loop evidence and meaningful incremental Git history | Challenge fix loop/process evidence; `REQUIREMENTS.md` §§8–9 | Process and reporting | Future `reports/fix-loop/` and Git history | Regenerable before/after runs, readable diff, commits | Planned |
| Previously unseen-property walk-in test against laser measurements | Challenge walk-in test; `REQUIREMENTS.md` §10 | Photo/video routes only; no full three-tier claim | Future `reports/benchmark-report.md` | Walk-in capture/evaluation records for implemented routes | Planned |
| Consumer capture, disclosures, portable execution, retrievable large assets, and difficult-surface handling | Challenge constraints; `REQUIREMENTS.md` §11 | Photo/video implementation and reporting | Future `README.md`, `reproduction/`, technical report | Disclosure, reproduction instructions, and evaluation evidence | Planned |

## Reporting terminology

- **Requirement:** something specified by the challenge.
- **Active scope:** something this project is actually implementing.
- **Out of scope:** a challenge requirement explicitly excluded from this
  implementation.
- **Evaluation-only:** information used to evaluate the system but never
  supplied to inference.
- **Literature/research expectation:** a result reported by external research,
  not a benchmark result achieved by this project.
- **Measured result:** a result actually obtained from this project's
  benchmark.

Future reports must not present literature accuracy claims as measured project
results, and must not claim a gate has passed without the corresponding
evaluation evidence.
