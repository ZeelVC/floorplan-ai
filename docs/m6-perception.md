# M6 perception
`input → photo/video frontend → COLMAP → camera/pose/point cloud → plane extraction → scale evidence → CanonicalWorldModel`.

Install Python dependencies and COLMAP (the `colmap` executable, tested against modern COLMAP 3.x releases). Run `floorplan-ai perceive-photo --input photos --output output` or `floorplan-ai perceive-video --input walk.mp4 --output output`. Outputs include `canonical.json`, `diagnostics.json`, reconstruction camera/pose JSON, PLY points, correspondence evidence, and video frames/trajectory.

COLMAP failures produce a degraded canonical model containing captures and image observations but no fabricated poses or geometry. Monocular COLMAP scale is normally `UNKNOWN`: factor 1.0 is only an unscaled coordinate convention, not metric evidence. Plane candidates are evidence only; M6 does not infer final walls, rooms, openings, measurements, stitching, or drift correction.
