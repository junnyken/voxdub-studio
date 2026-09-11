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

from autodub import story_image as sp_story  # noqa: E402
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

def test_trang_KHONG_dung_duong_sinh_anh_cua_C1(page):
    """H4d mở đường vẽ ảnh, nhưng KHÔNG được mở đường của C1.

    `product-scene` dựng lại ảnh sản phẩm THẬT và có luật tuân thủ riêng
    (`packaging_check` so với ảnh gốc). Ảnh minh hoạ không có ảnh gốc nào,
    nên đi nhờ cửa đó là đi qua một bước kiểm không kiểm được gì.
    """
    import inspect
    ma = inspect.getsource(sp)
    for cam in ("product-scene", "product_scene", "dung_boi_canh"):
        assert cam not in ma, f"trang không được đi cửa của C1: {cam}"


def test_nguoi_dung_tu_choi_thi_KHONG_ve_gi(page, monkeypatch):
    # Guardrail 3 của H4d. Trước H4d test này chốt "không có đường sinh ảnh
    # nào"; nay có đường rồi thì chốt phải chuyển thành "không tiêu tiền nếu
    # chưa được đồng ý" — đó mới là điều thật sự cần giữ.
    monkeypatch.setattr(sp.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (False, True)))
    monkeypatch.setattr(sp, "SinhAnhMinhHoaWorker",
                        lambda *a, **k: pytest.fail("đã vẽ khi người dùng từ chối"))
    page.dat_kich_ban(_kich_ban())
    page._ve_anh([0, 1])


def test_hop_thoai_phai_noi_ro_GIA_truoc_khi_ve(page, monkeypatch):
    thay = {}

    def _hoi(_parent, title, message, **kw):
        thay.update(title=title, message=message, detail=kw.get("detail", ""),
                    confirm=kw.get("confirm_label", ""))
        return (False, True)

    monkeypatch.setattr(sp.ConfirmDialog, "ask", staticmethod(_hoi))
    page.dat_kich_ban(_kich_ban())
    page._ve_anh([0, 1])

    tong = 2 * sp.GIA_MOI_ANH
    assert str(tong) in thay["title"], "tổng tiền phải nằm ngay trên tiêu đề"
    assert str(tong) in thay["confirm"], "nút đồng ý phải nhắc lại con số"
    assert str(sp.GIA_MOI_ANH) in thay["message"]
    # Tiền trừ kể cả khi ảnh không dùng được — phải nói ra, vì đó là thứ
    # người dùng sẽ tức nhất nếu chỉ phát hiện sau khi mất Vox.
    assert "không dùng" in thay["message"]


def test_hop_thoai_cho_doc_dung_goi_y_sap_duoc_ve(page, monkeypatch):
    thay = {}
    monkeypatch.setattr(sp.ConfirmDialog, "ask", staticmethod(
        lambda _p, _t, _m, **kw: (thay.update(detail=kw.get("detail", "")),
                                  (False, True))[1]))
    kb = _kich_ban(beats=[_beat("Sáng nào cũng vội.",
                                visualBriefVi="Bàn tay cắm điện lúc 6 giờ")])
    page.dat_kich_ban(kb)
    page._ve_anh([0])
    assert "Bàn tay cắm điện lúc 6 giờ" in thay["detail"], (
        "hỏi trả 30 Vox cho một tấm ảnh mà không cho đọc gợi ý sinh ra nó "
        "thì lượt bấm không còn là đồng ý có hiểu biết")


def test_hop_thoai_noi_truoc_rang_nguoi_moi_doan_mot_khac(page, monkeypatch):
    # Guardrail 6 của H4d. Hệ thống không có khái niệm nhân vật (H4 §B2) —
    # để người dùng tự phát hiện sau khi đã trả tiền là cách tệ nhất.
    thay = {}
    monkeypatch.setattr(sp.ConfirmDialog, "ask", staticmethod(
        lambda _p, _t, _m, **kw: (thay.update(detail=kw.get("detail", "")),
                                  (False, True))[1]))
    page.dat_kich_ban(_kich_ban())
    page._ve_anh([0])
    assert "KHÁC" in thay["detail"] and "nhân vật" in thay["detail"]


