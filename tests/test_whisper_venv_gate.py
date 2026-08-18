"""V74 — 3 lỗi quanh việc "máy đã cài Whisper hay chưa".

Người dùng báo trên bản `.exe` v3.4.0/v3.4.1 (2026-08-19): mở app là hiện
"Máy chưa đủ điều kiện lồng tiếng — Thiếu thư viện faster-whisper" dù đã cài
xong, và chép lời thì hỏng với `No module named 'av'`.

Gốc rễ chung: `autodub.spec` CỐ Ý loại `faster_whisper`/`ctranslate2`/`av`
khỏi bundle (Whisper chạy trong `.venv-whisper` qua `asr_whisper_worker.py`,
cắt ~112 MB), nhưng hai chỗ khác vẫn giả định import được chúng trong tiến
trình chính. Đúng lớp lỗi đã sửa ở `_smoke_report` (V38) — lần đó chưa rà hết.
"""
from __future__ import annotations

import sys

import pytest

from autodub.config import Settings


@pytest.fixture()
def st(tmp_path, monkeypatch):
    """Settings trỏ vào một thư mục ứng dụng rỗng (chưa cài venv nào)."""
    s = Settings()
    s.whisper_venv_python = str(tmp_path / "khong-co" / "python.exe")
    s.whisper_model_dir = str(tmp_path / "models")
    return s


def _cai_venv(st, tmp_path):
    """Giả lập một máy ĐÃ cài Whisper đúng cách."""
    py = tmp_path / "venv" / "python.exe"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    md = tmp_path / "models"
    md.mkdir(exist_ok=True)
    (md / "installed_ok.json").write_text("{}")
    st.whisper_venv_python = str(py)
    st.whisper_model_dir = str(md)


# -- 1. Preflight phải kiểm .venv-whisper, không phải import in-process -------

def test_da_cai_venv_thi_preflight_BAO_OK(st, tmp_path, monkeypatch):
    """Lỗi người dùng báo: đã cài xong mà mở app vẫn bị chặn.

    Trong bản `.exe`, `import faster_whisper` KHÔNG BAO GIỜ thành công (bị
    loại khỏi bundle), nên kiểm bằng nó là chặn nhầm 100% người dùng bản
    đóng gói — kể cả người đã cài đúng và chạy tốt."""
    from autodub import preflight

    _cai_venv(st, tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    r = preflight._check_asr(st)
    assert r.level == "ok", f"đã cài venv mà vẫn báo {r.level}: {r.message}"


def test_chua_cai_venv_o_ban_dong_goi_thi_chi_dung_cach_cai(st, monkeypatch):
    """Chưa cài thì vẫn phải chặn — nhưng bằng câu người dùng làm theo được,
    không phải "chạy pip install -r requirements.txt" (bản .exe không có
    requirements.txt, cũng chẳng có Python nào để chạy pip)."""
    from autodub import preflight

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    r = preflight._check_asr(st)
    assert r.level == "fail"
    assert "Cai dat Whisper ASR.bat" in r.advice
    assert "pip install" not in r.advice
    # Cạm bẫy nâng cấp: venv nằm trong thư mục ứng dụng nên bản mới mất sạch.
    assert "phiên bản mới" in r.advice


def test_ban_ma_nguon_van_kiem_import_nhu_cu(st, monkeypatch):
    """Chạy từ mã nguồn thì in-process là đường hợp lệ — không được đòi venv."""
    from autodub import preflight

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    r = preflight._check_asr(st)
    # Máy CI không cài faster-whisper → fail, nhưng phải là lời khuyên dành
    # cho người phát triển, không phải lời khuyên bấm .bat.
    if r.level == "fail":
        assert "Cai dat Whisper ASR.bat" not in r.advice


# -- 2. Bản .exe không được rơi sang in-process (đường đó không tồn tại) ------

def test_ban_dong_goi_chua_cai_venv_bao_loi_ro_rang(st, monkeypatch):
    """Trước: rơi sang in-process → `import faster_whisper` → `No module
    named 'av'`. Người dùng không thể suy ra phải làm gì từ câu đó."""
    from autodub.speech import transcriber as tr

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    goi = {}
    monkeypatch.setattr(tr, "_transcribe_whisper",
                        lambda *a, **k: goi.setdefault("da_goi", True))

    with pytest.raises(RuntimeError) as e:
        tr.transcribe("/tmp/a.wav", "en", st)

    assert not goi, "bản .exe không được gọi đường in-process"
    assert "Cai dat Whisper ASR.bat" in str(e.value)


def test_ban_dong_goi_loi_subprocess_giu_nguyen_ly_do(st, tmp_path, monkeypatch):
    """Subprocess hỏng thì báo đúng lý do đó, đừng đổi nó thành một lỗi
    import vô nghĩa bằng cách rơi sang đường không tồn tại."""
    from autodub.speech import transcriber as tr

    _cai_venv(st, tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(tr, "_transcribe_whisper_subprocess",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("worker chết: hết RAM")))
    monkeypatch.setattr(tr, "_transcribe_whisper",
                        lambda *a, **k: pytest.fail("không được rơi in-process"))

    with pytest.raises(RuntimeError, match="hết RAM"):
        tr.transcribe("/tmp/a.wav", "en", st)


# -- 3. Bấm Dừng không được biến thành "chạy lại bằng đường khác" -------------

def test_bam_dung_khong_bi_nuot_thanh_chay_lai(st, tmp_path, monkeypatch):
    """`TranscribeCancelled` kế thừa `RuntimeError` nên `except Exception`
    nuốt gọn nó, rồi chạy LẠI TOÀN BỘ ở in-process — bấm Dừng xong máy vẫn
    cày tiếp, chỉ khác là đổi đường.

    V72 tuyên bố "nút Dừng thật sự dừng" nhưng không bắt được ca này: máy
    thử nghiệm không có `.venv-whisper` nên chưa bao giờ đi vào nhánh
    subprocess."""
    from autodub.speech import transcriber as tr

    _cai_venv(st, tmp_path)
    monkeypatch.setattr(sys, "frozen", False, raising=False)   # cả bản nguồn
    monkeypatch.setattr(tr, "_transcribe_whisper_subprocess",
                        lambda *a, **k: (_ for _ in ()).throw(
                            tr.TranscribeCancelled("Đã dừng theo yêu cầu.")))
    monkeypatch.setattr(tr, "_transcribe_whisper",
                        lambda *a, **k: pytest.fail(
                            "bấm Dừng mà vẫn chạy lại ở in-process"))

    with pytest.raises(tr.TranscribeCancelled):
        tr.transcribe("/tmp/a.wav", "en", st)
