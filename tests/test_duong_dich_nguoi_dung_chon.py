"""D1 — người dùng CHỌN đường dịch, không để hoàn cảnh chọn hộ.

Bug thật đang ảnh hưởng người dùng: `translate_local` (NLLB trên máy, không
mất phí dịch) chỉ chạy khi `is_configured()` sai. Từ 22/8/2026 địa chỉ máy chủ
được nhúng thẳng vào `.exe` để sửa lỗi "bản offline câm" — hệ quả phụ không cố
ý: `is_configured()` LUÔN đúng trên mọi bản phát hành, nên nhánh ngoại tuyến
không bao giờ được chọn nữa dù ô cài đặt vẫn hiện.

Cách sửa là thêm cờ tường minh `translate_mode` Ở TRÊN, KHÔNG đụng vào bản vá
nhúng địa chỉ (đó là bản sửa đã chốt cho một lỗi khác).

Bộ test giữ bốn điều, mỗi điều là một cách bug có thể quay lại:

1. Chọn ngoại tuyến thì luôn ngoại tuyến — kể cả khi `is_configured()` đúng.
2. Chọn ngoại tuyến mà chưa cài thì BÁO LỖI, tuyệt đối không quay về máy chủ
   (quay về là trừ tiền cho việc người dùng vừa từ chối).
3. "auto" mất mạng thì rơi về ngoại tuyến, có ghi lý do.
4. Chọn ngoại tuyến thì KHÔNG giữ chỗ tiền dịch — máy chủ trừ đúng số ước
   tính lúc giữ chỗ và không hoàn phần chưa dùng.
"""
from __future__ import annotations

import ast
import logging
import re

import pytest

from autodub.config import Settings


class _KhongDuocGoi(AssertionError):
    """Ném ra nếu mã chạm vào máy chủ trong lúc lẽ ra phải chạy ngoại tuyến."""


