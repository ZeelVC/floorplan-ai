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
