"""Mini-spec V28 (docs/PLAN.md, Phase G) — style VieNeu PER-SEGMENT (khác
style cố định 1 lần/lượt chạy trước V28).

Worker giả THẬT (script Python nhỏ, đúng giao thức JSON của
vieneu_worker.py thật — ready handshake + serve loop) — không mock
`Popen`, cùng cách đã làm cho các worker khác trong V24/V26.
"""
from __future__ import annotations

import json
import sys
import textwrap

from autodub.config import Settings
from autodub.speech.tts import vieneu_vi


def _fake_worker(tmp_path) -> str:
    """Worker giả: nạp xong in "ready", rồi với mỗi request GHI LẠI style
    nhận được vào file "<out>.received_style.json" (để test đọc lại — style
    không có trong response JSON thật nên phải quan sát qua kênh khác)."""
    path = tmp_path / "fake_vieneu_worker.py"
    path.write_text(textwrap.dedent("""
        import json, sys
        print(json.dumps({"ready": True}), flush=True)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            with open(req["out"] + ".received_style.json", "w") as f:
                json.dump({"style": req.get("style")}, f)
            open(req["out"], "wb").close()
            print(json.dumps({"ok": True, "duration": 1.23}), flush=True)
    """), encoding="utf-8")
    return str(path)


def _synth(monkeypatch, tmp_path):
    worker = _fake_worker(tmp_path)
    monkeypatch.setattr(vieneu_vi, "_WORKER_SCRIPT", worker)
    settings = Settings()
    monkeypatch.setattr(settings, "vieneu_venv_python_path", lambda: sys.executable)
    monkeypatch.setattr(settings, "vieneu_model_dir_path", lambda: "/tmp/fake-model")
    # Bộ test này đo chuyện truyền phong cách đọc, không đo chuyện cài đặt.
    # `_start()` nay chặn sớm khi chưa cài (22/8/2026) nên phải nói rõ là đã
    # cài, thay vì để chốt đó chặn nhầm.
    monkeypatch.setattr(settings, "vieneu_configured", lambda: True)
    synth = vieneu_vi.VieNeuSynthesizer(settings, "Minh Trang", num_workers=1)
    return synth


def _received_style(output_path: str) -> str | None:
    with open(output_path + ".received_style.json", encoding="utf-8") as f:
        return json.load(f)["style"]


def test_style_none_by_default_worker_uses_its_own_default(monkeypatch, tmp_path):
    """Không truyền style -> request KHÔNG có field "style" (0 regression —
    worker tự dùng style khởi động của nó, đúng hành vi trước V28)."""
    synth = _synth(monkeypatch, tmp_path)
    out = str(tmp_path / "seg1.wav")
    synth.synthesize("Xin chào các bạn hôm nay.", out)
    assert _received_style(out) is None
    synth.close()


def test_explicit_style_is_sent_to_worker(monkeypatch, tmp_path):
    synth = _synth(monkeypatch, tmp_path)
    out = str(tmp_path / "seg2.wav")
    synth.synthesize("Tuyệt vời quá đi!", out, style="doc_truyen")
    assert _received_style(out) == "doc_truyen"
    synth.close()


def test_different_segments_can_use_different_styles(monkeypatch, tmp_path):
    """2 câu liên tiếp, style KHÁC NHAU -> mỗi request mang đúng style của
    riêng nó (không bị worker "nhớ" style của câu trước)."""
    synth = _synth(monkeypatch, tmp_path)
    out1 = str(tmp_path / "seg1.wav")
    out2 = str(tmp_path / "seg2.wav")
    synth.synthesize("Câu bình thường.", out1, style="tu_nhien")
    synth.synthesize("Cảnh báo nguy hiểm!", out2, style="tin_tuc")
    assert _received_style(out1) == "tu_nhien"
    assert _received_style(out2) == "tin_tuc"
    synth.close()
