"""Cổng 50 Vox phải đi HẾT từ giao diện xuống tầng gọi mạng.

Cổng nằm ở `doc_chu_may_chu.doc_lai_bang_may_chu` (xem
`tests/test_cong_vox_doc_chu.py`), nhưng nó chỉ có tác dụng nếu người hỏi đi
được xuống tới đó. Đường đi có BA chặng:

    FlowBlueprintWorker -> trich_bang_chung -> read_text_regions
                        -> doc_lai_bang_may_chu

Chốt thân hàm mà quên chốt chỗ gọi là lớp lỗi đã lặp bốn lần trong dự án này:
hàm mới đúng, test hàm xanh, mà nút bấm không nối vào đâu cả. Nên mỗi chặng
một test riêng, cộng một test đi hết chuỗi.

Hộp thoại phải dựng ở LUỒNG GIAO DIỆN — Qt không cho dựng widget từ luồng
nền. Worker phát tín hiệu rồi chặn lại chờ trả lời.
"""
from __future__ import annotations

import threading
from unittest.mock import patch

import pytest


# --- Chặng 3: read_text_regions -> doc_lai_bang_may_chu ---------------------

def test_read_text_regions_chuyen_xin_phep_xuong():
    """Bản đầu của test này giả lập nội tại RapidOCR và đỏ vì lý do khác
    hẳn (`DocChuThatBai`). Chốt đúng thứ cần chốt: hàm NHẬN và CHUYỂN tiếp.
    """
    import inspect

    from autodub.media import text_regions as tr

    ky = inspect.signature(tr.read_text_regions)
    assert "xin_phep" in ky.parameters, (
        "`read_text_regions` không nhận `xin_phep` — chuỗi đứt ở chặng 3")

    than = inspect.getsource(tr.read_text_regions)
    assert "xin_phep=xin_phep" in than, (
        "nhận `xin_phep` rồi nhưng KHÔNG chuyển xuống `doc_lai_bang_may_chu` "
        "— hàm mới chỉ là trang trí")


def test_doc_lai_bang_may_chu_that_su_nhan_duoc(tmp_path):
    """Đi HẾT chặng 3 bằng hành vi thật, không qua RapidOCR.

    Hai test trên chốt chữ ký và chỗ gọi; test này chốt rằng thứ đi tới đầu
    kia đúng là hàm mình truyền vào.
    """
    from autodub.media import doc_chu_may_chu as m

    def hoi(vox, khung):
        return False

    class _Khach:
        def assist(self, *a, **kw):
            raise AssertionError("từ chối rồi mà vẫn gọi mạng")

    quan_sat = [{"frame": i} for i in range(65)]
    with patch.object(m, "chia_doan", lambda _q: [[i] for i in range(65)]), \
         patch.object(m, "_anh_gui_di", return_value={"data": "x"}):
        ra = m.doc_lai_bang_may_chu(
            quan_sat, [str(tmp_path / f"{i}.jpg") for i in range(65)],
            client=_Khach(), xin_phep=hoi)
    assert ra == quan_sat


# --- Chặng 2: trich_bang_chung -> read_text_regions -------------------------

def test_trich_bang_chung_chuyen_xin_phep_xuong():
    import inspect

    from autodub import flow_blueprint as fb

    ky = inspect.signature(fb.trich_bang_chung)
    assert "xin_phep" in ky.parameters, (
        "`trich_bang_chung` không nhận `xin_phep` — chuỗi đứt ở chặng 2")

    than = inspect.getsource(fb.trich_bang_chung)
    assert "xin_phep=xin_phep" in than, (
        "nhận `xin_phep` rồi nhưng không truyền cho `read_text_regions`")


# --- Chặng 1: worker -> trich_bang_chung ------------------------------------

def test_worker_co_tin_hieu_hoi_va_ham_tra_loi():
    from autodub_gui.workers import FlowBlueprintWorker

    assert hasattr(FlowBlueprintWorker, "xin_phep_vox"), (
        "worker phải có tín hiệu `xin_phep_vox` — hộp thoại KHÔNG dựng được "
        "từ luồng nền, Qt cấm")
    assert hasattr(FlowBlueprintWorker, "tra_loi_vox"), (
        "phải có đường trả lời ngược lại, nếu không luồng nền chờ mãi")


def test_worker_chan_lai_cho_tra_loi_roi_di_tiep():
    """Luồng nền phải ĐỢI câu trả lời, không chạy tiếp rồi tiêu tiền."""
    from autodub_gui.workers import FlowBlueprintWorker

    w = FlowBlueprintWorker.__new__(FlowBlueprintWorker)
    w._tra_loi_vox = None
    w._co_tra_loi = threading.Event()
    w._cancel_event = threading.Event()
    phat = []
    w.xin_phep_vox = type("S", (), {"emit": lambda _s, *a: phat.append(a)})()

    def tra_loi_sau():
        FlowBlueprintWorker.tra_loi_vox(w, True)

    threading.Timer(0.05, tra_loi_sau).start()
    ket = FlowBlueprintWorker._hoi_vox(w, 88, 65)

    assert phat == [(88, 65)], "không phát tín hiệu, hoặc phát sai số"
    assert ket is True


def test_worker_huy_giua_chung_thi_khong_cho_mai():
    """Bấm Dừng lúc hộp thoại đang mở không được treo luồng nền."""
    from autodub_gui.workers import FlowBlueprintWorker

    w = FlowBlueprintWorker.__new__(FlowBlueprintWorker)
    w._tra_loi_vox = None
    w._co_tra_loi = threading.Event()
    w._cancel_event = threading.Event()
    w.xin_phep_vox = type("S", (), {"emit": lambda _s, *a: None})()

    threading.Timer(0.05, w._cancel_event.set).start()
    assert FlowBlueprintWorker._hoi_vox(w, 88, 65) is False


def test_worker_truyen_ham_hoi_xuong_trich_bang_chung():
    """CHỐT CHỖ GỌI: worker có `_hoi_vox` mà không đưa xuống là vô ích."""
    import inspect

    from autodub_gui import workers

    than = inspect.getsource(workers.FlowBlueprintWorker.run)
    assert "xin_phep=self._hoi_vox" in than, (
        "worker không đưa `_hoi_vox` xuống `trich_bang_chung`")


# --- Trang nối tín hiệu vào hộp thoại ---------------------------------------

def test_trang_noi_tin_hieu_vao_hop_thoai():
    import inspect

    from autodub_gui.pages import flow_blueprint_page as p

    than = inspect.getsource(p.FlowBlueprintPage)
    assert "xin_phep_vox.connect" in than, (
        "tín hiệu không được nối — luồng nền sẽ chờ tới khi bị huỷ")
