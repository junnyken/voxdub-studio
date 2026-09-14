"""E6 câu C.4 — vì sao lượt thật 12/09 thiếu `khoi_dong_s`/`quet_s`.

Bằng chứng dẫn tới nguyên nhân (14/09/2026), đọc từ chính tệp chẩn đoán thật:

    "thoi_gian": {"ocr_cuc_bo_s": 176.53, "duong": "subprocess", "so_khung": 104}

`duong` và `so_khung` nằm CÙNG MỘT khối dict với hai khoá còn thiếu, và vào
cùng một commit (v3.17.14). Chúng có mặt ⇒ mã phía cha đã là bản mới ⇒ thứ
không trả về hai khoá kia là **tệp worker**: bản thật sự chạy là bản CŨ.

Đây là lớp lỗi đã có tên trong dự án — "cha đời mới, worker đời cũ" (C53) —
chỉ khác là lần này nó im lặng: không ai khai đời, không ai ghi lại đã chạy
tệp nào. Bộ test này chốt việc nó không được im lặng nữa.
"""
import json
import pathlib
import subprocess
import sys
import types

import pytest

from autodub.media import text_regions as tr


class _CaiDat:
    """Đủ dùng cho `_detect_via_subprocess` — không đụng máy thật."""

    def ocr_configured(self):
        return True

    def ocr_venv_python_path(self):
        return sys.executable


def _gia_worker(monkeypatch, data: dict):
    """Giả worker trả về đúng JSON `data`, không chạy OCR thật."""
    def _run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 0, json.dumps(data, ensure_ascii=False), "")
    monkeypatch.setattr(subprocess, "run", _run)


# --- Worker phải TỰ KHAI đời -------------------------------------------------

def test_worker_khai_phien_ban_trong_json():
    """Không khai đời thì cha không bao giờ phân biệt được hai ca:
    "worker cũ" và "worker mới nhưng đo hỏng". Hai ca đó chữa khác nhau.
    """
    tho = pathlib.Path("autodub/media/text_regions_worker.py").read_text(
        encoding="utf-8")
    assert "PHIEN_BAN_WORKER" in tho
    assert '"worker_phien_ban": PHIEN_BAN_WORKER' in tho, (
        "worker phải khai đời NGAY TRONG JSON trả về — một hằng số không "
        "được in ra thì tiến trình cha vẫn mù như cũ")


def test_worker_doi_hien_tai_it_nhat_la_2():
    from autodub.media import text_regions_worker as w

    assert w.PHIEN_BAN_WORKER >= 2, (
        "đời 1 = bản chưa biết đo tách khởi động/quét")


# --- Cha phải GHI LẠI đã chạy tệp nào ----------------------------------------

def test_ghi_duong_dan_worker_da_chay(monkeypatch):
    """Ghi TRƯỚC khi chạy: worker chết giữa chừng thì vẫn còn manh mối."""
    _gia_worker(monkeypatch, {"ok": True, "boxes": [], "anh_loi": 0,
                              "worker_phien_ban": 2,
                              "khoi_dong_s": 1.0, "quet_s": 2.0})
    thong_ke: dict = {}
    tr._detect_via_subprocess(["a.jpg"], _CaiDat(), None, doc_chu=True,
                              thong_ke=thong_ke)
    assert thong_ke["worker_duong_dan"].endswith("text_regions_worker.py")
    assert thong_ke["worker_phien_ban"] == 2


def test_thieu_khoa_thi_coi_la_doi_1_khong_phai_khong_ro(monkeypatch):
    """Đây đúng là hình dạng JSON của lượt thật 12/09.

    Thiếu `worker_phien_ban` KHÔNG phải "không rõ đời" — worker đời 1 là bản
    duy nhất không khai, nên thiếu tức là đời 1. Đoán "không rõ" ở đây là
    ném đi đúng kết luận cần thiết.
    """
    _gia_worker(monkeypatch, {"ok": True, "boxes": [], "anh_loi": 0})
    thong_ke: dict = {}
    tr._detect_via_subprocess(["a.jpg"], _CaiDat(), None, doc_chu=True,
                              thong_ke=thong_ke)
    assert thong_ke["worker_phien_ban"] == 1
    assert "khoi_dong_s" not in thong_ke


# --- Tệp chẩn đoán phải TỰ NÓI RA nguyên nhân --------------------------------

def _doc_chu_gia(monkeypatch):
    """`read_text_regions` phải trả về ít nhất 1 quan sát để đi tới cuối hàm."""
    monkeypatch.setattr(
        tr, "_detect_via_subprocess",
        lambda paths, st, ev, doc_chu=False, thong_ke=None: (
            thong_ke.update({"anh_loi": 0, "worker_phien_ban": 1,
                             "worker_duong_dan": r"C:\App\_internal\autodub"
                                                 r"\media\text_regions_worker.py"})
            or [{"text": "hoa don", "confidence": 0.95,
                 "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1, "anh": 0}]))


def test_tai_hien_luot_that_12_09_va_noi_ra_nguyen_nhan(monkeypatch):
    """Tái hiện đúng triệu chứng 12/09, rồi đòi hệ thống tự giải thích.

    Trước bản vá: `thoi_gian` chỉ có `duong` + `so_khung`, và câu giải thích
    là "worker không báo ... KHÔNG suy ra được" — đúng nhưng vô dụng, vì nó
    không nói worker NÀO, ở ĐÂU. Chủ dự án phải gửi tệp về rồi chờ dò tay
    hai ngày.
    """
    _doc_chu_gia(monkeypatch)
    ket = tr.read_text_regions(["a.jpg"], settings=_CaiDat(),
                               moc_thoi_gian=[0.0])

    t = ket.thoi_gian
    assert "khoi_dong_s" not in t, "ca đang tái hiện là ca THIẾU số đo"
    assert t["worker_phien_ban"] == 1
    # Hai điều tệp chẩn đoán phải tự nói ra — thiếu một trong hai là lại phải
    # dò tay như lượt 12/09.
    assert "đời 1" in t["thieu_tach_khoi_dong"], "không nói đời worker"
    assert "text_regions_worker.py" in t["thieu_tach_khoi_dong"], (
        "không nói TỆP NÀO đang chạy — đó chính là thứ mất hai ngày để tìm")


def test_worker_moi_thi_khong_con_cau_canh_bao(monkeypatch):
    """Chốt mặt kia: worker đời mới thì không được kêu oan.

    Không có test này thì một bản vá kêu-mọi-lúc vẫn qua được test trên.
    """
    monkeypatch.setattr(
        tr, "_detect_via_subprocess",
        lambda paths, st, ev, doc_chu=False, thong_ke=None: (
            thong_ke.update({"anh_loi": 0, "worker_phien_ban": 2,
                             "worker_duong_dan": "/app/text_regions_worker.py",
                             "khoi_dong_s": 21.4, "quet_s": 171.6})
            or [{"text": "hoa don", "confidence": 0.95,
                 "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1, "anh": 0}]))
    ket = tr.read_text_regions(["a.jpg"], settings=_CaiDat(),
                               moc_thoi_gian=[0.0])
    assert ket.thoi_gian["khoi_dong_s"] == 21.4
    assert "thieu_tach_khoi_dong" not in ket.thoi_gian