@pytest.fixture
def dat_may_chu(monkeypatch):
    """Giả lập đúng tình huống của bản phát hành: LUÔN có máy chủ."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: (_ for _ in ()).throw(_KhongDuocGoi(
                            "đã gọi máy chủ trong khi người dùng chọn ngoại tuyến")))


def _pipeline(che_do: str, monkeypatch):
    from autodub.pipeline import DubPipeline

    st = Settings()
    monkeypatch.setattr(st, "translate_mode", che_do, raising=False)
    monkeypatch.setattr(st, "translate_enabled", True, raising=False)
    return DubPipeline(st)


def _segments():
    return [{"id": 0, "start": 0.0, "end": 1.0, "text": "你好"}]


# --- 1 + 2: chọn ngoại tuyến -------------------------------------------

def test_chon_ngoai_tuyen_thi_khong_goi_may_chu(dat_may_chu, monkeypatch):
    """Điều kiện đúng của bug: `is_configured()` trả True mà vẫn phải đi
    đường ngoại tuyến."""
    goi = {}
    monkeypatch.setattr("autodub.text.translate_local.is_available",
                        lambda s, lang: True)
    monkeypatch.setattr("autodub.text.translate_local.translate_segments_local",
                        lambda segs, *a, **k: goi.setdefault("chay", True) or segs)

    from autodub.languages import get_target
    ra = _pipeline("offline", monkeypatch)._auto_translate(
        _segments(), get_target("vi"), "zh-CN")
    assert goi.get("chay"), "không hề chạy đường ngoại tuyến"
    assert ra is not None


def test_ngoai_tuyen_chua_cai_thi_bao_loi_chu_khong_ve_may_chu(
        dat_may_chu, monkeypatch, caplog):
    """Rơi ngầm sang đường tốn tiền khi người dùng vừa chọn đường không mất
    phí là đúng kiểu sai đã có tên trong dự án (lớp lỗi #5)."""
    monkeypatch.setattr("autodub.text.translate_local.is_available",
                        lambda s, lang: False)
    from autodub.languages import get_target
    with caplog.at_level(logging.ERROR):
        ra = _pipeline("offline", monkeypatch)._auto_translate(
            _segments(), get_target("vi"), "zh-CN")
    assert ra is None, "phải chuyển sang dịch tay, không phải gọi máy chủ"
    assert any("ngoại tuyến" in r.message for r in caplog.records), \
        "không nói cho người dùng biết vì sao dừng"


def test_ngoai_tuyen_loi_giua_chung_van_khong_ve_may_chu(
        dat_may_chu, monkeypatch):
    from autodub.text.translate_local import LocalTranslateError

    monkeypatch.setattr("autodub.text.translate_local.is_available",
                        lambda s, lang: True)

    def _no(*a, **k):
        raise LocalTranslateError("model hỏng")
    monkeypatch.setattr("autodub.text.translate_local.translate_segments_local", _no)

    from autodub.languages import get_target
    ra = _pipeline("offline", monkeypatch)._auto_translate(
        _segments(), get_target("vi"), "zh-CN")
    assert ra is None      # nếu quay về máy chủ thì fixture đã ném _KhongDuocGoi


# --- 3: chế độ auto ------------------------------------------------------

def test_auto_mat_mang_thi_roi_ve_ngoai_tuyen_va_noi_ly_do():
    """Đọc mã: chạy thật nhánh này cần cả máy chủ lẫn NLLB."""
    nguon = open("autodub/pipeline.py", encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_auto_translate":
            than = ast.get_source_segment(nguon, nut) or ""
            break
    else:
        raise AssertionError("không còn _auto_translate")

    i = than.index("except OfflineError")
    sau = than[i:]
    assert 'che_do == "auto"' in sau, "mất mạng không hề xét chế độ auto"
    assert "translate_segments_local" in sau, "auto không có đường lui ngoại tuyến"
    assert "logger.warning" in sau, "rơi nhánh mà không ghi lý do (lớp lỗi #1)"
    # Chế độ server PHẢI vẫn dừng hẳn — không được im lặng đổi chất lượng dịch.
    assert "raise" in sau, "chế độ server không còn dừng khi mất mạng"


# --- 4: tiền -------------------------------------------------------------

def test_chon_ngoai_tuyen_thi_khong_giu_cho_tien_dich():
    """Máy chủ trừ đúng số ước tính lúc giữ chỗ và KHÔNG hoàn phần chưa dùng
    (hold.service.js: `chargedVox: hold.estimatedVox`). Kê phần dịch vào hold
    trong khi máy người dùng tự dịch = bắt trả cho việc không hề chạy."""
    nguon = open("autodub/pipeline.py", encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_run_impl":
            than = ast.get_source_segment(nguon, nut) or ""
            break
    else:
        raise AssertionError("không còn _run_impl")

    assert "dich_ngoai_tuyen" in than, "phần tính tiền không biết gì về chế độ dịch"
    assert "khong_tinh_phi_dich" in than
    assert than.count("khong_can_dich=khong_tinh_phi_dich") == 2, (
        "cờ ngoại tuyến phải đi vào CẢ cổng xem trước giá lẫn lúc giữ chỗ — "
        "thiếu một chỗ là báo một giá, trừ một giá khác")


def test_auto_van_giu_cho_du_tien():
    """"auto" vẫn ưu tiên máy chủ nên vẫn phải giữ chỗ đủ — bớt đi rồi mới
    gọi máy chủ là chặn nhầm người đủ tiền."""
    nguon = open("autodub/pipeline.py", encoding="utf-8").read()
    assert 'translate_mode", "server")\n                            == "offline")' in nguon \
        or '== "offline"' in nguon, "cờ miễn phí dịch không giới hạn ở đúng chế độ offline"


# --- Chống tái phát ------------------------------------------------------

def test_khong_con_suy_luan_duong_ngoai_tuyen_tu_hoan_canh():
    """Nếu ai đó sau này bỏ `translate_mode` và quay lại suy từ
    `is_configured()`, test này phải đỏ ngay — đó chính là lỗi gốc."""
    assert "translate_mode" in Settings.__dataclass_fields__, \
        "mất cờ tường minh — đường ngoại tuyến lại phụ thuộc hoàn cảnh"
    nguon = open("autodub/pipeline.py", encoding="utf-8").read()
    i = nguon.index("def _auto_translate")
    than = nguon[i:i + 4000]
    assert than.index('che_do == "offline"') < than.index("if not is_configured():"), \
        "phép hỏi is_configured() lại đứng trước lựa chọn của người dùng"


def test_khong_dao_lai_ban_va_nhung_dia_chi_may_chu():
    """Guardrail của chính mini-spec này: bản vá 22/8 phải còn nguyên."""
    nguon = open("autodub/saas_client.py", encoding="utf-8").read()
    assert "from autodub_gui._embedded import VOXDUB_API_URL" in nguon
    assert "def is_configured" in nguon


def test_nhan_ba_lua_chon_khong_hua_mien_phi():
    """Chạy ngoại tuyến chỉ bỏ phí DỊCH (2 Vox/dòng); giá nền 10 Vox/dòng vẫn
    tính. Nhãn là thứ người dùng đọc lúc bấm chọn, nên nó không được hứa
    "miễn phí" — tái tạo đúng lớp lỗi #5 mà chính mục này chống.

    Chỉ soi NHÃN của ba lựa chọn, không soi câu giải thích: câu giải thích có
    quyền (và cần) nói "KHÔNG miễn phí cả lượt", cấm cả chữ ở đó thì bộ canh
    tự chặn đúng câu nói thật.
    """
    nguon = open("autodub_gui/pages/settings_fields.py", encoding="utf-8").read()
    i = nguon.index('Field("TRANSLATE_MODE"')
    khoi = nguon[i:nguon.index("]),", i)]
    nhan = re.findall(r'\("([^"]*)",\s*"(?:server|offline|auto)"\)', khoi)
    assert len(nhan) == 3, f"không đọc được đủ 3 nhãn: {nhan}"
    for x in nhan:
        assert "miễn phí" not in x.lower(), f"nhãn hứa miễn phí: {x!r}"
    assert any("không phí dịch" in x.lower() for x in nhan), \
        "không nhãn nào nói rõ thứ thật sự tiết kiệm được là PHÍ DỊCH"


def test_cau_giai_thich_noi_ro_gia_nen_van_tinh():
    nguon = open("autodub_gui/pages/settings_fields.py", encoding="utf-8").read()
    i = nguon.index('Field("TRANSLATE_MODE"')
    khoi = nguon[i:nguon.index("]),", i)]
    assert "giá nền" in khoi, "không nói giá nền vẫn bị tính"
    assert "bỏ sót câu" in khoi, "không cảnh báo chất lượng (FEATURES.md §5.2)"
