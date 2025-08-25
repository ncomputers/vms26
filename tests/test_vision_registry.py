import pytest

from app.vision import registry


def setup_function() -> None:
    registry.unload_all()


def test_get_caches_and_unloads(monkeypatch, tmp_path):
    path = tmp_path / "dummy.pt"
    path.write_text("x")
    monkeypatch.setenv("VMS21_YOLO_PERSON", str(path))

    class DummyModel:
        def __init__(self, p):
            self.p = p
            self.model = self
            self.to_calls = []
            self.half_calls = 0

        def to(self, dev):
            self.to_calls.append(dev)

        def half(self):
            self.half_calls += 1

    loads = []

    def fake_yolo(p):
        loads.append(p)
        return DummyModel(p)

    monkeypatch.setattr(registry, "YOLO", fake_yolo)
    monkeypatch.setattr(registry, "torch", None)

    m1 = registry.get("yolo_person", device="cpu", half=False)
    assert loads == [str(path)]
    m2 = registry.get("yolo_person", device="cpu", half=False)
    assert m1 is m2
    registry.unload_all()
    assert registry._CACHE == {}


def test_missing_file_raises(monkeypatch, tmp_path):
    missing = tmp_path / "missing.pt"
    monkeypatch.setenv("VMS21_YOLO_PERSON", str(missing))
    monkeypatch.setattr(registry, "YOLO", lambda p: None)
    monkeypatch.setattr(registry, "torch", None)
    with pytest.raises(RuntimeError):
        registry.get("yolo_person")
