"""Trang Dựng video từ kịch bản — mini-spec H4e.

Hai chốt phải giữ:
  1. **Không tự sinh ảnh thay người dùng.** Sinh ảnh tốn 30 Vox mỗi tấm; tự
     bấm hộ là tiêu tiền của người ta mà không xin phép.
  2. **Thiếu ảnh thì không dựng được.** Nút phải TẮT, không phải bấm được rồi
     mới báo lỗi — bấm được nghĩa là người dùng đã kỳ vọng nó chạy.

Kèm: thời gian hiện ra phải là KHOẢNG. Bốn giọng đọc chênh nhau 1,21 lần (đo
thật), nên hiện một con số là để người dùng dựng hình khít theo rồi lệch tiếng.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import storyboard_page as sp  # noqa: E402


def _beat(loi, **kw):
    goc = {"beatType": "hook", "voiceoverTextVi": loi,
           "captionSuggestionVi": "Chữ", "visualBriefVi": "Cận cảnh"}
    goc.update(kw)
    return goc


def _kich_ban(status="ready", beats=None):
    return {"id": "s1", "flowBlueprintId": "bp1", "brandProfileId": "br1",
            "status": status,
            "beats": beats or [_beat("Sáng nào cũng vội."),
                               _beat("Cắm điện ba phút là xong.", beatType="proof")]}


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _WorkerGia:
    """Thay worker mạng — không gọi ra ngoài trong test, và không chạy luồng."""

    class _Sig:
        def connect(self, _f):
            pass

    def __init__(self, *a, **k):
        self.finished_ok = self._Sig()
        self.failed = self._Sig()

    def start(self):
        pass

    def isRunning(self):
        return False


@pytest.fixture()
def page(monkeypatch):
    # Chặn lượt gọi mạng lấy Blueprint — trang không được tự gọi mạng trong test.
    monkeypatch.setattr(sp, "FlowBlueprintCrudWorker", _WorkerGia)
    return sp.StoryboardPage(lambda: object())


# ------------------------------------------------------- chốt thiếu ảnh ----

def test_moi_dat_kich_ban_thi_CHUA_dung_duoc(page):
    page.dat_kich_ban(_kich_ban())
    assert not page.btn_dung.isEnabled(), "chưa có ảnh mà đã bấm dựng được"
    assert "chưa có ảnh" in page.status.text()


def test_du_anh_thi_moi_bat_nut(page):
    page.dat_kich_ban(_kich_ban())
    page._anh = ["/tmp/a.png", "/tmp/b.png"]
    page._ve()
    assert page.btn_dung.isEnabled()


def test_thieu_MOT_anh_van_khong_dung_duoc(page):
    page.dat_kich_ban(_kich_ban())
    page._anh = ["/tmp/a.png", ""]
    page._ve()
    assert not page.btn_dung.isEnabled()
    assert "Còn 1 đoạn" in page.status.text()


def test_bam_dung_khi_thieu_anh_thi_KHONG_chay_gi(page, monkeypatch):
    # Nút đang tắt, nhưng nếu ai đó gọi thẳng hàm thì cũng không được chạy.
    goi = []
    monkeypatch.setattr(sp, "DungDuAnWorker",
                        lambda *a, **k: goi.append(a) or pytest.fail("đã dựng khi thiếu ảnh"))
    page.dat_kich_ban(_kich_ban())
    page._board = None
    page._dung()
    assert not goi


# ------------------------------------------------- không tự sinh ảnh ------

def test_trang_KHONG_co_duong_sinh_anh(page):
    # Guardrail 4 của H4. Thêm một nút "sinh ảnh giúp tôi" sau này sẽ làm
    # test này đỏ — cố ý, vì đó là quyết định tiêu tiền, phải hỏi trước.
    import inspect
    ma = inspect.getsource(sp)
    for cam in ("product-scene", "product_scene", "dung_boi_canh", "image.scene"):
        assert cam not in ma, f"trang không được tự gọi đường sinh ảnh: {cam}"


def test_noi_ro_la_khong_ton_Vox(page):
    from PySide6.QtWidgets import QLabel
    chu = " ".join((w.text() or "") for w in page.findChildren(QLabel)).lower()
    assert "không tốn vox" in chu


# ------------------------------------------------- cổng kịch bản ready ----

@pytest.mark.parametrize("trang_thai", ["blocked", "unconfirmed", "draft", "failed"])
def test_kich_ban_chua_ready_thi_bao_ro_va_khoa_nut(page, trang_thai):
    page.dat_kich_ban(_kich_ban(status=trang_thai))
    assert not page.btn_dung.isEnabled()
    assert sp.STATUS_ERROR in page.status.text()
    assert trang_thai in page.status.text()


# ------------------------------------------------------- hiện KHOẢNG -----

def test_thoi_luong_hien_ra_la_KHOANG_khong_phai_mot_con_so(page):
    from autodub.storyboard import uoc_luong_giay_doc
    chu = sp._khoang_giay(uoc_luong_giay_doc("Một câu dài vừa phải để đo"))
    assert "–" in chu and "khoảng" in chu


def test_tong_thoi_luong_cung_hien_KHOANG(page):
    page.dat_kich_ban(_kich_ban())
    page._anh = ["/tmp/a.png", "/tmp/b.png"]
    page._ve()
    assert "–" in page.status.text(), "tổng thời lượng cũng phải là khoảng"


# ------------------------------------------------------- cảnh báo nhịp ----

def test_hien_canh_bao_lech_nhip_tu_storyboard(page):
    kb = _kich_ban(beats=[_beat(" ".join(["từ"] * 60) + ".")])
    page._kich_ban = kb
    page._anh = [""]
    page._blueprint = {"beats": [{"startS": 0, "endS": 8}]}
    page._ve()
    assert page.canh_bao.isVisibleTo(page)
    assert "dài gấp" in page.canh_bao.text()


def test_khong_lech_nhip_thi_an_canh_bao(page):
    page._kich_ban = _kich_ban(beats=[_beat(" ".join(["từ"] * 20) + ".")])
    page._anh = [""]
    page._blueprint = {"beats": [{"startS": 0, "endS": 10.5}]}
    page._ve()
    assert not page.canh_bao.isVisibleTo(page)


# --------------------------------------------------------- điều hướng -----

def test_trang_viet_kich_ban_phat_signal_sang_day():
    # Nút "Dùng kịch bản này" trước đây chỉ báo "chưa có" — nay phải dẫn thật.
    from autodub_gui.pages import brand_script_page as bsp
    assert hasattr(bsp.BrandScriptPage, "storyboard_requested")


def test_dung_xong_thi_yeu_cau_mo_Trinh_chinh_sua(page):
    nhan = []
    page.open_editor_requested.connect(nhan.append)

    class _Ket:
        work_dir = "/tmp/duan_gia"

    page._xong(_Ket())
    assert nhan == ["/tmp/duan_gia"]
