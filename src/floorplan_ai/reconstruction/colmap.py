"""Isolated subprocess adapter for COLMAP's sparse reconstruction pipeline."""
from __future__ import annotations

import json
import sqlite3
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .models import *

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
_PAIR_BASE = 2147483647


def colmap_pose_to_canonical(qvec: Sequence[float], tvec: Sequence[float]) -> tuple[tuple[float, float, float, float], ...]:
    qw, qx, qy, qz = (float(x) for x in qvec)
    n = (qw * qw + qx * qx + qy * qy + qz * qz) ** 0.5
    if n == 0:
        raise ValueError("COLMAP quaternion must be non-zero")
    qw, qx, qy, qz = (x / n for x in (qw, qx, qy, qz))
    r = (
        (1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)),
        (2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)),
        (2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)),
    )
    rt = tuple(tuple(r[j][i] for j in range(3)) for i in range(3))
    t = tuple(float(x) for x in tvec)
    c = tuple(-sum(rt[i][j] * t[j] for j in range(3)) for i in range(3))
    return tuple(tuple(rt[i][j] if j < 3 else c[i] for j in range(4)) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),)


class ColmapBackend:
    def __init__(self, executable: str = "colmap", dense: bool = False):
        self.executable = executable
        self.dense = dense

    def _run(self, args: list[str], log: Path) -> None:
        result = subprocess.run(args, check=False, capture_output=True, text=True)
        log.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{' '.join(args[1:])} failed ({result.returncode}): {result.stderr.strip()}")

    @staticmethod
    def _is_initialization_failure(error: RuntimeError) -> bool:
        message = str(error).lower()
        return any(marker in message for marker in (
            "failed to create any sparse model",
            "no good initial image pair found",
            "discarding reconstruction due to bad initial pair",
            "discarding reconstruction due to no initial pair",
        ))

    @staticmethod
    def _clear_sparse_models(sparse: Path) -> None:
        sparse.mkdir(parents=True, exist_ok=True)
        for child in sparse.iterdir():
            if child.is_dir(): shutil.rmtree(child)
            else: child.unlink()

    @staticmethod
    def _stage_images(inputs: Sequence[Path], root: Path) -> tuple[Path, ...]:
        stage = root / "images"
        if stage.exists(): shutil.rmtree(stage)
        stage.mkdir(parents=True)
        staged = []
        for index, source in enumerate(inputs):
            if source.suffix.lower() not in _IMAGE_EXTENSIONS:
                continue
            target = stage / source.name
            if target.exists(): target = stage / f"{index:04d}_{source.name}"
            target.symlink_to(source.resolve())
            staged.append(target)
        if not staged:
            raise RuntimeError("No supported image files supplied to COLMAP")
        return tuple(staged)

    @staticmethod
    def _geometry_diagnostics(database: Path) -> dict:
        if not database.is_file(): return {}
        try:
            con = sqlite3.connect(database)
            cur = con.cursor()
            images = {r[0]: r[1] for r in cur.execute("SELECT image_id, name FROM images")}
            rows = []
            for pair_id, inliers, config in cur.execute("SELECT pair_id, rows, config FROM two_view_geometries WHERE rows > 0 ORDER BY rows DESC"):
                second = int(pair_id % _PAIR_BASE)
                first = int((pair_id - second) // _PAIR_BASE)
                rows.append({"image1": images.get(first, str(first)), "image2": images.get(second, str(second)), "inliers": int(inliers), "config": int(config)})
            con.close()
            calibrated = sum(item["config"] != 3 for item in rows)
            return {"verified_pair_count": len(rows), "calibrated_pair_count": calibrated, "verified_pairs": rows,
                    "sfm_readiness": "METRIC_SFM_READY" if calibrated >= 2 else "DEGENERATE_OR_UNCALIBRATED"}
        except sqlite3.Error as exc:
            return {"geometry_diagnostics_error": str(exc)}

    @staticmethod
    def _seed_pairs(database: Path, limit: int = 4) -> list[tuple[int, int, int]]:
        if not database.is_file(): return []
        con = sqlite3.connect(database); cur = con.cursor()
        pairs = []
        for pair_id, rows, config in cur.execute("SELECT pair_id, rows, config FROM two_view_geometries WHERE rows > 0 ORDER BY rows DESC"):
            second = int(pair_id % _PAIR_BASE); first = int((pair_id - second) // _PAIR_BASE)
            pairs.append((first, second, int(rows)))
            if len(pairs) >= limit: break
        con.close()
        return pairs

    def _run_mapper_with_retry(self, database: Path, image_path: Path, sparse: Path, logs: Path) -> tuple[Path, str]:
        base = [self.executable, "mapper", "--database_path", str(database), "--image_path", str(image_path), "--output_path", str(sparse)]
        attempts = [(None, "default")]
        attempts += [((a, b), f"seed_{a}_{b}") for a, b, _ in self._seed_pairs(database)]
        attempts.append((None, "relaxed_initialization"))
        last_error = None
        for seed, mode in attempts:
            self._clear_sparse_models(sparse)
            args = list(base)
            if seed is not None:
                args += ["--Mapper.init_image_id1", str(seed[0]), "--Mapper.init_image_id2", str(seed[1])]
            elif mode == "relaxed_initialization":
                args += ["--Mapper.init_min_num_inliers", "15", "--Mapper.init_min_tri_angle", "1.0", "--Mapper.init_max_error", "8.0"]
            try:
                self._run(args, logs / f"mapper_{mode}.log")
                models = sorted(p for p in sparse.iterdir() if p.is_dir())
                if models:
                    return models[0], mode
            except RuntimeError as exc:
                last_error = exc
                if not self._is_initialization_failure(exc): raise
        raise last_error or RuntimeError("mapper produced no sparse model")

    def reconstruct(self, inputs: Sequence[Path], output_dir: Path, *, camera_model: str = "SIMPLE_RADIAL", single_camera: bool = False, camera_priors: dict[str, dict] | None = None) -> ReconstructionResult:
        if shutil.which(self.executable) is None:
            return ReconstructionResult(success=False, backend_name="COLMAP", failure_reason="COLMAP executable not found. Install COLMAP and ensure `colmap` is on PATH.")
        if not inputs:
            return ReconstructionResult(success=False, backend_name="COLMAP", failure_reason="No input images supplied.")
        root = output_dir / "colmap"; sparse = root / "sparse"; logs = root / "logs"; dense = root / "dense"
        for path in (sparse, logs, dense): path.mkdir(parents=True, exist_ok=True)
        db = root / "database.db"
        try:
            staged = self._stage_images(inputs, root)
            args = [self.executable, "feature_extractor", "--database_path", str(db), "--image_path", str(root / "images"), "--ImageReader.camera_model", camera_model, "--ImageReader.single_camera", "1" if single_camera else "0"]
            focal_pixels = [p["focal_length_pixels"] for p in (camera_priors or {}).values() if p.get("focal_length_pixels")]
            if focal_pixels:
                width = next((p.get("width") for p in (camera_priors or {}).values() if p.get("width")), None)
                if width: args += ["--ImageReader.default_focal_length_factor", str(float(focal_pixels[0]) / float(width))]
            self._run(args, logs / "feature_extractor.log")
            self._run([self.executable, "exhaustive_matcher", "--database_path", str(db)], logs / "exhaustive_matcher.log")
            geometry = self._geometry_diagnostics(db); (logs / "geometry.json").write_text(json.dumps(geometry, indent=2, sort_keys=True), encoding="utf-8")
            model, init_mode = self._run_mapper_with_retry(db, root / "images", sparse, logs)
            if self.dense:
                self._run([self.executable, "image_undistorter", "--image_path", str(root / "images"), "--input_path", str(model), "--output_path", str(dense)], logs / "image_undistorter.log")
                self._run([self.executable, "patch_match_stereo", "--workspace_path", str(dense)], logs / "patch_match_stereo.log")
                self._run([self.executable, "stereo_fusion", "--workspace_path", str(dense), "--output_path", str(dense / "fused.ply")], logs / "stereo_fusion.log")
            self._run([self.executable, "model_converter", "--input_path", str(model), "--output_path", str(model / "text"), "--output_type", "TXT"], logs / "model_converter.log")
            parsed = self._parse(model / "text")
            return parsed.model_copy(update={"diagnostics": {**parsed.diagnostics, **geometry, "initialization_mode": init_mode, "workspace": str(root)}})
        except (OSError, RuntimeError) as exc:
            geometry = self._geometry_diagnostics(db)
            return ReconstructionResult(success=False, backend_name="COLMAP", failure_reason=str(exc), diagnostics={"workspace": str(root), **geometry})

    def _parse(self, path: Path) -> ReconstructionResult:
        cams=[]; poses=[]; images=[]; points=[]
        for line in (path / "cameras.txt").read_text().splitlines():
            if line.startswith("#") or not line: continue
            x=line.split(); cams.append(ReconstructionCamera(camera_id=int(x[0]), model=x[1], width=int(x[2]), height=int(x[3]), params=tuple(map(float,x[4:]))))
        lines=[x for x in (path / "images.txt").read_text().splitlines() if x and not x.startswith("#")]
        for line in lines[::2]:
            x=line.split(); pose=ReconstructionPose(image_id=int(x[0]),qvec=tuple(map(float,x[1:5])),tvec=tuple(map(float,x[5:8])),camera_id=int(x[8]),image_name=x[9]); poses.append(pose); images.append(ReconstructionImage(image_id=pose.image_id,name=pose.image_name,camera_id=pose.camera_id))
        for line in (path / "points3D.txt").read_text().splitlines():
            if line.startswith("#") or not line: continue
            x=line.split(); points.append(ReconstructionPoint(point_id=int(x[0]),xyz=tuple(map(float,x[1:4])),rgb=tuple(map(int,x[4:7])),error=float(x[7])))
        return ReconstructionResult(success=True,backend_name="COLMAP",camera_models=tuple(cams),poses=tuple(poses),points=tuple(points),images=tuple(images),diagnostics={"model_path":str(path)})
