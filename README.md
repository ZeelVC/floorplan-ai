# floorplan-ai

`floorplan-ai` is an incremental Applied AI engineering project for reconstructing
indoor, metric floor plans from property captures. Its intended outputs include
per-room and whole-property plans, geometry, openings, measurements with
confidence intervals, structured JSON, and rendered plans.

## Current scope

This project currently accepts **PHOTO** and **VIDEO** capture tiers as future
inputs. They will be developed as independent perception pipelines that converge
on one canonical spatial representation. LiDAR, damage detection, and damage
assessment are explicitly out of scope.

Physical laser or tape measurements are ground truth for evaluation only. They
must never be used as inference input in the production pipeline.

The benchmark currently comprises one three-room property with distinct
horizontal-phone and vertical-phone capture trials, 24 still photographs in
total, and one walkthrough video per trial. This repository makes no accuracy
or benchmark-result claims at this milestone.

## High-level architecture

```text
capture -> preprocessing -> reconstruction/{photo,video} -> depth
        -> geometry -> rooms/openings -> stitching -> measurements
        -> calibration -> rendering/evaluation -> pipeline
```

The photo and video branches will remain independently testable until they
converge at the canonical spatial representation.

## Development philosophy

Build the system in small, reviewable milestones. Keep experimental captures
separate, evaluate against held-out ground truth, record uncertainty rather than
false precision, and avoid adding models or heavyweight dependencies before they
are needed.

## Current milestone

Repository initialization only: package layout, packaging metadata, a minimal
CLI, and import/CLI smoke tests. No reconstruction, depth estimation, room or
opening detection, stitching, or AI models are implemented.

## Create an environment

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## Install the project

Install in editable/development mode:

```bash
python -m pip install -e .
```

For test tooling, install the development extra:

```bash
python -m pip install -e '.[dev]'
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Run the CLI

```bash
floorplan-ai --help
# or
python -m floorplan_ai --help
```
