"""Lớp ĐỌC nội dung chữ overlay — mini-spec H2a (docs/PLAN.md), đóng gap
audit H2 vừa tìm ra: `detect_text_regions()` (V5) chỉ trả VÙNG để làm mờ/
xoá, cố ý vứt nội dung chữ. `read_text_regions()` là đường mới, SONG SONG,
giữ lại chữ đã đọc được.

Guardrail 1 của H2a: KHÔNG được đổi hành vi `detect_text_regions()` cho
caller cũ (`style_dialog.py`) — test này canh RIÊNG bằng cách chạy lại toàn
bộ `test_text_regions.py` (không sửa gì ở đó) và thêm một khoá canh trực
tiếp "không có khoá text trong output cũ" ở cuối tệp này.

Guardrail 4: bốn trạng thái `co_chu`/`no_text`/`unavailable`/`failed`
không được trộn vào nhau — trọng tâm bộ test này.
"""
from __future__ import annotations

import tempfile
import os

import pytest
from PIL import Image

from autodub.media import text_regions as tr


def _anh_trong(ten: str = "x.png") -> str:
    p = os.path.join(tempfile.gettempdir(), ten)
    Image.new("RGB", (200, 100), (30, 30, 30)).save(p)
    return p


class _EngineGia:
    """Engine giả trả đúng khuôn RapidOCR: (box, text, confidence)."""

    def __init__(self, ket_qua):
        self._ket_qua = ket_qua

    def __call__(self, path):
        return (self._ket_qua, 0.1)


# --------------------------------------------------------- co_chu / ok ----

def test_doc_duoc_chu_giu_du_text_confidence_bbox_timestamp(monkeypatch):
    box = [[10, 20], [110, 20], [110, 40], [10, 40]]
    monkeypatch.setattr(tr, "_get_engine",
                        lambda: _EngineGia([(box, "FLASH SALE", 0.98)]))
    path = _anh_trong()

    ket = tr.read_text_regions([path], moc_thoi_gian=[3.5])

    assert ket.trang_thai == "co_chu"
    assert len(ket.quan_sat) == 1
    q = ket.quan_sat[0]
    assert q.text == "FLASH SALE"
    assert q.confidence == 0.98
    assert (q.x, q.y, q.w, q.h) != (0, 0, 0, 0)
    assert q.timestamp_s == 3.5
    assert q.frame_index == 0
    assert q.status == "ok"


def test_khong_gan_moc_thoi_gian_thi_timestamp_la_none(monkeypatch):
    box = [[0, 0], [10, 0], [10, 10], [0, 10]]
    monkeypatch.setattr(tr, "_get_engine",
                        lambda: _EngineGia([(box, "hi", 0.99)]))
    ket = tr.read_text_regions([_anh_trong()])
    assert ket.quan_sat[0].timestamp_s is None


def test_khong_gop_quan_sat_qua_nhieu_khung(monkeypatch):
    """Scope A của H2a: trả RAW observations, không bịa thuật toán gộp nội
    dung — hai khung có chữ trùng vị trí vẫn phải ra HAI quan sát riêng."""
    box = [[0, 0], [50, 0], [50, 20], [0, 20]]
    monkeypatch.setattr(tr, "_get_engine",
                        lambda: _EngineGia([(box, "SUBSCRIBE", 0.95)]))
    ket = tr.read_text_regions(
        [_anh_trong("a.png"), _anh_trong("b.png")], moc_thoi_gian=[0.0, 5.0])
    assert len(ket.quan_sat) == 2, "hai khung phải ra hai quan sát, không gộp"
    assert {q.timestamp_s for q in ket.quan_sat} == {0.0, 5.0}


# --------------------------------------------------------------- no_text --

def test_anh_sach_chu_ra_no_text_khong_phai_loi(monkeypatch):
    monkeypatch.setattr(tr, "_get_engine", lambda: _EngineGia([]))
    ket = tr.read_text_regions([_anh_trong()])
    assert ket.trang_thai == "no_text"
    assert ket.quan_sat == []


def test_danh_sach_rong_ra_no_text_khong_goi_engine():
    ket = tr.read_text_regions([])
    assert ket.trang_thai == "no_text"


