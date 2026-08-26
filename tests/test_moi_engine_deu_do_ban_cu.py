"""Mọi bộ máy nặng phải biết dò lại bản cài cũ nằm cạnh bên.

Lỗi thật, chủ dự án gặp ngay sau khi cài (26/08/2026): cài dịch ngoại tuyến
và tách giọng vào thư mục v3.10.2, rồi giải nén v3.10.4 cạnh bên và chạy —
app coi như CHƯA CÀI cả hai, lặng lẽ rơi về dịch tay.

Nguyên nhân: V77 dạy Whisper/Paraformer/VieNeu dò bản cũ, V81 làm cho FFmpeg,
V96 cho `.env` — nhưng `.venv-mt` (dịch ngoại tuyến) và `.venv-diar` (tách
giọng) thì chưa ai nối vào. Mỗi lần thêm engine mới là một lần phải nhớ, và
lần này quên. Nên test này canh CẢ LỚP thay vì hai cái vừa sửa: hàm nào trả
đường dẫn tới venv/model của một engine đều phải có đường lui `_ban_cu`.
"""
from __future__ import annotations

import ast
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Hàm đường dẫn engine → tên venv nó quản. Thêm engine mới thì thêm vào đây;
#: quên thì `test_khong_bo_sot_engine_nao` bắt được.
ENGINE = {
    "whisper_venv_python_path": ".venv-whisper",
    "whisper_model_dir_path": ".venv-whisper",
    "asr_venv_python_path": ".venv-asr",
    "vieneu_venv_python_path": ".venv-vieneu",
    "translate_local_venv_python_path": ".venv-mt",
    "translate_local_model_dir_path": ".venv-mt",
    "diarization_venv_python_path": ".venv-diar",
    "diarization_model_dir_path": ".venv-diar",
    "lipsync_venv_python_path": ".venv-lipsync",
    "lipsync_model_dir_path": ".venv-lipsync",
}

#: Engine không có `installed_ok.json` để đối chiếu nên dò bằng cách khác —
#: kèm lý do, và vẫn PHẢI có đường lui.
DO_KIEU_KHAC = {
    "ocr_venv_python_path": (
        "tim_venv_cu_bat_ky",
        "OCR không có bước tải model riêng (RapidOCR mang sẵn model trong gói "
        "pip) nên không có installed_ok.json để _ban_cu đối chiếu"),
}


@pytest.fixture(scope="module")
def cay():
    nguon = open(os.path.join(REPO, "autodub", "config.py"), encoding="utf-8").read()
    return nguon, ast.parse(nguon)


def _than(nguon, cay_ast, ten: str) -> str:
    for nut in ast.walk(cay_ast):
        if isinstance(nut, ast.FunctionDef) and nut.name == ten:
            return ast.get_source_segment(nguon, nut) or ""
    raise AssertionError(f"config.py không còn hàm {ten}")


@pytest.mark.parametrize("ten", sorted(ENGINE))
def test_moi_duong_dan_engine_deu_co_duong_lui(cay, ten):
    """Thiếu `_ban_cu` = nâng cấp xong engine "biến mất" mà không báo lỗi."""
    nguon, cay_ast = cay
    than = _than(nguon, cay_ast, ten)
    assert "_ban_cu(" in than, (
        f"{ten} chỉ tìm trong thư mục app — nâng cấp sang thư mục mới là "
        "engine coi như chưa cài, và app degrade im lặng")


def test_khong_bo_sot_engine_nao(cay):
    """Có venv nào trong config mà chưa nằm trong bảng trên không."""
    nguon, _c = cay
    import re

    thay = set(re.findall(r'"(\.venv-[a-z]+)"', nguon))
    da_canh = set(ENGINE.values())
    # `.venv-gpu` (Demucs) cố ý ngoài danh sách: `tim_venv_cu_bat_ky` lo phần
    # đó vì venv torch không có `installed_ok.json` để đối chiếu.
    thay.discard(".venv-gpu")
    thay.discard(".venv-ocr")     # có đường lui riêng, xem DO_KIEU_KHAC
    thieu = thay - da_canh
    assert not thieu, (
        f"venv chưa được canh — thêm vào bảng ENGINE hoặc nêu lý do: {thieu}")


def test_chay_that_dung_tinh_huong_nang_cap(tmp_path, monkeypatch):
    """Cài ở thư mục cũ, chạy ở thư mục mới nằm cạnh — phải nhận lại được."""
    from autodub import config as cfg
    from autodub import venv_discovery as vd

    cu, moi = tmp_path / "v-cu", tmp_path / "v-moi"
    moi.mkdir()
    for venv, model in ((".venv-mt", "translate-local"),
                        (".venv-diar", "diarization")):
        (cu / venv / "bin").mkdir(parents=True)
        (cu / venv / "bin" / "python").touch()
        (cu / venv / "Scripts").mkdir()
        (cu / venv / "Scripts" / "python.exe").touch()
        (cu / "models" / model).mkdir(parents=True)
        (cu / "models" / model / "installed_ok.json").write_text("{}")

    monkeypatch.setattr(cfg, "app_root", lambda: str(moi))
    monkeypatch.setattr(vd, "app_root", lambda: str(moi))
    vd.quen_cache()
    st = cfg.Settings()
    assert st.translate_local_configured(), "không nhận lại bộ dịch ngoại tuyến"
    assert st.diarization_configured(), "không nhận lại bộ tách giọng"
    vd.quen_cache()


@pytest.mark.parametrize("ten", sorted(DO_KIEU_KHAC))
def test_engine_khong_co_dau_van_phai_co_duong_lui(cay, ten):
    nguon, cay_ast = cay
    ham, ly_do = DO_KIEU_KHAC[ten]
    than = _than(nguon, cay_ast, ten)
    assert ham in than, f"{ten} không có đường lui nào ({ly_do})"
    assert len(ly_do) > 40, "lý do dùng cách dò khác phải viết ra"
