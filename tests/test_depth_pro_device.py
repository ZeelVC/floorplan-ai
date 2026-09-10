from pathlib import Path
from types import SimpleNamespace

from floorplan_ai.depth.depth_pro import DepthProEstimator


def _estimator(tmp_path, device="auto"):
    checkpoint = tmp_path / "depth_pro.pt"
    checkpoint.write_bytes(b"test")
    return DepthProEstimator(checkpoint, device=device)


def test_auto_depth_device_prefers_mps(tmp_path, monkeypatch):
    import floorplan_ai.depth.depth_pro as depth_pro

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
    )
    monkeypatch.setattr(depth_pro.importlib, "import_module", lambda name: fake_torch if name == "torch" else None)

    assert _estimator(tmp_path)._resolve_device() == "mps"


def test_auto_depth_device_falls_back_to_cpu(tmp_path, monkeypatch):
    import floorplan_ai.depth.depth_pro as depth_pro

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
    )
    monkeypatch.setattr(depth_pro.importlib, "import_module", lambda name: fake_torch if name == "torch" else None)

    assert _estimator(tmp_path)._resolve_device() == "cpu"


def test_explicit_depth_device_is_preserved(tmp_path):
    assert _estimator(tmp_path, device="cpu")._resolve_device() == "cpu"


def test_native_loader_overrides_depth_pro_cwd_checkpoint(tmp_path, monkeypatch):
    import floorplan_ai.depth.depth_pro as adapter

    checkpoint = tmp_path / "depth_pro.pt"
    checkpoint.write_bytes(b"test")
    estimator = DepthProEstimator(checkpoint, device="cpu")
    calls = {}

    class FakeModel:
        def eval(self):
            calls["eval"] = True

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
        device=lambda name: (calls.__setitem__("device", name) or name),
        float32="float32",
    )
    fake_config = SimpleNamespace(checkpoint_uri="./checkpoints/depth_pro.pt")
    fake_depth_module = SimpleNamespace(DEFAULT_MONODEPTH_CONFIG_DICT=fake_config)
    fake_module = SimpleNamespace(
        create_model_and_transforms=lambda **kwargs: (
            calls.update(kwargs) or FakeModel(),
            lambda image: image,
        )
    )

    def fake_import(name):
        if name == "torch":
            return fake_torch
        if name == "depth_pro":
            return fake_module
        if name == "depth_pro.depth_pro":
            return fake_depth_module
        raise ImportError(name)

    monkeypatch.setattr(adapter.importlib, "import_module", fake_import)
    estimator._load()

    assert calls["device"] == "cpu"
    assert calls["precision"] == "float32"
    assert calls["config"].checkpoint_uri == str(Path(checkpoint))
    assert calls["eval"] is True