def test_dang_ve_do_thi_KHONG_ve_chong_len(page, monkeypatch):
    """Bấm «Vẽ» ở đoạn 1 rồi bấm tiếp ở đoạn 2 khi lượt đầu chưa xong sẽ ghi
    đè worker cũ — mà tiền của nó thì đã trừ rồi. Nút hàng loạt tự tắt, nút
    vẽ từng dòng thì không, nên chốt phải nằm trong hàm.
    """
    class _DangChay:
        def isRunning(self):
            return True

    page.dat_kich_ban(_kich_ban())
    page._ve_worker = _DangChay()
    monkeypatch.setattr(sp.ConfirmDialog, "ask", staticmethod(
        lambda *a, **k: pytest.fail("còn hỏi tiếp khi đang vẽ dở")))
    page._ve_anh([1])


def test_kich_ban_chua_ready_thi_KHONG_ve_duoc(page):
    page.dat_kich_ban(_kich_ban(status="blocked"))
    assert not page.btn_ve_het.isEnabled(), (
        "kịch bản không dựng được mà vẫn cho tiêu 30 Vox mỗi ảnh cho nó")


def test_khong_co_goi_y_hinh_thi_nut_ve_TAT(page):
    page.dat_kich_ban(_kich_ban(beats=[_beat("Sáng nào cũng vội.",
                                             visualBriefVi="")]))
    assert not page.btn_ve_het.isEnabled(), "bật nút rồi mới báo không có gợi ý"


# ------------------------------------------- ảnh vẽ xong: ai được vào video --

def _ket(chi_so, dat=True, ly_do="ổn"):
    return sp_story.AnhMinhHoa(
        duong_dan=f"/tmp/doan_{chi_so}.jpg", goi_y="g",
        phan_quyet="DAT" if dat else "CO_SAN_PHAM", ly_do=ly_do,
        da_kiem=True, da_dong_nhan=True, chi_so=chi_so)


def test_anh_TRUOT_kiem_khong_duoc_vao_video(page, monkeypatch):
    monkeypatch.setattr(sp.ConfirmDialog, "show_error",
                        staticmethod(lambda *a, **k: None))
    page.dat_kich_ban(_kich_ban())
    me = sp_story.MeAnh(thu_muc="/tmp")
    me.ket_qua = [_ket(0, dat=False, ly_do="có hộp có nhãn ở góc phải")]
    page._ve_anh_xong(me)
    assert page._anh[0] == "", "ảnh trượt kiểm mà vẫn ghép vào video"
    assert not page.btn_dung.isEnabled()


def test_anh_di_dung_doan_cua_no_khong_theo_thu_tu(page, monkeypatch):
    # Vẽ riêng cho đoạn 2: nếu ghép theo thứ tự danh sách thì ảnh lên đoạn 1.
    monkeypatch.setattr(sp.ConfirmDialog, "show_error",
                        staticmethod(lambda *a, **k: None))
    page.dat_kich_ban(_kich_ban())
    me = sp_story.MeAnh(thu_muc="/tmp")
    me.ket_qua = [_ket(1)]
    page._ve_anh_xong(me)
    assert page._anh == ["", "/tmp/doan_1.jpg"]


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


# ============================================================ H4d-0 =========
# Lỗi mẻ phải TỚI ĐƯỢC màn hình, kèm tiền và việc làm được.
#
# Trước H4d-0: `me.hong` được ghi mà KHÔNG NƠI NÀO ĐỌC. Hỏng cả mẻ thì màn
# hình im lặng hoàn toàn — không hộp thoại, không toast, chỉ còn dòng "Còn N
# đoạn chưa có ảnh" y như lúc chưa bấm. Người dùng bấm nút, chờ vài phút, rồi
# không biết chuyện gì đã xảy ra hay mất bao nhiêu tiền.

def _me(ket_qua=(), hong=()):
    m = sp_story.MeAnh(thu_muc="/tmp")
    m.ket_qua = list(ket_qua)
    m.hong = list(hong)
    return m


def _hong(chi_so, ly_do="mô hình từ chối vẽ", vox=0, thu_lai=True):
    return sp_story.DoanHong(chi_so=chi_so, ly_do=ly_do, vox=vox,
                             thu_lai_duoc=thu_lai)


def _bat_hop_thoai(monkeypatch):
    thay = {}
    monkeypatch.setattr(sp.ConfirmDialog, "show_error", staticmethod(
        lambda _p, tieu_de, loi, detail="": thay.update(
            tieu_de=tieu_de, loi=loi, detail=detail)))
    return thay


