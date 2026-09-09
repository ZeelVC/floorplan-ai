# floorplan-ai

Local, offline-first **photo and video** reconstruction of a canonical, stitched property floorplan. The active scope is wall geometry, rooms, openings where supported by evidence, measurements with intervals, and JSON/SVG/DXF output. LiDAR and all damage analysis are intentionally out of scope.

## Use

```bash
pip install -e '.[dev]'
floorplan-ai fetch-models --check  # optional Depth Pro validation
floorplan-ai reconstruct --input ./capture --output ./result
floorplan-ai reconstruct --input ./walkthrough.mp4 --output ./result
floorplan-ai evaluate --prediction result/floorplan.json --ground-truth ground-truth.json --report-out result/report.json
```

Photo folders may contain room subdirectories; all images are routed through one canonical model and shared structural core. Video uses the existing COLMAP/video frontend and records its trajectory artifact. Runtime does not download model weights; Depth Pro is optional and must be installed and placed locally first (see `models/manifest.json`).

## Outputs

`floorplan.json` is the canonical model, while `floorplan.svg` and `floorplan.dxf` are deterministic renderings. `diagnostics.json`, `provenance.json`, and reconstruction artifacts make a run inspectable. Measurements have a 95% interval based on available geometric residual evidence.

## Limits

COLMAP and optional local model assets must be available for real media. Structural inference emits only geometrically closed rooms and does not invent openings from missing points. Challenge accuracy gates are targets, not claims of passing benchmark validation.