# ------------------------------------------------------------ unconfirmed -

def test_confidence_thap_thi_status_unconfirmed(monkeypatch):
    box = [[0, 0], [10, 0], [10, 10], [0, 10]]
    monkeypatch.setattr(
        tr, "_get_engine",
        lambda: _EngineGia([(box, "chu mo", tr.NGUONG_TIN_CAY_DOC - 0.1)]))
    ket = tr.read_text_regions([_anh_trong()])
    assert ket.trang_thai == "co_chu", "vẫn có quan sát, chỉ là không chắc"
    assert ket.quan_sat[0].status == "unconfirmed"


def test_confidence_dat_nguong_thi_status_ok(monkeypatch):
    box = [[0, 0], [10, 0], [10, 10], [0, 10]]
    monkeypatch.setattr(
        tr, "_get_engine",
        lambda: _EngineGia([(box, "chu ro", tr.NGUONG_TIN_CAY_DOC)]))
    ket = tr.read_text_regions([_anh_trong()])
    assert ket.quan_sat[0].status == "ok"


# -------------------------------------------------------------- unavailable

def test_chua_cai_ocr_nem_ChuaCaiOcr_khong_phai_no_text(monkeypatch):
    """Guardrail 4: KHÔNG được gộp 'unavailable' thành 'no_text' — nếu ai
    lỡ đổi thành `return KetQuaDocChu(trang_thai="no_text")` khi thiếu
    engine, test này phải đỏ."""
    monkeypatch.setattr(
        tr, "_get_engine",
        lambda: (_ for _ in ()).throw(ImportError("no rapidocr")))

    with pytest.raises(tr.ChuaCaiOcr):
        tr.read_text_regions([_anh_trong()])


# ------------------------------------------------------------------ failed

def test_toan_bo_khung_loi_nem_DocChuThatBai(monkeypatch):
    """Guardrail 4: 'failed' (OCR gọi lỗi) khác 'no_text' (đã chạy, sạch
    chữ) — nếu ai lỡ nuốt lỗi rồi trả no_text, test này phải đỏ."""

    class _EngineLoi:
        def __call__(self, path):
            raise RuntimeError("engine crash")

    monkeypatch.setattr(tr, "_get_engine", lambda: _EngineLoi())

    with pytest.raises(tr.DocChuThatBai):
        tr.read_text_regions([_anh_trong()])


def test_mot_khung_loi_mot_khung_ok_thi_KHONG_phai_failed(monkeypatch):
    """Chỉ 'failed' khi TẤT CẢ khung đều lỗi — một khung lỗi giữa nhiều
    khung ổn vẫn phải trả về quan sát của khung ổn, không ném lỗi oan."""
    goi = {"n": 0}
    box = [[0, 0], [10, 0], [10, 10], [0, 10]]

    class _EngineNuaLoi:
        def __call__(self, path):
            goi["n"] += 1
            if goi["n"] == 1:
                raise RuntimeError("crash frame 1")
            return ([(box, "ok", 0.95)], 0.1)

    monkeypatch.setattr(tr, "_get_engine", lambda: _EngineNuaLoi())
    ket = tr.read_text_regions([_anh_trong("a.png"), _anh_trong("b.png")])
    assert ket.trang_thai == "co_chu"
    assert len(ket.quan_sat) == 1


# ----------------------------------------------- regression: contract cũ --

def test_detect_text_regions_KHONG_co_khoa_text(monkeypatch):
    """Guardrail 1 của H2a: `detect_text_regions()` (đường xoá/làm mờ chữ
    cũ) không được thêm khoá `text` — nếu ai lỡ đổi mặc định `doc_chu`
    thành True ở lời gọi nội bộ, test này phải đỏ."""
    box = [[0, 0], [10, 0], [10, 10], [0, 10]]
    monkeypatch.setattr(tr, "_get_engine",
                        lambda: _EngineGia([(box, "SUBSCRIBE", 0.99)]))
    regions = tr.detect_text_regions([_anh_trong()])
    assert regions, "phải phát hiện được vùng"
    assert all("text" not in r for r in regions), (
        "detect_text_regions() không được lộ nội dung chữ — đó là việc của "
        "read_text_regions()")