def test_hong_CA_ME_thi_KHONG_duoc_im_lang(page, monkeypatch):
    thay = _bat_hop_thoai(monkeypatch)
    page.dat_kich_ban(_kich_ban())
    page._ve_anh_xong(_me(hong=[_hong(0), _hong(1)]))

    assert thay, "hỏng cả mẻ mà màn hình không nói gì"
    assert "Không vẽ được ảnh nào" in thay["tieu_de"]
    assert "Đoạn 1" in thay["detail"] and "Đoạn 2" in thay["detail"]


def test_noi_ro_SO_TIEN_da_mat_va_phan_mat_khong_duoc_gi(page, monkeypatch):
    thay = _bat_hop_thoai(monkeypatch)
    page.dat_kich_ban(_kich_ban())
    # Đoạn 1 vẽ được nhưng trượt kiểm ⇒ mất 33 Vox mà không có ảnh.
    truot = _ket(0, dat=False, ly_do="có hộp có nhãn")
    truot.vox_ve, truot.vox_kiem = 30, 3
    page._ve_anh_xong(_me(ket_qua=[truot, _ket(1)], hong=[]))

    assert "33 Vox không đổi được ảnh nào dùng được" in thay["loi"], thay["loi"]


def test_hong_vi_cua_dong_thi_KHONG_bao_thu_lai(page, monkeypatch):
    """Bảo người dùng thử lại một thứ không thể khác đi là làm mất thời gian
    và có khi mất tiền."""
    thay = _bat_hop_thoai(monkeypatch)
    page.dat_kich_ban(_kich_ban())
    page._ve_anh_xong(_me(hong=[_hong(0, "Tính năng đang tắt.", thu_lai=False),
                                _hong(1, "Tính năng đang tắt.", thu_lai=False)]))

    assert "Thử lại sẽ ra đúng kết quả này" in thay["loi"]
    assert "thử lại cũng vậy" in thay["detail"]


def test_hong_tam_thoi_thi_CO_bao_thu_lai_kem_gia(page, monkeypatch):
    thay = _bat_hop_thoai(monkeypatch)
    page.dat_kich_ban(_kich_ban())
    page._ve_anh_xong(_me(hong=[_hong(0), _hong(1)]))

    assert "Bấm «Vẽ» lại" in thay["loi"]
    assert str(sp.GIA_MOI_ANH) in thay["loi"], "phải nói rõ thử lại tốn bao nhiêu"


def test_chi_tiet_gop_HAI_loai_hong_theo_so_doan(page, monkeypatch):
    """Người dùng nhìn theo ĐOẠN, không nhìn theo cách hệ thống phân loại lỗi."""
    thay = _bat_hop_thoai(monkeypatch)
    page.dat_kich_ban(_kich_ban(beats=[_beat(f"Câu {i}.") for i in range(3)]))
    truot = _ket(1, dat=False, ly_do="có chữ trên hình")
    truot.vox_ve, truot.vox_kiem = 30, 3
    page._ve_anh_xong(_me(ket_qua=[_ket(0), truot], hong=[_hong(2)]))

    dong = [d for d in thay["detail"].splitlines() if d.strip()]
    assert [d.split(":")[0] for d in dong] == ["Đoạn 2", "Đoạn 3"], dong


def test_ca_me_XONG_thi_khong_doa_nguoi_dung(page, monkeypatch):
    monkeypatch.setattr(sp.ConfirmDialog, "show_error", staticmethod(
        lambda *a, **k: pytest.fail("mẻ thành công mà vẫn hiện hộp lỗi")))
    page.dat_kich_ban(_kich_ban())
    me = _me(ket_qua=[_ket(0), _ket(1)])
    for k in me.ket_qua:
        k.vox_ve, k.vox_kiem = 30, 3
    page._ve_anh_xong(me)
    assert page._anh == ["/tmp/doan_0.jpg", "/tmp/doan_1.jpg"]


def test_trang_thai_me_phan_ba_ca_khong_phai_hai():
    assert _me(ket_qua=[_ket(0)]).trang_thai == "xong"
    assert _me(ket_qua=[_ket(0), _ket(1, dat=False)]).trang_thai == "hong_mot_phan"
    assert _me(hong=[_hong(0)]).trang_thai == "hong_ca_me"
    # Ảnh vẽ được nhưng trượt kiểm mà không đoạn nào đạt ⇒ vẫn là hỏng cả mẻ.
    assert _me(ket_qua=[_ket(0, dat=False)]).trang_thai == "hong_ca_me"
